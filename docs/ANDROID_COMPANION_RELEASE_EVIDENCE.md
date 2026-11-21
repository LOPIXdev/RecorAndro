# RecorAndro Companion A5 release evidence

**Final-icon RC1 · AWAITING_SIGNING.** Code-freeze scope is limited to the
launcher mark and release evidence. Physical acceptance of the final
`v0.2.0-android-rc1` APK is **DEVICE_ACCEPTANCE_PENDING**. The owner-reported A4
Redmi PASS covers installing and launching the debug app, completing audio
processing, and seeing verified ZIP entries. Physical Save As, Share and
interrupted recovery remain **NOT VERIFIED**. [A4 device evidence](ANDROID_COMPANION_A4.md)

## Reviewed baseline and package

A5 started on clean `main` at `e79c0b0fe85256ab4e974270ddb4191a030fc051`,
matching local `origin/main` and live GitHub `main`. Live GitHub had no tags or
published releases. The public API check does not cover private release drafts.
The icon freeze started on clean `main` at
`3cdfff891ae83d54dab83b6a5baea6f229be800f`, which records the A4 evidence, A5
preparation and the prior signed APK. [GitHub releases](https://github.com/LOPIXdev/RecorAndro/releases)

| Item | A5 proposal |
| --- | --- |
| App label and ID | RecorAndro Companion, `dev.lopix.recorandro.companion` |
| Release version | `0.2.0-android-rc1`, version code `4`. Debug variants have a `-debug` suffix. |
| SDK | Minimum API `31` (Android 12), target API `34`, compile API `35` platform revision `2` |
| Toolchain | Eclipse Temurin `17.0.21.1+2`, Gradle `8.9`, Android Gradle Plugin `8.7.3`, Build Tools `34.0.0` |
| Direct dependencies | AndroidX Core `1.15.0` for FileProvider, JUnit `4.13.2` for JVM tests |
| Permissions and components | `INTERNET`. Launcher Activity exported. ZIP FileProvider non-exported, with URI grants scoped to app-private ZIP cache. |
| Signing | Same owner-controlled release certificate as the prior RC1. A2–A4 use the local debug signer. |
| Launcher | The Processing Deck's existing `.deck-mark` tile, with the same colors, proportions and 28° strokes inside the Android adaptive mask. |

The recorded SDKs are for owner sideloading. Target API 34 exceeds the Android
14 and Android 15 platform installation floors. The Android 12 Redmi remains
the physical qualification target. The build makes no Play distribution or
later Android/MIUI compatibility claim. [AGP compatibility](https://developer.android.com/build/releases/agp-8-7-0-release-notes) ·
[Android 14 install floor](https://developer.android.com/about/versions/14/behavior-changes-all) ·
[Android 15 install floor](https://developer.android.com/about/versions/15/behavior-changes-all)

The Termux backend still uses the Python `0.1.0` freeze at
`1a995068196e33b544ad226fd777514df7e5cff2`. The exact Deck HTML, JavaScript and
CSS remain in the source tree and match the APK client's pinned SHA-256 values.
Termux serves those assets at runtime. The companion checks the hashes before
WebView execution. The WebView and native requests restrict traffic to the
fixed `http://127.0.0.1:8765` origin and reviewed routes. File navigation and
redirects are blocked. Termux still enforces Host, Origin, cookie, CSRF and
ZIP registry verification. Cleartext loopback relies on the owner checking the
live Termux adapter before entering the launch code. [A1 architecture](ANDROID_COMPANION_ARCHITECTURE.md) ·
[Frozen Python/browser release](V0_1_FREEZE.md)

## Prior A5 verification and signing

The original A5 preflight produced a **4,935,652-byte unsigned APK** with
SHA-256 `8ecd0275ff0ad19eef2e181d45d3a38154b525243d65d17a0085e62dd62e4c26`.
`aapt2` confirmed the proposed identity and SDKs, a non-debuggable release,
backups disabled, one exported launcher, a non-exported ZIP provider with
grants, and `INTERNET` as the sole requested permission. `zipalign -c 4` and
ZIP CRC passed. The APK has no `lib/` entries or bundled Python/FFmpeg, so it
has no APK-native ABI requirement. Termux supplies the tools for the phone's ABI.
The only `assets/` entries are ART baseline profiles. The 65-entry APK inventory
had no Deck copies, keystores, audio, session data, logs or launch credentials.
The ignored files are local tools and fixtures, build output, local data and
caches.

The [previously signed RC1](../final-apk/recorandro-companion-v0.2.0-android-rc1.apk)
is **SUPERSEDED** by the final-icon build. It remains available as historical
evidence. Its verified APK SHA-256 is
`420e0ecda86113cbf298e1bcb9075b7caa08fce8efb98c8cf6dfeb1cc8f56362`.
The release certificate SHA-256 is
`180ac304237015f409f8c8b0014bf89d59152e957a01aaf0d3fce777a0b6191e`.
The final APK must verify against that certificate.

| Check | A5 host result | Physical A5 Redmi |
| --- | --- | --- |
| Assemble, manifest, alignment and payload | PASS for the unsigned release. `apksigner verify` rejected the unsigned file as expected. | Installability **NOT VERIFIED**. Awaiting release signing. |
| Lint and native tests | PASS. Nine JVM tests covered route, port and token validation, repeated Connect, session ID restoration and ZIP length, filename and corruption checks. Lint had zero errors and two warnings for target API 34 and the conservative cache-space check. | **NOT VERIFIED**. |
| Authentication, picker cancellation, repeated Start, and original/ZIP integrity | PASS in seven focused adapter tests. Covered Host/Origin/cookie/CSRF, a truncated upload, busy Stop, canonical Resume, optional archive failure and corrupt ZIP refusal. Python, the tests and Deck source match the freeze. | **NOT VERIFIED** for A5. A4 owner PASS covers installation, launch, processing and visible exports only. |
| Real M4A, Save As, Share and interruption recovery | A4 Android 12 emulator evidence exists. A5 validation is limited to this unsigned release's host checks. | **NOT VERIFIED**. See the owner test sheet. |
| Production signer, signed APK size/digest and signature | PASS for the superseded signed RC1. See the APK and certificate fingerprints above. | **NOT VERIFIED**. |

Both the Deck JavaScript and the companion's injected script passed syntax
checks. Local documentation links and `git diff --check` passed. The historical
full Android suite was outside the A5 verification scope.

## Final-icon RC1 verification

The [Deck CSS mark](../recorandro/mobile_web/style.css#L62) supplies the tile
shape, two rotated strokes and exact palette. The adaptive launcher uses the
Deck canvas behind a centered copy of the complete tile. A geometry check and
rendered comparison matched the CSS and verified fit within Android's mask-safe
area. The app label, layout and code remain the reviewed A5 values.
[Android adaptive icon guidance](https://developer.android.com/develop/ui/views/launch/icon_design_adaptive)

| Check | Final-icon result |
| --- | --- |
| Release build and package verification | PASS for the unsigned APK. AAPT resolved the launcher to an adaptive icon with both layers. Package `dev.lopix.recorandro.companion`, version `0.2.0-android-rc1` / code `4`, min API `31`, target API `34` and the prior APK permissions matched. APK alignment and ZIP CRC passed. |
| Focused tests | Nine release JVM tests passed. Release lint reported zero errors and three warnings for target API 34, the cache-space check and the optional monochrome launcher layer. The Deck, Python engine, Java companion logic and permission policy resources match the code-freeze baseline. |
| Final unsigned output | `android-companion/app/build/a5/outputs/apk/release/app-release-unsigned.apk`, **4,937,928 bytes**, SHA-256 `092aac3c4d8f96d22b4b970c588595b18bdbbb4b9c086de869b552325044813c`. |
| Final signed output | **AWAITING_SIGNING**. Expected path is `android-companion/app/build/a5/outputs/apk/release/recorandro-companion-v0.2.0-android-rc1-final.apk`. Record the final signed digest only after signature verification with the established RC1 certificate. |
| Physical Redmi | **DEVICE_ACCEPTANCE_PENDING** for the final-icon build. Save As, Share and interrupted recovery remain **NOT VERIFIED** on the Redmi. |

## Build and local signing

Build the unsigned release from the repository root with the pinned toolchain.
The offline invocation requires those SDKs and Gradle caches to be present.

```powershell
$toolchain = (Resolve-Path android-companion/.toolchain).Path
$env:JAVA_HOME = Join-Path $toolchain 'jdk-17.0.21.1+2'
$env:ANDROID_HOME = Join-Path $toolchain 'sdk'
$env:GRADLE_USER_HOME = Join-Path $toolchain 'gradle-home'
& (Join-Path $toolchain 'gradle-8.9\bin\gradle.bat') --offline --no-daemon --rerun-tasks -p android-companion :app:assembleRelease :app:lintRelease :app:testReleaseUnitTest
```

Gradle leaves `android-companion/app/build/a5/outputs/apk/release/app-release-unsigned.apk`
unsigned. It is a preflight artifact. Android requires a valid signature to
install it. A debug-signed build is suitable for debug testing. A release-signed
APK is a candidate for owner acceptance. A published GitHub Release is a
separate owner-approved action. [Android signing](https://developer.android.com/studio/publish/app-signing)

The owner uses the existing release keystore **outside the checkout** and
makes these values available only in the local signing process. Keep the
keystore and passwords out of chat, files under the repository and command
history. The command passes password variable names to `apksigner`.

| Environment variable | Owner-supplied value |
| --- | --- |
| `RECORANDRO_RELEASE_KEYSTORE` | Absolute path to the off-repository keystore file |
| `RECORANDRO_RELEASE_KEY_ALIAS` | Release key alias |
| `RECORANDRO_RELEASE_STORE_PASSWORD` | Keystore password |
| `RECORANDRO_RELEASE_KEY_PASSWORD` | Key password, which can match the store password |

In a local PowerShell 7 signing terminal, password values can be entered with
`Read-Host -MaskInput`. Variables set in a separate terminal are local to that
process and its children. A session performing the signing needs those variables
in its own process environment.

Use the following in the same PowerShell environment with the existing key.
The build-local signing helper performs the same checks and clears its password
variables after use. The output path distinguishes the final-icon APK from the
superseded build.

```powershell
$signingNames = @('RECORANDRO_RELEASE_KEYSTORE', 'RECORANDRO_RELEASE_KEY_ALIAS',
    'RECORANDRO_RELEASE_STORE_PASSWORD', 'RECORANDRO_RELEASE_KEY_PASSWORD')
foreach ($signingName in $signingNames) {
    if ([string]::IsNullOrWhiteSpace([Environment]::GetEnvironmentVariable($signingName))) {
        throw "Missing local signing variable $signingName"
    }
}
$repo = (Resolve-Path .).Path
$store = Get-Item -LiteralPath $env:RECORANDRO_RELEASE_KEYSTORE -ErrorAction Stop
$relativeStore = [IO.Path]::GetRelativePath($repo, $store.FullName)
if ($store.PSIsContainer -or (-not [IO.Path]::IsPathRooted($relativeStore) -and
        $relativeStore -ne '..' -and -not $relativeStore.StartsWith('..\'))) {
    throw 'Choose a release keystore file outside this checkout.'
}
$buildTools = Join-Path $env:ANDROID_HOME 'build-tools\34.0.0'
$out = 'android-companion/app/build/a5/outputs/apk/release'
$unsigned = Join-Path $out 'app-release-unsigned.apk'
$candidate = Join-Path $out 'recorandro-companion-v0.2.0-android-rc1-final.apk'
if (Test-Path -LiteralPath $candidate) { throw 'A signed candidate already exists at this path.' }
if ((Get-FileHash -LiteralPath $unsigned -Algorithm SHA256).Hash -ne '092aac3c4d8f96d22b4b970c588595b18bdbbb4b9c086de869b552325044813c') {
    throw 'The unsigned APK does not match the reviewed final-icon build.'
}
& (Join-Path $buildTools 'zipalign.exe') -c 4 $unsigned
if ($LASTEXITCODE -ne 0) { throw 'The unsigned APK failed alignment verification.' }
& (Join-Path $buildTools 'apksigner.bat') sign --min-sdk-version 31 `
    --ks $store.FullName --ks-key-alias $env:RECORANDRO_RELEASE_KEY_ALIAS `
    --ks-pass env:RECORANDRO_RELEASE_STORE_PASSWORD `
    --key-pass env:RECORANDRO_RELEASE_KEY_PASSWORD --out $candidate $unsigned
if ($LASTEXITCODE -ne 0) { throw 'Candidate signing failed.' }
$signature = & (Join-Path $buildTools 'apksigner.bat') verify --min-sdk-version 31 --verbose --print-certs $candidate
if ($LASTEXITCODE -ne 0) { throw 'Candidate signature verification failed.' }
if (-not ($signature -match 'certificate SHA-256 digest: 180ac304237015f409f8c8b0014bf89d59152e957a01aaf0d3fce777a0b6191e$')) {
    throw 'The APK does not use the established RC1 certificate.'
}
$signature | Select-String 'Verifies|certificate SHA-256 digest'
& (Join-Path $buildTools 'aapt2.exe') dump badging $candidate
Get-Item -LiteralPath $candidate | Select-Object Length
Get-FileHash -LiteralPath $candidate -Algorithm SHA256
```

Compare the public certificate fingerprint with the approved release identity.
Capture the APK size, digest, manifest metadata and signing result. Keep the
signing environment local to the signing process. [APK signing tool](https://developer.android.com/tools/apksigner)

## Redmi owner test sheet

Use the final-icon release-signed candidate once available. Confirm the Deck
mark appears on the Redmi launcher. Record APK SHA-256, signer fingerprint,
version, model, Android/MIUI, WebView, and Termux version/source.
If Android refuses an in-place update from A4 because the signer differs,
record the last session ID first. The owner may uninstall only the debug
companion and then install the reviewed candidate. Termux and its separate data
root are outside that uninstall. If Android Files asks for permission to install
the APK, the owner can grant it for the reviewed install and restore the prior
setting afterwards. The companion has no runtime storage or Termux command grant.

Use the reviewed checkout in ordinary Termux with Python 3.10 or newer,
`ffmpeg` and `ffprobe` available. The Redmi baseline used F-Droid Termux.
Keep the working Termux installation and its separate data root. Use the
dependency guide if a test device still needs Python or FFmpeg. Start a
separate test root. [Termux dependency guide](TERMUX_ENVIRONMENT.md)

```sh
python --version
command -v python ffmpeg ffprobe
export RECORANDRO_DATA_ROOT="$(mktemp -d "$HOME/recorandro-a5.XXXXXXXX")"
python -m recorandro.mobile_ui --port 8765
```

1. Confirm the printed loopback origin on the phone. In the companion, test an
   absent adapter, a wrong code and a correct live code. Check that pairing
   captures and recents hide the entry. A successful live code opens the Deck.
2. Cancel selection, then choose a short nonpersonal M4A and press **Process
   recording**. Record one session ID, verified Exports, archive OFF and the
   original's size and hash. Reopening or repeated taps should leave a single
   import. For storage, provider and stale ZIP cases use disposable data only.
3. Cancel **Save As**, then save a verified ZIP and compare its SHA-256 and
   byte size with `python -m recorandro status SESSION_ID`. Confirm ZIP CRC
   and the two manifests. Open **Share**, cancel once, then send the ZIP to a
   trusted receiving app. A receiver-side digest check is a separate result.
4. In a separate test run, interrupt the disposable adapter after the session
   ID appears. Restart it with the same data root. Try the stale code, pair
   with the new code and choose **Open run** for the same ID. Use **Resume** if
   offered. Confirm verified Exports and the original hash with no second
   import. Try idle Stop and verify the companion never stops Termux by closing.
5. To exercise a stale or invalid download on the phone, leave a disposable
   export visible. With the adapter idle, temporarily rename only its registry
   ZIP inside the disposable test root. Tap the existing Download button and
   confirm refusal with no saved file. Restore the exact filename and use
   **Open run** to check that the verified ZIP is offered again.
6. Record each outcome as **PASS**, **FAIL**, or **NOT VERIFIED**. Use only
   redacted screenshots and logs. Keep the accepted lecture outside all tests.
   Record any remaining [A2 device checks](ANDROID_COMPANION_A2_DEVICE_GATE.md#6-record-evidence).

## Release-note draft and approval

**RecorAndro Companion v0.2.0 Android RC1** brings the existing Processing Deck
into an Android app. The launcher uses the Deck's existing aubergine mark.
Start the reviewed adapter manually in Termux, pair locally,
choose a recording, follow Processing, and save or share verified part ZIPs.
Reopen an existing session ID and use Resume when the adapter allows it.
Optional photos and the opt-in Full Archive follow the existing Deck behavior.
Termux, Python, FFmpeg and Android System WebView are required. MIUI process
survival remains unverified. This draft describes a proposed owner-sideloaded
candidate.

The owner must approve the candidate name and release certificate, confirm the
signed APK and Redmi results, and record the disposition of each open check.
The active Processing screenshot and independent receiver ZIP SHA-256 remain
**DEFERRED / NOT VERIFIED** on the physical Redmi. An emulator screenshot or
receiver comparison leaves those deferrals open. [Original RC1 deferrals](V0_1_RELEASE_EVIDENCE.md#deferred-checks-for-rc1)

Propose `chore(android): freeze RC1 with the Processing Deck launcher icon` for
the icon and updated evidence. Record the reviewed source commit with the
final-icon signed artifact. After device acceptance and separate tag approval, propose
annotated tag `v0.2.0-android-rc1` on that exact commit. The Termux/browser
`v0.1-rc1` release remains a separate decision. Publication requires its own
approval.
