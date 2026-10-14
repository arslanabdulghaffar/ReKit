# ReKit demo recording workflow

This is an offline preparation guide, not a recorded video or a submission.
The commands below were checked against the existing launcher and browser specs.
The continuation passed both local preflight modes and a separate headless
synthetic replay. It performed no model inference. The headed recording commands
remain instructions; no movie was captured. This guide preserves the NVIDIA and
CPU workflows and requires no new recording tool, UI change or model change.

Use the [narration script](demo-script.md) for the shot sequence and the
[local demo runbook](local-demo.md) for launcher details. This companion covers
capture, evidence checks, editing and release decisions. Its **4:00 target is
provisional**, inherited from the script. The [submission checklist](hackathon-submission-checklist.md)
records general media guidance rechecked on October 15; the actual event form's
limits and submission cutoff/timezone still need confirmation. Event-end dates
are not a submission deadline. The public event and live pages still disagree
on October 18 versus October 17 as the online-build end, without an explicit
submission cutoff/timezone. The general guide still specifies a video within
five minutes and below 300 MB; event-specific form limits remain unverified.

## What the recording can establish

| Track | Label to keep visible | Demonstrated boundary |
| --- | --- | --- |
| Original product views | Local NVIDIA inspection · ABO catalog images · simulated intake | Two original catalog images are associated with one simulated component. One joint local Qwen request produces unverified observations. Operator-role rejection leaves the component unknown and held, with zero identity verifications, reservations or kits. |
| Recovery workflow | Separate synthetic recovery fixture · CPU CP-SAT · no AI in this mode | Three returns, four unique components and explicit verification feed deterministic compatibility and planning. Approval reserves four components; two completion confirmations produce two kit records and lineage. The fixture's 17,500 cents / USD 175 is modeled value, not actual returns recovered, revenue or savings. |
| AMD status | AMD visual qualification pending | The [Mission 06 checkpoint](reports/development-mission-06.md) records three authenticated GETs and two single-image synthetic POST attempts, both HTTP 400. This does not prove an AMD model ran. No successful AMD visual/schema result, ABO request, joint-image qualification, AMD browser run or paired comparison exists in that checkpoint. |

Keep a clear transition between the first two tracks. The ABO views do not supply
parts for the synthetic kits. A repeated upload is another view or a duplicate
of the same physical record, not new stock. Source images do not establish hidden
function or safety. Empty candidates in the no-catalog inspection are enforced
by software, not evidence of recognition accuracy.

Humans retain verification, approval and completion authority; an LLM cannot
perform those decisions. The automated replay uses authorized human-role
credentials to exercise these gates. It does not establish independent human
ground truth, hands-on rebuilding or an operator time-saving measurement.

## Prepare a private capture

1. Record the repository commit and selected mode in private recording notes.
   Choose either a new approved local replay or clearly dated historical stills.
   Do not present screenshots as motion footage or reuse an old run's timings
   for a new run.
2. Use an already approved local recorder with application-window capture. Save
   originals and editing projects in an ignored, access-restricted local folder,
   outside cloud sync; `var/` is ignored but that alone does not restrict readers.
   Recorder selection and a short private audio/capture check remain manual
   preparation tasks. Do not install tools or start recording from this guide
   during an offline-only audit.
3. Close unrelated tabs and disable notification previews. Exclude terminals,
   developer tools, network panels, password managers, `.secrets/`, `.env`,
   temporary manifests and credential setup screens. Do not use desktop-wide
   capture when a private window could appear.
4. Prepare a readable 16:9 canvas and clear microphone audio. The existing browser
   replay uses a 1440 × 1000 desktop viewport and briefly checks mobile layouts;
   it does not natively produce a 16:9 movie. Place its capture on the canvas
   without stretching or cropping out provider labels, warnings or decisions.
5. Start application capture only after automatic sign-in has completed and the
   workbench is visible. A separate login shot may show empty fields only.
   Never include a populated Operator token field, even if it appears masked.
   Do not enable Playwright traces or automatic video: they are intentionally off.

## Preflight and replay, when local execution is authorized

Run from the repository root with its existing `.venv`. Stop only your own ReKit
servers; the launcher refuses occupied loopback ports and does not kill unrelated
processes. These are the existing supported commands, not new infrastructure:

```powershell
Set-Location -LiteralPath A:\hackathon\ReKit
git rev-parse HEAD
.\.venv\Scripts\python.exe evaluation/run_demo.py --mode synthetic-recovery --check
.\.venv\Scripts\python.exe evaluation/run_demo.py --mode product-ai --check --device 1
```

Preflight checks local packages, fixtures, the installed browser and ports
`127.0.0.1:8000` / `127.0.0.1:5173`. Product preflight also verifies existing
model/image hashes and queries CUDA availability and at least 7 GiB free VRAM
on device 1. It loads no model, performs no inference and starts no server or
browser. It installs and downloads nothing. A failed prerequisite is a blocker;
do not change environments or silently switch modes to make the recording work.

For the product track, run one approved replay:

```powershell
.\.venv\Scripts\python.exe evaluation/run_demo.py --mode product-ai --headed --slow-mo-ms 100 --hold-seconds 60 --device 1
```

Capture originals before the AI result, the actual pending state, the returned
observations and source references, the rejection reason, and the held state.
Keep the actual provider `local-transformers`, model and local NVIDIA provenance
visible when explaining the inference. Do not relabel it AMD or replace model
text with better wording. This command makes one local joint image request; it
does not qualify TokenFactory or any other remote provider.

Wait for that command and its cleanup to finish. For the separate recovery track:

```powershell
.\.venv\Scripts\python.exe evaluation/run_demo.py --mode synthetic-recovery --headed --slow-mo-ms 100 --hold-seconds 60
```

Capture the distinct component IDs, explicit human verification and compatibility
denial/correction, cost assumptions, selected recovery actions, approval and
reserved state, each completion confirmation, final kit lineage and audit.
State that the real CPU optimizer is executing against synthetic inputs. Do not
imply the product-image track supplied verified inventory to this plan.

Both commands replay UI actions automatically using fresh temporary state and
ephemeral operator credentials. Allow automation to finish before interacting
with the final screen. The 60-second hold is bounded and occurs after acceptance
assertions; actions taken during that hold are outside those recorded checks.
The launcher then closes its owned processes and removes its state. Ctrl+C in
the launching terminal requests interruption; wait for cleanup and inspect its
receipt. A run failure is not permission for automatic inference retries.

## Check the evidence before editing

The launcher reports a fresh directory under `var/mission02-acceptance/run-*/`
or `run-ai-*/`. Preserve that directory and the unedited capture privately. Do
not open its temporary credential manifest for the camera. After the run:

| File | Required review |
| --- | --- |
| `runner-result.json` | Check actual status, browser exit code, `temporary_state_removed`, `credentials_removed`, and empty cleanup/reporting error lists. A successful browser alone does not prove cleanup. |
| `acceptance-result.json` | Check the actual mode and workflow outcome. Absence of a successful record, or a failure record, is not a pass. |
| `product-inference-results.json` for product mode | Check actual provider/model, ordered input hashes, raw output, status, request count and held state. Use this run's timing if one is narrated. |
| Screenshots and raw motion capture | Review originals → AI → human decision order, readable labels, actual output, absence of secrets and consistency with the receipts. |

The launcher saves screenshots and receipts, **not a movie**; Playwright video
is disabled. A capture-tool file and a fully inspected edit are separate outputs.
If the local run fails, keep its failure evidence and either show that manual
review path or use a clearly dated prior successful run. Never silently replace
failed inference with a different provider or fixture response.

Historical source directories in [the script](demo-script.md) remain usable as
labeled stills. Their 38.568-second inference and 47.187-second provider request
refer to one specific local product run, not a mean, a new recording or AMD
performance. Keep inference time, complete request time and browser duration
separate. Use a visible “Inference wait shortened” caption for time compression,
and retain the uncut source. Do not run extra inference merely to improve an
output or conceal an earlier failure.

## Edit and review the final cut

Use the existing script as a provisional four-minute sequence: problem and
architecture, original product evidence and local unverified inspection, a clear
transition to synthetic recovery, explicit human decisions and inventory lineage,
then limitations and next gates. Keep the closing description aligned with
current evidence:

> Local NVIDIA inspection and deterministic recovery workflows are demonstrated.
> Two single-image submissions to the AMD service returned HTTP 400, so AMD visual
> inference remains unconfirmed. Humans retain verification and approval authority.

The [private pitch deck](pitch-deck.md) is a Mission 05 evidence snapshot. Its
original PPTX and builder are unchanged. Do not narrate a historic slide as a
current successful AMD result. Keep the title qualification prominent: **AMD
deployment planned; visual qualification pending**.

Retain Amazon Berkeley Objects / Amazon.com **CC BY 4.0** attribution, source and
license links, and identify crops or overlays; see the [source notices](real-product-evaluation.md#source-license-and-attribution).
Credit the pinned Qwen model under its [recorded provenance](local-inference.md).
Avoid invented industry statistics, calibrated-confidence claims, customer savings,
recognition accuracy or functional/safety assurances. Independent semantic reviews
remain zero in the accepted evidence; pending forms are not reviewed labels.

Inspect the entire rendered edit, including audio, captions and every transition.
Check that tokens, clipboard contents, usernames, private file paths, notifications
and hidden browser/terminal panels were not exposed. Verify runtime, file size,
format and cover against the actual form once confirmed. Keep a private final
review note linking the source commit, run receipts, capture filenames, edits,
export duration/size/hash and reviewer decision. Do not claim these outputs or
checks exist until they have been produced and inspected.

## Blockers and release decisions

| Gate | Current gap / required action |
| --- | --- |
| AMD working-product evidence | Two HTTP 400 attempts do not qualify vision, schema, joint images or the integrated UI. Resolve the provider failure through the [TokenFactory procedure](tokenfactory.md) before any separately authorized next request; no new remote call belongs to this recording plan. |
| Provider and hardware claims | No deployed weights, processor, GPU or runtime attestation follows from an advertised model ID or error response. Preserve the unknowns. |
| Actual recording | Recorder/capture/audio setup, new motion footage, editing, export and complete visual/privacy review remain unfinished. This workflow does not create a video. |
| Submission cutoff and media requirements | Exact cutoff/timezone, event-specific formats, file-size/runtime limits and authenticated form requirements need confirmation. The four-minute target is provisional. |
| Release assets | Private deck/cover and submission copy need final owner review against the form. Do not change counted submission fields silently. |
| Publication and licensing | Repository remains private; code licensing, third-party notices, public visibility and upload require explicit owner decisions. No automatic MIT license or publication. |
| Judge access | No approved public app URL is established by a loopback demo. Hosting and a fresh-session access check remain separate work; never expose an operator token or development server. |
| Evidence limitations | Independent semantic labels and measured customer outcomes are absent. This blocks accuracy/business-impact claims, not an honestly labeled local software demonstration. |
| Submission receipt | No upload or submission is performed here. Preserve the actual submitted URLs, timestamp and confirmation only after an authorized submission. |

Use the [submission checklist](hackathon-submission-checklist.md) for the release
decision. A review-ready video is a concrete artifact for owner approval; it is
not permission to publish, deploy, change repository visibility or spend credits.
