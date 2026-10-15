# Winning-quality Block D: final evidence and presentation

October 15, 2026, Asia/Seoul. Accepted baseline:
`5c6f437ce1ad6fe0e9a84e9450cac2bcf7ec4568` (Block C).
**Mission 06 remains open. Mission 07 has not started.** This block improves
presentation, reproducible economic evidence and handoff readiness. It adds no
runtime/UI feature, inference schema, model, dependency or operational data.
No AMD call, external contact, download, provisioning, publication, license
change or submission occurred. The original two AMD attempts remain 2/6.

## D1 — Seven-slide presentation

Selected candidate directory:
`var/mission06-submission/block-d-deck-20261015-224720-21fd9f/`.

- [Editable PowerPoint](../../var/mission06-submission/block-d-deck-20261015-224720-21fd9f/ReKit-Block-D-candidate.pptx).
- [Cover candidate](../../var/mission06-submission/block-d-deck-20261015-224720-21fd9f/ReKit-Block-D-cover.png), identical to slide 1's 1920 × 1080 render.
- [Build receipt](../../var/mission06-submission/block-d-deck-20261015-224720-21fd9f/build-result.json) and [visual/source peer QA](../../var/mission06-submission/block-d-deck-20261015-224720-21fd9f/visual-qa-peer-review.json).

| Before / gap in Block C | Block D result | Before → after evidence |
| --- | --- | --- |
| Capability-led opening | A concrete commercial problem: one return lacks a part that another may contain; compare permitted choices using evidence and explicit costs. No market-size or savings claim. | [C1](../../var/mission06-submission/block-c-deck-20261015-192428-1ac2f7/slides/slide-01.png) → [D1](../../var/mission06-submission/block-d-deck-20261015-224720-21fd9f/slides/slide-01.png) |
| Small correction screenshot and close-up | Full-width revision comparison and a larger original synthetic A marking, with versions/history explained alongside. | [C3](../../var/mission06-submission/block-c-deck-20261015-192428-1ac2f7/slides/slide-03.png) → [D3](../../var/mission06-submission/block-d-deck-20261015-224720-21fd9f/slides/slide-03.png) |
| Economic winner required reading small detail | A large sentence states rebuild at USD 0.25/minute and liquidate at USD 2/minute. The editable table retains all original values, noncash retention and fixed-input limits; labor usage is explicit. | [C4](../../var/mission06-submission/block-c-deck-20261015-192428-1ac2f7/slides/slide-04.png) → [D4](../../var/mission06-submission/block-d-deck-20261015-224720-21fd9f/slides/slide-04.png) |
| Narrow slide 5 explanation broke words; kit IDs were small | Full-width kit-detail crop and full-width captions. Actual 409 conflict remains stated; both kit IDs and their four source components are readable. Audit below the crop remains in the embedded original and notes. | [C5](../../var/mission06-submission/block-c-deck-20261015-192428-1ac2f7/slides/slide-05.png) → [D5](../../var/mission06-submission/block-d-deck-20261015-224720-21fd9f/slides/slide-05.png) |
| Small model output and older test count | Enlarged exact NVIDIA response keeps repetition, unfinished uncertainty and redundant back-view request visible. **1,485 backend / 91 frontend at Block C** is explicitly sourced to the accepted checkpoint and its CI. | [C6](../../var/mission06-submission/block-c-deck-20261015-192428-1ac2f7/slides/slide-06.png) → [D6](../../var/mission06-submission/block-d-deck-20261015-224720-21fd9f/slides/slide-06.png) |
| Ending primarily recalled the AMD blocker | The contribution comes first: accountable evidence-to-kit decisions, human verification, deterministic policy, CP-SAT and exclusive reservations. AMD pending and the two failed attempts remain prominent. | [C7](../../var/mission06-submission/block-c-deck-20261015-192428-1ac2f7/slides/slide-07.png) → [D7](../../var/mission06-submission/block-d-deck-20261015-224720-21fd9f/slides/slide-07.png) |

All seven actual 1920 × 1080 renders were inspected at presentation size. Final
slides 1–6 are byte-identical to the first fully inspected D candidate; final
slide 7 was directly reinspected. A factual slide 3 source note was corrected
from Block B to Block C; the closing now says independent review is pending,
distinguishing it from scripted human-role workflow tests. No clipping, overlap
or broken words remains in the reviewed renders. There are 52 native editable
text shapes, two native tables and four embedded original PNGs. Geometry, text
extents, aspect ratios, source hashes and Open XML were checked. Small source
credits remain smaller than headlines; this is not a claim that every text run
is presentation-heading size. The screenshot text remains pixels, not editable
model output.

The source captures remain the accepted Block C canonical browser and actual
prior Block B local NVIDIA run. The full original image bytes are preserved
inside native PowerPoint crops. Synthetic labels, ABO CC BY 4.0 attribution,
Qwen revision/license, model failures and human/business limitations remain.
The new sensitivity frontier is **not** inserted into the deck pending review.

PPTX SHA-256: `a7b203b9297331babe19d6ab5505e198b92246e6390d3ffed41781146f3ba97f`.
Cover SHA-256: `f953110121ebbbd96ee700efb0c8934a725b01289735768e7587c2ebfede5445`.
Original Block C/Mission 05 decks and the Block C cover/movie are unchanged.
The new builder uses installed PowerPoint; the presentation artifact runtime
was unavailable. No installation was required. Both candidates remain local
and ignored; only the selected final directory above is proposed for review.

## D2 — Actual economic sensitivity

The [reproducible study and proposal](../canonical-sensitivity-proposal.md)
uses the frozen synthetic case and existing CP-SAT 9.15.6755. It checks all
integer labor rates **0–200 cents/minute**, holding other inputs fixed.
All **201 solves are OPTIMAL**, with matching best bounds and zero gaps.
The allocation oracle enumerates **210 complete feasible allocations** from
19 actions, including mixed hold, retain, salvage, liquidation and rebuilding.
These form 73 distinct value/labor lines.

| Labor rate, USD/min | Globally optimal pattern in the tested fixture | Modeled value, USD |
| --- | --- | ---: |
| 0.00–1.69 | Two rebuilds; two equally valued physical pairings | 190.00 down to 88.60 |
| 1.70 | Two rebuild pairings and all-return liquidation tie: three physical allocations | 88.00 |
| 1.71–2.00 | All-return liquidation | 87.90 down to 85.00 |

The crossing of two lines alone is insufficient: all competing feasible covers
were checked at all 201 rates. No fractional-cent or out-of-range result is
claimed. The oracle is independent of CP-SAT/allocation validation but shares
the production candidate generator; this limitation is explicit. A separate
agent arithmetic review reconstructs all 19 actions directly from the frozen
fixture using only the Python standard library, also matching all 210 covers
and 201 optima. Neither review establishes human semantic accuracy or real
business inputs. The retained script and result are in the private backend
validation directory referenced below.

The [final-source sensitivity receipt](../../var/mission06-offline/block-d-canonical-sensitivity-20261015-224735/receipt.json)
has SHA-256 `cb565d5cdf87a46aa68bc02f3fe4b34da619c9d45d54c8304c63faf787a4ee3f`.
It retains full problems/plans, source/code hashes, ties, solver statuses/bounds,
and six conditional evidence comparisons. The runner refuses changed frozen
inputs, output replacement and linked/escaped output paths. Its generated
synthetic receipts are **nonsecret and ignored**; it does not promise private
filesystem ACLs. Peer review corrected that wording instead of overstating
Git-ignore protection.

The proposed addition is a compact 1.69 / 1.70 / 1.71 comparison. It requires
owner review before any UI, deck or video expansion. No additional optimizer
or commercial feature was introduced.

## D3/D4 — Review handoff and recording readiness

The [short reviewer sheet and owner checklist](../block-d-reviewer-handoff.md)
specifies original-first review, separate baseline/after tabs, exact three
filenames, private saving, output-page saving limitations and read-only export
validation. A fresh package check verifies 12 listing groups, 13 original-image
cases and 26 unchanged output cases. **All 39 assessments remain pending**;
eligible semantic denominators are zero and no accuracy rate is reported.
All 57 frozen package files match the accepted hashes. No human review,
declaration or export completion was synthesized. The earlier Block C browser
readiness exercise remains the actual save/export usability evidence.

The [final capture/edit specification](../block-d-capture-edit-specification.md)
supplies a 12-shot, provisional four-minute edit, exact captions/narration,
source credits, transitions, privacy checks and OBS/microphone steps. It opens
with the recovery problem, keeps real NVIDIA inspection separate from synthetic
recovery, and shows correction, fixed economic assumptions, reservation conflict,
two kits, source navigation, human authority and limitations. The final AMD
segment is separately replaceable only after actual qualification/integration.

No new video, voice take or inference was generated. The preserved Block C
240.219667-second 1080p MP4 has zero audio tracks and is explicitly a **silent
stills draft**. It is a pacing reference, not a completed narrated demonstration.
All twelve shot renders and decoded sample frames were reviewed in Block C;
that is not full uninterrupted playback. Its historical 76-frontend count must
not be reused as Block C's 91. OBS exists, but capture/microphone/editor setup,
actual takes, editing, full playback and final content approval remain manual
owner work. Existing NVIDIA stills can be used without another inference.

## D5 — Official AMD alternatives and preferred contingency

The [ten-criterion options brief](../amd-contingency-options.md) cites official
AMD, event and vLLM documentation checked October 15. It evaluates:

1. Provider-confirmed repair of existing TokenFactory access: the best fit if
   support resolves eligibility, model ID, image/schema contract and quota.
2. An isolated AMD Developer Cloud MI300X Linux/vLLM deployment: the preferred
   contingency, conditional on actual access and an enforceable approved
   spending boundary.
3. A dedicated Radeon Cloud endpoint funded by an actually issued event coupon:
   no entitlement is verified, and the documented URL shape is incompatible
   with the current exact `/v1` adapter without a reviewed integration change.
4. Specifically offered organizer-managed AMD hardware: no offer exists; Radeon
   or NPU access would require a separate device/runtime feasibility assessment.

Current ADC/ADP documentation advertises $100/30-day credits, while older AMD
pages retain 25-hour/10-day and card language. Actual ReKit access, grant, card
state, capacity and hard cap are unverified. Current ADC terms describe charging
after credit exhaustion and billing powered-off VMs until destruction. A credit
advertisement or manual alarm is not an enforceable no-charge allocation.
No resource may be launched under the present no-spending scope.

The Qwen3-VL ROCm recipe supports an architectural route; its worked example
does not qualify ReKit's exact 2B snapshot, schema or Windows CUDA packages on
ROCm. A later approved plan must pin hardware/runtime/model/processor/decoder,
test exact strict schema support and secure ingress, and collect execution-linked
AMD device/process telemetry plus request/image/model provenance. Branding or
a model-name echo alone does not prove AMD accelerator inference.

No AMD account inspection, authenticated AMD API request, credential read, support contact,
instance, download, paid resource or generation occurred. The original 400
error wording remains unavailable; neither research nor the support referral
resolves it. Fresh quota and explicit owner approval remain required for any
new attempt. No new six-call budget is presumed for a contingency.

## D6 — Decision-aware evidence proposal

The [bounded innovation proposal](../decision-aware-evidence-proposal.md)
explains a concrete opportunity: show which unresolved fact could change the
available choices or preferred modeled allocation. It recommends review of a
fixed-receipt, offline comparison card, with no live state or mutation controls.

Six actual read-only conditional CP-SAT solves compare the saved scripted B,
review-required/held and corrected A states. All are OPTIMAL with matching
bounds and exact-cover checks. At USD 0.25/minute, their modeled totals are
USD 107.75 / 93.50 / 175; the first two include USD 6 noncash retention. At
USD 2/minute, they are USD 85 / 76 / 85. Thus A can change rebuild compatibility
without changing the preferred disposition at higher labor cost. Held still
excludes that component from consuming actions; no economic result waives review.

These are hypothetical planning states with deliberately varied evidence and
eligibility, not predictions, new assertions or the expected value of a photo.
No probabilities, capture-success estimates, risk utility or capture costs are
available. The proposal specifies receipt fingerprints, separate current
availability checks for any later live version, visible assumptions, exact
six-row reproduction, failure/tie handling, zero writes/requests and regression
criteria. Owner approval precedes any implementation or presentation expansion.

## D7 — Validation and preservation

The final local validation results are below. The deck keeps
its explicitly requested historical Block C 1,485/91 row; Block D tests are a
separate checkpoint and are not an accuracy or business-outcome measurement.

| Command / check | Actual result |
| --- | --- |
| `.venv\Scripts\python.exe -B -m pytest -q -W error` | **1,500 passed in 60.27 seconds** on the fresh complete run; initial native failure retained below. |
| `npm.cmd test` in `frontend` | 91 passed in six files, 28.52 seconds. |
| `npm.cmd run typecheck` and `npm.cmd run build` | TypeScript and Vite production build passed. |
| `npm.cmd ls --all --depth=0` | Installed direct dependency graph consistent; no install. |
| `.venv\Scripts\python.exe -m pip check` | No broken requirements. |
| `.venv\Scripts\python.exe -B evaluation/run_demo.py --mode product-ai --check` | Read-only preflight passed: ten pinned model files and two original source images hash-verified; PyTorch 2.9.0 / CUDA 12.8 preserved; no model load, inference or state creation. |
| `.venv\Scripts\python.exe -B evaluation/run_demo.py --mode canonical-recovery` | 1 passed in 6.8 seconds; 24 captures in `run-canonical-742e4_dp`. |
| `.venv\Scripts\python.exe -B evaluation/run_canonical_sensitivity.py --output var/mission06-offline/block-d-canonical-sensitivity-20261015-224735` | 201 sweep and six conditional solves passed, all OPTIMAL with matching bounds and zero gaps. |
| `.venv\Scripts\python.exe -B evaluation/package_product_review.py check --package var/mission06-offline/block-b-independent-review` | Verified; all 39 pending, no eligible semantic assessments. |
| `powershell.exe -NoProfile -File scripts/build_block_d_deck.ps1` | Seven slides and cover generated; all slides visually inspected and original images verified. |

The first full backend run stopped with a native Windows access violation
(`0xC0000005`) in Pydantic action construction while running the sensitivity
zero-time-status test. The trace is preserved; its exact cause remains
unresolved. That test passed alone (1.56 seconds), then a fresh full run passed
all 1,500 tests. No package, environment or production code was changed to
obtain the pass. The only intervening test edit renamed an inaccurate
"private" output-path description to "under ignored root". This is an observed
non-reproduction, not a diagnosed or fixed native defect. Logs, source hashes,
[final validation](../../var/mission06-offline/block-d-validation-20261015-224752-f4e5f3/validation-fresh.json)
and the [independent arithmetic review](../../var/mission06-offline/block-d-validation-20261015-224752-f4e5f3/independent-arithmetic-review.json)
are retained together. Frontend command logs are under
`var/mission06-offline/block-d-frontend-validation-20261015-2248/`.

The fresh canonical replay preserves nine original views across three returns
and four identities, the scripted B → new view → A history, USD 175 baseline,
USD 85 high-labor plan, atomic four-part reservation, rejected 409 competitor,
two kits and four consumed parts. It reports no page errors and no document
overflow at 1440/390/320 pixels. Disposable state and temporary credentials were
removed; cleanup/reporting errors are empty. No inference ran.

Eleven fresh desktop/mobile captures were visually inspected; the
[browser QA receipt](../../var/mission02-acceptance/run-canonical-742e4_dp/browser-visual-review.json)
records exact files and scope. No required display correction was found.
The 320-pixel result is automated layout coverage, not a separate visual review.
The mobile correction's citation row is below the viewport; inventory tables
retain horizontal columns. Three tall full-page captures were viewer-downscaled,
so their fine print is not claimed inspected at native scale. Focused crops and
scrolling remain necessary for recording.

The [preservation receipt](../../var/mission06-offline/block-d-preservation.json)
confirms unchanged hashes for both original AMD receipts, saved catalog and
persistent ledger, with a read-only count of two attempts. It also confirms all
57 frozen review files and original presentation/movie assets. Credential
contents were not inspected. No environment or model artifact was altered.

New Office metadata names NeuralFoundry. Four embedded original images and five
source receipts match recorded hashes. The package has no macros or external
relationships; a selected high-signal secret scan covers its 65 XML/relationship
parts. Source notes intentionally retain private repository/evidence paths for
owner inspection; they do not provide public judge access.

A selected-pattern current-tree scan covered **190 text files**, with no
high-signal private-key/GitHub/AWS/key matches or forbidden release paths. The
[scan receipt](../../var/mission06-offline/block-d-source-scan.json) records its
scope. PowerShell parsing and `git diff --check` pass. These are bounded checks,
not a full-history release audit or a guarantee of vulnerability absence.
Peer review checked all **114 relative links across nine changed Markdown files**,
including five heading targets, and found no blocking source/security/claim
issue. Its receipt is
`var/mission06-offline/block-d-validation-20261015-224752-f4e5f3/final-peer-security.json`.
The AMD brief's new external sources were reviewed as official public documents;
older external links in preserved historical sections were not all re-fetched.
This final report-only paragraph records those completed checks.
No license, repository visibility,
public hosting or submission decision was made. GitHub confirmed private `main`
before commit. Media stays ignored; its selected output directory has restricted
current-user/SYSTEM/Administrators ACLs.

## Remaining owner decisions

| Decision / dependency | Ready for review and required next action |
| --- | --- |
| Presentation | Review the selected D deck/cover and source notes; approve content/title before release. |
| Optional economics / innovation | Review the sensitivity comparison and fixed-receipt evidence card proposals before adding either to UI, deck or video. Neither should displace AMD qualification or recording without a concrete benefit. |
| Independent assessment | Assign a genuine reviewer, privately supply the unchanged package/sheet, receive the three files and validate actual judgments. All 39 remain pending. |
| Final video | Follow the capture/microphone test, record/edit approved evidence, rehearse narration, measure the actual export and perform full playback/privacy review. The silent draft is unfinished media. |
| AMD repair | Await a definitive provider contract/eligibility answer; approve one concrete revised synthetic request with fresh quota before any call. Preserve 2/6 history. |
| AMD contingency | Establish actual access/grant/expiry/capacity and enforceable financial boundary; separately approve a pinned isolated plan, downloads, one bounded request and teardown. Nothing is provisioned. |
| Deadline / form | Obtain the exact online cutoff/timezone and signed-in form constraints. Earlier official on-site agendas state October 18, 16:00 Europe/Rome / 23:00 KST; applicability online remains unconfirmed. No new online cutoff was established in this block; do not use build-end dates as deadlines. See the [checklist](../hackathon-submission-checklist.md). |
| Judge access / release | Review the [isolated CPU viewer proposal](../submission-release-review.md), host/cost/access controls, licensing, third-party notices and exact release/history/media scan. Nothing has been published or deployed. |
| Mission 06 and submission | Actual AMD visual inference plus provenance-linked application integration are still required. Approve final files/URLs and submission only after the applicable gates; retain an actual submission receipt. |

## Files and exact delivery record

New source files: this report; `docs/amd-contingency-options.md`,
`docs/block-d-reviewer-handoff.md`, `docs/block-d-capture-edit-specification.md`,
`docs/canonical-sensitivity-proposal.md`, `docs/decision-aware-evidence-proposal.md`,
`evaluation/run_canonical_sensitivity.py`,
`tests/backend/test_canonical_sensitivity.py`, `scripts/build_block_d_deck.ps1`.

Updated status/index files: `docs/pitch-deck.md`,
`docs/hackathon-submission-checklist.md`,
`docs/reports/development-mission-06.md`. Original deck builders, runtime source,
frontend, dependency files and frozen source evidence remain unchanged.

After validated private commit/push, the exact local/tracking/remote SHA,
private visibility, exact-head GitHub Actions results, clean tree and artifact
hashes are recorded in `var/mission06-offline/block-d-final-verification.json`
and the owner handoff. This separate post-push receipt avoids embedding a
commit's own hash or a future CI claim inside itself. This report alone is not
evidence that a pending CI run succeeded.
