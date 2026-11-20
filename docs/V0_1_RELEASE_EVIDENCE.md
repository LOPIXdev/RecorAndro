# Step 7.1 — v0.1 release evidence

**Decision `RC_READY` under the owner-approved release-candidate scope.** The
owner confirmed the Processing Deck run, Chrome ZIP download and Android Share
on Redmi. The accepted lecture original passed its independent read-only
integrity check. On 2026-11-21, the owner explicitly deferred the two remaining
checks for RC1. Both remain unverified. See [deferred checks](#deferred-checks-for-rc1).

The release close-out started on `main` at
`6bd01b1d6929b833a3bd8764e409fde56044787d`, with the prior evidence update still
uncommitted. That commit includes the Processing Deck redesign. The owner
reported the redesigned UI on the phone without supplying its checkout SHA.

## Current Redmi acceptance

The owner observed these results on the physical Redmi Note 10 Pro in Chrome:

- The Processing Deck opened and Android file selection and import worked.
- A real M4A recording of about 61.5 minutes reached `packaged`. Exports showed
  three verified part ZIPs. The Part 01 manifest showed the expected 25-minute
  nominal segment and 5-second overlap.
- Chrome downloaded a part ZIP and Android Share worked according to the owner.
  Receiver-side ZIP hash equality remains unverified.
- The owner supplied real Android screenshots for New run and completed Exports.
  A clean capture while work is active remains unverified and is deferred for RC1.

An independent read-only check of the previously accepted lecture's managed
original passed. Session `d0c39956c17943299dd17e67bf6d1d68` matched the expected
44,941,318 bytes and SHA-256
`9a3843145f2978defbf6a1afcb2b272abf77cbc520598573861b84682e5294ab`.
See the [historical hash and session reference](PACKAGE_AND_ARCHIVE.md).

## Scope and findings

Audited `60e4a6fd4a6d284fd105c5fb693bdc8e2eef92ed..f24801c239e5cbf16a60c0914602ffda1ff0e1b3`
from a clean `main`, plus the uncommitted fixes and release entry point in this
review. The range covers the Step 5.2 evidence close-out, archive decision,
one-command workflow and Termux browser UI. A scoped Git comparison found no
changes to the original import, storage, media, recovery, visual intake,
manifest or package implementations. Review traced the new callers through
owned staging and preflight, immutable import, recovery, current registry
verification and download under the existing session lock. See the
[processing workflow](PROCESS_AUDIO.md) and [mobile launch guide](MOBILE_UI_PROTOTYPE.md).

Fixed two adapter issues. A missing or inaccessible session lookup now keeps
the current session ID and recovery controls. When a download discovers stale
or damaged evidence, the adapter refreshes status and withdraws the rejected
item from Ready. Invalid part evidence hides Ready and exposes the existing
retry classification. Invalid optional archive evidence leaves verified part
ZIPs available. Focused regressions exercise both cases.

## Recorded Step 7.1 host results

- **24/24 focused tests passed** in 31.363 s with
  `PYTHONPATH=tests python -m unittest test_mobile_ui test_workflow -v`. This
  covered unsafe requests and paths, storage denial, incomplete uploads,
  duplicate Start, immutable import, recovery, stale output rejection and
  photo-inclusive archive order. The photo check was in scope because the new
  entry points changed how optional photos reach the workflow before archiving.
- One separate disposable end-to-end case ran through
  `python -m recorandro.mobile_ui` in Windows Chrome at a mobile viewport. A
  45-second synthetic WAV went through authenticated Select, Processing and
  Ready, followed by an actual Chrome download and idle Stop. The file input
  was supplied by Chrome automation. No Android picker or Share was exercised.
- Session `2b36e4b6583549d0bfe5902524143cf2` reached `packaged` with one verified
  part and archive `explicit_off`. Source and managed original were identical
  at 1,440,078 bytes and SHA-256
  `c3de1a833a6214ef71076f595ae796fd24e91a514ade1bccf6bf019a1923f8ed`.
  The downloaded ZIP matched the managed ZIP at 287,332 bytes and SHA-256
  `fc6981fb9a1c80d4e6941a78e42ac153e16600d0672d72ffea5d55f69533d579`.
  CRC passed. It contained one audio part and the JSON and Markdown manifests.
  Session ID, part number, audio hash and size, and source range 0–45 s matched.
  Visual count was zero, status was `not_present`, and there were no visual
  warnings or errors. The ordinary `storage_estimate_unverified` warning remained.
- Python compilation, JavaScript syntax, document links and `git diff --check`
  passed.

## Historical results and scope

Step 5.1 Redmi acceptance recorded **295/295** tests and **10/10** visual tests.
The accepted 61.5-minute zero-photo lecture was packaged with three verified
parts and a verified archive. A separate 20-second session accepted two real
Xiaomi JPEGs and a photo-inclusive archive. The broader lecture plus 3–10 photos
fixture and earlier manual listening were waived. The full suite and legacy
matrices were skipped in this audit. Screen-off survival, hotspot coexistence,
thermal behavior and long recording performance remain unverified for this UI.
See the [accepted close-out](STEP5_1_REVIEW.md#2026-11-20--step-52--part-2-acceptance-close-out)
and [lecture export evidence](SESSION_EXPORT.md#accepted-android-validation--step-24-final-pass).

## Deferred checks for RC1

| Check | Result | Remaining uncertainty |
| --- | --- | --- |
| Real Redmi screenshot during active Processing | **DEFERRED / NOT VERIFIED** | Device screenshots cover New run and completed Exports. |
| Independent SHA-256 equality at the Android Share receiver | **DEFERRED / NOT VERIFIED** | The owner observed Share working. Byte equality at the receiver remains unverified. |

The deferrals apply to RC1. See the [technical freeze and promotion conditions](V0_1_FREEZE.md).

## Step 7.2 candidate checks

On 2026-11-21, an isolated Windows wheel build and install verified package
version `0.1.0`, imports, the console entry point and all three browser assets.
CLI, `process-audio` and adapter help passed. The installed CLI processed a
disposable two-second WAV to `packaged` with Full Archive OFF. Its one verified
part ZIP was readable, passed CRC and contained the JSON and Markdown manifests.
Release links and `git diff --check` passed. The historical suites were reused
as recorded evidence.
