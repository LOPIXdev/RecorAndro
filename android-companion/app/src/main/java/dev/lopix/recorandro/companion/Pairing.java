package dev.lopix.recorandro.companion;

final class Pairing {
    private int sequence;
    private boolean active;
    private boolean authenticated;

    int begin() {
        if (active) {
            return 0;
        }
        active = true;
        return ++sequence;
    }

    boolean isCurrent(int attempt) {
        return active && sequence == attempt;
    }

    boolean isAuthenticated() {
        return authenticated;
    }

    void authenticate(int attempt) {
        if (isCurrent(attempt)) {
            authenticated = true;
        }
    }

    void close() {
        active = false;
        authenticated = false;
    }
}
