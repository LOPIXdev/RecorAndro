# RecorAndro Companion A3

A3 opens the existing New Run, Processing and Exports views in the Android
companion. Termux owns adapter startup, FFmpeg, session storage and verification.
**A3 core device acceptance · PASS.** The owner reported installing the A3
debug APK on a Xiaomi Redmi Note 10 Pro, pairing with the live Termux adapter,
selecting a recording through Android Files, and reaching visible ZIP entries
in Exports after processing completed. The physical acceptance covers those
observations. Native ZIP Save As, Android Share and interrupted-session recovery
remain **NOT VERIFIED** on Redmi and are A4 work.
[Owner-accepted A2 gate](ANDROID_COMPANION_A2_DEVICE_GATE.md)

## Install and run

1. On the host, verify the SHA-256 of the A3 APK before copying it to the phone.
   The build output is `android-companion/app/build/a3/outputs/apk/debug/app-debug.apk`.
   The SHA-256 for this build is
   `0e231263e611fdbcf7a7ee5cb54e57bf8e88e7eecca2bf2d48647ac3062bf85a`.
   Install it through Android Files. The debug APK can update A2 when both use
   the same signing key. The proposed identity is **RecorAndro Companion**,
   `dev.lopix.recorandro.companion`, with the standard Android placeholder
   icon. A3 uses `0.2.0-a3`, version code `2`, and requires Android 12 or newer.
2. Run the following commands from the reviewed checkout as the normal Termux
   user. They start the adapter with a fresh private directory for the test.

   ```sh
   export RECORANDRO_DATA_ROOT="$(mktemp -d "$HOME/recorandro-a3.XXXXXXXX")"
   python -m recorandro.mobile_ui --port 8765
   ```

3. Confirm that the live terminal prints `http://127.0.0.1:8765/#…`. Type only
   the value after `#` into the masked field. Tap **Connect**. **Deck ready**
   means that the WebView paired and read authenticated state at the fixed origin.
4. In **New Run**, choose one on-device recording in Android Files. Use **Attach**
   for up to eight optional photos. Back in the picker cancels that selection.
   The Deck keeps its 128 MiB audio, 16 MiB per photo and 192 MiB combined limits.
   Android supplies temporary document URI grants to WebView. The existing
   upload sends the file bytes to Termux, where the adapter still validates media
   and the duration budget. The photo-free path and Full Archive OFF are defaults.
5. Tap **Process recording** and keep the session ID shown in **Processing**.
   **Exports** lists verified artifacts. Use the existing standalone Chrome
   flow to download or share these ZIPs. [Chrome fallback](V0_1_FREEZE.md#quick-start-on-android)

**Disconnect** or Android Back returns to the pairing screen. Leaving for
another app disconnects and clears WebView credentials. Android Files is an
exception while its selection is pending. On return, the app rechecks the
protected origin before resuming interaction. Rotation and screen resizing
keep the current WebView and in-progress selection while the Activity survives.
After reconnecting, a retained session ID can prefill **Session → Open run**.
Tap **Open run** yourself. The existing recovery classification controls
**Resume**. If the app no longer has the ID, use the ID you recorded.

Closing the app does not send Termux a stop command. Leaving during an upload
can interrupt that transfer. Check the session's actual status before trying
another run. For an idle shutdown, use **Session → Stop adapter** or stop the
foreground adapter in Termux yourself. Restarting Termux's adapter requires
pairing with its new code.

## Build and verification

Run the following from the repository root. It uses the workspace toolchain and
the existing owner-approved debug key at `android-companion/.toolchain/a2-debug.keystore`.

```powershell
$toolchain = (Resolve-Path android-companion/.toolchain).Path
$env:JAVA_HOME = Join-Path $toolchain 'jdk-17.0.21.1+2'
$env:ANDROID_HOME = Join-Path $toolchain 'sdk'
$env:GRADLE_USER_HOME = Join-Path $toolchain 'gradle-home'
& (Join-Path $toolchain 'gradle-8.9\bin\gradle.bat') --offline --no-daemon -p android-companion :app:assembleDebug :app:lintDebug :app:testDebugUnitTest
Get-FileHash -Algorithm SHA256 android-companion/app/build/a3/outputs/apk/debug/app-debug.apk
```

The pinned Android Gradle Plugin is `8.7.3`, with SDK `35`, Build Tools `34.0.0`
and target SDK `34`. The offline command expects the pinned dependencies in the
local Gradle cache. A3 has a separate output directory so the reviewed A2 APK
remains available for A5.

Debug assembly, signature verification, all five JVM tests and the injected
JavaScript syntax check passed. Android lint reported zero errors and one
warning for target SDK `34`. The A3 debug signer matches the reviewed A2 debug
signer.

On a Windows-hosted Android 12/API 31 emulator with WebView `91.0.4472.114`,
the APK reached the existing New Run page, opened Android Files, and returned
from a picker cancelled after rotation without creating a session. A separate
run selected a synthetic 12-second WAV and two JPEGs through Android Files.
The WebView uploaded the files to the existing adapter over loopback using ADB
reverse. Processing displayed the session ID, the original matched the input
bytes, and the session reached verified Exports with Full Archive OFF. The
part ZIP passed CRC and contained `part_01.m4a`, `manifest.json` and
`manifest.md`. After stopping and restarting the disposable adapter, the old
code was rejected. After pairing with a fresh code, **Open run** reopened
the retained ID and displayed Exports. Back disconnected the APK while the
adapter still responded. This test used
the Windows Python/FFmpeg backend with a disposable root.

## Remaining Redmi checks

- With a disposable root and files, check offline use, portrait and landscape,
  Back, and picker cancellation. Check optional photo selection and clearing.
  Compare the session ID shown during Processing with the retained run opened
  from the session menu.
- Stop and restart the adapter while idle. Check the stale connection state,
  pair with a fresh code and reopen the same session ID. Record whether any
  issue was specific to MIUI, the WebView provider or a document provider.
- Keep the [remaining A2 items](ANDROID_COMPANION_A2_DEVICE_GATE.md#6-record-evidence)
  on the A5 list, including full inventory, wrong/stale code rejection, wrong
  port, STOP/restart, screenshot and recents protection, and uninstall.

Only reviewed Deck assets run in the WebView. Local HTTP can still be imitated
by a process occupying the same port, so confirm the live Termux launch before
entering the code. Keep launch codes, cookies, CSRF values and private media
names out of test evidence. MIUI process survival and physical renderer-failure
recovery still require device evidence.
[A4 export and recovery guide](ANDROID_COMPANION_A4.md)
