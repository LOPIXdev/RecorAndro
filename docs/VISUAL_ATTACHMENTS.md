# Step 5.1 optional session attachments

Candidate based on accepted Step 4.2 `57a7dd46253274b3b7b3bd79bb0b872e65536c52`.
HEAD and origin/main matched; working tree was clean before changes. No commit
or push. Independent review, Redmi acceptance and explicit FINAL PASS pending.

## Intake and preservation

```sh
python -m recorandro import-photos "$session_id" "/path/to/Şubat fotoğraf.jpg" "/path/to/slide.heic"
```

Audio must already be successfully imported. Photo selection is a separate,
optional user action. Each selection is an append-only transaction: open safe
regular files, resolve storage, copy into owned staging, fsync, independently
hash and compare source identity, publish new exclusive originals, publish an
index, then atomically update the existing canonical session. The existing
session lock and publisher are used throughout. There is no second session
system or visual processing milestone.

Protected `photos` entries carry V001, V002, ... IDs, original filename, safe
session-relative path, size, SHA-256, verification time and lightweight metadata.
Managed paths are `originals/photos/<attempt>/V001.jpg` etc. Original names are
data only; Unicode, Turkish letters, long names and repeated source basenames
cannot collide in managed storage. Allowed suffixes are the frozen jpg/jpeg/png/
heic/heif set. Unsupported or unreadable files cancel the selected batch.
Malformed admitted image bytes are retained with unavailable metadata, without
pretending that a decoder validated them. There is no image conversion.

Metadata reading is bounded to the first MiB. JPEG SOF/APP1 and PNG IHDR are
read with the standard library; TIFF EXIF directories have explicit entry bounds.
HEIF storage is supported without claiming complete container metadata support.
No Pillow, OCR, semantic model, network or photo decoder is required.

DateTimeOriginal and OffsetTimeOriginal are preserved as unvalidated camera
strings when available. Missing timezone remains null/unknown. A camera offset
is marked an unvalidated claim. Every entry has timing_role=hint_only. No audio
clock origin, offset, exact timestamp or part association is inferred.

## Index, summary and existing documents

`generated/visuals/<attempt>/visual_index.json` is the regenerable, session-level
summary and index. Schema 1 contains session_id, visual_count, timing_role and
the ordered photo records. The session's visual_index pointer carries its actual
size and SHA-256. Registry readers independently verify originals and index;
an unavailable original is never reported as verified. Missing/corrupt optional
evidence produces visual_status=failed_nonblocking and visual_errors, while audio
progress remains governed by its existing verified records.

Successful intake reports indexed; an unidentified image produces partial_warning.
Missing EXIF alone is normal partial metadata, not an audio warning or failure.
The technical command reports intake errors as failed_nonblocking and explicitly
permits audio-only continuation. No failed intake is committed as a successful
photo selection. Previous accepted photos remain intact on a failed append.

Audio manifests and processing_report.md retain their document-time visual
snapshot, saved in document_visuals at first attachment intake. The current
session-level visual index and technical status provide the live attachment
summary. This deliberately prevents later optional photo selection from changing
accepted audio manifests or part ZIPs. No visual warnings enter the audio
document model. Parts still contain exactly audio + manifest.json + manifest.md.

Calling import-photos with no paths is a no-op when the index verifies. If an
existing index is missing/corrupt, the same command can rebuild it from verified
protected photos without recopying originals. A damaged protected photo requires
manual attention; it is never silently replaced from an external path. Repeating
a nonempty selection appends new IDs, even for the same source photo; there is no
content deduplication. Originals are never overwritten or removed.

## Failure and interruption lifecycle

Preflight denial occurs before staging/photo directories are created. Source
open/hash/copy failure cancels the selected batch. Publication or process death
before canonical update may retain unreferenced owned files, but never adds
unverified photos to the canonical selection. Retrying explicitly creates a new
owned attempt. Orphans are not automatically adopted or deleted. There is no
complex visual recovery state machine. The audio pipeline can continue normally.

The visual budget uses actual selected bytes, index/header allowance, a possible
additional archive copy when the stored archive decision reserves it, and any
remaining initial audio provisioning estimate before completed audio export.
Actual existing verified bytes are credited against pending audio work; already
occupied disk is reflected in measured free bytes. Reserve is max(256 MiB, 20%
of this new budget). Resolved values are stored in visual_storage_preflight;
denials report required/free bytes without mutating the prior session. The old
audio-only preflight record remains historical, not rewritten. Later archive
generation still performs its actual-size second-stage check.

## Archives

Full Archive includes verified managed photo originals and the current visual
index at session level, never inside part ZIPs. New attachments change the
archive input revision and snapshot. A previous archive is therefore no longer
reported as current/archived; status is failed_nonblocking with invalid archive
evidence until regeneration. Its verified bytes remain on disk. Explicit archive
generation or existing ON resume publishes a replacement only after verification.
If storage is insufficient, packages remain successful and the prior archive is
retained. The Lecture Full Archive default remains OPEN.

## Zero-photo compatibility

No visual selection invokes no visual import at all. An explicit empty selection
also creates no photo directory, index, placeholder, warning or metadata rewrite.
The ordinary existing session lock may be created by a first technical session
open; it is not a visual artifact. A zero-photo session needs no migration.

The canonical tree before and after this feature is identical:

```text
session.json
originals/audio/<original>
generated/normalization/<revision>/...
generated/segmentation/<revision>/...
generated/exports/<revision>/...
generated/manifests/<revision>/...
generated/package_generation/<revision>/part_NN.zip
generated/full_archive/<revision>/full_archive.zip   (only when explicitly ON)
```

No originals/photos, generated/visuals or visual_index exists. visual_count=0
and technical visual_status=not_present are normal; no visual warnings/prompts or
degraded package status are introduced. Tests compare every accepted artifact
byte and repeat canonical session bytes at this boundary.

## Redmi validation

Use the reviewed source-transfer ZIP in a fresh Termux directory. Preserve the
accepted deployment and data. Install no image library. Run:

```sh
python -m compileall -q recorandro tests scripts
RECORANDRO_DATA_ROOT="$TMPDIR/recorandro-step5.1-unrelated" python -m unittest discover -s tests -v > android-step5.1-full.txt 2>&1
PYTHONPATH=tests env -u RECORANDRO_DATA_ROOT python -m unittest test_visuals -v > android-step5.1-visuals.txt 2>&1
```

Primary acceptance uses the existing data-root environment or existing --config
file (normal precedence unchanged). Run the accepted zero-photo lecture through
the existing package/archive validator. It verifies prior audio/document hashes
and successful no-op repeats without audio processing:

```sh
python scripts/validate_packages.py --session-id d0c39956c17943299dd17e67bf6d1d68 --expected-parts 3 --expected-original-sha256 9a3843145f2978defbf6a1afcb2b272abf77cbc520598573861b84682e5294ab --archive-on > android-step5.1-zero.json
python -m recorandro status d0c39956c17943299dd17e67bf6d1d68 > android-step5.1-zero-status.json
```

Do not attach photos or inject failures into the accepted lecture. For secondary
acceptance, create a separate disposable session with a short actual audio file,
then use one real camera JPEG, a PNG and optional actual HEIC/HEIF:

```sh
python -m recorandro import-audio /path/to/disposable.wav --provision-seconds 60 --archive not_requested
# Set sid to the newly returned disposable session_id, never the lecture ID.
python -m recorandro resume "$sid"
python -m recorandro import-photos "$sid" /path/to/camera.jpg /path/to/image.png
python -m recorandro status "$sid" > android-step5.1-photos.json
python -m recorandro archive-session "$sid" --decision on
```

Save the index via the status registry's visual_index relative path. Compare
source/managed SHA-256 and size, dimensions/capture tags where available, unknown
timezone handling, unchanged part ZIP hashes, archive member list and snapshot.
Use only disposable test fixtures for malformed EXIF, unavailable source,
storage denial and interrupted publication; the automated suite injects these
conditions without filling disk or killing Termux. Return logs/index/status and
independent findings. No commit/push, Step 5.2, Part 3 implementation or final UI.
