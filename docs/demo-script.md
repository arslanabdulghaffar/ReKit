# ReKit recording script

Prepared October 14, 2026 for **NeuralFoundry — Forging Intelligent Systems.**
Target duration: **4:00**. This is a recording plan, not a recorded or uploaded
video. Source captures below are actual successful Mission 05 runs on the polished
UI. Historical measurements remain in the [Mission 04 report](reports/development-mission-04.md).

## Reproduce and record

Run from the repository root in the existing environment. Stop your own ReKit
development servers first. Use one isolated mode at a time:

```powershell
.\.venv\Scripts\python.exe evaluation/run_demo.py --mode product-ai --check --device 1
.\.venv\Scripts\python.exe evaluation/run_demo.py --mode product-ai --headed --slow-mo-ms 100 --hold-seconds 60 --device 1
.\.venv\Scripts\python.exe evaluation/run_demo.py --mode synthetic-recovery --check
.\.venv\Scripts\python.exe evaluation/run_demo.py --mode synthetic-recovery --headed --slow-mo-ms 100 --hold-seconds 60
```

The launcher replays real UI actions with fresh temporary state, ephemeral
credentials and loopback services. It installs and downloads nothing. The final
hold is bounded; automatic cleanup follows. See [local demo instructions](local-demo.md).
Capture only the application window. Exclude sign-in entry, private manifests,
developer tools and terminals containing credentials.

Use a newly recorded actual run for motion footage. The PNGs below are still
images, not video footage. If showing them as stills, label them “Actual local run
· October 14, 2026.” No motion footage has been produced. Recording, editing and
authorized publication remain outstanding.

## Four-minute narration and screen sequence

The narration leaves time for clicks and reading. Keep the real-image and
synthetic demonstrations visibly labeled throughout.

| Time | Exact screen / transition | Narration |
| --- | --- | --- |
| 0:00–0:20 | Title: ReKit — AMD-Powered Visual Recovery Intelligence, alongside “AMD deployment pending qualification.” Show architecture briefly. | “We are NeuralFoundry. ReKit helps a return-recovery operator work out which incomplete products could become complete kits. The difficult work is identifying parts, checking revisions, and preventing the same part from being promised twice.” |
| 0:20–0:50 | Product track: `product-originals-desktop.png`; open Integrity & provenance while recording. | “First, visual inspection. These are two original Amazon Berkeley Objects catalog images, uploaded into one simulated component record. They are not an actual customer return. ReKit preserves their source and byte hashes. Another image is another view, not another item in inventory.” |
| 0:50–1:25 | `product-analysis-in-progress.png` → `product-ai-result-desktop.png`. Record Analyze images and actual completion; label any shortened wait. | “This run used the pinned Qwen3-VL two-billion-parameter model on a local NVIDIA GPU. It took about 38.6 seconds for inference. Each claim refers to the recorded input order. The model repeated an appearance phrase and produced an unfinished uncertainty statement. Valid structured output does not establish that its claims are true.” |
| 1:25–1:50 | Product rejection reason → `product-review-held.png`; show held count. | “There is no approved matching catalog in this inspection. The software therefore permits no catalog identity proposal. We reject the output as proof of exact identity and request a readable label and connector view. This scripted operator action leaves the component unverified and held. It creates no recovered kit or independent accuracy label.” |
| 1:50–2:30 | Explicit transition: “Separate synthetic recovery scenario.” Show `desktop-evidence.png`, manual verification, `compatibility-denied.png` → `compatibility-approved.png`. | “Now we switch to a separate synthetic recovery example. Three returns contain four unique components. A human reviewer records identity, revision, visible condition and supporting evidence. The approved catalog rules reject an incompatible revision. A correction is a new accountable decision; the original history stays available.” |
| 2:30–3:10 | `planning-form-desktop.png` → `plan-overview.png`; selected actions precede approval. | “We enter the scenario’s costs, demand and labor limits. The real CPU CP-SAT optimizer finds two complete kits while allocating each physical part at most once. Estimated net recovery is 175 US dollars in this fixture. That is a modeled scenario value, not customer savings or realized revenue. The operator can inspect selected parts, costs and exclusions before approval.” |
| 3:10–3:40 | `reserved-plan.png` → `completion-open-desktop.png` → `final-inventory.png` → `audit-completed-desktop.png`. | “Approval reserves all four components atomically. Each kit still needs a separate completion confirmation against the reserved parts. After both confirmations, inventory records two kits and four consumed components, with their source returns and audit trail. These visible checks do not establish hidden functionality or safety.” |
| 3:40–4:00 | Architecture / final slide, current versus pending status. | “Local execution works today. The AMD remote adapter is implemented and tested offline; actual AMD execution still needs authorized resources and qualification. Independent semantic reviews are also pending, so recognition accuracy is not measurable yet. Our next gate is an evidence-backed AMD demonstration.” |

Do not fit a 47-second request into the 35-second segment without an edit label
such as “Inference wait shortened; actual request 47.19 s.” This is one measured
request, not an average or guarantee. Keep actual output unchanged and preserve
the unedited recording and run artifacts. If a live request fails, show the
failure/manual-review path or identify a previous actual run by date and version.
Do not silently substitute results.

## Current source shots and evidence

| Track | Actual artifact directory | Outcome |
| --- | --- | --- |
| Original ABO images | `var/mission02-acceptance/run-ai-5p7lbguu/` | Browser/API passed in 49.8 s. One joint GPU request, two original images, one simulated component, zero identity candidates, held=1, reservations=0, kits=0. Six inspected screenshots. |
| Synthetic recovery without inference | `var/mission02-acceptance/run-g563yhm_/` | Passed in 5.4 s. Three returns, four components, eight managed images, four exclusive reservations, two kits, four audit events. Fourteen inspected screenshots. |
| Optional synthetic AI regression | `var/mission02-acceptance/run-ai-kny95rau/` | Passed in about 1.2 min. Two actual GPU requests on synthetic illustrations; unsupported ambiguity hypothesis rejected before fixture-based human verification. Same two-kit result. Seventeen screenshots generated; five inspected in this run. |

The first two tracks supply the script's shots. The optional AI regression is
separate validation, not evidence that the ABO photographs form the synthetic
kits. Automation acting under a human role does not create independent ground
truth. There are 19 selected pending original-image reviews; all 52 cached-image
semantic records and both 13-case model-output queues remain pending.

Product request: Qwen/Qwen3-VL-2B-Instruct revision
`89644892e4d85e24eaac8bacfd4f463576704203`, RTX 4080 SUPER, Torch 2.9.0+cu128,
Transformers 4.57.6, schema v2, one vision-forward call. Inference **38.568 s**;
request **47.187 s**; peak allocated CUDA memory **4,901,876,736 bytes**.
This single observation supplies no AMD measurement or calibrated confidence.
Untouched `product-inference-results.json`, `acceptance-result.json` and
`runner-result.json` retain output, provenance, outcomes and owned cleanup.

## Recording and export checklist

- [ ] Record actual motion footage or clearly label stills; do not imply a video already exists.
- [ ] Use 16:9, readable controls, a visible cursor and clear audio.
- [ ] Keep simulated intake / synthetic recovery labels and AMD qualification status visible.
- [ ] Show original provenance, unverified output, rejection, held state and explicit human decisions.
- [ ] Exclude passwords, bearer values, network panels and unrelated private data from every frame.
- [ ] Label shortened waits and historical recordings with date/version.
- [ ] Inspect the rendered edit from beginning to end, including title, subtitles and attribution.
- [ ] Recheck the actual event form's media limits. General guidance says at most five minutes and below 300 MB.
- [ ] Obtain approval before uploading, hosting, publishing the repository or submitting.

On screen and in the description credit **Amazon Berkeley Objects (c) by
Amazon.com — CC BY 4.0**. Link the [official dataset README](https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/README.md)
and [license](https://creativecommons.org/licenses/by/4.0/); identify screen crops
or added overlays. Retain full [dataset attribution](real-product-evaluation.md#source-license-and-attribution),
including builder credits, in accompanying material. Credit Qwen/Qwen3-VL-2B-Instruct
under Apache-2.0 with its [pinned provenance](local-inference.md). Do not imply endorsement.

Use the editable [architecture SVG](assets/rekit-architecture.svg),
[pitch outline](pitch-deck.md), [submission copy](submission-content.md) and
[official checklist](hackathon-submission-checklist.md). The
[AMD activation gate](../deploy/amd/README.md#activation-checklist) must pass
before any execution is described as actually AMD-powered.
