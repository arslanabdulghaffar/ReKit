# Evaluation and benchmarking boundary

ReKit separates CPU correctness, controlled inference-contract tests, actual
local GPU execution, and real-browser integration. The synthetic recovery runner
still performs no perception inference. GPU procedures below explicitly invoke
the already downloaded local model; none measures AMD performance, representative
product-recognition accuracy, or operator time savings.

**Historical Mission 03 Task 5 local integration qualification passed.** Its
API acceptance, two complete real-AI browser runs, the default browser
regression, and final CPU/frontend checks passed with schema-constrained joint
generation. The four earlier failures and reproduced v4 baseline remain
historical evidence below. Unsupported visual claims still occurred and required
human rejection; these runs do not qualify recognition accuracy or AMD inference.
See the [mission report](../docs/reports/development-mission-03.md) for final
artifacts and the separate commit, push, and CI record.

## Mission 04 real-image evaluation and review

Block B freezes the existing paired output collection into a portable private
review package: twelve listing groups, thirteen cases per variant, thirteen
original images, and twenty-six pending output assessments. Open
`var/mission06-offline/block-b-independent-review/index.html`; the
[Block B report](../docs/reports/winning-quality-block-b.md) records provenance,
exclusions, reproduction commands and limitations. This creates no new inference
or human judgments. `package_product_review.py check --package PATH` verifies
the frozen hashes and separately exported assessments without modifying them.

The independent [canonical synthetic case](../docs/canonical-case.md) is available
through `run_canonical_case.py` (in-process API receipt) and
`run_demo.py --mode canonical-recovery` (actual browser). It does not use the
product review images, outputs or any inference provider.

The existing ABO cache contains 52 catalog images from 48 listing groups, with
original-byte hashes and source/license provenance in
[`fixtures/abo-manifest.json`](fixtures/abo-manifest.json). It includes product
views, composites, a logo and reference charts; it is not a set of 52 verified
product photographs or actual customer returns. All 52 image reviews remain
pending. Baseline and corrected-output queues each contain 13 pending cases and
zero independently reviewed cases. Semantic rates remain null with zero eligible
denominators.

Task 2 executed 13 local GPU requests before and 13 after the catalog-scope fix:
26 requests, 28 image presentations, 13 unique images and 12 listing groups.
Both passes accepted 13/13 responses under their recorded contracts. Responses
with candidates despite no supplied catalog changed from **9/13 to 0/13**.
The corrected decoder and strict parser enforce an empty candidate array in that
mode; catalog-backed requests retain unverified hypotheses. This establishes a
protocol boundary, not better recognition, accurate markings, correct prose,
source attribution, or useful additional-view advice. The holdout split was not
used. [Detailed results and review rules](../docs/real-product-evaluation.md)
retain the actual raw outputs, timings, hashes, and exclusions.

These commands check the existing cache and the pending output-assessment file
without downloading data or invoking a model:

```powershell
.\.venv\Scripts\python.exe evaluation/product_data.py check --manifest evaluation/fixtures/abo-manifest.json --root var/evaluation/abo
.\.venv\Scripts\python.exe evaluation/product_review.py check --result var/evaluation/abo/qwen-after-v2.json --assessments var/evaluation/abo/review-after-v2/case-assessments.json
```

Open `var/evaluation/abo/review-after-v2/index.html` locally for the human-review
queue. Reviewers must supply their own judgments and export a separate assessment;
opening or generating the queue does not complete a review. See the detailed guide
for image-review templates and digest-bound output assessment. An explicitly
requested new evaluation uses the current provider and a new output destination:

```powershell
.\.venv\Scripts\python.exe evaluation/run_product_evaluation.py --output var/evaluation/abo/qwen-current-new.json
```

That command makes 13 actual local GPU requests; it is not part of CPU CI and
must not overwrite the preserved baseline or corrected-run artifacts.

The `openai-remote` provider is implemented and qualified with controlled offline
HTTPS responses. No actual remote inference or AMD execution has been measured.
Remote model/processor revisions are configured declarations; a matching response
model ID does not attest deployed weights, runtime or hardware. Complete the
[AMD activation gate](../deploy/amd/README.md#activation-checklist) before making
an AMD claim. The Mission 03 sections below preserve historical measurements and
failed attempts rather than relabeling them as current real-product results.

## Reproduce the synthetic evaluation

From the repository root in the existing environment:

```powershell
.\.venv\Scripts\python.exe evaluation/run_synthetic.py
.\.venv\Scripts\python.exe -m pytest -q -W error
.\.venv\Scripts\python.exe -m pip check
```

The runner uses [synthetic recovery inputs](../tests/fixtures/synthetic_recovery.json)
and [controlled comparison cases](fixtures/recovery_cases.json). It creates a
temporary SQLite database, exercises real HTTP application routes in process,
uses actual CP-SAT results, validates expected outputs, prints JSON, and removes
the temporary database. Re-running does not reuse or mutate operational inventory.

Expected fixture results (all amounts are scenario estimates in USD cents):

| Case | CP-SAT modeled value | Greedy modeled value | Modeled difference |
| --- | ---: | ---: | ---: |
| Two-kit operator workflow | 17,500 | Not compared | Not compared |
| Scarce components across competing BOMs | 4,000 | 2,800 | 1,200 |
| Uneconomic rebuilds | 400 | 400 | 0 |

The workflow starts with three individually incomplete returns: two bodies in
one return and one adapter in each of the other two. Explicit synthetic operator
verifications permit two rebuilds. Each contributes 10,000 sale estimate minus
750 labor and 500 other costs = 8,750 cents. Approval reserves four physical
components; only the two subsequent confirmations create completed kits.

For the allocation comparison, two bodies and two adapters can make two standard
kits worth 2,000 cents each, or one larger kit needing two bodies and one adapter
worth 2,700 cents. Each donor has a retained asset estimate of 100 cents. Greedy
selects the greatest positive incremental value relative to retaining its donors,
then rejects overlapping actions and respects labor/demand limits. It fills
remaining stock with retain/hold actions. Its larger kit contributes 2,700 cash
estimate plus a 100-cent retained adapter. CP-SAT instead selects the two standard
kits for 4,000 modeled cents. The 1,200-cent difference is specific to this
constructed case and is not evidence of business uplift.

Both algorithms retain all four donors in the uneconomic case, so their 400-cent
modeled values contain zero cash recovery. All greedy allocations pass the same
deterministic feasibility validation; greedy shares candidate generation with
CP-SAT but uses a different allocation strategy. Independent exhaustive subset
oracles in tests verify tiny-case optima. This is a correctness check, not an
independent implementation of every catalog rule or a production-scale benchmark.

## Real local GPU qualification

Use the existing verified checkpoint and optional inference packages; these
commands do not download a model or change PyTorch/CUDA. Check available GPU
memory before selecting the explicit device. From the repository root:

```powershell
.\.venv\Scripts\python.exe evaluation/run_vision_smoke.py --device 1 --repeat 2
.\.venv\Scripts\python.exe evaluation/run_api_inference_acceptance.py --device 1
```

The smoke runner sends actual generated PNG bytes to the local Transformers
adapter twice, checks visual-encoder execution and image hashes, and measures
loading, warm reuse, inference time, tokens, and peak PyTorch GPU memory. It
writes ignored `var/mission03-qualification.json` and its synthetic image. The
API runner uses authenticated in-process ASGI HTTP, real managed assets,
SQLite, the background service, strict parsing, and the actual GPU provider.
It writes ignored `var/mission03-api-acceptance.json` plus the source illustration
and removes its temporary database/image state. It is not a listening-server or
browser test. Both accept an explicit output path for preserving distinct runs.

The checkpoint is `Qwen/Qwen3-VL-2B-Instruct`, immutable revision
`89644892e4d85e24eaac8bacfd4f463576704203`; its ten verified files total
4,266,640,306 bytes. Model provenance, package pins, limits, license declaration,
measured Task 1/3 results, and interpretation limits are documented in
[local inference](../docs/local-inference.md).

The Task 3 API execution passed its software checks but proposed an unsupported
`adapter` revision `A` from a shapes illustration, using `SYNTHETIC` as a claimed
revision marking. Its own uncertainty contradicted that candidate. Raw output
was retained, evidence remained under review, and inventory stayed held. Treat
this as an observed recognition error, not a correct prediction or accuracy
benchmark. A schema cannot determine whether a quoted marking exists or proves
the proposed revision.

## Structured-output recovery qualification

The recovery baseline is an actual browser/GPU run, preserved in
`var/mission02-acceptance/run-ai-znk3_cc4/inference-results.json`. It reproduced
the earlier v4 response from `run-ai-ngy_f2t6` exactly: 839 characters, 257 tokens,
raw UTF-8 SHA-256
`4db4750ba7578322a14f24f4a79e278ee5b2a8dc9091d4da43539bcbdde40f09`.
The same forbidden root `image_indices` caused `invalid_output`, with zero model
events and evidence version 3 unchanged. Actual load/inference/request times were
3.830398 / 25.420950 / 34.283795 seconds; peak allocated/reserved GPU memory was
4,683,341,312 / 4,747,952,128 bytes. This establishes a reproduced failure, not
successful inspection. See [the recorded settings](../docs/local-inference.md#task-5-recovery-continuation).

The selected Approach 1 uses a bounded decoding schema for the full output contract
using LM Format Enforcer `0.11.3`, with the existing model and Transformers runtime.
The primary project documents
[Transformers token filtering](https://github.com/noamgat/lm-format-enforcer#basic-tutorial)
and explicitly separates format enforcement from
[semantic correctness](https://github.com/noamgat/lm-format-enforcer#diagnostics---will-i-always-get-good-results).
ReKit still applies the strict parser/domain rules to untouched generated text.
Both bounded direct-provider cases passed; this is a structure/execution result,
with semantic errors retained, rather than final API/browser acceptance.

Run the bounded direct-provider experiment with a fresh output path:

```powershell
.\.venv\Scripts\python.exe evaluation/run_structured_qualification.py --output var/mission03-recovery/approach1.json
```

This invokes actual local GPU generation for two cases on the same provider:
one joint request with the synthetic body views in fixed **VIEW 2, VIEW 1** order,
then one request with the ambiguous shapes illustration. It is **neither API nor
browser acceptance**. The second request can measure warm model reuse. Inputs
are generated locally with the existing fixture generator; no model, image, or
dataset is downloaded. The runner refuses to overwrite an existing report and
removes its temporary credential/image state afterward.

The report preserves configuration, exact ordered source hashes, raw outputs,
execution metrics, JSON syntax validity, domain validity, and failures. Review
source attribution and unsupported claims separately; `structure_passed` is
only a structural/execution result, not a recognition-accuracy claim. The selected
configuration records prompt `rekit-inspection-v5-constrained`, decoder/schema
provenance, and `rekit-inspection-schema-v1`. It retains the 512-token cap,
120-second generation deadline, and strict downstream validation. Constrained
decoding does not guarantee completion before these bounds or truthful claims.

The actual `approach1.json` report contains one joint two-image request and one
single-image request, both JSON-valid and domain-valid. Prompt text/hash is
identical to the v4 baseline; the implementation added constrained decoding.
The grammar bounds observation/reason/marking/uncertainty text to 160 characters,
view text to 100, identifiers to 128, and records to two observations, one
candidate, one or two uncertainties, and one additional view. The independent
domain parser and revision/marking rule were not weakened.

| Direct-provider case | Raw chars / output tokens | Inference seconds | Peak allocated bytes |
| --- | ---: | ---: | ---: |
| Joint VIEW 2, VIEW 1 | 1,018 / 304 | 36.708006 | 4,683,341,312 |
| Ambiguous single illustration | 733 / 201 | 21.103608 | 4,565,379,072 |

The first load took 3.799643 seconds; the second request reused weights. Each
record confirms the actual input hashes and one visual-encoder forward call.
The label-view source indices were correct, but the reason ended at its
160-character bound and the requested view was already supplied. The ambiguous
response invented `body/A` with marking `A`; its valid structure does not make
that claim supported. Subsequent browser acceptance preserved the claim as
unverified, explicitly rejected it for this known illustration, and required human
verification for eligibility. Full ordered fingerprints, schema hashes and
measurement limits are in [the measured result](../docs/local-inference.md#approach-1-measured-result).

For each approach, retain the implementation/version, exact prompt and schema
hashes, constraints, input order, and execution topology. Separate joint-image
generation from any future per-image calls and deterministic aggregation; never
present two calls as one joint inference. Record any intermediate contract and
translation explicitly, with the original model claims intact. Record raw
length/token count, JSON and domain errors, independently reviewed source/visual
claims, latency boundaries, memory, events, inventory state, and artifact paths.
Preserve failed attempts; unknown output and failed parsing are different outcomes.

Mission 03's recorded API acceptance, **two complete real-AI browser passes**, the
default browser regression, and the documented backend/frontend checks passed
separately from this direct experiment. All results retain the actual
model/prompt/schema configuration; the mission report records screenshot review.

## Final local qualification

| Gate | Observed result / local artifact |
| --- | --- |
| Current authenticated API with actual GPU inference | Passed: `var/mission03-recovery/api-current.json` and final repeat `final-api.json` in the same directory. |
| Two complete AI browser scenarios | Passed: `var/mission02-acceptance/run-ai-52823ogs/` and `run-ai-73rjz6dy/`, about 1.2 minutes each. |
| Default browser regression | Passed: `var/mission02-acceptance/run-ugm19txq/`, 4.5 seconds. |
| Additional actual-AI screenshot QA repeat | Passed: `var/mission02-acceptance/run-ai-2qrs3sdt/`, about 1.3 minutes. |
| Backend | 631 passed in 24.20 seconds; focused inference selection 264 passed in 12.56 seconds. |
| Frontend and synthetic evaluation | 48 passed in 27.85 seconds; TypeScript, build, dependency graph, and synthetic evaluation passed. Recorded in `var/mission03-recovery/final-cpu-validation.json`. |

Each complete AI scenario made two actual requests: the labelled views jointly
in VIEW 2, VIEW 1 order, then one ambiguous illustration. It checked original
asset hashes, source indices, model/decoder/schema provenance, GPU execution,
and the held state before human verification. The ambiguous response contained
unsupported hypotheses and was explicitly rejected; it was not scored as correct
abstention. Human verification cited original uploaded observations and linked
the actual inference run IDs in its reason. Nine managed images still represented
four unique components. CPU planning and human approval/completion then produced
two kits, four consumed components, four audit events, and a synthetic 17,500-cent
modeled value.

The extra QA repeat waited for the visible reserved count before screenshots;
it did not change the model, schema, or production UI. These are narrow synthetic
integration results. See the [mission report](../docs/reports/development-mission-03.md)
for retained failures, measured runs, visual review, and repository/CI status.

## Real-browser acceptance

Default mode exercises the React workbench and FastAPI over loopback HTTP,
using actual SQLite stores and CPU CP-SAT, with inference disabled:

```powershell
.\.venv\Scripts\python.exe evaluation/run_browser_acceptance.py
```

First install the pinned frontend packages with `npm ci` in `frontend`, and use
the existing Python environment. Chrome or Edge must already be installed. The
runner does not download a browser, model, dataset, or container. Stop your own
ReKit development servers first: the runner refuses occupied IPv4 loopback ports
8000 and 5173 and does not attach to or terminate unrelated services.

Each run creates an empty database, server-approved synthetic catalog/policy,
random test credentials, and two distinct PNG views for each of the four fixture
components. Every generated image is labeled as synthetic test evidence, not a
product photograph. Registration, upload, human-review controls, scenario entry,
planning, approval, and completion are exercised through the browser; independent
authenticated HTTP reads check the resulting records. No browser route is mocked
and no successful planner output is supplied by the test.

The acceptance spec covers native file validation, multiple views of one identity,
duplicate reuse, invalid image feedback, authorization, unresolved/incompatible
stock, identity correction, compatible two-kit planning, reservation, explicit
completion, lineage, and audit. Test assertions use the invented fixture's
17,500-cent modeled outcome; they do not force the solver to return it. Software
automation of a human-role review form does not establish an actual physical
assembly, real product identity, functionality, or safety.

The private fixture manifest, database, and image state exist only for the run.
The runner stops its child services and removes that state on exit. Sanitized
results, screenshots taken after sign-in, and service logs remain in a unique
ignored directory under `var/mission02-acceptance/`. Traces, videos, and automatic
failure screenshots are disabled so a sign-in failure cannot capture a token.
Do not commit generated artifacts or copy private fixture manifests into reports.

`browser.log` is redacted UTF-8, and `runner-result.json` records the browser exit
status plus actual credential/state cleanup and reporting failures. Both are
written independently of best-effort console output; legacy Windows encodings
display unsupported characters as escapes. A failed run retains any safe
milestone screenshots already taken. Reporting or cleanup failures make the
runner fail even when the browser test passed.

The spec is `frontend/e2e/recovery.spec.ts`; the fixture lifecycle is
`evaluation/run_browser_acceptance.py`. Vitest runs only component/unit tests
under `frontend/src`. The GitHub Actions workflow runs backend tests and frontend
unit, type, build, and dependency checks on CPU; it does not claim a remote browser
run. Local browser results and actual GitHub job status are reported separately
in the [Mission 02 report](../docs/reports/development-mission-02.md).

### Original product images with simulated held intake

The separate Mission 04 mode passed its first actual browser/API acceptance in
49.8 seconds. Reproduce it with:

```powershell
.\.venv\Scripts\python.exe evaluation/run_browser_acceptance.py --real-inference --real-product-images --device 1
```

It uses the verified original JPEG pair `71rr7OjqWqL` and `812Xgtrv0EL`, supplies
no approved identity catalog to inference, and makes **one** joint GPU request.
The UI registers one simulated batch, return and physical-unit ID, uploads both
originals, and displays actual observations, uncertainty and immutable provenance.
An automated operator-role rejection records a request for readable label/detail
evidence; duplicate additional uploads retain the same component and observations.
The scenario requires the component to remain unverified and held, with no plan,
reservation, completion, or recovered value. It does not supply human truth labels
or judge whether model prose is visually correct.

`frontend/e2e/real-product.spec.ts` is selected only for this explicit mode; the
existing synthetic recovery spec remains separate. Sanitized
`product-inference-results.json` preserves actual output, source records, manifest
hash, API checks, held history and limitations. Desktop/mobile screenshots and
the normal runner cleanup record accompany it under the ignored run directory.
No synthetic replacement images, model download, or browser download are involved.
The accepted run is `var/mission02-acceptance/run-ai-_hto37ic/`: one joint model
request, zero page errors, held/unverified inventory, no plans, 401/403 authority
checks, duplicate evidence reuse, and successful credential/state cleanup. Three
screenshots were inspected. This adds one request to Task 2's 26, for **27 actual
local requests on real catalog imagery**; browser and API are the same request,
not two measurements. Independent human semantic reviews remain zero, and this
pass supplies no recognition-accuracy or AMD-execution result.
See the [demo script](../docs/demo-script.md),
[submission checklist](../docs/hackathon-submission-checklist.md), and
[Mission 04 report](../docs/reports/development-mission-04.md) for presentation
boundaries and the acceptance record.

### Explicit browser and GPU mode

After the default regression, run the integrated local AI workflow explicitly:

```powershell
.\.venv\Scripts\python.exe evaluation/run_browser_acceptance.py --real-inference --device 1
```

The optional `--model-dir` selects a server-owned verified checkpoint directory;
it requires `--real-inference` and never downloads weights. Default mode remains
GPU-free. `--check` verifies disposable fixture setup only; it is not inference
or browser acceptance. Use the same free loopback ports and installed browser
as the default runner, with a single model-owning backend process.

The real-inference scenario makes two actual model requests through the UI.
The first uses two distinct labelled synthetic views of one registered body.
The second uploads a deliberately ambiguous shapes illustration as an additional
view of that same physical component and analyzes it separately. It records
actual observations, hypotheses, uncertainty, additional-view requests, raw text,
input hashes, prompt/model/runtime identity and measured GPU metrics. It also
checks that the second request reuses loaded weights.

Before manual review, authenticated HTTP reads must show held, unverified stock
and no compatible kit eligibility. Unknown output remains unknown; unsupported
hypotheses are rejected through the human review control. The test records
which branch the actual model produced rather than supplying a canned answer.
Explicit synthetic human verification/correction then permits deterministic
planning, atomic four-component reservation, and two separate completion
confirmations. The expected 17,500 cents is a scenario outcome, not measured
profit or an AI-created valuation.

Artifacts remain under ignored `var/mission02-acceptance/run-ai-*` (the directory
name is retained from the original runner). `inference-results.json` preserves
actual runs incrementally, including failure output. `browser-results.json` and
`acceptance-result.json` describe a completed scenario; failures instead retain
`acceptance-failure.json`. `runner-result.json` records process and cleanup
outcomes separately. Post-login screenshots cover evidence, AI inspection,
ambiguity, planning, reservation, and final inventory when those milestones are
reached. Token-bearing fixtures and temporary database/image state are removed.

Running the command is not a pass claim. The first Task 5 real-inference browser
attempt with prompt `rekit-inspection-v1` failed on its two-image response:
candidate and additional-view objects omitted required `image_indices`.
The strict parser recorded `invalid_output`, appended zero model events, and
kept the component held. The preserved artifact is
`var/mission02-acceptance/run-ai-jiwykyk_/inference-results.json`. The default
browser regression passed separately in `run-btavldmf`.

The first bounded repair used `rekit-inspection-v2`, a complete JSON example
and explicit required-key checks, retaining the strict schema and 384-token
budget. Its browser attempt also failed: the model generated exactly 384 tokens,
omitted candidate `image_indices`, and truncated an additional-view reason
before completing the JSON. It produced `invalid_output` and zero applied
events. The preserved artifact is
`var/mission02-acceptance/run-ai-kxmilqsw/inference-results.json`. These are two
distinct observed failures; safe rejection is not successful visual inference.

The second bounded repair used `rekit-inspection-v3`: a shorter example put
`image_indices` first and asked for fewer, shorter records. Its backend
generation budget was 512 tokens, within the pre-existing adapter maximum.
The parser/schema and 120-second generation / 150-second request deadlines are
unchanged. Its attempt generated 188 tokens of complete JSON with source indices,
but paired candidate `body` revision `A` with `revision_marking: null`, violating
the required revision/marking pair. It also copied placeholder phrases such as
`visible support`, `unresolved detail`, and `needed photograph`. The parser
recorded `invalid_output` and zero applied events. The artifact is
`var/mission02-acceptance/run-ai-zpfefrhu/inference-results.json`. Preserve all
three failures and their original settings rather than counting safe rejection
as a completed inference gate.

The third and final prompt repair in the earlier attempt used
`rekit-inspection-v4`: a valid unknown
example plus record-key definitions replaces the populated placeholder answer,
and a final check reiterates source indices and the revision/marking pair after
catalog context. Supported hypotheses remain permitted; no fixture identity or
unknown outcome is forced. The 512-token limit, strict schema and deadlines are
unchanged. Its attempt returned 257 tokens of complete JSON but added a forbidden
top-level `image_indices` field. The parser recorded `invalid_output`, with zero
applied events, and the browser stopped at the first two-image inspection. Its
artifact is `var/mission02-acceptance/run-ai-ngy_f2t6/inference-results.json`.
The intended second ambiguous-image request and integrated recovery steps did
not run in any of these four attempts. The v4 candidate was unqualified and work
stopped at that repair limit. The later recovery continuation above is separately
authorized; it preserves this blocked history and these original configurations.

At that earlier stop, the local suite passed 588 backend tests, 48 frontend tests,
TypeScript validation and production build. Ten actual local inference
requests were executed, including successful standalone/API runs and these four
failed browser inspections. Their purposes and outcomes must stay separate.
Neither the CPU passes nor earlier GPU success establishes the failed integrated
gate, representative recognition reliability, correct abstention, or AMD readiness.

## Executable coverage

| Required behavior | Tests |
| --- | --- |
| Valid reconstruction and final confirmation | `test_api.py`, `test_evaluation.py` |
| Incompatible revision, unknown identity, insufficient stock | `test_api.py`, `test_catalog.py`, `test_recovery.py` |
| Repeated observations and corrected identity | `test_api.py`, `test_evidence_store.py` |
| Uneconomic rebuild and price/labor sensitivity | `test_api.py`, `test_recovery.py`, `test_evaluation.py` |
| Conflicting reservations, stale approvals, cancelled plans | `test_api.py`, `test_inventory.py` |
| Transaction rollback, idempotency, audit and lineage | `test_inventory.py`, `test_evidence_store.py` |
| Exhaustive optimizer oracle and greedy comparison | `test_recovery.py`, `test_evaluation.py` |
| Strict model output, source indices, run provenance, staleness and replay | `test_inference_models.py`, `test_inference_store.py` |
| Provider metadata, lazy imports, authenticated lifecycle, rejection and failure outcomes | `test_local_vision.py`, `test_inference_provider.py`, `test_inference_api.py` |
| Remote HTTPS bounds, credential redaction, strict response/provenance validation; controlled endpoints only | `test_remote_transport.py`, `test_remote_provider.py`, `test_inference_api.py` |
| Original image/source integrity, isolated metadata acquisition, pending human reviews and bound output assessments | `test_product_data.py`, `test_abo_acquisition.py`, `test_product_evaluation.py`, `test_product_review.py` |
| UI polling, stale sessions/components, proposal prefill and explicit human decisions | `frontend/src/inference.test.tsx`, `frontend/src/App.test.tsx` |

The solver timeout test uses a real zero-second limit. Additional non-optimal/error
status branches are explicitly simulated to test reporting behavior; they are not
represented as observed production solver outcomes. Controlled model/provider
and HTTP responses in unit/component tests exercise software failure boundaries;
they are labelled test doubles, not real inference results. The end-to-end
planner is never replaced by a hardcoded plan.

The sections below describe broader evidence collection and AMD/perception
measurement requirements. The bounded ABO collection and execution results above
exist; independent human labels, representative returned-product coverage and
recognition-accuracy evaluation remain incomplete.

## Evidence and ground truth

Use reviewed annotations linked to capture IDs, unique physical-component IDs,
return IDs, source-image hashes, and annotation versions. Preserve crop and
preprocessing lineage, model and prompt versions, and human corrections. Split
training, calibration, and held-out evaluation by physical item and return so
multiple views of an item cannot leak across splits. Record near-duplicate
checks, catalog revisions, collection conditions, and known coverage gaps.

Include ambiguous, missing, duplicate, occluded, damaged, and out-of-catalog
components, plus closely related revisions. Reviewers must be able to label
identity or condition as unknown. Visible inspection does not establish hidden
functional or safety properties; any required physical or electrical checks
need separate evidence and acceptance criteria.

## Planned evaluation areas

| Area | Measures and failure cases |
| --- | --- |
| Localization and OCR | Detection precision/recall, localization overlap, missed components, and exact label/part/revision extraction with unreadable-text cases. |
| Visual matching and VLM reasoning | Candidate ranking, incorrect accepted identities, unsupported claims, conflicting observations, and evidence references. |
| Additional evidence | Abstention and false-accept rates, coverage versus error, usefulness of requested close-ups, and resolution rate after recapture. |
| Physical identity | Duplicate counting, identity merges/splits, multiple views, cross-return transfers, and full provenance reconstruction. |
| Deterministic catalog policy | Approved BOM quantities, revisions, substitutions, compatibility exclusions, unknown-policy handling, and visible-condition requirements. |
| Recovery optimization | Hard-constraint violations, unique component assignment, solver status, feasible alternatives, objective bounds, runtime, and economic sensitivity. |
| Approvals and inventory | Stale approvals, reservation races, double use, transaction rollback, retry/idempotency behavior, cancellation, and audit completeness. |
| Final verification | Approved BOM reconciliation, required evidence and checks, failed verification handling, and atomic inventory/audit updates. |
| AMD inference | Quality, end-to-end and inference-only latency, p50/p95, throughput, timeout/error rates, memory use, and behavior under concurrency. |

Choose denominators, acceptance thresholds, and representative operating
conditions before evaluating a release. Model-written confidence statements and
raw similarity scores are not probabilities. If probabilistic decisions are
introduced, define a separate calibration method, evaluate it on held-out data,
and report reliability and subgroup limitations.

Economic evaluation must expose currency, valuation date, resale assumptions,
labor, testing, replacement, shipping, holding, and disposal costs. Compare
recovery with alternatives such as resale as-is, holding, or disposal using
explicit assumptions. Unknown failure rates must not be fabricated from model
confidence.

## Reproducible run record

Each qualification run should record the repository commit, dataset/annotation version
and split manifest, catalog and policy versions, model identifier and immutable
revision, prompt/template version, preprocessing settings, decoding settings,
and raw outputs with evidence references. Record exact AMD GPU model/count/VRAM,
OS/kernel/driver, ROCm, vLLM, Python, serving package or image digest, precision,
quantization, image sizes/counts, warm-up procedure, concurrency, sample count,
and timing boundaries. Compare local CUDA and AMD results on identical inputs
without presenting local timings as AMD measurements.

Keep raw captures, personal/customer data, credentials, and generated benchmark
artifacts outside Git. Use sanitized, intentionally reviewed fixtures when
tests need repository data. Future reports should separate measured results
from targets and untested assumptions.

See [architecture](../docs/architecture.md), [roadmap](../docs/roadmap.md), and
[AMD deployment planning](../deploy/amd/README.md).
