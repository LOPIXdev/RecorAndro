# Step 6.3A — runnable audio-only browser feasibility prototype

This implements the [selected loopback adapter](ANDROID_INTEGRATION_DECISION.md),
using [Step 6.2 process_audio](PROCESS_AUDIO.md), existing status/recovery and
package verifiers. It is not Android feasibility acceptance or stable UI release.
No photos, recording/capture, native APK, launcher, framework or remote backend.

## Launch on Redmi

Dependencies: existing ordinary F-Droid Termux/Python/FFmpeg/ffprobe installation
and an Android browser with JavaScript/file uploads. No new Python packages or
Termux add-ons. Preserve the accepted deployment and lecture; run this reviewed
source in a separate checkout and use a disposable private data root:

```sh
cd /path/to/reviewed/RecorAndro
RECORANDRO_DATA_ROOT="$HOME/recorandro-ui-feasibility" python -m recorandro.mobile_ui --port 8765
```

Alternatively use `python -m recorandro.mobile_ui --config /path/to/disposable-config.json --port 8765`.
Environment overrides retain existing config precedence. No root or broad shared
storage permission is required by the adapter. Browser/provider prompts belong
to Android; record actual prompts rather than granting extra permissions preemptively.

Termux prints **`http://127.0.0.1:8765/#<random-launch-secret>`**. Copy the entire
actual URL into the browser **on that same phone**, including its fragment.
Do not use the hotspot address, `localhost`, a LAN address or literal placeholder.
Treat this URL as private; exclude it from screenshots. Authentication removes
the fragment from the address bar. Reopening the same URL/tab works during this
launch; a server restart requires its new URL. The cookie is launch-specific.

Select one existing on-device recording (not a new recording made by this UI).
Set a conservative Lecture duration budget in seconds, 1..604800, then Start.
The budget is not measured duration. Auto media modes and explicit Full Archive
OFF come from process_audio; local profile ON does not override this workflow.
No photo controls are exposed, and zero photos is complete.

The three sections show selection, actual worker activity and verified package
results. During import there is no session ID yet. The workflow callback exposes
the real ID immediately after verified import, both on screen and in Termux.
Keep this ID. During opaque resume the message says “Resuming verified pipeline”;
there is no synthetic percentage, ETA or invented per-FFmpeg progress. Finished
results show ZIP names/byte sizes and core milestone/warnings. They are a verified
snapshot; every download independently rechecks current evidence.

Click a ZIP to download a local copy. Use Chrome Downloads → ⋮ → Share (or Open)
and explicitly choose an available local receiver. Sharing is a two-step browser
handoff; no direct Web Share API or successful recipient delivery is assumed.
If there is no receiver, retain the downloaded ZIP and install/select a receiver
only by owner choice. A download can require extra shared-storage free space.

## Stop, cancellation and recovery

- Cancelling the chooser starts nothing. Cancel upload aborts the browser request;
  an incomplete upload never starts import. If the entire upload already arrived,
  cancellation may be too late: inspect status before starting again.
- A denied/unreadable provider, invalid budget, bad suffix, empty/oversized file,
  interrupted upload or staging storage denial is an error, not completion.
  The core still owns media admission and its separate storage preflight.
- Closing the tab does not stop work. Reopen it to see the same in-memory job.
  Open status with a known session ID after adapter restart; Resume is enabled
  only for core `resumable` / `failed_retryable` classifications. Manual-attention
  imports/originals are never silently repaired. Core locks still reject another
  caller working on the same session.
- Stop adapter works only when idle. While busy, wait for completion. Termux
  Ctrl-C is an interruption, not clean cancellation: restart the launch command,
  use the new URL and reopen the retained ID. Do not repeat Start to recover an
  existing import. Force-stopping Termux/background process death and FFmpeg child
  lifetime remain physical-device checks; no survival guarantee is made.

## Bounds and security

Only IPv4 127.0.0.1 is bound. Four concurrent HTTP requests maximum; each has a
15-second socket inactivity timeout and a 180-second total connection deadline.
Headers have the stdlib parser's bounded read limits and a 16 KiB post-parse
application limit. No keep-alive, transfer-encoded uploads or open CORS. Only
enumerated static/auth/state/start/open/resume/download/stop routes exist.
Unknown paths never expose files; session IDs and download capabilities are
32-character lowercase hex identifiers, not paths.

Static assets are public but contain no session/media data. A random 256-bit
per-launch fragment secret authenticates an exact-Origin POST with a custom
header; subsequent requests use an HttpOnly SameSite=Strict cookie. Mutations
also require the random CSRF token and exact Origin. Host must match the literal
127.0.0.1 address and port, preventing alternate-host/DNS-rebinding use. GETs with
a foreign Origin are refused. CSP allows only local assets/connections and no
framing; text is rendered via textContent, not injected HTML. Responses are
no-store/no-referrer/nosniff; access logs and token query strings are absent.
Cookies cannot be Secure on this HTTP-only listener; loopback is not isolation
from other local apps. Credentials remain essential. Same-UID compromise is
outside this boundary.

Uploads use a raw File body, not content-URI/path interpretation or multipart
buffering. Limit: 128 MiB/file, one active job, 64 accepted Start IDs per launch.
Repeated Start with the same job ID never starts another import. New IDs mean
new imports; deduplication is not global or persistent across launches. Filename
validation rejects separators/control characters, unsafe suffixes and names over
240 UTF-8 bytes. Exclusive private staging lives under
`<data_root>/mobile-staging/<job-id>/<validated-name>`, streamed in 64 KiB blocks.
Free space must cover upload plus 256 MiB and is rechecked while receiving; core
preflight then accounts for storage already occupied by staging. This adds a
temporary source copy; it is not a media-processing/hash implementation.

Incomplete upload files are removed only from their newly owned staging folder.
Completed staging files are **retained**, including after workflow failure, so
there is no unsafe automatic cleanup. For disposable experiments the owner may
remove the separately chosen experiment root only after stopping the adapter and
confirming no needed sessions remain. Accepted data is never a cleanup target.

Download IDs resolve only to part-ZIP registry identities. Each request takes
the existing core session lock, projects current evidence, requires verified
`packaged`/package status, opens via owned no-follow paths, uses the existing
size/SHA verifier and streams from that same handle while holding the lock.
Corrupt/stale/missing evidence is refused even if a file exists. No UI hash,
ZIP-writing, media or canonical-state algorithm is introduced. Authenticated
status snapshots are in memory; opening a session calls the existing verifier.
Worker polling does not acquire the processing session lock or rehash media.

## Physical Redmi checklist — NOT run here

1. Record Android/MIUI, browser/version, Termux source/version and ordinary UID.
   Launch the reviewed revision with the disposable root. Disconnect external
   networking; choose only local on-device files.
2. Cancel the picker: no job/session. Select a short nonpersonal recording,
   enter an invalid budget once, then a valid budget and Start. Observe real
   activity, real session ID and verified Ready ZIP. Capture Select, Processing
   and Ready screenshots without secret URL or personal filenames/media.
3. Download and Open/Share one ZIP to an available local receiver. Compare its
   SHA-256/CRC with the managed ZIP; check its audio + two manifests and absence
   of photos. Record provider permission denial/unreadable selection if possible;
   it must not claim Ready. No receiving app: record unavailable, not PASS.
4. In a second disposable attempt exercise upload cancellation or controlled
   processing interruption. Keep the session ID when import completed. Restart
   and reopen/resume that session, checking no duplicate import or false Ready.
   Do not kill or corrupt the accepted lecture/session.
5. Check Stop when idle, busy Stop refusal, browser close/reopen, and inability
   to connect through the phone's hotspot/LAN address. Long lecture, screen-off,
   hotspot coexistence, battery/thermal behavior and photos remain deferred.

Host validation commands (from the repository root):

```sh
PYTHONPATH=tests python -m unittest test_mobile_ui -v
python -m compileall -q recorandro tests/test_mobile_ui.py
git diff --check
```

HTTP tests need permission for disposable loopback sockets. The optional client
controller check needs Node (host development only, not a Termux dependency).
The actual-media test needs FFmpeg/ffprobe. No host result proves Android
feasibility; historical Redmi 295/295 and visuals 10/10 remain historical.
