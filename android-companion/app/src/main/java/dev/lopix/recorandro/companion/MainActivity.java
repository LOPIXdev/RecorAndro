package dev.lopix.recorandro.companion;

import android.annotation.SuppressLint;
import android.app.Activity;
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

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public final class MainActivity extends Activity {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService worker = Executors.newSingleThreadExecutor();
    private final Pairing pairing = new Pairing();
    private LinearLayout layout;
    private EditText codeField;
    private Button connect;
    private Button disconnect;
    private TextView status;
    private WebView deck;
    private String pendingCode;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        protectWindow();
        layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        int margin = Math.round(16 * getResources().getDisplayMetrics().density);
        layout.setPadding(margin, margin, margin, margin);
        layout.setImportantForAutofill(View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS);
        layout.setSaveFromParentEnabled(false);
        setContentView(layout);

        TextView title = addLabel(R.string.app_name);
        title.setTextSize(23);
        addLabel(R.string.instructions);
        status = addLabel(R.string.idle);
        status.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE);

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
        layout.addView(codeField);

        LinearLayout actions = new LinearLayout(this);
        layout.addView(actions);
        connect = new Button(this);
        connect.setText(R.string.connect);
        connect.setOnClickListener(view -> connect());
        actions.addView(connect);
        disconnect = new Button(this);
        disconnect.setText(R.string.disconnect);
        disconnect.setEnabled(false);
        disconnect.setOnClickListener(view -> close(R.string.idle));
        actions.addView(disconnect);
        addLabel(R.string.scope);
    }

    private TextView addLabel(int label) {
        TextView text = new TextView(this);
        text.setText(label);
        layout.addView(text);
        return text;
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
        connect.setEnabled(false);
        disconnect.setEnabled(true);
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
            layout.addView(deck, new LinearLayout.LayoutParams(-1, 0, 1));
            deck.loadUrl(DeckEndpoint.ROOT);
        } catch (RuntimeException exception) {
            failIfCurrent(attempt, R.string.failed);
        }
    }

    private void monitor(int attempt, WebView view) {
        if (!pairing.isCurrent(attempt)) {
            return;
        }
        view.evaluateJavascript(DeckEndpoint.STATUS_SCRIPT, value -> {
            if (!pairing.isCurrent(attempt)) {
                return;
            }
            switch (value == null ? "" : value) {
                case "\"rejected\"" -> close(R.string.rejected);
                case "\"failed\"" -> close(R.string.failed);
                case "\"connected\"" -> {
                    if (!pairing.isAuthenticated()) {
                        pairing.authenticate(attempt);
                        status.setText(R.string.authenticated);
                        deck.setVisibility(View.VISIBLE);
                        getWindow().clearFlags(WindowManager.LayoutParams.FLAG_SECURE);
                    }
                }
                default -> {
                    if (pairing.isAuthenticated()) {
                        close(R.string.connection_lost);
                    }
                }
            }
            if (pairing.isCurrent(attempt)) {
                handler.postDelayed(() -> monitor(attempt, view), 500);
            }
        });
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
        codeField.getText().clear();
        codeField.setEnabled(true);
        connect.setEnabled(true);
        disconnect.setEnabled(false);
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

    @Override
    protected void onStop() {
        close(R.string.idle);
        super.onStop();
    }

    @Override
    protected void onDestroy() {
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
            return true; // A2 performs just the initial, app-directed navigation.
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
            return null; // /auth and /state use Chromium's same-origin HTTP and cookie behavior.
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
            String script = DeckEndpoint.authenticationScript(pendingCode);
            pendingCode = null;
            view.evaluateJavascript(script, value -> monitor(attempt, view));
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
                layout.removeView(view);
                view.destroy();
                deck = null;
            }
            failIfCurrent(attempt, pairing.isAuthenticated() ? R.string.connection_lost : R.string.failed);
            return true;
        }
    }
}
