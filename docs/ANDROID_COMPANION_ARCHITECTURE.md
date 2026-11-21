# RecorAndro Android companion architecture

**A1 decision proposed for owner approval · 2026-11-21.** The companion opens
the existing Processing Deck in an Android app window. Termux remains required
and owns Python, FFmpeg, the foreground listener and the data root.

## Baseline and release boundary

The initial worktree was clean on `main`, with no local tags or Android/Gradle
module. Local `HEAD`, local `origin/main` and live GitHub `main` matched
`1a995068196e33b544ad226fd777514df7e5cff2`. All milestone commit IDs in the
handoff resolved in the local history. Although the configured `origin` uses
`berksc/RecorAndro`, both GitHub names resolve to `LOPIXdev/RecorAndro` (repository
ID `1398394147`). The live Git refs had no tags and the public Releases API
returned an empty list. Draft release visibility was outside that query.
[GitHub repository](https://github.com/LOPIXdev/RecorAndro) ·
[Public Releases API](https://api.github.com/repos/LOPIXdev/RecorAndro/releases)

The freeze commit subject says `v1.0`. The frozen Termux/browser candidate is
**v0.1**, with Python version **`0.1.0`** and proposed tag **`v0.1-rc1`**. Propose
`feat/android-companion` from the verified freeze SHA and a separate
**`v0.2.0-android-rc1`** candidate after owner acceptance. The APK's proposed
`versionName` is `0.2.0-android-rc1` with initial `versionCode` 1, increasing for
each distributed update. Record Python `0.1.0` and its tested revision as the
backend dependency. A1 and A2 use the frozen core version, and a future core
release would carry its own reviewed version and compatibility evidence.
[Technical freeze](V0_1_FREEZE.md) · [Candidate notes](RELEASE_NOTES_V0_1.md) ·
[Release evidence](V0_1_RELEASE_EVIDENCE.md) · [Python metadata](../pyproject.toml)

## Decision

| Route | Decision and tradeoff |
| --- | --- |
| Owner starts Termux, then pairs manually | **Selected.** Uses the existing foreground launch. Pairing takes a trip to Termux and manual entry after a restart. Android keeps each application in its own sandbox. |
| Companion starts a fixed script with Termux `RUN_COMMAND` | **Rejected for A2 and the proposed candidate.** A foreground button might save a step on a qualified device. It requires a privileged grant, adds startup and provenance checks, and gives the APK no independently trusted way to obtain the launch secret. |
| Same-origin Android WebView | **Selected for A2.** Keeps the Deck in the companion window and gives the app control of secret entry and separate browser state. It must prove the Android picker, authenticated download and navigation behavior on the Redmi. |
| Chrome Custom Tab | Browser-owned picker, downloads and session state reduce integration work. The browser owns the visible surface and launch `Intent`. Including the existing fragment would put the credential in that intent, while the current Deck has no browser pairing form for a bare URL. Use the existing standalone Chrome flow as the owner-operated fallback. |

Embedding Python/FFmpeg, rewriting media, running arbitrary shell commands,
granting broad storage access and adding a service are outside this design.
[Prior loopback decision](ANDROID_INTEGRATION_DECISION.md) ·
[Chrome Custom Tabs](https://developer.chrome.com/docs/android/custom-tabs/)

## Components and pairing

```text
Owner -> Termux terminal -> foreground Python adapter -> existing workflow / FFmpeg
  |                              |                         |
  | reads live origin and token   | HTTP 127.0.0.1:8765     +-> owned session root
  v                              |
Masked companion input -> same-origin WebView <-> existing Processing Deck
                                   |                         |
                      system picker supplies content URIs    +-> verified ZIP GET
                                                                  |
                                       app-private temporary copy -> system Save As
```

1. The owner sets `RECORANDRO_DATA_ROOT` to the intended private data root and
   runs `python -m recorandro.mobile_ui --port 8765` in the reviewed Termux checkout. The
   adapter prints its origin and 256-bit launch secret only after binding.
   A2 displays the fixed origin `http://127.0.0.1:8765` for the owner to confirm
   against the live terminal. A port conflict or a different printed origin
   stops pairing. The companion accepts just the 43-character base64url value
   after `#` in its masked field. The URL is constructed internally.
2. Use a password-style field with screenshot/recents protection (`FLAG_SECURE`)
   during pairing, with copy, paste, autofill, saved state and keyboard learning
   disabled or suppressed where supported. Use a trusted keyboard. Enter the
   value from the live terminal without screenshots, clipboard, sharing or
   redirecting terminal output to a file. The companion keeps the value in
   memory for one submission and clears its field immediately. It passes the
   fragment directly to its WebView, with no Android intent, query parameter,
   logging, telemetry, backup, public storage or WebView state restoration.
   The existing Termux terminal can still show the token in scrollback, and
   the companion cannot protect Termux or the input method from capture.
3. The stock page removes the fragment with `history.replaceState` before sending
   it in `X-Launch-Token` on the same-origin `POST /auth`. The existing adapter
   checks exact Host and Origin, issues its HttpOnly, SameSite=Strict session
   cookie and returns the CSRF token. The page keeps CSRF in memory and sends it
   on later mutations. `/state` and the verified ZIP route require the cookie.
   Server response policy, route checks, locks and registry verification apply
   through both clients. The launch value can be reused until adapter restart.
4. Use the companion's isolated WebView cookie store and the page's existing
   `sessionStorage` for the session ID. Disable backups, WebView debugging and
   browser-state restoration. Clear cookies and WebView state on explicit
   disconnect and before a new pairing, including cold start after process
   death. Treat any provider-written cookie state as sensitive app-private data.
   After a failed or stale pairing, the owner uses the companion's pairing
   screen again with the live launch value. The owner retains the session ID
   for recovery.

The existing adapter sets a host-only cookie on `/`. HTTP cookies lack a port
boundary, and this cookie lacks `Secure` on the HTTP listener. A2 keeps the
WebView and native download to the one exact origin and uses a cookie from that
store only for the validated ZIP request. Keep cookies, CSRF values, download
capabilities and filenames out of diagnostic output.
[Adapter](../recorandro/mobile_ui.py) · [Deck controller](../recorandro/mobile_web/app.js) ·
[Browser launch and bounds](MOBILE_UI_PROTOTYPE.md) ·
[Android secure window flag](https://developer.android.com/reference/android/view/WindowManager.LayoutParams#FLAG_SECURE) ·
[WebView cookie APIs](https://developer.android.com/reference/android/webkit/CookieManager)

## Security and lifecycle

- **Listener trust.** Loopback confines network reachability to the phone.
  Other local apps can connect, and an impostor can bind the port when it is
  vacant. Exact Host and Origin checks protect the real service from browsers
  using another origin. Neither those checks nor cleartext HTTP proves the
  listener's identity to the companion. Pair only against the owner's freshly
  confirmed live Termux listener. A missing listener, unexpected response,
  port conflict or navigation failure exits pairing without retrying the
  credential. A malicious same-port listener could see a submitted token or
  serve a false Deck. Exposure calls for rotating the launch credential by
  restarting Termux's adapter. The trust assumption is an owner-controlled
  phone, trusted keyboard and WebView, and a genuine live bind from the reviewed
  checkout. Root, compromised device software and same-UID compromise are
  outside this boundary.
- **Network and component scope.** Request the normal `INTERNET` permission.
  Deny cleartext by default and propose a Network Security Config exception
  only for literal `127.0.0.1`, with no subdomains. Verify it with Android 12 and
  the installed WebView. Independently restrict navigation, subresources where
  the platform exposes them, and native ZIP requests to the exact scheme,
  host and port. Reject aliases, external redirects, popups and external
  schemes. WebView callbacks have gaps for POSTs and redirected subresources.
  The stock page's same-origin CSP is another layer for the genuine page, and
  the native downloader must disable redirects. Turn off file URL access and
  universal file access, block mixed content and third-party cookies, and use
  no JavaScript bridge. Permit JavaScript and browser storage for the Deck.
  Give only the launcher Activity an exported entry point and ignore incoming
  intent data and extras. No deep links, services, receivers or exported
  providers are needed for A2.
  [Android network policy](https://developer.android.com/privacy-and-security/security-config) ·
  [Android 12 hostname policy](https://raw.githubusercontent.com/aosp-mirror/platform_frameworks_base/android-12.0.0_r1/core/java/android/security/net/config/ApplicationConfig.java) ·
  [WebView callback limits](https://developer.android.com/reference/android/webkit/WebViewClient) ·
  [Android 12 component rules](https://developer.android.com/about/versions/12/behavior-changes-12)
- **Termux provenance and authority.** Qualify the installed F-Droid Termux on
  the Redmi first. Record its installed source, version and signing identity.
  `com.termux` alone is not proof of authenticity. Termux and any existing
  plugins must use compatible source signatures. Upstream's GitHub APKs use
  a shared test key, which cannot prove genuine upstream provenance. Treat
  other distributions as unqualified until tested. Manual pairing needs no
  package lookup. If a later approved flow checks `com.termux`, Android 12
  package visibility calls for a narrow `<queries>` entry and signer validation.
  A future `RUN_COMMAND` route would need a supported Termux build, its exported
  service, `com.termux.permission.RUN_COMMAND` and `allow-external-apps=true`.
  This gives the granted app command execution as the Termux UID, including
  access to that UID's private files. Even a reviewed, fixed absolute script
  path under the Termux home with fixed arguments and no shell interpolation
  cannot restrict a compromised APK to that script. It also does not solve
  secret delivery. Keep that permission and configuration change outside A2.
  [Termux sources and signing](https://github.com/termux/termux-app#installation) ·
  [Termux RUN_COMMAND permission and privacy](https://github.com/termux/termux-app/wiki/RUN_COMMAND-Intent) ·
  [Android package visibility](https://developer.android.com/training/package-visibility/declaring)
- **Process ownership.** Foreground interaction can switch apps but gives the
  companion no control over Termux's lifetime. Android background activity and
  foreground-service launch limits depend on the calling path and targets.
  MIUI may terminate Termux or FFmpeg. Missing or unreachable Termux produces
  an in-app manual startup explanation with no dispatch or installation prompt.
  Closing the companion sends no Stop; the existing Stop is idle-only. If the
  server dies, restart it manually with the same data root, pair again, then
  use **Session → Open run** and **Resume** only if offered. The existing locks
  and recovery classifications govern retries. Root, wake locks and battery,
  overlay or autostart policy changes are outside A2.
  [Android 12 background limits](https://developer.android.com/about/versions/12/behavior-changes-12) ·
  [Existing recovery rules](SESSION_RECOVERY.md) · [Process-audio workflow](PROCESS_AUDIO.md)

## File selection, export and APK ownership

Use `WebChromeClient.onShowFileChooser` with the system document picker. Preserve
single recording selection and optional multi-photo selection. Accept only
user-granted, readable `content://` URIs from the chooser, validate the result
and resolve the pending callback once, including on cancellation. WebView still
has to stream the selected bytes through the stock upload. The backend owns
media admission, including the raw AAC normalization gate, and retains the
immutable original, source timeline and overlap, atomic publication and
verified registry. Zero-photo runs are complete, with archive OFF by default.
[WebView file chooser](https://developer.android.com/reference/android/webkit/WebChromeClient#onShowFileChooser(android.webkit.WebView,%20android.webkit.ValueCallback%3Candroid.net.Uri[]%3E,%20android.webkit.WebChromeClient.FileChooserParams)) ·
[Android document picker](https://developer.android.com/training/data-storage/shared/documents-files) ·
[Media contract](MEDIA_CONTRACT.md) · [Behavior contract](BEHAVIOR_CONTRACT.md)

Handle the Deck's ZIP link explicitly. Fetch only an exact-origin
`/download/<32 lowercase hex>` URL, without redirects, using the active WebView
session cookie. Require a successful ZIP response and complete transfer of the
declared length into an app-private temporary file with a free-space check and
timeouts. Then offer the system Save As picker (`ACTION_CREATE_DOCUMENT`) and a
safe ZIP filename. Report success only after copying the complete staged file.
On cancel or failure, clean temporary data and report any incomplete destination
the provider could not remove. The canonical ZIP stays under Termux ownership.
Fail the path if WebView/native cookie handoff cannot work with the existing
HttpOnly policy. A future native Share should expose only an app-owned export
through a `FileProvider` `content://` URI and a temporary read grant. If A2
picker or export support fails, the owner manually opens the current private
launch URL in standalone Chrome and uses its download/share flow. The APK never
forwards the secret or a protected download link to another app.
[Package and archive rules](PACKAGE_AND_ARCHIVE.md) ·
[Photo intake](VISUAL_ATTACHMENTS.md) ·
[Android file sharing](https://developer.android.com/training/secure-file-sharing/share-file)

Propose one `android-companion/app` module, display name **RecorAndro Companion**,
and application ID `dev.lopix.recorandro.companion`, subject to owner approval.
A2 targets the Android 12/API 31 device scope. Use one Kotlin Activity with
platform WebView and document picker APIs, a small origin/pairing policy and a
ZIP transfer helper. Pin the Android build tools, Gradle and Kotlin versions
when A2 is authorized. The system WebView is a runtime dependency. No bundled
web assets, native media dependencies, browser library or background worker are
needed. Candidate provenance should record the source commit, toolchain,
backend compatibility revision, APK SHA-256 and signing certificate fingerprint.
Use an owner-controlled signing key for approved distributions. An update uses
the same app ID and signing identity. Installing or uninstalling the companion
does not touch the separate Termux app or its data. Files explicitly saved with
the picker can remain after uninstall. Uninstalling or clearing Termux can
remove its private checkout and sessions, including managed originals.
[Android signing verification](https://developer.android.com/tools/apksigner)

## Proposed A2 acceptance gates

Run focused host checks for the companion's origin parsing, secret handling,
chooser state and ZIP response handling, plus module compilation and
`git diff --check`. For the HTTP contract, use only the focused adapter checks
and disposable fixtures. Review the merged manifest, backup and debug settings.
Obtain separate owner approval before installation, signing or keystore
generation, including automatic debug-key generation.
[Existing adapter tests](../tests/test_mobile_ui.py)

| Manual Redmi action | Pass condition and failure gate |
| --- | --- |
| Record OS/MIUI, WebView, Termux source/version/signer, and tested revisions. Use the F-Droid Termux checkout in ordinary UID context, a fresh private data root, and local disposable files with external networking off. Try opening the companion before starting the listener. | Clear stopped/unreachable guidance and no automatic dispatch, privilege request or remote attempt. Test actual missing Termux on a clean emulator or test device if it cannot be tested on the Redmi without disturbing the existing installation. |
| Start the adapter at port 8765. Try invalid input and a wrong token, then submit the current token. Check screenshot/recents protection with a disposable value and inspect redacted device diagnostics. | The app pairs only on the literal origin and reaches authenticated state with the stock cookie and CSRF flow. A wrong token gives no access. Host checks reject a foreign Host or Origin, missing cookie or CSRF, and navigation away from the permitted endpoint. Device checks reject remote HTTP, external navigation and a wrong port. A credential in a capture, log, intent, query, clipboard, restored state or public file blocks A2. |
| Cancel the picker, then select a short local WAV or M4A. Process with zero photos and archive OFF. Open Exports and Save As for its single part ZIP. | Cancellation starts no job. One verified session reaches `packaged` and a saved ZIP matches the registry SHA-256 and size in an independent read-only comparison. ZIP CRC passes, with exactly the audio part and two manifests. Stale or rejected downloads, cancellation and interrupted copies never report success. Optional multi-photo selection and explicit archive ON get a second disposable smoke check, with the photos excluded from part ZIPs. |
| Reopen the companion while the disposable adapter is live. Then restart the adapter with the same disposable root, try the stale token, pair with the new one, and reopen the retained ID. In a separate disposable run, interrupt after verified import and exercise Resume if the core classifies it as retryable. | No duplicate import, stale credentials fail, the same ID reopens, and an offered Resume recovers that ID to verified Exports. Incomplete or manual-attention cases stay explicit. Record an unobserved active interruption as pending, using a longer disposable fixture if needed. |

If an essential APK gate fails, keep the Chrome fallback and report the failed
gate before advancing to a candidate. The historical lecture session
`d0c39956c17943299dd17e67bf6d1d68` is outside the A2 fixtures and stays untouched.
The v0.1 active Processing screenshot and receiver-side independent ZIP hash
remain **DEFERRED / NOT VERIFIED**. A2 Save As verification is for its disposable
fixture. Screen-off survival, MIUI interruption tolerance, hotspot coexistence,
battery and thermal measurements require separate device evidence.
