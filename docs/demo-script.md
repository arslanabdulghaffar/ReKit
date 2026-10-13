# ReKit demo script

Updated October 14, 2026. This is a recording plan with the measured real-product
acceptance below, not a finished presentation video. Use the
[Mission 04 report](reports/development-mission-04.md) for the full run record,
failures and final validation. Keep the two demonstrations visibly separate.

## Reproduce the two tracks

Run from the repository root in the existing environment after stopping your own
ReKit development servers. The runner uses temporary, isolated loopback services
and an installed browser. Never display its private credential manifest or sign-in
token. No model, dataset, browser or container download is part of these commands.

**Real catalog imagery with actual local inference:**

```powershell
.\.venv\Scripts\python.exe evaluation/run_browser_acceptance.py --real-inference --real-product-images
```

This Task 4 mode uses the existing ABO fan-view pair, `71rr7OjqWqL` and
`812Xgtrv0EL`, from listing `B07XGQ9QJF`. It uploads the actual image bytes through
the UI into one **simulated, unverified physical-unit record**. The source is
catalog imagery, not photographs of an actual returned kit. Same-listing views
do not prove that the images show one physical unit. The demonstration creates no
verified fan BOM, recovered kit or realized business value.

The current browser scenario makes **one joint two-image inference request** with
no matching catalog supplied to the model. It records a scripted operator
rejection whose reason requests readable label and connector/detail views. Its
later upload repeats the same originals to check deduplication; that is not a
new capture or fulfillment of the requested evidence. No human truth labels are
created, and the single component remains held.

**Synthetic recovery with deterministic execution:**

```powershell
.\.venv\Scripts\python.exe evaluation/run_browser_acceptance.py
```

This separate fixture has three simulated returns, four unique components and
two completed kits after explicit verification, approval and completion. Its
17,500 cents are **USD 175 of modeled net disposition value**, not sales, savings
or measured customer recovery. The default command performs no AI inference.
The existing optional `--real-inference` mode adds two actual local model requests
using clearly labeled synthetic illustrations; it is not the real-product mode.

## Narration and screen sequence: target 4 minutes 40 seconds

| Time | Show | Say or establish |
| --- | --- | --- |
| 0:00–0:25 | Workbench and a short problem statement | “ReKit helps an operator assess incomplete returns and recover compatible kits. Visual observations are proposals; catalog rules and inventory transactions control recovery.” |
| 0:25–1:15 | Real-product track: upload both ABO views; show the single simulated component, original asset hashes and ordered inputs | “These are real catalog image files in a simulated intake workspace. Their source and bytes are traceable, but they do not establish a real returned unit or an approved kit.” |
| 1:15–2:05 | Actual completed local Qwen run: model revision, source references, observations, uncertainty and any requested views | Read only what this run actually returned. Explain unsupported claims if present. Do not replace output, invent a confidence score, or describe schema validity as recognition accuracy. Show unknown identity and held/ineligible state; no-catalog candidate restrictions do not measure autonomous abstention. |
| 2:05–2:30 | Explicit operator rejection/reason requesting further evidence; retained run history | “This scripted operator action rejects the output as proof of exact identity or revision and keeps the item on hold. No identity verification or compatibility approval follows automatically.” It neither judges every model observation false nor creates an independent dataset label. |
| 2:30–3:35 | Clearly switch to the synthetic fixture: human verification, scenario costs, actual CP-SAT proposal and approval | “This is a separate controlled recovery example. Four unique parts across three returns form two approved BOMs. USD 175 is a scenario estimate.” Show four reserved components and no duplicate allocation. |
| 3:35–4:10 | Explicit completion of both synthetic kits, consumed inventory and audit | “Approval reserves parts atomically. Separate operator confirmations create the two kit records and preserve component lineage.” This confirms workflow behavior, not hidden function or safety. |
| 4:10–4:40 | Architecture and measured limits | “Local inference is measured; AMD execution is still unqualified. The remote adapter has offline tests only. Human-reviewed semantic labels remain zero, so recognition quality is not yet measurable.” |

If generation waits are shortened in editing, label the cut and retain actual run
timings. Show failures honestly; do not substitute a successful historical run
without identifying its date and version. Retain the unedited run artifacts.

Task 2 made 26 actual local GPU requests: 13 before and 13 after a catalog-scope
constraint. No-catalog candidate violations changed from 9/13 to 0/13. That is
protocol enforcement, not a demonstrated recognition gain; free-text claims
still require review. See [real-product evaluation](real-product-evaluation.md).

## Completed real-product acceptance

The first Task 4 real-product browser/API attempt passed in **49.8 seconds** on
Chrome **154.0.8037.98**. It made one actual joint two-image request. The model
returned two appearance observations, zero identity candidates, one uncertainty
and one back-view request. Its prose mentioned `amazon commercial`; this is an
unverified model claim. The uncertainty ends mid-thought at `The 'amazon'`:
schema validity did not guarantee a complete or correct explanation.

The scripted operator rejection preserved the run and kept the component unknown
and held, with zero verifications, plans, reservations or kits. Original-byte
hashes matched; duplicate upload preserved the original assets and evidence;
unauthenticated/viewer inference requests returned 401/403. The run recorded
zero page errors, and owned-service/credential cleanup passed.

The actual local artifacts are under
`var/mission02-acceptance/run-ai-_hto37ic/`:

- `product-inference-results.json`: source records, raw/parsed model output,
  provenance, rejection and final held state.
- `runner-result.json` and `acceptance-result.json`: execution and gate outcomes.
- `desktop-product-inspection.png`, `mobile-product-inspection.png` and
  `product-review-held.png`: the three inspected, credential-free captures.

Mission 04 has **27 real-catalog-image model requests** at this point: the 26
evaluation requests plus this one browser/API request, counted once. Human truth
labels remain zero; recognition quality and the usefulness of this view request
remain unmeasured. Separate synthetic regression results belong in the mission
report and do not change this real-image count.

## Capture and attribution plan

Capture credential-free desktop and mobile views of: the real-image pair and
hashes; the actual model result with source references expanded; the explicit
review action and held state; the separate synthetic plan with four reservations;
and final two-kit inventory/audit. Keep the simulated-data labels visible.
Use the completed real-product captures above. Record final synthetic regression
results separately: the actual-AI synthetic regression passed on its first
attempt in about 1.2 minutes at `var/mission02-acceptance/run-ai-n2j7_p4b/`, and
the default recovery regression passed in 4.4 seconds at
`var/mission02-acceptance/run-qz_ybush/`. Their 13 screenshots were inspected;
all three browser runs passed owned-service/credential cleanup. The
[mission report](reports/development-mission-04.md) records final validation.

The runner stores credential-free files under a fresh
`var/mission02-acceptance/run-*/` or `run-ai-*/` directory:

| Scenario | Evidence files and status |
| --- | --- |
| Real-product imagery, passed | Files listed above in `run-ai-_hto37ic`. |
| Actual-AI synthetic recovery, passed | `run-ai-n2j7_p4b`: two actual illustration requests, recorded results and eight screenshots, including ambiguity/rejection. |
| Default synthetic recovery, passed | `run-qz_ybush`: `acceptance-result.json`, `desktop-evidence.png`, `mobile-evidence.png`, `plan-overview.png`, `reserved-plan.png`, `final-inventory.png`. |

Inspect the actual files before using them. Expand provenance details separately
for recording if the automatic screenshot does not show them. The runner also
saves its result and sanitized logs; a failure is not a successful capture.

Do not record sign-in, authorization headers, private manifests, terminals showing
credentials or unrelated customer evidence. The automated runner's screenshots
are evidence captures; they are not a finished presentation video.

Credit ABO images to Amazon.com under CC BY 4.0, link the source/license and
identify presentation crops or overlays; retain the full
[dataset attribution](real-product-evaluation.md#source-license-and-attribution).
The [official README](https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/README.md)
uses `Amazon Berkeley Objects (c) by Amazon.com`; use that source-faithful credit
with the license link in the recording and retain the builder credits in the
accompanying description.
Credit Qwen/Qwen3-VL-2B-Instruct and its Apache-2.0
[model provenance](local-inference.md). Do not imply endorsement.
Complete the [AMD activation gate](../deploy/amd/README.md#activation-checklist)
before presenting any execution as AMD-powered, then use the
[submission checklist](hackathon-submission-checklist.md).
