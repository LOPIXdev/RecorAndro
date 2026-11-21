# RecorAndro A2 Redmi device gate

**Physical Redmi status · NOT TESTED.** This checklist qualifies manual Termux
startup and authenticated, read-only viewing in the companion. File picker,
download and Share in the APK are **NOT IMPLEMENTED** for this narrowed A2.
Use the existing standalone Chrome flow for those actions.
[Architecture decision](ANDROID_COMPANION_ARCHITECTURE.md) ·
[Termux/browser fallback](V0_1_FREEZE.md#quick-start-on-android)

## Reviewed build and prerequisites

- APK path from the repository root is
  `android-companion/app/build/outputs/apk/debug/app-debug.apk`.
- APK SHA-256 is `c016d8cd38ad47815939816eff4aaa9bc532c7ea2f37615fa499e2417119fcf5`.
- Debug signing certificate SHA-256 is
  `805406a272bc9a43047b889f541c8e72b11194969810ddce317eab0b050f73d3`.
- Application ID is `dev.lopix.recorandro.companion`, version `0.2.0-a2`
  (version code `1`), with Android 12/API 31 as the minimum. This is a
  workspace-local debug-signed artifact for this device gate.
- Build tools are Eclipse Temurin JDK `17.0.21.1+2`, Gradle `8.9`, Android Gradle
  Plugin `8.7.3`, SDK platform `35`, Build Tools `34.0.0`, and target SDK `34`.
  The app uses Java and the platform WebView with no runtime dependencies. Set
  `JAVA_HOME` and `ANDROID_HOME` for the installed SDK, then run
  `gradle -p android-companion :app:assembleDebug :app:lintDebug :app:testDebugUnitTest`
  with Gradle `8.9`. The owner-approved debug key is at
  `android-companion/.toolchain/a2-debug.keystore` and is ignored by Git.
- The backend serves the stock browser source at the `0.1.0` freeze
  `1a995068196e33b544ad226fd777514df7e5cff2`, also present in the A1 commit
  `d4b27eaa2a6d4f423ff10aefb6c8980169028bda`. The APK checks the three public
  assets against their SHA-256 values before the WebView can receive a code.
  The WebView opens the bare origin and sends the code only in the existing
  `/auth` header. That avoids exposing the code in a WebView URL. An app that
  occupies the same port can still imitate the listener. The owner's live
  Termux launch remains the source of listener identity.

Host checks passed for debug assembly, APK signature, the four JVM tests,
and the disposable headless Windows Chrome handshake against the unchanged
Python adapter. The host checked absent and wrong servers, wrong and stale
codes, valid pairing, HttpOnly cookie use, wrong Host and Origin, missing CSRF,
and loss of connection after STOP. Android lint reported zero errors and three
warnings for the pinned target SDK, pinned Gradle plugin and omitted custom
icon. The SDK metadata version warning did not block the build. The host
checks leave Android WebView and the complete Redmi procedure unverified.

## 1. Identify the Redmi and Termux

In Settings → About phone, record the exact model, Android version, MIUI
version and Android security patch. In Settings → Apps → Manage apps, record
the Termux and Android System WebView versions. If Android reports a different
active WebView provider, record that provider and version.

In the installed Termux, run `termux-info`. Record `com.termux`, installed app
version and APK release source as reported. Check it against the owner's F-Droid
installation record. Installer metadata alone is insufficient to verify the
signer. If ADB is already authorized and the signing certificate is needed,
use `adb shell pm path com.termux`, pull the reported `base.apk` to a private
host directory, and use `apksigner verify --print-certs` on it. Compare its
SHA-256 certificate fingerprint with the trusted F-Droid package for the same
app source. Record unavailable signer evidence as **NOT TESTED**. Keep the
existing Termux installation and its data. [Termux environment](TERMUX_ENVIRONMENT.md) ·
[Termux distribution and signing](https://github.com/termux/termux-app#installation)

From the reviewed Termux checkout, run these read-only checks:

```sh
id -u
git rev-parse HEAD
git diff 1a995068196e33b544ad226fd777514df7e5cff2 -- recorandro/mobile_ui.py recorandro/mobile_web
python --version
command -v python ffmpeg ffprobe
```

Expect ordinary Termux UID, no adapter or browser diff, and available tools.
If Termux or a dependency is missing, record the exact missing item. The
companion shows an unreachable endpoint when Termux cannot start the Deck.
Any missing dependency remains a device gate failure until resolved by the
owner through the established Termux setup.

## 2. Verify and install the APK · owner action

On Windows, run `Get-FileHash -Algorithm SHA256` on the reviewed APK before
copying it to the Redmi. Match the digest above. Verify
the APK certificate with SDK Build Tools `apksigner verify --print-certs` if
recording signer evidence. Use an owner-controlled local transfer, then open
the file in the phone's Files app and review the installer prompt. After
installation, confirm **RecorAndro Companion** version `0.2.0-a2` in App info.

The companion requests Android's normal `INTERNET` permission for loopback.
There is no runtime grant to approve. If Android asks for permission to install
from the Files app, the owner can cancel and continue in standalone Chrome.
If the owner chooses to allow this one reviewed installation, restore the
previous **Allow from this source** setting afterwards. If the installer
rejects the APK or shows an unexpected prompt, record the exact error and use
the Chrome fallback. Keep Termux external command, storage, battery and root
settings as they are.

## 3. Check absent and wrong-port behavior

Use a fresh Termux terminal and this owned disposable root. Use a different
directory from every accepted lecture or previous session.

```sh
export RECORANDRO_DATA_ROOT="$(mktemp -d "$HOME/recorandro-a2.XXXXXXXX")"
```

1. With the A2 adapter stopped and port `8765` clear, open the companion and
   type a 43-character dummy code. Tap **Connect**. Expect **No response from
   the Deck on port 8765**, with manual Termux guidance and no Deck shown.
   If an existing owner session uses `8765`, avoid stopping it for this test.
2. In that disposable terminal run
   `python -m recorandro.mobile_ui --port 8766`. Confirm the printed port is
   `8766`. Use a dummy code in the APK, never the code from `8766`. Expect the
   same no-response result for `8765`. Stop this idle test adapter with Ctrl+C.
3. If a different listener answers at `8765`, record any **reviewed Deck**
   mismatch and stop. A port conflict in Termux takes priority. Enter a real code
   only after seeing the reviewed adapter bind and print the expected origin.
   Actual absence of the Termux package can be checked on a spare device or a
   clean emulator. Preserve the installed Redmi Termux.

## 4. Pair on the same phone

1. In the disposable terminal run:

   ```sh
   python -m recorandro.mobile_ui --port 8765
   ```

   Confirm the foreground terminal printed `http://127.0.0.1:8765/#…` on the
   Redmi. Keep Termux running. Browser and APK access work through loopback,
   so this check can be performed with Wi-Fi and cellular data off.
2. Try short input first, then a syntactically valid 43-character dummy code.
   Expect a format message for the short input and **Launch code rejected**
   for the dummy. Neither attempt should reveal the Deck.
3. Type only the 43 characters after `#` from the confirmed live terminal in the
   masked companion field. Use a trusted keyboard. Avoid clipboard use,
   terminal screenshots, terminal capture and recorded typing. Tap **Connect**.
   Expect **Connected. The protected Processing Deck responded** and the stock
   Processing Deck preview. A spinner or just seeing a title is insufficient.
   The APK declares Connected only after the same-origin `/auth` response and a
   successful cookie-authenticated `/state` read with matching CSRF evidence.
4. Try rapid repeated taps during pairing. Expect one attempt, with the button
   disabled until disconnect or failure. File picker, download and Share remain
   marked **NOT IMPLEMENTED**. If wrong code opens the Deck, pairing succeeds
   against the wrong origin, or a credential is exposed, stop and use Chrome.

## 5. Reopen, reject stale credentials and stop

1. Tap **Disconnect**, or leave the companion using Home and reopen it. Expect a
   blank masked field, no Deck preview and the disconnected indicator. Termux
   should still be running. Re-entering the same code succeeds while the same
   Termux launch is live.
2. To observe live connection loss, use split-screen if supported and stop the
   idle disposable adapter with Ctrl+C while the preview remains visible.
   Expect **Connection lost** and the preview to close. If switching windows
   already disconnects the companion, record the live-loss check as **NOT TESTED**.
3. Start the adapter again on `8765` in the same disposable terminal. Type the
   previous launch code manually. Expect rejection, then success with the new
   code. If retaining the previous code is impractical without copying it,
   record stale-code validation as **NOT TESTED** on the Redmi.
4. For final STOP, disconnect in the companion and stop only the disposable
   idle adapter with Ctrl+C. A dummy code should now show the no-response message.

## 6. Record evidence

Use **PASS**, **FAIL** or **NOT TESTED** for each row and record the model,
versions, checkout SHA, APK SHA-256 and concise observations. A screenshot of
the connected preview may be captured after pairing. The pairing screen should
be protected from normal screenshots and the recents preview. Test capture
protection with dummy input. Record only redacted error/status excerpts. Omit
the Termux launch line, code, cookie, CSRF value, personal filenames and paths
from all evidence. If the auth or secret containment gate fails, stop and use
standalone Chrome for the disposable test setup.

| Check | Redmi result | Observation |
| --- | --- | --- |
| Device, Termux source, signer and toolchain | NOT TESTED | |
| Exact APK and owner installation or decline | NOT TESTED | |
| Absent/misconfigured adapter and wrong port | NOT TESTED | |
| Bad input and wrong code rejected | NOT TESTED | |
| Valid code reaches authenticated Deck, repeated Connect | NOT TESTED | |
| Pairing screenshot/recents and redaction | NOT TESTED | |
| Disconnect, reopen, stopped adapter and restart with stale code | NOT TESTED | |
| Final STOP and owner uninstall | NOT TESTED | |

## 7. Uninstall · owner action

Disconnect and stop the idle disposable adapter. In Android Settings → Apps,
uninstall only **RecorAndro Companion** (`dev.lopix.recorandro.companion`). Confirm
Termux is still installed and opens normally. Keep the disposable Termux root
for the gate record if needed. Existing Termux sessions, including the accepted
lecture, require no action. Restore any installer-source setting changed in
step 2 to its previous value.
