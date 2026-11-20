# Step 6.1 — archive policy and Android GUI decision

2026-11-20. Decision proposal for owner approval; documentation only. No UI or
device experiment implemented or run. Baseline: clean local `main`,
`f91655a217d25cd1e9ee0e7504f35ca8b5de4f70`, containing the Step 5.2 close-out,
committed under the owner's Git identity. A separate owner-approval message is
not present in this chat; the commit is verified, explicit approval is not.

## Archive release choice

Recommend **Lecture automatic Full Archive OFF**, with explicit ON supported.
This is a conservative release choice to avoid extra storage, copying and
verification work, **not a measured battery, thermal or hotspot optimum**.
The accepted lecture archive was 103,143,715 bytes / 18 members ([README](../README.md)).
The compact archive duplicates original/current generated media and documents,
not the part ZIPs; the [storage policy](PACKAGE_AND_ARCHIVE.md) retains its
actual-size preflight and nonblocking failure behavior. The committed
[example measurements](examples/step4.2/validation-example.json) are a short host
fixture, including reuse calls, not Redmi generation benchmarks. No accepted
Redmi battery/hotspot/peak-storage time series is available here.

No Python/config edit is necessary to express the recommendation: current
[config](../recorandro/config.py) accepts `"profile_archives":{"lecture":false}`.
Owner adoption in the selected release/local config makes new Lecture imports
using `--archive profile` resolve OFF. Omitting that setting still resolves
unresolved today; this document does not change the runtime fallback. Explicit
`--archive requested` or `archive-session <id> --decision on` remains available.
Do not migrate existing session choices, remove archives or tune reserve values.
The future GUI starts archive selection OFF for new sessions and labels ON as
optional. Historical OPEN statements remain historical; approval/adoption of
this proposal closes the release-default decision, not the measurement work.

## GUI selection and alternatives

Select a **responsive HTML/CSS/plain-JavaScript interface served only at
127.0.0.1 by a small foreground Python adapter in Termux**. It must actually
select files, run the existing core, display results and deliver verified ZIPs.
This is the owner's conditional loopback exception to the frozen
[behavior](BEHAVIOR_CONTRACT.md) / [media](MEDIA_CONTRACT.md) no-server/web-UI
scope; media algorithms, timeline, verification and recovery remain authoritative.
The comparisons below are engineering estimates, not device-tested costs.

| Option | Verified support / requirements | Cost and decision |
| --- | --- | --- |
| Termux:GUI native widgets | Official plugin has buttons, layouts, dialogs and Python bindings [G]. F-Droid APK plus binding installation; API access may also need Termux:API. No verified turnkey picker/share bridge established here. | Feasible alternative; plugin IPC, binding compatibility and activity lifecycle add maintenance. Not selected. |
| Android shortcut plus supported GUI | Termux:Widget launches scripts, not an application UI [W]. Can launch the selected browser or Termux:GUI. Requires matching-source Widget APK if used. | Optional convenience after feasibility; shortcut alone does not meet v0.1. |
| Loopback browser GUI | Standard file inputs provide selected file objects/bytes [H]; Chrome Android documents download and share [C]. Existing Python and a browser; no mandatory add-on APK. | Selected: three screens, bounded adapter, no build framework. Requires HTTP security and browser/device gates below. |
| Tiny native shell | Native SAF returns content URIs [A]; sharing uses URI grants [S]. Termux bridge needs RUN_COMMAND permission and `allow-external-apps=true` [R], or embedding Python/FFmpeg would add packaging work. | Not cheaper: APK/signing, URI copies, bridge and lifecycle code; not authorized in this step. |

Recorded device: Redmi Note 10 Pro, Android 12 / MIUI 13.0.7.0, F-Droid Termux
0.118.3, Python 3.14.6, FFmpeg/ffprobe 8.1.3, ordinary non-root UID ([baseline](DEVICE_BASELINE.md)).
Installed browser/version, Termux:GUI, Termux:API, Widget and companion packages
are **unknown**, not assumed installed. Owner records `termux-info`, Android App
Info and installed add-ons before any installation. Preserve the existing
F-Droid installation/data; Termux shared-UID plug-ins must use the same signing
source [T]. No reinstall, root, overlay permission, broad storage permission,
`termux-setup-storage` or external command permission is required by the selected
route. Browser/provider permission prompts remain owner-controlled.

## Three honest screens and transport

| Screen | Required functioning behavior |
| --- | --- |
| Select / Setup | One audio file, optional photos with zero selected as normal, title, provisioning duration bound, Auto modes and archive OFF/explicit ON. Select an existing known session to recover. Start requires explicit user action. |
| Processing / Status | Show uploading, named active command or “Resuming verified pipeline”, elapsed time and last verified milestone. Indeterminate activity, no fabricated percentage/ETA. Lock contention is busy, not failure/completion. |
| Ready / Results / Share | Only after fresh core verification of the required `packaged` frontier. Show verified parts and ZIP sizes, separate optional archive outcome, download buttons and Android download/share instructions. Photo errors cannot degrade audio success. |

Interrupted work appears on Status with Resume/Retry or manual-attention action
from the existing [recovery classification](SESSION_RECOVERY.md). No UI state
may assert canonical success. Closing a tab does not mean cancel or success.

Use fixed argument arrays with `shell=False` to invoke the existing
[CLI](../recorandro/cli.py), fixed config/tool locations and validated session IDs.
For new work, run import, inspection, normalization, planning, export, manifests
and packaging through existing commands, then optional archive; never reproduce
media processing. Existing sessions use `resume`/`retry`, preserving recorded modes.
One active job per adapter; core locks remain authoritative across other callers.
Poll the adapter's in-memory worker liveness/last completed command over
authenticated same-origin JSON. [Core status](../recorandro/session_state.py)
takes the same session lock and hashes files: call it between commands/on final
verification, not every second while a worker owns the lock. During opaque
`resume`, show only worker liveness and the last verified snapshot, marked stale.
After adapter restart, reread known canonical sessions; do not infer success or
adopt orphan files. Interrupted import requires file reselection. Repeated Start
requests must reuse an adapter job ID, not create duplicate imports.

## Selection, output delivery and local security

- File selection uses `<input type="file">` with audio suffix hints and a
  separate optional multiple-photo control [H]. Browser/provider handles Android
  content URIs [A]; the adapter receives streamed bytes, never converts a URI or
  `C:\\fakepath` into a Termux path. `accept` is only a hint; core admission stays
  decisive. Owner selects on-device files, tested offline; no cloud provider is
  required or accessed by application code. Original filename/suffix is retained
  as validated metadata; reject path separators, traversal/control characters,
  invalid suffixes and unsafe names instead of silently renaming media types.
- Stream into exclusive private staging with server-generated IDs and validated
  basenames. Enforce declared/actual byte limits, request timeouts and free-space
  checks before/during upload; reserve the additional staging copy separately
  from core import provisioning. No whole-lecture buffering. Incomplete uploads
  never enter a session. Call immutable import only after staging completes;
  photo intake remains optional. Cleanup of adapter-owned staging must be
  explicit and cannot delete core originals/attempts.
- Serve downloads only by opaque session/artifact ID from the current verified
  registry; resolve through owned no-follow file access, recheck size/hash and
  revision under the core lock, retain the verified open handle for delivery.
  No client-supplied path, directory listing or general file endpoint. Use safe
  `Content-Disposition: attachment` names and `application/zip`. Download is an
  additional local copy: show its size/storage cost. Chrome Downloads → Share
  opens Android sharing [C]; the GUI must label this two-step handoff honestly.
  No assumed `navigator.share(files)` or `file://` sharing API. Do not report
  successful delivery to another app merely because download started. Sharing
  outside the phone is solely the owner's explicit recipient choice.
- Bind IPv4 **127.0.0.1 only**, chosen local port; never 0.0.0.0, LAN, hotspot,
  IPv6 wildcard, reverse proxy, remote backend or automatic boot service. Start
  only from a foreground user launch; show a Stop action. Exact Host validation
  including port rejects DNS rebinding; no CORS. A random per-launch secret in
  the initial URL fragment is exchanged via same-origin authenticated POST for
  an HttpOnly SameSite=Strict session cookie; remove the fragment immediately.
  Require exact Origin plus CSRF token/custom header on every mutation, including
  uploads and shutdown; reject missing/null/foreign Origin and form-simple
  mutation requests. Require authentication for status and artifact reads too.
  No tokens in query strings/logs, no arbitrary command/config endpoint.
- Bundle all assets locally; escape filenames/text, enforce a restrictive CSP
  (`default-src 'self'`, no framing, objects or remote connections), `no-store`
  and no-referrer. Bound connections/header/body sizes and allow only enumerated
  routes/methods. Loopback alone is not authentication: other apps can reach it.
  Same-UID compromised Termux programs are outside this boundary. No analytics,
  CDN, uploads to remote services, browser service worker or persistent daemon.

## Component boundaries, lifecycle and Step 6.3 gate

Proposed files only, **not created in Step 6.1**: `recorandro/mobile_ui.py`
(loopback/auth/upload/download handlers), `recorandro/mobile_jobs.py` (fixed CLI
adapter and worker liveness), `recorandro/mobile_web/{index.html,app.js,style.css}`
(screens), `scripts/start_mobile_ui.py` (foreground launch/stop), and focused
`tests/test_mobile_ui.py`. Existing CLI/config/storage/session/recovery/package/
visual implementations own all media and canonical state; no second state machine
or database. No native APK, framework, arbitrary remote API or core rewrite.

Browser foregrounding backgrounds Termux. Android 12 can kill Termux children
[T]; wake locks do not prove survival or bypass MIUI policy. No screen-off,
hotspot, battery or thermal PASS is claimed. User starts/restarts Termux, keeps
its notification/session available and explicitly resumes after interruption.
No automatic OS/battery/security setting changes. Stop refuses new jobs; while
busy it offers waiting for completion rather than claiming safe cancellation.

**Step 6.3 feasibility gate, not an executed test:** owner confirms browser and
add-on inventory, runs a reviewed disposable prototype in a separate source/data
root, and records revision/build/permissions. Use a short real audio file, first
zero photos, then two real JPEGs in a separate disposable session. Offline:
select/cancel/reselect via the actual picker, compare source/staged/managed hashes,
observe real Processing and verified Ready screens, download a verified ZIP and
share it to a local receiver; compare delivered hash/CRC. Capture all three actual
screens. Close/reopen the browser, then interrupt only the disposable worker and
demonstrate truthful interrupted state plus core resume without duplicate import.
Check Host/Origin/token/traversal rejections and a non-loopback/hotspot connection
refusal. Record failures without changing the accepted lecture or deployment.

Picker byte/name preservation, authenticated ZIP download/share on the installed
browser, duplicate-start handling, lock-safe status and restart recovery, bounded
large-file streaming and all HTTP protections remain **unproven gates**. A short
success does not establish full-lecture survival. Historical Redmi **295/295**
and visuals **10/10** remain historical evidence ([close-out](STEP5_1_REVIEW.md));
the waived full-lecture/3–10-photo fixture remains waived. If feasibility requires
substantial bridging or broader scope, stop and ask the owner to choose RC-only
versus one additional bounded GUI task; do not silently ship CLI-only v0.1.

## Official sources checked 2026-11-20

- [G — Termux:GUI features, bindings and installation](https://github.com/termux/termux-gui)
- [W — Termux:Widget launch behavior](https://github.com/termux/termux-widget)
- [T — Termux installation/signing and Android 12 limits](https://github.com/termux/termux-app#installation)
- [R — Termux RUN_COMMAND requirements](https://github.com/termux/termux-app/wiki/RUN_COMMAND-Intent)
- [H — HTML file-upload state](https://html.spec.whatwg.org/multipage/input.html#file-upload-state-(type=file))
- [A — Android document selection and content URIs](https://developer.android.com/training/data-storage/shared/documents-files)
- [S — Android secure file sharing](https://developer.android.com/training/secure-file-sharing/share-file)
- [C — Chrome Android download and sharing](https://support.google.com/chrome/answer/95759?co=GENIE.Platform%3DAndroid&hl=en)
