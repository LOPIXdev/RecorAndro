package dev.lopix.recorandro.companion;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.Proxy;
import java.net.URI;
import java.net.URL;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

final class DeckEndpoint {
    static final String ORIGIN = "http://127.0.0.1:8765";
    static final String ROOT = ORIGIN + "/";
    static final String STATUS_SCRIPT = "typeof recorandroStatus === 'function'"
            + " ? recorandroStatus() : ['pending', '']";
    static final String RECHECK_SCRIPT = "typeof recorandroRecheck === 'function' && recorandroRecheck()";
    static final String CSP = "default-src 'self'; frame-ancestors 'none'; object-src 'none';"
            + " base-uri 'none'; form-action 'self'";
    private static final String HOST = "127.0.0.1:8765";
    private static final int MAX_ASSET_BYTES = 64 * 1024;
    private static final Pattern CODE = Pattern.compile("[a-zA-Z0-9_-]{43}");
    private static final Pattern SESSION = Pattern.compile("[0-9a-f]{32}");
    private static final Pattern EXPORT = Pattern.compile("/download/[0-9a-f]{32}");
    private static final Set<String> ACTIONS = Set.of("/auth", "/start", "/open", "/resume", "/stop");

    // Exact assets from the v0.1 freeze. Only reviewed same-origin code sees the launch code.
    static final Map<String, Asset> ASSETS = Map.of(
            "/", new Asset("text/html", "b6181449b0b1f531ddde8f5fa6790b7ee1fcf091a405b278e092fbb865c9dc41"),
            "/app.js", new Asset("text/javascript", "eda2d28d22041a8dae2af76c326ec71bca87beecd5e8aba8879736a1550da64e"),
            "/style.css", new Asset("text/css", "b6e579c879c41b4daf8c4a977c5b91519234341cea119bbbc7d1d71d89fe7b25"));

    private DeckEndpoint() {}

    static boolean validCode(String input) {
        return CODE.matcher(input).matches();
    }

    static boolean validSessionId(String input) {
        return input != null && SESSION.matcher(input).matches();
    }

    private static String localPath(String url) {
        URI uri;
        try {
            uri = URI.create(url);
        } catch (IllegalArgumentException exception) {
            return null;
        }
        if (!"http".equals(uri.getScheme()) || !HOST.equals(uri.getRawAuthority())
                || uri.getRawQuery() != null || uri.getRawFragment() != null) {
            return null;
        }
        return uri.getRawPath();
    }

    static boolean isExport(String url) {
        String path = localPath(url);
        return path != null && EXPORT.matcher(path).matches();
    }

    static String allowedPath(String url, String method, boolean mainFrame) {
        String path = localPath(url);
        if (path == null) {
            return null;
        }
        if (mainFrame) {
            return "GET".equals(method) && "/".equals(path) ? path : null;
        }
        if ("GET".equals(method) && (ASSETS.containsKey(path) || "/state".equals(path))) {
            return path;
        }
        return "POST".equals(method) && ACTIONS.contains(path) ? path : null;
    }

    static Map<String, byte[]> readDeck() throws IOException {
        Map<String, byte[]> assets = new HashMap<>();
        for (Map.Entry<String, Asset> entry : ASSETS.entrySet()) {
            String path = entry.getKey();
            Asset asset = entry.getValue();
            HttpURLConnection response = (HttpURLConnection) new URL(ORIGIN + path)
                    .openConnection(Proxy.NO_PROXY);
            response.setInstanceFollowRedirects(false);
            response.setConnectTimeout(2500);
            response.setReadTimeout(2500);
            response.setUseCaches(false);
            response.setRequestProperty("Connection", "close");
            try {
                if (response.getResponseCode() != 200 || !asset.mime.equals(response.getContentType())
                        || !CSP.equals(response.getHeaderField("Content-Security-Policy"))) {
                    throw new UnexpectedDeck();
                }
                byte[] bytes;
                try (InputStream stream = response.getInputStream()) {
                    bytes = readAsset(stream);
                }
                if (!asset.sha256.equals(sha256(bytes))) {
                    throw new UnexpectedDeck();
                }
                assets.put(path, bytes);
            } finally {
                response.disconnect();
            }
        }
        return assets;
    }

    private static byte[] readAsset(InputStream stream) throws IOException {
        ByteArrayOutputStream content = new ByteArrayOutputStream();
        byte[] buffer = new byte[8192];
        int count;
        while ((count = stream.read(buffer)) != -1) {
            if (content.size() + count > MAX_ASSET_BYTES) {
                throw new UnexpectedDeck();
            }
            content.write(buffer, 0, count);
        }
        return content.toByteArray();
    }

    private static String sha256(byte[] bytes) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes);
            StringBuilder hex = new StringBuilder(64);
            for (byte value : digest) {
                hex.append(String.format(Locale.ROOT, "%02x", value & 0xff));
            }
            return hex.toString();
        } catch (NoSuchAlgorithmException exception) {
            throw new AssertionError(exception);
        }
    }

    static String authenticationScript(String code, String sessionId) {
        if (!validCode(code)) {
            throw new IllegalArgumentException("Invalid launch code format");
        }
        // Use browser Fetch for the real Origin and HttpOnly cookie. Avoid a secret-bearing URL.
        return String.format(Locale.ROOT, """
                (() => {
                  if (location.href !== '%s') return;
                  const deck = document.querySelector('main');
                  deck.inert = true;
                  document.querySelector('#ready .share-note p').textContent =
                    'Tap Download on a verified ZIP, then choose Save As or Share.';
                  const audio = document.getElementById('audio');
                  const aacNotice = document.createElement('p');
                  aacNotice.className = 'support-note';
                  aacNotice.setAttribute('role', 'status');
                  document.getElementById('audio-info').after(aacNotice);
                  const updateAacNotice = () => {
                    aacNotice.textContent = /\\.aac$/i.test(audio.files[0]?.name || '')
                      ? 'Raw AAC duration cannot always be verified. Use an M4A, MP3 or WAV recording if RecorAndro cannot establish the duration.'
                      : '';
                  };
                  audio.addEventListener('change', updateAacNotice);
                  document.getElementById('new-session').addEventListener('click', updateAacNotice);
                  const fetchLocal = window.fetch.bind(window);
                  window.fetch = (input, options) => fetchLocal(input, {...options, redirect: 'error'});
                  let report = () => ['pending', ''];
                  window.recorandroStatus = () => report();
                  fetch('/auth', {method: 'POST', body: '', redirect: 'error',
                    headers: {'X-Launch-Token': '%s'}}).then(async (response) => {
                      if (response.status === 403) { report = () => ['rejected', '']; return; }
                      if (!response.ok) { report = () => ['failed', '']; return; }
                      const snapshot = await response.json();
                      if (!/^[a-zA-Z0-9_-]{43}$/.test(snapshot.csrf) ||
                          typeof snapshot.busy !== 'boolean' || typeof snapshot.state !== 'string') {
                        report = () => ['failed', ''];
                        return;
                      }
                      let lastState, lastResponse = 0, lastProbe = 0;
                      let checking = false, rechecking = false, expired = false;
                      const markLive = () => {
                        lastResponse = performance.now();
                        rechecking = false;
                        deck.inert = false;
                      };
                      const probe = async () => {
                        if (checking) return;
                        checking = true;
                        lastProbe = performance.now();
                        const timeout = new AbortController();
                        const timer = setTimeout(() => timeout.abort(), 2500);
                        try {
                          const response = await fetch('/state', {signal: timeout.signal});
                          if (response.status === 403) expired = true;
                          if (response.ok) {
                            const state = await response.json();
                            if (state.csrf === snapshot.csrf) markLive();
                            else expired = true;
                          }
                        } catch (_) {
                          // The last verified response sets the deadline.
                        } finally {
                          clearTimeout(timer);
                          checking = false;
                        }
                      };
                      window.recorandroRecheck = () => {
                        if (!lastState) return;
                        deck.inert = true;
                        lastState = current;
                        rechecking = true;
                        lastResponse = performance.now();
                        probe();
                      };
                      report = () => {
                        const id = typeof current !== 'undefined' && /^[0-9a-f]{32}$/.test(current.session_id)
                          ? current.session_id : '';
                        if (typeof stopped !== 'undefined' && stopped) return ['stopped', id];
                        if (expired) return ['lost', id];
                        if (typeof connected !== 'undefined' && connected && csrf === snapshot.csrf && lastState !== current) {
                          if (!lastState) {
                            document.getElementById('notice').textContent = '';
                            const savedId = '%s';
                            if (!id && savedId) {
                              document.getElementById('sid').value = savedId;
                              document.getElementById('reopen').open = true;
                            }
                          }
                          lastState = current;
                          markLive();
                        }
                        if (!lastState) return ['accepted', id];
                        const now = performance.now();
                        if (now - lastResponse >= 8000) return ['lost', id];
                        // The stock controller pauses its poll during an explicit session action.
                        if (now - lastResponse >= 3000 && now - lastProbe >= 3000) probe();
                        return [rechecking ? 'checking' : 'connected', id];
                      };
                  }).catch(() => { report = () => ['failed', '']; });
                })()
                """, ROOT, code, validSessionId(sessionId) ? sessionId : "");
    }

    static final class Asset {
        final String mime;
        final String sha256;

        Asset(String mime, String sha256) {
            this.mime = mime;
            this.sha256 = sha256;
        }
    }

    static final class UnexpectedDeck extends IOException {}
}
