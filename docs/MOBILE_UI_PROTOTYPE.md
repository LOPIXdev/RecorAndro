# Step 6.3 — RecorAndro on Android

RecorAndro runs in the phone's browser with a foreground Termux adapter. It uses
the existing processing workflow, session recovery and package verifiers. Redmi
acceptance is **NOT YET VERIFIED**. See the [integration decision](ANDROID_INTEGRATION_DECISION.md)
and [processing workflow](PROCESS_AUDIO.md).

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

In **New run**, tap **Choose audio** and select one existing M4A, MP3, WAV or AAC
recording. Use **Attach** if you want photos. Open **Run settings** to set a
conservative duration budget of 1 to 604800 seconds for storage provisioning,
enter optional title or course, or choose **Include a Full Archive**. Archive is
off by default. Tap **Process recording** to start with Auto media settings.

New run, Processing and Exports are separate views. Termux prints the session ID as
soon as import verifies, and the browser picks it up on its next status check.
Keep this ID. Processing shows actual adapter activity and the last verified stage
available from the core. Exports shows each verified part ZIP with its size,
measured audio duration and source range when available.
A Full Archive appears only when the current archive verifies. Every download
checks current evidence again.

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
- Refresh or reopen the same browser page to see the active job. The browser
  issues no Start request on refresh. Processing can continue while the tab is closed.
  After an adapter restart, use **Session → Open run** with a known session ID.
  Resume is enabled only for core `resumable` / `failed_retryable` classifications. Manual-attention
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

Uploads send the selected browser Files as a raw Blob body. Bounded metadata in
the request describes photo names and lengths so the adapter can stream one
audio file and optional photos into separate owned files. The browser needs no
Termux path and the adapter reads 64 KiB blocks. Limits are 128 MiB for audio,
eight JPEG, PNG, HEIC or HEIF photos up to 16 MiB each, and 192 MiB total.
The adapter accepts one active job and up to 64 distinct Start IDs per launch.
Repeated Start with the same job ID never starts another import. New IDs mean
new imports; deduplication is not global or persistent across launches. Filename
validation rejects separators/control characters, unsafe suffixes and names over
240 UTF-8 bytes. Exclusive private staging lives under
`<data_root>/mobile-staging/<random-id>/<index>/<validated-name>`.
Free space must cover upload plus 256 MiB and is rechecked while receiving; core
preflight then accounts for storage already occupied by staging. This adds a
temporary source copy; it is not a media-processing/hash implementation.

The adapter removes its staging files after the worker exits or an upload fails.
Empty staging directories can remain. Abrupt process death can leave staged
copies on disk. For disposable experiments, stop the adapter and confirm no
sessions are needed before removing the experiment root. If a browser cannot read
a selected photo during transfer, remove it and retry the selection. After
transfer, photo intake failures follow the existing nonblocking workflow.

Download IDs resolve only to part ZIP and current Full Archive registry identities. Each request takes
the existing core session lock, projects current evidence, requires verified
`packaged`/package status and, for an archive, `archived`. It opens via owned no-follow paths, uses the existing
size/SHA verifier and streams from that same handle while holding the lock.
Corrupt/stale/missing evidence is refused even if a file exists. No UI hash,
ZIP-writing, media or canonical-state algorithm is introduced. Authenticated
status snapshots are in memory; opening a session calls the existing verifier.
Worker polling does not acquire the processing session lock or rehash media.

## Redmi acceptance checklist — NOT YET VERIFIED

1. Record Android/MIUI, browser/version, Termux source/version and ordinary UID.
   Launch the reviewed revision with the disposable root. Disconnect external
   networking; choose only local on-device files.
2. Cancel the picker and confirm no import starts. Select a short nonpersonal
   recording. Try an invalid budget, then a valid budget with photos empty and
   archive OFF. Tap **Process recording**. Capture New run, Processing and
   Exports. Keep the secret URL and personal filenames out of captures.
3. Download and Open/Share one ZIP to an available local receiver. Compare its
   SHA-256/CRC with the managed ZIP; check its audio + two manifests and absence
   of photos. Record provider permission denial/unreadable selection if possible;
   record whether processing stopped before any verified exports appeared.
   If no receiving app is available, leave Android Share unverified.
4. Start a second disposable session with local photos and Full Archive ON.
   Confirm the part ZIP still has only audio and two manifests. Confirm the
   verified Full Archive includes the selected originals and visual index.
5. Refresh during processing and confirm the ID stays the same. In a disposable
   attempt, interrupt after the ID is printed, restart Termux, open the new
   private URL and check that ID. Use **Resume** when offered and verify the
   same session reaches Exports. Use a longer disposable recording if the short
   one finishes before you can interrupt it.
6. Check Stop when idle, busy Stop refusal, browser close/reopen, and inability
   to connect through the phone's hotspot/LAN address. Long lecture, screen-off,
   hotspot coexistence and battery/thermal behavior remain deferred.

Host validation commands (from the repository root):

```sh
PYTHONPATH=tests python -m unittest test_mobile_ui -v
python -m compileall -q recorandro tests/test_mobile_ui.py
node --check recorandro/mobile_web/app.js
git diff --check
```

HTTP tests need permission for disposable loopback sockets. The optional client
controller check needs Node (host development only, not a Termux dependency).
The actual-media test needs FFmpeg/ffprobe. No host result proves Android
feasibility; historical Redmi 295/295 and visuals 10/10 remain historical.
