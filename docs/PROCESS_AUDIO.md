# Step 6.2 — one-command audio workflow

`process-audio` creates one new Lecture session using the existing immutable
import, optional photo intake, recovery/resume and verified status APIs. It adds
no media processing, lock, hashing, ZIP writer or canonical state implementation.

```sh
python -m recorandro --config config.local.json process-audio "/path/lecture.m4a" --provision-seconds 7200
# Optional photos and explicit Full Archive ON:
python -m recorandro --config config.local.json process-audio "/path/lecture.m4a" --provision-seconds 7200 --photo "/path/one.jpg" --photo "/path/two.png" --archive on
```

Exactly one audio positional path is accepted. Repeat `--photo` for 0..N paths;
`--title` and `--course` are optional. `--provision-seconds` is required, 1..604800,
and is a user-supplied conservative duration budget, **not measured duration**.
Import uses the existing storage preflight. Auto normalization/segmentation remain
the recovery defaults. OFF is this entry point's default (`--archive off`), in
line with the [Step 6.1 release recommendation](ANDROID_INTEGRATION_DECISION.md).
It is an explicit import choice, including when local profile settings say ON;
legacy `import-audio --archive profile` behavior is unchanged.

After verified import, an `audio_imported` JSON event is immediately flushed to
stderr with session ID and resume argv. Final JSON goes to stdout. The import
itself has the existing interruption semantics; an incomplete import requires
explicit source reselection, not resume. No new checkpoint file is introduced.

Selected photos are imported **before resume**, after managed audio import.
Failure is reported as optional and audio continues. With no selection, intake
is never called. Resume owns processing through verified `packaged` and creates
an ON archive only after photo selection. This avoids creating a stale archive
and avoids changing archive reservation/provenance between phases. Photo intake
uses the existing session-level model: audio part ZIPs still contain only audio
and manifests, with the document-time visual snapshot. See
[visual semantics](VISUAL_ATTACHMENTS.md) and [package policy](PACKAGE_AND_ARCHIVE.md).

Example output shape (illustrative, abridged; IDs/paths are placeholders):

```json
{
  "ok": true, "session_id": "<id>", "stage": "packaged",
  "part_zips": ["<data_root>/sessions/<id>/generated/package_generation/<attempt>/part_01.zip"],
  "optional_issues": [], "recovery_actions": [],
  "resume_args": ["python", "-m", "recorandro", "--config", "config.local.json", "resume", "<id>"],
  "status": {"current_state": "packaged", "archive_status": {"status": "explicit_off"}}
}
```

The full response includes fresh core status, recovery classification, verified
part ZIP paths and warnings; `ok` means required audio/packages verified, not
that optional visuals/archive succeeded. Optional failures appear separately
with explicit retry argv; an archive is complete only when current core status
says `archived`. Exit 0 means packaged (possibly with optional issues), 1 means
critical failure, 130 means interrupted, and 2 means argument/config error.
On critical failure, inspect `stage`, `error`, `recovery` when available and the
retained session ID. `resume_args` and `recovery_actions` include explicit config;
environment-based runs must preserve the same data-root/tool environment.

Resume an imported session with `python -m recorandro --config config.local.json
resume <id>`. Photo selection is not a queued/persistent workflow: if interrupted
during intake, inspect status before explicitly selecting photos again (nonempty
intake appends). Use `archive-session <id> --decision on` after any later photo
selection to regenerate a current archive. If metadata needs manual attention,
resume may refuse it; do not repeat import to disguise failure.

All calls are synchronous and use existing API locks. There is no background
worker or duplicate invocation. Starting `process-audio` again is a **new import**;
use the emitted ID and resume instead. Concurrent actions on that session remain
subject to core lock rejection; final verification can truthfully report busy or
failure. The adapter does not promise atomicity across independent user commands.

Focused tests cover orchestration failures/ordering and short actual host media;
historical Redmi 295/295 and visuals 10/10 are not rerun. No Android GUI, device
survival, full-lecture benchmark or newly completed waived fixture is claimed.
