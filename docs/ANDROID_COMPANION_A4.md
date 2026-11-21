# RecorAndro Companion A4

**Physical A4 Redmi status · NOT VERIFIED.** The owner accepted [A3 on the
Redmi](ANDROID_COMPANION_A3.md) for installation, pairing, recording selection,
processing and visible ZIP exports. A4 adds the native export and recovery flow.

## Build and install

A4 is `0.2.0-a4` (version code `3`) and uses application ID
`dev.lopix.recorandro.companion`. It can update A3 using the same debug signer.
The artifact is `android-companion/app/build/a4/outputs/apk/debug/app-debug.apk`.
Its SHA-256 is `f058e2867c9b5692f1584424db39d667f3ee00d2b31e77828e5cce418e068283`.
The separate A2 and A3 build paths preserve their reviewed APKs.

Run from the repository root with the installed workspace toolchain. The build
uses the existing owner-approved `android-companion/.toolchain/a2-debug.keystore`
and pinned AndroidX Core `1.15.0` for FileProvider.

```powershell
$toolchain = (Resolve-Path android-companion/.toolchain).Path
$env:JAVA_HOME = Join-Path $toolchain 'jdk-17.0.21.1+2'
$env:ANDROID_HOME = Join-Path $toolchain 'sdk'
$env:GRADLE_USER_HOME = Join-Path $toolchain 'gradle-home'
& (Join-Path $toolchain 'gradle-8.9\bin\gradle.bat') --no-daemon -p android-companion :app:assembleDebug :app:lintDebug :app:testDebugUnitTest
Get-FileHash -Algorithm SHA256 android-companion/app/build/a4/outputs/apk/debug/app-debug.apk
```

## Focused verification

Debug build, APK signature, nine JVM tests, JavaScript syntax, and the local
documentation and whitespace checks passed. Android lint reported zero
errors and three warnings for the pinned target SDK, Android Gradle Plugin
and conservative usable-space check. A disposable localhost fixture verified
wrong-server and ZIP redirect rejection. The injected JavaScript showed and
cleared the raw AAC guidance in a DOM check.

The nine existing adapter checks covered cookie/Host/Origin/CSRF enforcement,
storage denial, repeated Start, busy and idle Stop, permitted Resume, optional
photo failure, and refusal of corrupt ZIPs. The archive failure test retained
the verified audio ZIPs. Run those checks from the repo root.

```powershell
$env:PYTHONPATH = (Resolve-Path tests).Path
$adapterTests = @(
    'test_mobile_ui.SecurityTests.test_binding_auth_cookie_and_response_headers'
    'test_mobile_ui.SecurityTests.test_foreign_origin_host_missing_origin_and_csrf'
    'test_mobile_ui.SecurityTests.test_staging_space_denial'
    'test_mobile_ui.SecurityTests.test_duplicate_start_single_worker_and_stop_busy'
    'test_mobile_ui.SecurityTests.test_stop_idle'
    'test_mobile_ui.SecurityTests.test_reopen_resume_classification_and_worker'
    'test_mobile_ui.SecurityTests.test_optional_photo_failure_keeps_verified_parts_ready'
    'test_mobile_ui.ActualMediaTests.test_photos_and_explicit_archive_are_verified'
    'test_mobile_ui.ActualMediaTests.test_upload_process_download_corruption_resume'
)
python -m unittest @adapterTests -v
```

On the Windows-hosted Android 12 emulator, Android Files selected a synthetic
eight-second M4A. A test-only fixture paused the existing adapter after verified
import. After stopping the disposable adapter and cold-restarting the app,
the old code was rejected. A fresh login prefilled the same session ID.
**Open run → Resume** reached verified Exports with one session and identical
original bytes. Save As cancellation created no file. A completed Save As
matched the registry SHA-256, and the separate Android receiving app read the
shared ZIP through a read-only `content://` grant and independently matched
the registry SHA-256 and byte count. Cancelling the Sharesheet did not launch
the receiver. These tests used the existing Windows-hosted adapter over
ADB loopback and a disposable root. Redmi and MIUI behavior remain unverified.

## Export and recovery behavior

- In **Exports**, tap **Download** on an existing part or a verified Full
  Archive. Android fetches the exact loopback route using the active WebView
  session cookie. Termux re-verifies the artifact under its existing registry
  and session lock before emitting bytes. Android checks the response, complete
  length, available private-cache space and readable ZIP directory before it
  offers any action. Staging and Save As use a transfer digest for byte-copy
  consistency. The registry still establishes which artifacts are verified.
- **Save As** opens Android Files with the ZIP name. Select a local destination.
  Android reports success after copying the complete ZIP and closing the output
  stream. Cancellation or an error suppresses success. If the provider cannot
  remove a failed or partial file, check the selected destination before retrying.
  A force stop while Android Files is creating or writing the document can also
  leave a destination entry that needs inspection. [Android document picker](https://developer.android.com/training/data-storage/shared/documents-files)
- **Share** opens Android Sharesheet with one app-private ZIP `content://` URI
  and a temporary read grant. Select a trusted recipient. The receiver may
  keep its own copy. A Sharesheet launch does not establish receipt or byte
  equality. Back cancels selection. Android may clear the private cache, and
  the companion removes cache entries older than 24 hours on a later export.
  If a recipient is unavailable, use **Save As** and Android Files to share the
  saved ZIP. [Android file sharing](https://developer.android.com/training/secure-file-sharing/share-file)
- The last adapter-reported session ID is retained in the companion's private
  preferences, excluded from backups. After a cold restart, pair using the
  live adapter code. Select **Session → Open run** to reopen that exact ID.
  **Resume** appears only if the canonical classification permits it. A
  session interrupted before verified import may require explicit source
  selection. The app does not silently re-import or auto-resume.
  [Canonical recovery](SESSION_RECOVERY.md)
- **Stop adapter** is an explicit action for the idle adapter. The Deck hides
  the action while busy and Termux refuses a busy Stop. Leaving or disconnecting
  the companion does not stop Termux. After restarting the adapter, pair with
  its fresh code. Screen-off and MIUI process survival require separate evidence.
- Selecting `.aac` shows an early raw-duration warning. The existing adapter
  still decides media admission and may block normalization of raw AAC with
  unverified duration. If that happens, select a source recording already in
  M4A, MP3 or WAV. The Deck displays adapter import and storage failures. Android
  displays separate messages for missing picker access, insufficient staging
  space, stale/rejected exports, malformed ZIPs and failed saves. Optional photo
  or archive failure does not suppress independently verified part ZIPs.

The only exported component is the launcher Activity. The FileProvider is
non-exported and maps only the app's ZIP cache. `INTERNET` is the only requested
permission. Pairing stays manual on `http://127.0.0.1:8765`. The app keeps
redirects and external/file navigation blocked. Android passes the WebView
session cookie only to the existing exact-origin ZIP route. Launch codes,
cookies, CSRF values and download capabilities are excluded from recipient
intents and diagnostic evidence. Cleartext loopback still relies on the owner
confirming the live Termux adapter. The companion makes no battery policy or
Termux permission changes.

## Redmi owner checklist

1. Verify the APK digest. Install through Android Files and confirm
   `0.2.0-a4` in App info. Use the reviewed checkout and a fresh private test
   root. Start the adapter manually from the checkout.

   ```sh
   export RECORANDRO_DATA_ROOT="$(mktemp -d "$HOME/recorandro-a4.XXXXXXXX")"
   python -m recorandro.mobile_ui --port 8765
   ```

2. Pair on the live port. With disposable files, cancel one picker and confirm
   no import. Select a raw `.aac` fixture to check the warning, then replace it
   with a short nonpersonal M4A. Process the M4A and retain its ID. Record
   actual Processing and Exports screens when possible.
3. Tap a verified part's **Download**. Cancel **Save As** once, then save it in
   local Downloads. A read-only `python -m recorandro status SESSION_ID` on the
   same Termux data root shows the verified ZIP size and SHA-256. Independently
   compute the saved file's size and SHA-256, for example by transferring that
   saved copy to a trusted host. Use `Get-Item` for the byte length and
   `Get-FileHash -Algorithm SHA256` for the digest.
   Compare both values and check ZIP CRC and its audio and two manifests.
4. Open **Share**, press Back, and confirm no receiver was launched. Repeat and
   choose a trusted receiving app. Verify the receiver's independent copy
   against the original registry SHA-256 and byte length. If the chosen app
   cannot show or export its received bytes, mark receiver integrity **NOT
   VERIFIED**. Record unexpected permission prompts and any partial file left
   after a provider error. Keep the accepted lecture outside all fault tests.
5. For interruption, use a second disposable run. Wait until Processing shows
   its ID; then close the companion and interrupt only the disposable foreground
   adapter with Ctrl+C. If it completed before interruption, repeat with a
   longer disposable recording or mark the interrupted case **NOT VERIFIED**.
   Restart the adapter on the same root. Check the old code is rejected, pair
   with the new code, select **Open run**, and use **Resume** if offered. Confirm
   the same ID, immutable original and verified Exports without a second import.
6. Check that backing out of the app leaves Termux running, that an idle **Stop
   adapter** disconnects, and that a busy run stays protected. Record results as
   **PASS**, **FAIL** or **NOT VERIFIED**. Record Android/MIUI, WebView, Termux
   source/version and the APK digest. Remove launch codes, credentials, private
   paths and personal filenames from screenshots or logs. The remaining [A2
   device checks](ANDROID_COMPANION_A2_DEVICE_GATE.md#6-record-evidence) carry
   forward to A5 unless directly evidenced.
