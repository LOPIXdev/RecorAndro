# RecorAndro v0.1 technical freeze

**2026-11-21 · `RC_READY` for owner review.** The proposed candidate tag is
`v0.1-rc1`. The Python package version is `0.1.0`. See the
[release evidence](V0_1_RELEASE_EVIDENCE.md) and [candidate notes](RELEASE_NOTES_V0_1.md).

## Frozen scope

RecorAndro processes an existing M4A, MP3, WAV or AAC recording locally. It uses
an immutable managed original, a storage check, automatic normalization and
segmentation, and verified part ZIPs containing audio and manifests. Optional
session photos stay separate from the audio part ZIPs. A requested Full Archive
includes applicable originals and generated outputs and appears in Exports once
verified. Full Archive defaults to OFF in the browser and `process-audio`.
Choose **Include a Full Archive** in Run settings or pass `--archive on` in the CLI.

The **Processing Deck** is the browser UI served by the foreground Python
adapter in Termux. It uses authenticated loopback on `127.0.0.1`. New run
collects the file and settings, Processing shows actual status and the session
ID, and Exports lists verified downloads. **Session → Open run** opens an
existing ID. **Resume** appears when recovery permits it.

## Quick start on Android

Have Termux, Python 3.10 or newer, `ffmpeg` and `ffprobe` on PATH, and Chrome.
The reviewed source runs from the checkout with Python's standard library.
With Python and FFmpeg already installed, launch from the repository root:

```sh
export RECORANDRO_DATA_ROOT="$HOME/recorandro-data"
python -m recorandro.mobile_ui --port 8765
```

Open the full private `http://127.0.0.1:8765/#…` URL printed by Termux in
Chrome on the same phone. In **New run**, choose a recording such as
`Download/lecture.m4a`. Open **Run settings** and enter a conservative
duration budget in seconds. Tap **Process recording**, then keep the session ID
shown after import. When **Exports** appears, tap **Download** on a verified
part. Open the ZIP from Chrome Downloads or use its menu to **Share** to an
available receiver. Use the new private URL after restarting the adapter.

The CLI can process an existing file at a path readable by Termux, such as a
recording already copied into its home directory:

```sh
python -m recorandro process-audio "$HOME/lecture.m4a" --provision-seconds 7200
```

Read `part_zips` in the JSON result for the verified ZIP paths. Use
`python -m recorandro status SESSION_ID` to inspect a run and
`python -m recorandro resume SESSION_ID` to continue a recoverable run.
Use the same data root for all commands. See the [CLI workflow](PROCESS_AUDIO.md)
and [Android launch details](MOBILE_UI_PROTOTYPE.md#launch-on-redmi).

## Accepted device scope and limits

On Redmi Note 10 Pro with Chrome, the owner confirmed file selection, import,
packaging of a real ~61.5-minute M4A into three verified part ZIPs, Chrome
download and Android Share. New run and Exports have real device screenshots.
The previously accepted managed lecture original matched its expected hash and
size in an independent read-only check. The active Processing screenshot and
receiver-side ZIP SHA-256 comparison are **DEFERRED / NOT VERIFIED** for RC1.

The browser adapter accepts one active job, up to 128 MiB of audio, eight photos
of up to 16 MiB each, and 192 MiB total. Allow free space for staged uploads and
output ZIPs. Device coverage is limited to the documented Redmi run. Screen-off
survival, hotspot coexistence and thermal behavior remain unverified. See the
[release evidence](V0_1_RELEASE_EVIDENCE.md) for scope and limitations.

## Candidate and promotion

After explicit owner approval, create the annotated tag from a clean `main` at
the reviewed freeze commit. Inspect the SHA printed by `git rev-parse HEAD`
before running the tag command.

```sh
git status --short --branch
git rev-parse HEAD
git tag -a v0.1-rc1 HEAD -m "RecorAndro v0.1 RC1"
git show --no-patch v0.1-rc1
```

Promote an owner-approved candidate to `v0.1` after testing its documented launch
and export flow, resolving any release-blocking regressions and recording the
disposition of both RC1 deferrals for the stable scope. Obtain explicit owner
approval for the stable tag and publication.
