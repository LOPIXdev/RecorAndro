package dev.lopix.recorandro.companion;

import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.text.InputFilter;
import android.text.InputType;
import android.view.View;
import android.view.WindowManager;
import android.view.inputmethod.EditorInfo;
import android.view.inputmethod.InputMethodManager;
import android.webkit.CookieManager;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebStorage;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.window.OnBackInvokedDispatcher;

import org.json.JSONArray;
import org.json.JSONException;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private static final String LAST_SESSION = "last-session-id";
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final Pairing pairing = new Pairing();
    private final Runnable heartbeat = this::monitor;
    private final Runnable rendererUnresponsive = () -> close(R.string.connection_lost);
    private LinearLayout layout;
    private LinearLayout connectionForm;
    private EditText codeField;
    private Button connect;
    private Button disconnect;
    private TextView status;
    private DeckFileChooser chooser;
    private ZipExport zipExport;
    private WebView deck;
    private int deckAttempt;
    private String pendingCode;
    private String lastSessionId;
    private SharedPreferences recovery;
    private boolean foreground;
    private boolean recheckAfterExport;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        protectWindow();
        recovery = getSharedPreferences("recovery", MODE_PRIVATE);
        lastSessionId = recovery.getString(LAST_SESSION, null);
        chooser = new DeckFileChooser(this);
        zipExport = new ZipExport(this);
        layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);
        layout.setSaveFromParentEnabled(false);
        setContentView(layout);

        int margin = Math.round(16 * getResources().getDisplayMetrics().density);
        connectionForm = new LinearLayout(this);
        connectionForm.setOrientation(LinearLayout.VERTICAL);
        connectionForm.setPadding(margin, margin, margin, 0);
        layout.addView(connectionForm);
        TextView title = new TextView(this);
        title.setText(R.string.app_name);
        title.setTextSize(23);
        connectionForm.addView(title);
        TextView instructions = new TextView(this);
        instructions.setText(R.string.instructions);
        connectionForm.addView(instructions);

        codeField = new EditText(this) {
            @Override
            public boolean onTextContextMenuItem(int id) {
                return switch (id) {
                    case android.R.id.copy, android.R.id.cut, android.R.id.paste,
                            android.R.id.pasteAsPlainText -> false;
                    default -> super.onTextContextMenuItem(id);
                };
            }
        };
        codeField.setHint(R.string.launch_code);
        codeField.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_VARIATION_PASSWORD
                | InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS);
        codeField.setImeOptions(EditorInfo.IME_FLAG_NO_PERSONALIZED_LEARNING | EditorInfo.IME_ACTION_DONE);
        codeField.setFilters(new InputFilter[]{new InputFilter.LengthFilter(43)});
        codeField.setSingleLine(true);
        codeField.setLongClickable(false);
        codeField.setTextIsSelectable(false);
        codeField.setSaveEnabled(false);
        connectionForm.addView(codeField);

        LinearLayout actions = new LinearLayout(this);
        actions.setGravity(android.view.Gravity.CENTER_VERTICAL);
        actions.setPadding(margin, 0, margin, 0);
        layout.addView(actions);
        status = new TextView(this);
        status.setText(R.string.idle);
        status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);
        actions.addView(status, new LinearLayout.LayoutParams(0, -2, 1));
        connect = new Button(this);
        connect.setText(R.string.connect);
        connect.setOnClickListener(view -> connect());
        actions.addView(connect);
        disconnect = new Button(this);
        disconnect.setText(R.string.disconnect);
        disconnect.setVisibility(View.GONE);
        disconnect.setOnClickListener(view -> close(R.string.idle));
        actions.addView(disconnect);
        if (Build.VERSION.SDK_INT >= 33) {
            getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
                    OnBackInvokedDispatcher.PRIORITY_DEFAULT, this::goBack);
        }
    }

    private void protectWindow() {
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
    }

    private void connect() {
        String code = codeField.getText().toString();
        if (!DeckEndpoint.validCode(code)) {
            codeField.getText().clear();
            status.setText(R.string.invalid_code);
            return;
        }
        int attempt = pairing.begin();
        if (attempt == 0) {
            return;
        }
        protectWindow();
        pendingCode = code;
        codeField.getText().clear();
        codeField.setEnabled(false);
        getSystemService(InputMethodManager.class).hideSoftInputFromWindow(codeField.getWindowToken(), 0);
        connect.setVisibility(View.GONE);
        disconnect.setVisibility(View.VISIBLE);
        status.setText(R.string.connecting);
        handler.postDelayed(() -> {
            if (pairing.isCurrent(attempt) && !pairing.isAuthenticated()) {
                close(R.string.failed);
            }
        }, 15_000);
        try {
            WebView.setWebContentsDebuggingEnabled(false);
            CookieManager.getInstance().removeAllCookies(removed -> {
                if (pairing.isCurrent(attempt)) {
                    WebStorage.getInstance().deleteAllData();
                    worker.execute(() -> loadReviewedDeck(attempt));
                }
            });
        } catch (RuntimeException exception) {
            close(R.string.failed);
        }
    }

    private void loadReviewedDeck(int attempt) {
        try {
            Map<String, byte[]> assets = DeckEndpoint.readDeck();
            handler.post(() -> {
                if (pairing.isCurrent(attempt)) {
                    showDeck(attempt, assets);
                }
            });
        } catch (DeckEndpoint.UnexpectedDeck exception) {
            handler.post(() -> failIfCurrent(attempt, R.string.wrong_server));
        } catch (IOException exception) {
            handler.post(() -> failIfCurrent(attempt, R.string.offline));
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void showDeck(int attempt, Map<String, byte[]> assets) {
        try {
            deck = new WebView(this);
            deckAttempt = attempt;
            WebSettings settings = deck.getSettings();
            settings.setJavaScriptEnabled(true); // Only the reviewed Deck bytes are executed.
            settings.setDomStorageEnabled(true);
            settings.setAllowFileAccess(false);
            settings.setAllowContentAccess(false);
            settings.setSafeBrowsingEnabled(false); // No remote lookup for the pinned local page.
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
            settings.setCacheMode(WebSettings.LOAD_NO_CACHE);
            CookieManager.getInstance().setAcceptThirdPartyCookies(deck, false);
            deck.setSaveEnabled(false);
            deck.setVisibility(View.INVISIBLE);
            deck.setWebViewClient(new DeckViewClient(attempt, assets));
            deck.setWebChromeClient(new WebChromeClient() {
                @Override
                public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback,
                                                 FileChooserParams params) {
                    if (view != deck || !foreground || !pairing.isAuthenticated()
                            || !DeckEndpoint.ROOT.equals(view.getUrl())) {
                        callback.onReceiveValue(null);
                        return true;
                    }
                    return chooser.open(callback, params);
                }
            });
            layout.addView(deck, new LinearLayout.LayoutParams(-1, 0, 1));
            deck.loadUrl(DeckEndpoint.ROOT);
        } catch (RuntimeException exception) {
            failIfCurrent(attempt, R.string.failed);
        }
    }

    private void monitor() {
        WebView view = deck;
        if (view == null || !foreground) {
            return;
        }
        // The adapter holds the session lock while serving a verified ZIP.
        if (zipExport.isFetching()) {
            recheckAfterExport = true;
            handler.postDelayed(heartbeat, 500);
            return;
        }
        if (recheckAfterExport) {
            recheckAfterExport = false;
            setStatus(R.string.checking);
            view.evaluateJavascript(DeckEndpoint.RECHECK_SCRIPT, null);
        }
        handler.removeCallbacks(rendererUnresponsive);
        handler.postDelayed(rendererUnresponsive, 9000);
        view.evaluateJavascript(DeckEndpoint.STATUS_SCRIPT, value -> {
            if (view != deck || !foreground) {
                return;
            }
            handler.removeCallbacks(rendererUnresponsive);
            showConnectionState(value);
            if (view == deck) {
                handler.postDelayed(heartbeat, 500);
            }
        });
    }

    private void showConnectionState(String value) {
        try {
            JSONArray response = new JSONArray(value == null ? "[]" : value);
            String sessionId = response.optString(1);
            String connection = response.optString(0);
            if ((pairing.isAuthenticated() || "connected".equals(connection))
                    && DeckEndpoint.validSessionId(sessionId) && !sessionId.equals(lastSessionId)) {
                lastSessionId = sessionId;
                recovery.edit().putString(LAST_SESSION, sessionId).apply();
            }
            switch (connection) {
                case "rejected" -> close(R.string.rejected);
                case "failed" -> close(R.string.failed);
                case "stopped" -> close(R.string.stopped);
                case "lost" -> close(R.string.connection_lost);
                case "checking" -> setStatus(R.string.checking);
                case "connected" -> {
                    if (!pairing.isAuthenticated()) {
                        pairing.authenticate(deckAttempt);
                        connectionForm.setVisibility(View.GONE);
                        deck.setVisibility(View.VISIBLE);
                        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_SECURE);
                    }
                    setStatus(R.string.ready);
                }
                default -> {
                    if (pairing.isAuthenticated()) {
                        close(R.string.connection_lost);
                    }
                }
            }
        } catch (JSONException exception) {
            close(R.string.failed);
        }
    }

    private void setStatus(int message) {
        if (!getText(message).equals(status.getText())) {
            status.setText(message);
        }
    }

    private void failIfCurrent(int attempt, int message) {
        if (pairing.isCurrent(attempt)) {
            close(message);
        }
    }

    private void close(int message) {
        protectWindow();
        pairing.close();
        handler.removeCallbacksAndMessages(null);
        pendingCode = null;
        recheckAfterExport = false;
        chooser.cancel();
        zipExport.cancel();
        connectionForm.setVisibility(View.VISIBLE);
        codeField.getText().clear();
        codeField.setEnabled(true);
        connect.setVisibility(View.VISIBLE);
        disconnect.setVisibility(View.GONE);
        status.setText(message);
        if (deck != null) {
            layout.removeView(deck);
            deck.clearHistory();
            deck.clearCache(true);
            deck.destroy();
            deck = null;
        }
        try {
            CookieManager.getInstance().removeAllCookies(null);
            WebStorage.getInstance().deleteAllData();
        } catch (RuntimeException exception) {
            // A missing WebView also prevents any new pairing.
        }
    }

    private void goBack() {
        if (disconnect.getVisibility() == View.VISIBLE) {
            close(R.string.idle);
        } else {
            finish();
        }
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        goBack();
    }

    @Override
    protected void onStart() {
        super.onStart();
        foreground = true;
        if (deck != null && pairing.isAuthenticated()) {
            setStatus(R.string.checking);
            deck.evaluateJavascript(DeckEndpoint.RECHECK_SCRIPT, null);
            handler.post(heartbeat);
        }
    }

    @Override
    protected void onStop() {
        foreground = false;
        if (chooser.isOpen() || zipExport.isPicking()) {
            handler.removeCallbacks(heartbeat);
            handler.removeCallbacks(rendererUnresponsive);
        } else {
            close(R.string.idle);
        }
        super.onStop();
    }

    @Override
    protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        chooser.onResult(request, result, data);
        zipExport.onResult(request, result, data);
    }

    @Override
    protected void onDestroy() {
        if (deck != null) {
            close(R.string.idle);
        }
        zipExport.destroy();
        worker.shutdownNow();
        super.onDestroy();
    }

    private final class DeckViewClient extends WebViewClient {
        private final int attempt;
        private final Map<String, byte[]> assets;

        DeckViewClient(int attempt, Map<String, byte[]> assets) {
            this.attempt = attempt;
            this.assets = assets;
        }

        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
            if (view == deck && foreground && pairing.isAuthenticated()
                    && DeckEndpoint.ROOT.equals(view.getUrl()) && request.isForMainFrame()
                    && request.hasGesture() && !request.isRedirect() && "GET".equals(request.getMethod())
                    && DeckEndpoint.isExport(request.getUrl().toString())) {
                zipExport.start(request.getUrl().toString(), CookieManager.getInstance().getCookie(DeckEndpoint.ROOT));
            }
            return true; // The only page navigation is the initial app-directed load.
        }

        @Override
        public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
            String path = DeckEndpoint.allowedPath(request.getUrl().toString(),
                    request.getMethod(), request.isForMainFrame());
            if (path == null) {
                return new WebResourceResponse("text/plain", "UTF-8", 403, "Blocked", Map.of(),
                        new ByteArrayInputStream(new byte[0]));
            }
            if (assets.containsKey(path)) {
                return new WebResourceResponse(DeckEndpoint.ASSETS.get(path).mime, "UTF-8", 200, "OK",
                        Map.of("Content-Security-Policy", DeckEndpoint.CSP,
                                "Cache-Control", "no-store", "Referrer-Policy", "no-referrer",
                                "X-Content-Type-Options", "nosniff"),
                        new ByteArrayInputStream(assets.get(path)));
            }
            return null; // Termux handles every action with the existing browser cookie and CSRF.
        }

        @Override
        public void onPageFinished(WebView view, String url) {
            if (!pairing.isCurrent(attempt) || pendingCode == null) {
                return;
            }
            if (!DeckEndpoint.ROOT.equals(url)) {
                close(R.string.wrong_server);
                return;
            }
            String script = DeckEndpoint.authenticationScript(pendingCode, lastSessionId);
            pendingCode = null;
            view.evaluateJavascript(script, null);
            handler.post(heartbeat);
        }

        @Override
        public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
            if (request.isForMainFrame()) {
                failIfCurrent(attempt, R.string.failed);
            }
        }

        @Override
        public boolean onRenderProcessGone(WebView view, RenderProcessGoneDetail detail) {
            if (view == deck) {
                chooser.cancel();
                layout.removeView(view);
                view.destroy();
                deck = null;
            }
            failIfCurrent(attempt, pairing.isAuthenticated() ? R.string.connection_lost : R.string.failed);
            return true;
        }
    }
}
