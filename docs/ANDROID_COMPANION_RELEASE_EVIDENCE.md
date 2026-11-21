# RecorAndro Companion A5 release evidence

**Status · AWAITING_SIGNING.** The proposed candidate is
`v0.2.0-android-rc1`, subject to owner approval. Physical acceptance of an A5
release-signed APK is **DEVICE_ACCEPTANCE_PENDING**. A4's owner-reported Redmi
PASS covers installing and launching the debug app, completing audio
processing, and seeing verified ZIP entries. Device Save As, Share and
interrupted recovery remain open. [A4 device evidence](ANDROID_COMPANION_A4.md)

## Reviewed baseline and package

A5 started on clean `main` at `e79c0b0fe85256ab4e974270ddb4191a030fc051`,
matching local `origin/main` and live GitHub `main`. Live GitHub had no tags or
published releases. The public API check does not cover private release drafts.
The A4 implementation is already in that commit. The A4 evidence update and
A5 preparation are in the working tree. [GitHub releases](https://github.com/LOPIXdev/RecorAndro/releases)

| Item | A5 proposal |
| --- | --- |
| App label and ID | RecorAndro Companion, `dev.lopix.recorandro.companion` |
| Release version | `0.2.0-android-rc1`, version code `4`. Debug variants have a `-debug` suffix. |
| SDK | Minimum API `31` (Android 12), target API `34`, compile API `35` platform revision `2` |
| Toolchain | Eclipse Temurin `17.0.21.1+2`, Gradle `8.9`, Android Gradle Plugin `8.7.3`, Build Tools `34.0.0` |
| Direct dependencies | AndroidX Core `1.15.0` for FileProvider, JUnit `4.13.2` for JVM tests |
| Permissions and components | `INTERNET`. Launcher Activity exported. ZIP FileProvider non-exported, with URI grants scoped to app-private ZIP cache. |
| Signing | Owner-controlled release key off-repository. A2–A4 use the local debug signer. |

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

## A5 verification results

The working-tree preflight produced a **4,935,652-byte unsigned APK** with
SHA-256 `8ecd0275ff0ad19eef2e181d45d3a38154b525243d65d17a0085e62dd62e4c26`.
`aapt2` confirmed the proposed identity and SDKs, a non-debuggable release,
backups disabled, one exported launcher, a non-exported ZIP provider with
grants, and `INTERNET` as the sole requested permission. `zipalign -c 4` and
ZIP CRC passed. The APK has no `lib/` entries or bundled Python/FFmpeg, so it
has no APK-native ABI requirement. Termux supplies the tools for the phone's ABI.
The only `assets/` entries are ART baseline profiles. The 65-entry APK inventory
had no Deck copies, keystores, audio, session data, logs or launch credentials.
The ignored files are local tools and fixtures, build output, local data and
caches. No ignored product files were tracked, and the index had no staged files.

| Check | A5 host result | Physical A5 Redmi |
| --- | --- | --- |
| Assemble, manifest, alignment and payload | PASS for the unsigned release. `apksigner verify` rejected the unsigned file as expected. | Installability **NOT VERIFIED**. Awaiting release signing. |
| Lint and native tests | PASS. Nine JVM tests covered route, port and token validation, repeated Connect, session ID restoration and ZIP length, filename and corruption checks. Lint had zero errors and two warnings for target API 34 and the conservative cache-space check. | **NOT VERIFIED**. |
| Authentication, picker cancellation, repeated Start, and original/ZIP integrity | PASS in seven focused adapter tests. Covered Host/Origin/cookie/CSRF, a truncated upload, busy Stop, canonical Resume, optional archive failure and corrupt ZIP refusal. Python, the tests and Deck source match the freeze. | **NOT VERIFIED** for A5. A4 owner PASS covers installation, launch, processing and visible exports only. |
| Real M4A, Save As, Share and interruption recovery | A4 Android 12 emulator evidence exists. A5 validation is limited to this unsigned release's host checks. | **NOT VERIFIED**. See the owner test sheet. |
| Production signer, signed APK size/digest and signature | **AWAITING_SIGNING**. The owner intends to configure signing locally. The four required variables were unavailable in this session. | **DEVICE_ACCEPTANCE_PENDING**. |

Both the Deck JavaScript and the companion's injected script passed syntax
checks. Local documentation links and `git diff --check` passed. The historical
full Android suite was outside the A5 verification scope.

## Build and local signing

Build the unsigned release from the repository root with the pinned toolchain.
The offline invocation requires those SDKs and Gradle caches to be present.

```powershell
$toolchain = (Resolve-Path android-companion/.toolchain).Path
$env:JAVA_HOME = Join-Path $toolchain 'jdk-17.0.21.1+2'
$env:ANDROID_HOME = Join-Path $toolchain 'sdk'
$env:GRADLE_USER_HOME = Join-Path $toolchain 'gradle-home'
& (Join-Path $toolchain 'gradle-8.9\bin\gradle.bat') --offline --no-daemon -p android-companion :app:assembleRelease :app:lintRelease :app:testReleaseUnitTest
```

Gradle leaves `android-companion/app/build/a5/outputs/apk/release/app-release-unsigned.apk`
unsigned. It is a preflight artifact. Android requires a valid signature to
install it. A debug-signed build is suitable for debug testing. A release-signed
APK is a candidate for owner acceptance. A published GitHub Release is a
separate owner-approved action. [Android signing](https://developer.android.com/studio/publish/app-signing)

The owner creates or selects the release keystore **outside the checkout** and
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

After approval of the proposed version and local signing setup, use the
following in the same PowerShell environment. Use the owner-controlled release
identity for future updates and keep its certificate SHA-256 in the evidence.

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
$candidate = Join-Path $out 'recorandro-companion-v0.2.0-android-rc1.apk'
if (Test-Path -LiteralPath $candidate) { throw 'A signed candidate already exists at this path.' }
& (Join-Path $buildTools 'zipalign.exe') -c 4 $unsigned
if ($LASTEXITCODE -ne 0) { throw 'The unsigned APK failed alignment verification.' }
& (Join-Path $buildTools 'apksigner.bat') sign --min-sdk-version 31 `
    --ks $store.FullName --ks-key-alias $env:RECORANDRO_RELEASE_KEY_ALIAS `
    --ks-pass env:RECORANDRO_RELEASE_STORE_PASSWORD `
    --key-pass env:RECORANDRO_RELEASE_KEY_PASSWORD --out $candidate $unsigned
if ($LASTEXITCODE -ne 0) { throw 'Candidate signing failed.' }
$signature = & (Join-Path $buildTools 'apksigner.bat') verify --min-sdk-version 31 --verbose --print-certs $candidate
if ($LASTEXITCODE -ne 0) { throw 'Candidate signature verification failed.' }
if ($signature -match '805406a272bc9a43047b889f541c8e72b11194969810ddce317eab0b050f73d3') {
    throw 'The candidate uses the A2–A4 debug certificate.'
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

Use the release-signed candidate once available. Record APK SHA-256, signer
fingerprint, version, model, Android/MIUI, WebView, and Termux version/source.
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
into an Android app. Start the reviewed adapter manually in Termux, pair locally,
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

Propose `docs: record limited A4 Redmi acceptance` for the A4 evidence and
`build: prepare Android companion release candidate` for A5 preparation. After
owner approval, build from the reviewed clean commit and record its SHA with
the signed artifact. After device acceptance and separate tag approval, propose
annotated tag `v0.2.0-android-rc1` on that exact commit. The Termux/browser
`v0.1-rc1` release remains a separate decision. Publication requires its own
approval.
