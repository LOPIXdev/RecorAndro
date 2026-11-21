package dev.lopix.recorandro.companion;

import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertNotEquals;
import static org.junit.Assert.assertNull;
import static org.junit.Assert.assertThrows;
import static org.junit.Assert.assertTrue;

public class DeckEndpointTest {
    @Test
    public void onlyReviewedDeckAndAuthenticationRoutesAreAllowed() {
        assertEquals("/", DeckEndpoint.allowedPath(DeckEndpoint.ROOT, "GET", true));
        assertEquals("/app.js", DeckEndpoint.allowedPath(DeckEndpoint.ORIGIN + "/app.js", "GET", false));
        assertEquals("/state", DeckEndpoint.allowedPath(DeckEndpoint.ORIGIN + "/state", "GET", false));
        assertEquals("/auth", DeckEndpoint.allowedPath(DeckEndpoint.ORIGIN + "/auth", "POST", false));
        for (String path : new String[]{"/start", "/stop", "/open", "/resume", "/state", "/download/id"}) {
            assertNull(path, DeckEndpoint.allowedPath(DeckEndpoint.ORIGIN + path, "POST", false));
        }
        assertNull(DeckEndpoint.allowedPath(DeckEndpoint.ORIGIN + "/state", "GET", true));
        assertNull(DeckEndpoint.allowedPath(DeckEndpoint.ORIGIN + "/auth", "GET", false));
        assertNull(DeckEndpoint.allowedPath(DeckEndpoint.ROOT, "POST", true));
    }

    @Test
    public void rejectsDifferentOriginsAndNonCanonicalLinks() {
        for (String url : new String[]{"http://127.0.0.1:8766/", "http://127.0.0.1/",
                "http://localhost:8765/", "http://[::1]:8765/", "http://127.1:8765/",
                "http://127.0.0.1:08765/", "http://someone@127.0.0.1:8765/",
                "https://127.0.0.1:8765/", "http://127.0.0.1:8765.example/",
                "http://example.invalid/", "file:///local", "content://provider/file",
                "javascript:void(0)", DeckEndpoint.ROOT + "?query", DeckEndpoint.ROOT + "#fragment",
                DeckEndpoint.ROOT + "%2e", DeckEndpoint.ROOT + "[ "}) {
            assertNull(url, DeckEndpoint.allowedPath(url, "GET", true));
            assertNull(url, DeckEndpoint.allowedPath(url, "GET", false));
        }
    }

    @Test
    public void invalidCodeNeverReachesTheBrowser() {
        String code = "z".repeat(41) + "-_";
        assertTrue(DeckEndpoint.validCode(code));
        assertFalse(DeckEndpoint.validCode(code + "\n"));
        assertFalse(DeckEndpoint.validCode(code.substring(1)));
        assertThrows(IllegalArgumentException.class, () -> DeckEndpoint.authenticationScript("'" + code));
        String script = DeckEndpoint.authenticationScript(code);
        assertTrue(script.contains("redirect: 'error'"));
        assertTrue(script.contains("'X-Launch-Token': '" + code + "'"));
        assertFalse(script.contains("#" + code));
        assertFalse(script.contains("?" + code));
    }

    @Test
    public void repeatedConnectAndStaleCallbacksCannotAuthenticateAnotherAttempt() {
        Pairing pairing = new Pairing();
        int first = pairing.begin();
        assertEquals(0, pairing.begin());
        assertFalse(pairing.isAuthenticated());
        pairing.close();
        int next = pairing.begin();
        assertNotEquals(first, next);
        pairing.authenticate(first);
        assertFalse(pairing.isAuthenticated());
        pairing.authenticate(next);
        assertTrue(pairing.isAuthenticated());
        assertEquals(0, pairing.begin());
        pairing.close();
        assertFalse(pairing.isCurrent(next));
        assertFalse(pairing.isAuthenticated());
    }
}
