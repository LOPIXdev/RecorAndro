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
import java.util.regex.Pattern;

final class DeckEndpoint {
    static final String ORIGIN = "http://127.0.0.1:8765";
    static final String ROOT = ORIGIN + "/";
    static final String STATUS_SCRIPT = "typeof recorandroA2Status === 'function'"
            + " ? recorandroA2Status() : 'pending'";
    static final String CSP = "default-src 'self'; frame-ancestors 'none'; object-src 'none';"
            + " base-uri 'none'; form-action 'self'";
    private static final String HOST = "127.0.0.1:8765";
    private static final int MAX_ASSET_BYTES = 64 * 1024;
    private static final Pattern CODE = Pattern.compile("[a-zA-Z0-9_-]{43}");

    // Exact assets from the v0.1 freeze. Only reviewed same-origin code sees the launch code.
    static final Map<String, Asset> ASSETS = Map.of(
            "/", new Asset("text/html", "b6181449b0b1f531ddde8f5fa6790b7ee1fcf091a405b278e092fbb865c9dc41"),
            "/app.js", new Asset("text/javascript", "eda2d28d22041a8dae2af76c326ec71bca87beecd5e8aba8879736a1550da64e"),
            "/style.css", new Asset("text/css", "b6e579c879c41b4daf8c4a977c5b91519234341cea119bbbc7d1d71d89fe7b25"));

    private DeckEndpoint() {}

    static boolean validCode(String input) {
        return CODE.matcher(input).matches();
    }

    static String allowedPath(String url, String method, boolean mainFrame) {
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
        String path = uri.getRawPath();
        if (mainFrame) {
            return "GET".equals(method) && "/".equals(path) ? path : null;
        }
        if ("GET".equals(method) && (ASSETS.containsKey(path) || "/state".equals(path))) {
            return path;
        }
        return "POST".equals(method) && "/auth".equals(path) ? path : null;
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

    static String authenticationScript(String code) {
        if (!validCode(code)) {
            throw new IllegalArgumentException("Invalid launch code format");
        }
        // Use browser Fetch for the real Origin and HttpOnly cookie. Avoid a secret-bearing URL.
        return String.format(Locale.ROOT, """
                (() => {
                  if (location.href !== '%s') return;
                  document.querySelector('main').inert = true;
                  let report = () => 'pending';
                  window.recorandroA2Status = () => report();
                  fetch('/auth', {method: 'POST', body: '', redirect: 'error',
                    headers: {'X-Launch-Token': '%s'}}).then(async (response) => {
                      if (response.status === 403) { report = () => 'rejected'; return; }
                      if (!response.ok) { report = () => 'failed'; return; }
                      const snapshot = await response.json();
                      if (!/^[a-zA-Z0-9_-]{43}$/.test(snapshot.csrf) ||
                          typeof snapshot.busy !== 'boolean' || typeof snapshot.state !== 'string') {
                        report = () => 'failed';
                        return;
                      }
                      // Stock app.js replaces current after each successful protected /state read.
                      let lastState, lastResponse = 0;
                      report = () => {
                        if (typeof connected === 'undefined' || !connected || csrf !== snapshot.csrf) return 'accepted';
                        if (lastState !== current) {
                          if (lastState === undefined) document.getElementById('notice').textContent = '';
                          lastState = current;
                          lastResponse = performance.now();
                        }
                        return performance.now() - lastResponse < 8000 ? 'connected' : 'accepted';
                      };
                  }).catch(() => { report = () => 'failed'; });
                })()
                """, ROOT, code);
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
