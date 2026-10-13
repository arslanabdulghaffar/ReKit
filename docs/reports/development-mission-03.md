# ReKit Development Mission 03

Report date: 2026-10-13. Repository: `A:\hackathon\ReKit`, private `arslanabdulghaffar/ReKit`, branch `main`.

**Task 5 local acceptance completed.** Mission 03 Tasks 1–4 remain accepted, committed and pushed at last verified HEAD `f6aa873dc6c3e47b36b744da756ecea91a88d28c`. Their exact records are retained in Appendix 1. Task 5's earlier blocked attempt and ten-request measurement history are retained in Appendix 2. The separately authorized recovery continuation below preserves that work and investigates implementation reliability; it does not begin Mission 04.

Current evidence: constrained direct-provider experiment passed both cases; current-version API acceptance and its final repeat passed with explicit rejection of an unsupported claim; three complete constrained browser scenarios and the default regression passed. Final backend/frontend/dependency/synthetic/smoke checks, scoped source scans and actual screenshot QA passed. Task 5 commit/push and remote CI verification follow this local validation record; no unobserved CI success is claimed.

## A. Root cause and repair

The original integration asked unconstrained greedy generation to produce a nested evidence contract. Prompt compliance was insufficient: the actual model omitted mandatory source references, exhausted a 384-token budget before closing JSON, proposed a revision without its marking, and added an unsupported root field. It also produced placeholder-like or weak explanations. These were observed output-contract failures, not CUDA initialization failures or fabricated test responses. Strict parsing correctly rejected them; it did not cause the bad output.

Read-only revalidation reproduced the exact errors against saved raw text:

| Historical attempt | Raw characters / tokens | JSON syntax | Actual strict rejection |
| --- | ---: | --- | --- |
| v1, `run-ai-jiwykyk_` | 1,122 / 324 | Valid | Missing `candidates[0].image_indices` and both additional-view source fields. |
| v2, `run-ai-kxmilqsw` | 1,571 / 384 | Invalid | Incomplete JSON fence and string; actual parser reports `Expecting value: line 1 column 1`. The token cap was reached. |
| v3, `run-ai-zpfefrhu` | 638 / 188 | Valid | Revision `A` paired with null `revision_marking`. |
| v4, `run-ai-ngy_f2t6` | 839 / 257 | Valid | Forbidden root `image_indices`. |

Each ended `invalid_output`, nonstale, with evidence version 3 unchanged and zero applied model events. All artifacts remain under `var/mission02-acceptance/`. The v3 input order was VIEW 1, VIEW 2; v1/v2/v4 used VIEW 2, VIEW 1. This ordering difference remains explicit rather than treating all historical prompt comparisons as identical inputs.

Before repair, actual v4 browser run `run-ai-znk3_cc4` reproduced the last failure byte-for-byte: raw UTF-8 SHA-256 `4db4750ba7578322a14f24f4a79e278ee5b2a8dc9091d4da43539bcbdde40f09`, 839 characters, 257 generated tokens. It used the same ordered image hashes, prompt, model, runtime, token budget and deadlines. Evidence remained version 3 with no applied events.

One distinct recovery implementation approach was selected: LM Format Enforcer token filtering through Transformers' `prefix_allowed_tokens_fn`, followed by the unchanged strict parser and domain models. The current configuration is `rekit-inspection-v5-constrained` with `rekit-inspection-schema-v1`. Its prompt text/hash is exactly the v4 prompt; this repair changed the generation mechanism rather than repeatedly tuning prompt words. The model still processes two submitted images together in one joint request. There is no smaller intermediate contract, hidden per-image aggregation, JSON repair, dropped contradiction, or invented source metadata.

The decoder bounds output to at most two observations, one candidate, one or two uncertainties, and one additional view. Descriptions/reasons/markings/uncertainties are capped at 160 characters, view text at 100, and identifiers at 128. Revision and marking are paired strings or paired nulls. Extra fields are prohibited and valid source indices are bounded by the actual input count. Independent domain checks remain responsible for conditions the decoder does not fully enforce, including unique references and nonblank values. Finite token/time limits can still produce a rejected incomplete result.

Tokenizer vocabulary data is cached with the loaded provider; each request receives fresh parser state. Optional decoder imports remain lazy. Decoder diagnostics are sanitized without disabling application logging. Actual decoder version, schema version/hash, setup time and original input hashes are recorded. Structured generation controls shape, not whether a visual claim is true; the model retains no approval or inventory authority.

Only two optional dependencies were added: `lm-format-enforcer==0.11.3` and `interegular==0.3.3`, totaling 69,053 audited wheel bytes. No existing package, PyTorch/CUDA installation, model weight, global software, cloud resource or frontend dependency was replaced. The primary [LMFE documentation](https://github.com/noamgat/lm-format-enforcer#basic-tutorial) describes the Transformers integration and [its semantic limitation](https://github.com/noamgat/lm-format-enforcer#diagnostics---will-i-always-get-good-results).

One later browser-harness failure is preserved separately from model failure: `run-ai-w8qjj4zp` completed a valid joint two-image inference, then Chrome refused `response.json()` for the additional-view upload because its response body had been evicted from the inspector cache. It raised `Network.getResponseBody: Request content was evicted from inspector cache`; there were no page errors. The repair retained the actual UI POST/201 and visible success assertion, then independently read authenticated persisted assets and selected the unique original-byte hash. Component, return, actor, asset count and physical-identity assertions remain. It did not replace the upload or fabricate its result.

## B. Actual model results

Model and processor: `Qwen/Qwen3-VL-2B-Instruct`, immutable revision `89644892e4d85e24eaac8bacfd4f463576704203`, Apache-2.0 declaration. The same ten verified checkpoint files total 4,266,640,306 bytes; weight SHA-256 is `7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0`. No additional weights were downloaded during recovery.

Actual device: `cuda:1`, one NVIDIA GeForce RTX 4080 SUPER with 16 GB-class memory. Python 3.12.10, PyTorch 2.9.0+cu128, torchvision 0.24.0+cu128, CUDA 12.8, Transformers 4.57.6, Qwen3VLProcessor and Pillow 12.3.0 remain. BF16/SDPA, greedy `do_sample=False`, 512 output tokens, 120-second cooperative generation deadline and 150-second service deadline are unchanged from v4. There is no CPU fallback or multi-GPU pooling.

Input bounds remain one/two static JPEG/PNG/WebP images, 10 MiB each, 16 million original pixels, original side at most 8,192; EXIF transpose, RGB, side bound 768, official processor range 65,536–589,824 pixels and total input cap 8,192 tokens.

Exact provenance:

- Prompt SHA-256: `6d4fb1690f7f50e36fba647e31944d4d67eb8bb4217ecbc704089ad77742a7ec`.
- Two-image schema SHA-256: `906d95c1e45e74cd0f45c759eb9c48dbb748d32de82f2ee483f87cdbb17a6aad`.
- Single-image schema SHA-256: `27facf0396266bc294975d293391c27def44f5a9d8373f0ddfa05d682a74449e`.
- Ordered label input 1, VIEW 2: `46ec41e1283e4d9e51db0039a38a903d859bd056f4177ab34cb2a14dd2295caf`, 9,687 bytes, 720×440.
- Ordered label input 2, VIEW 1: `b5c752dced801379fd69d686df342b190b6036540cf6e8aeea0ff08f4ca71c35`, 9,551 bytes, 720×440.
- Ambiguous single illustration: `cf1a8f595ff3986a947e7160cdb76d7493e9748d2d1f5a03b83d0d23343de38b`, 10,904 bytes, 768×512.

The label PNG hashes were independently reproduced from the unchanged fixture generator in memory. Original browser fixture state is cleaned after each run; saved inference records retain exact hashes and safe screenshots. These are invented label illustrations and a shapes illustration, not independently labelled real product photographs.

Across the mission, **24 real GPU requests** are evidenced: the historical ten plus fourteen recovery requests below. That is **34 image presentations** of the same three distinct synthetic inputs. Six are plain-text smoke requests; 18 are structured requests, thirteen domain-valid and five rejected. The recovery count is one reproduced baseline, two direct-provider cases, two API requests, one request in the browser-harness failure, six requests in three completed browser runs, and two smoke requests. These mix configurations and purposes and are not production success-rate estimates.

| Recovery request | Images | Outcome | Load seconds | Inference seconds | Request seconds | Peak allocated / reserved bytes | Tokens in / out |
| --- | ---: | --- | ---: | ---: | ---: | --- | --- |
| Reproduced v4 browser baseline | 2 | invalid_output | 3.830398 | 25.420950 | 34.283795 | 4683341312 / 4747952128 | 1145 / 257 |
| Approach 1 joint label views | 2 | JSON/domain valid | 3.799643 | 36.708006 | Direct provider | 4683341312 / 4747952128 | 1145 / 304 |
| Approach 1 ambiguous image | 1 | JSON/domain valid, unsupported hypothesis | Reused | 21.103608 | Direct provider | 4565379072 / 4747952128 | 911 / 201 |
| Current API | 1 | succeeded; hypothesis explicitly rejected | 3.855743 | 26.168705 | 34.756142 | 4563994624 / 4601151488 | 911 / 201 |
| Browser before cache-eviction failure | 2 | Inference succeeded; browser failed later | 3.800264 | 36.376392 | 45.007566 | 4683341312 / 4747952128 | 1145 / 304 |
| First completed browser, label views | 2 | succeeded | 3.821943 | 37.009500 | 45.592733 | 4683341312 / 4747952128 | 1145 / 304 |
| First completed browser, ambiguous image | 1 | succeeded; hypothesis explicitly rejected | Reused | 21.236041 | 21.263121 | 4565379072 / 4747952128 | 911 / 201 |
| Second completed browser, label views | 2 | succeeded | 3.805789 | 36.531412 | 45.210336 | 4683341312 / 4747952128 | 1145 / 304 |
| Second completed browser, ambiguous image | 1 | succeeded; hypothesis explicitly rejected | Reused | 21.406357 | 21.432433 | 4565379072 / 4747952128 | 911 / 201 |
| Final smoke 1 | 1 | succeeded, plain text | 3.808645 | 14.258898 | Direct adapter | 4398954496 / 4460642304 | 474 / 100 |
| Final smoke 2 | 1 | succeeded, plain text | Reused | 13.736795 | Direct adapter | 4397340672 / 4469030912 | 474 / 100 |
| Final API repeat | 1 | succeeded; hypothesis explicitly rejected | 3.885666 | 24.647776 | 33.308177 | 4563994624 / 4601151488 | 911 / 201 |
| Additional QA browser, label views | 2 | succeeded | 3.811080 | 35.605637 | 44.167183 | 4683341312 / 4747952128 | 1145 / 304 |
| Additional QA browser, ambiguous image | 1 | succeeded; hypothesis explicitly rejected | Reused | 23.493211 | 23.519842 | 4565379072 / 4747952128 | 911 / 201 |

Each recorded one actual visual-encoder forward call and matching original-byte hashes. Initial decoder setup took 2.465740 seconds in Approach 1; its second request took 0.000983 seconds with cached vocabulary/weights. This setup is included in inference timing, not added afterward. Reused responses retain the initial load measurement but explicitly report `model_loaded_this_request=false`. Memory figures are PyTorch allocator peaks, not total driver/device use or worst-case guarantees.

Approach 1 artifact: `var/mission03-recovery/approach1.json`, status `structure_passed`. Both raw outputs passed the unchanged domain parser. VIEW 2 correctly mapped to image 1 and VIEW 1 to image 2. The `body/A` hypothesis and `REV A` quotation have support only in the invented labels. The 160-character reason ended mid-sentence; uncertainty also ended mid-thought, and the requested VIEW 2 was already supplied. Neither complete JSON nor a source index establishes useful guidance.

The ambiguous image repeatedly produced unsupported `body/A` with marking `A` and an unsupported description of a future top view. Its observed heading/footer and referenced image were correct, but the identity/revision was not established. The API and completed browser retained the raw claim and explicitly rejected it. No recognition-accuracy, calibrated confidence, correct-abstention rate, operator-time saving, commercial uplift, hidden-function or safety claim follows from these examples.

## C. Evidence and workflow

Trusted component IDs, source returns, asset IDs, byte hashes, ordered images, source observation IDs, evidence versions, actors and runtime configuration come from ReKit. Model text describes unverified observations and hypotheses; it does not create physical stock or authoritative metadata. Multiple images remain attached to one existing identity.

Current API artifact `var/mission03-recovery/api-current.json` passed real authenticated ASGI acceptance using managed bytes and the actual model. It stored full decoder/model/source provenance, reused the immutable run on exact replay and preserved the physical component. Valid nonstale model events moved evidence version 2 to 5; actor `real-inference-reviewer` then explicitly rejected the unsupported illustration hypothesis, producing version 6 with `review_required` and no verification. Compatibility remained false; inventory remained held, unreserved and unconsumed, with no completed kit.

The first completed browser artifact, `var/mission02-acceptance/run-ai-52823ogs/`, passed one Chrome 154.0.8037.98 test in 1.2 minutes with no page errors. It made two actual model requests, uploaded the ambiguous additional view onto the same component, and recorded `hypotheses_rejected`. Human `browser-reviewer` verified identity from the original two label observations, with both AI run IDs in the reason; `model_verified_identity=false` and evidence version 13 are recorded.

That browser scenario registered three returns and four physical components, retained nine managed images, rejected unresolved/incompatible rebuilds, and obtained actual CP-SAT OPTIMAL two-kit planning worth a synthetic 17,500 cents. Approval reserved all four identities atomically; explicit confirmations created two kits, consumed four components and recorded four audit events. Repeated completion returned 200; invalid upload 422, missing authentication 401, viewer upload 403, and invalid completions 409 were observed. Runner state/credential cleanup succeeded with empty cleanup/reporting error lists.

The second complete scenario, `run-ai-73rjz6dy`, independently passed in 1.2 minutes with the same two actual requests, explicit rejection, actor-bound original-image verification, 17,500-cent plan, four reserved/consumed components, two kits and four audit events. Both runs report no page errors and successful private-state cleanup. Final API repetition in `var/mission03-recovery/final-api.json` also passed; the unsupported illustration claim remained rejected and held.

Root visually inspected the first run's `desktop-ai-inspection.png`, `mobile-ai-inspection.png`, `ambiguous-ai-inspection.png`, `plan-overview.png`, `reserved-plan.png`, and `final-inventory.png`. The reservation screenshot caught a transient header count of zero before the existing asynchronous refresh completed, while authoritative reservation assertions showed four. The browser test now waits for the approval-success message and Reserved 4 before capturing. Default regression `run-ugm19txq` passed in 4.5 seconds with that wait, and root inspected its stable Reserved 4 capture. Extra AI QA run `run-ai-2qrs3sdt` passed in 1.3 minutes with both real requests, explicit hypothesis rejection, two kits/four consumed/four audit events, no page errors and successful state cleanup. Root inspected its actual stabilized reservation, ambiguous-result and final-inventory captures: Reserved 4 with the success notice, the held/rejected historical AI result, and two completed kits/four consumed identities were visible. Layout was satisfactory without overlap. This was a screenshot-timing safeguard, not an inventory implementation change. Generated images and automated use of a human-role form do not establish actual assembly, functional testing or safety.

The existing safeguards remain: strict extra-field/duplicate-key/truncation/source validation; ownership and original-byte integrity; actor-bound idempotency; version checks; stale/failure outcomes applying no model events; append-only history; distinct unknown versus invalid/failed outcomes; explicit human identity/condition verification; deterministic catalog/BOM/compatibility; CPU optimization; atomic exclusive reservations and consumption. Models cannot write policy/economics, approve, reserve or complete stock. Inference holds no database transaction while computing.

## D. Full verification

Observed recovery evidence and pending final gates must be distinguished. Historical counts in Appendix 2 apply to the earlier stopped attempt, not the final recovery tree.

| Gate | Result |
| --- | --- |
| Saved failure audit and actual v4 reproduction | Complete; exact failure preserved. |
| Controlled direct-provider experiment | Passed both actual cases; semantic limits recorded. |
| Current-version API acceptance | Passed; unsupported body/A explicitly rejected, inventory held. |
| First constrained browser attempt | Failed after valid inference because Chrome upload-response body was evicted; fixed harness and failure preserved. |
| Complete real-AI browser pass 1 | Passed `run-ai-52823ogs`, one test / 1.2m; actual screenshot findings recorded above. |
| Complete real-AI browser pass 2 | Passed `run-ai-73rjz6dy`, one test / 1.2m; independent full workflow and two actual requests. |
| Extra AI screenshot-stability run | Passed `run-ai-2qrs3sdt`, one test / 1.3m, two actual requests and full workflow; actual final captures inspected. |
| Final default non-AI browser regression | Passed `run-ugm19txq`, one test / 4.5s, 17,500 cents / two kits / four consumed / four audit events. |
| Final backend pytest with warnings as errors | 631 passed, 0 failed, 24.20s. |
| Final focused inference/parser/decoder tests | 264 passed, 0 failed, 12.56s: constrained, local vision, models, store, provider, API and browser runner. |
| Final frontend Vitest | 48 passed, 0 failed, 27.85s. |
| Final TypeScript / production build | Passed; 21 modules, build 89ms. |
| Final pip check / npm dependency graph | Passed; normalized installed-package comparison changed no existing versions, adding only LMFE/interegular. |
| Final synthetic recovery evaluation | Passed; actual two-kit workflow, four consumed, four audit events, 17,500 scenario cents. |
| Final actual GPU smoke | Passed two requests, `var/mission03-recovery/final-smoke.json`; actual image execution and warm reuse. |
| Final whitespace / scoped secrets and ignored-artifact checks | Whitespace passed; scoped secret scan of 114 files found zero matches. Ignore checks confirmed weights, local run artifacts and credentials remain excluded; staging is reviewed separately before commit. |
| Actual screenshot QA | Root inspected six first-pass screenshots and the stabilized third-run reservation/ambiguity/final-inventory captures; satisfactory readability/state and no overlap. Transient header timing was addressed by the test wait. |
| Task 5 GitHub Actions | Pending the validated Task 5 commit and normal push. |

The source tree includes focused decoder, domain, API and provider tests; controlled doubles are software evidence, not model outputs. The counts above are measured local results. CPU GitHub Actions remains free of model downloads and GPU/browser requirements.

Commands used for local validation follow; actual results are listed above. Use fresh output paths so historical artifacts are not overwritten.

```powershell
.\.venv\Scripts\python.exe evaluation/run_structured_qualification.py --output var/mission03-recovery/approach1.json
.\.venv\Scripts\python.exe evaluation/run_api_inference_acceptance.py --device 1 --output var/mission03-recovery/api-current.json
.\.venv\Scripts\python.exe evaluation/run_api_inference_acceptance.py --device 1 --output var/mission03-recovery/final-api.json
.\.venv\Scripts\python.exe evaluation/run_browser_acceptance.py --real-inference --device 1
.\.venv\Scripts\python.exe evaluation/run_browser_acceptance.py
.\.venv\Scripts\python.exe -m pytest -q -W error
.\.venv\Scripts\python.exe -m pytest -q -W error tests/backend/test_constrained.py tests/backend/test_local_vision.py tests/backend/test_inference_models.py tests/backend/test_inference_store.py tests/backend/test_inference_provider.py tests/backend/test_inference_api.py tests/backend/test_browser_runner.py
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe evaluation/run_synthetic.py
.\.venv\Scripts\python.exe evaluation/run_vision_smoke.py --device 1 --repeat 2 --output var/mission03-recovery/final-smoke.json
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend ls --all
git diff --check
git diff --cached --check
git status --short
git rev-parse HEAD
git rev-parse origin/main
git ls-remote origin refs/heads/main
```

## E. Repository status

At the pre-commit review, branch is `main`; local HEAD, origin/main and independently queried remote main match `f6aa873dc6c3e47b36b744da756ecea91a88d28c`. Accepted Tasks 1–4 remain intact. The 13 starting working-tree files were backed up before this continuation; all backup SHA-256 hashes still match. The validated Task 5 commit, normal push and actual remote CI results will be recorded after those operations complete.

The reviewed Task 5 change set contains exactly **22 paths: 18 modified and four new**. No new source directory was required:

| Status | Path |
| --- | --- |
| Modified | `README.md` |
| Modified | `backend/src/rekit/inference/adapters/local_transformers.py` |
| Modified | `backend/src/rekit/inference/provider.py` |
| Modified | `backend/src/rekit/inference/service.py` |
| Modified | `deploy/amd/README.md` |
| Modified | `docs/architecture.md` |
| Modified | `docs/local-inference.md` |
| Modified | `docs/roadmap.md` |
| Modified | `evaluation/README.md` |
| Modified | `evaluation/run_api_inference_acceptance.py` |
| Modified | `evaluation/run_browser_acceptance.py` |
| Modified | `frontend/e2e/recovery.spec.ts` |
| Modified | `frontend/playwright.config.ts` |
| Modified | `requirements-inference.txt` |
| Modified | `tests/backend/test_browser_runner.py` |
| Modified | `tests/backend/test_inference_api.py` |
| Modified | `tests/backend/test_inference_provider.py` |
| Modified | `tests/backend/test_local_vision.py` |
| New | `backend/src/rekit/inference/constrained.py` |
| New | `docs/reports/development-mission-03.md` |
| New | `evaluation/run_structured_qualification.py` |
| New | `tests/backend/test_constrained.py` |

Only the reviewed Task 5 changes and this report are selected for the validated increment. Weights, local inputs, credentials, databases, logs and generated reports remain outside Git. Preserve private visibility and normal history; no force push or reset is authorized. Historical verified CI links remain in Appendix 1 and must not be presented as CI for the current dirty tree.

## F. Remaining limitations

Structured output is now validated in the measured cases, but visual truth remains unreliable. The ambiguous fixture still elicits unsupported identity/revision claims; explanation length limits can end prose mid-thought; additional-view suggestions may repeat supplied views or assert unsupported content. No representative recognition, revision-reading, abstention or recapture-quality rate has been measured. Synthetic examples cannot establish merchant outcomes, calibrated probabilities, hidden functionality or safety.

Dedicated localization, crop lineage, OCR and matching remain unimplemented. The UI permits extra views, but camera control and measured active view selection are absent. Real-photo collection with independently reviewed identities/revisions, unreadable/unknown cases and physical-item/return-separated splits remains needed. Keep original model claims and human corrections auditable.

The service remains one process/worker and one GPU slot with no queue. Timeouts are cooperative and cannot interrupt a blocked CUDA kernel; timed-out work holds its slot until return. A crash may leave an orphaned pending run without automatic resumption. Distributed scheduling, fuller monitoring, credential lifecycle, backup/restore, evidence retention, reservation expiry, supervised partial completion recovery, richer rebuild instructions and external functional/safety checks remain future work.

AMD Developer Cloud, Linux ROCm and vLLM are not deployed or qualified. The handoff requires a separately pinned actual runtime/model/decoder combination, equivalent validation/error/provenance behavior, service credentials separate from operator bearers, TLS/network restriction and measured workload quality/memory/latency. Local LMFE support does not imply an AMD serving backend is compatible. AMD remains a required hackathon delivery gate. Evolus remains optional and unimplemented; it cannot bypass deterministic decisions or human authority.

## G. Next milestone

After successful completion and review of this Task 5 increment, the smallest high-impact follow-up is a separately authorized, small real-photo evaluation using the same pinned model and strict evidence path. Obtain authorized product images and independently reviewed identity/revision/marking labels, include unreadable and out-of-catalog cases, split by physical item/return, and measure unsupported-claim and source-attribution errors plus useful recapture and human correction. Use those results to decide whether targeted OCR/localization or a narrower hypothesis policy is justified before expanding the model stack.

This recommendation is not execution of Mission 04 or permission to collect private images, download models, train, or spend cloud credits. AMD qualification must follow when access and resource use are authorized. Stop after the current accepted Task 5 work, final report, and verified normal push.

## Appendix 1. Preserved accepted Task 1–4 records

The following task sections are copied verbatim from the existing mission report. Their test counts, commits and CI results describe those accepted increments, not the pending Task 5 final gates.

### Task 1 — completed

Qualified the pinned Qwen3-VL checkpoint on one GPU. Added bounded official image preprocessing, typed chat templates, serialized lazy GPU loading, cached weights, explicit errors, hash-verified download and reproducible measured smoke execution.

Baseline: backend 362 passed; frontend 25 passed. Task gate: backend 409 passed (17.62 s), including 34 adapter and 13 downloader checks; frontend 25 passed; TypeScript/build and pip check passed. Two actual GPU smoke requests passed.

Commit: `7b6d5aa11c813675b38c0ef754c73186d3a13d75`. Local HEAD, origin/main and independent `git ls-remote origin refs/heads/main` matched after this task's push. Both GitHub Actions jobs (Python backend and TypeScript operator workspace) completed successfully: [run 38355404967](https://github.com/arslanabdulghaffar/ReKit/actions/runs/38355404967).

Exact files changed:

- `README.md`
- `backend/src/rekit/inference/__init__.py`
- `backend/src/rekit/inference/adapters/__init__.py`
- `backend/src/rekit/inference/adapters/local_transformers.py`
- `configs/inference/qwen3-vl-2b.json`
- `docs/local-inference.md`
- `evaluation/download_vision_model.py`
- `evaluation/run_vision_smoke.py`
- `requirements-inference.txt`
- `tests/backend/test_local_vision.py`
- `tests/backend/test_model_download.py`

### Task 2 — completed

Added strict inference request/configuration/output/outcome contracts, strict JSON parsing and immutable same-database run persistence. Bound every input to component, return, asset/hash, observation and evidence version. Added unverified evidence only when current; preserved failures and stale outcomes without authority.

Backend 516 passed (20.64 s), including 74 inference-model/parser and 33 inference-store checks. pip check passed. These are CPU software tests; no new real-model request in this task.

Commit: `5d03e1d0de03a37548ac8147bea673a33ca4a0a8`. Local HEAD, origin/main and independent `git ls-remote origin refs/heads/main` matched after this task's push. Both GitHub Actions jobs (Python backend and TypeScript operator workspace) completed successfully: [run 38356763345](https://github.com/arslanabdulghaffar/ReKit/actions/runs/38356763345).

Exact files changed:

- `backend/src/rekit/inference/models.py`
- `backend/src/rekit/inference/parsing.py`
- `backend/src/rekit/inference/store.py`
- `docs/inference-evidence.md`
- `tests/backend/test_inference_models.py`
- `tests/backend/test_inference_store.py`

### Task 3 — completed

Added a small provider interface, authenticated API, one background worker and one admission slot, idempotent requests, cooperative/model and service deadlines, provenance checks and lazy server configuration. Executed actual managed-image inference and proved inventory stayed held.

Backend 565 passed (24.23 s), including 30 inference API and 19 provider checks; pip check passed. One actual managed-image API acceptance passed its software boundary checks, despite an unsupported model identity/revision.

Commit: `e4eab98979673954d2d8f0c448033f340ad76a23`. Local HEAD, origin/main and independent `git ls-remote origin refs/heads/main` matched after this task's push. Both GitHub Actions jobs (Python backend and TypeScript operator workspace) completed successfully: [run 38358064561](https://github.com/arslanabdulghaffar/ReKit/actions/runs/38358064561).

Exact files changed:

- `.env.example`
- `README.md`
- `backend/src/rekit/api/inference.py`
- `backend/src/rekit/inference/adapters/local_transformers.py`
- `backend/src/rekit/inference/provider.py`
- `backend/src/rekit/inference/service.py`
- `backend/src/rekit/inference/store.py`
- `backend/src/rekit/main.py`
- `docs/inference-evidence.md`
- `docs/local-inference.md`
- `evaluation/run_api_inference_acceptance.py`
- `tests/backend/test_inference_api.py`
- `tests/backend/test_inference_provider.py`

### Task 4 — completed

Extended existing component review with image selection, polling, actual model identity, escaped observations/alternatives/uncertainty/additional views, provenance, manual retry, same-component uploads, and attributable rejection. Proposal review prefills identity only; existing explicit human verification remains mandatory.

Backend 574 passed (21.92 s); inference API 39 passed, including nine rejection checks. Frontend 48 passed (28.00 s), including 23 AI-inspection checks. TypeScript/build passed. Controlled frontend responses were test doubles, not GPU results.

Commit: `f6aa873dc6c3e47b36b744da756ecea91a88d28c`. Local HEAD, origin/main and independent `git ls-remote origin refs/heads/main` matched after this task's push. Both GitHub Actions jobs (Python backend and TypeScript operator workspace) completed successfully: [run 38359513193](https://github.com/arslanabdulghaffar/ReKit/actions/runs/38359513193).

Exact files changed:

- `README.md`
- `backend/src/rekit/api/inference.py`
- `backend/src/rekit/inference/models.py`
- `backend/src/rekit/inference/store.py`
- `docs/inference-evidence.md`
- `docs/local-inference.md`
- `frontend/README.md`
- `frontend/src/App.test.tsx`
- `frontend/src/evidence.tsx`
- `frontend/src/inference.test.tsx`
- `frontend/src/inference.tsx`
- `frontend/src/styles.css`
- `frontend/src/types.ts`
- `tests/backend/test_inference_api.py`

## Appendix 2. Historical stopped Task 5 attempt and first ten actual requests

The following excerpt is copied verbatim from the report saved at the earlier stop. References to "final," "current," "blocked," authorization limits, file counts or absence of a successful browser flow refer only to that historical snapshot. The new authorization, reproduced baseline, constrained-decoding work and later results are recorded above; no historical failure is erased or relabelled.

## Task 5 — BLOCKED; not committed or pushed

Implemented reviewable evaluation changes: explicit `--real-inference` opt-in for the isolated browser runner, two-image and ambiguous-image acceptance, stored raw runs and GPU/provenance checks, same-identity extra-view upload, human review links, desktop/mobile captures, and preservation of the default recovery regression. Added CPU runner/prompt tests, a reproducible evaluation procedure and concrete AMD handoff. The acceptance code exists; **its AI scenario did not complete**.

Final local checks: **588 backend tests passed, 0 failed, in 24.23 s**; focused provider checks **24 passed**, browser-runner checks **17 passed**. Full frontend **48 passed, 0 failed, in 27.93 s**; TypeScript, production build (21 modules), npm dependency graph and pip check passed. These cannot replace the required real-inference gate.

The default browser regression passed: one test in 4.5 s on Chrome 154.0.8037.98; three returns, four components, eight managed images; negative plan with zero rebuilds; actual CP-SAT OPTIMAL plan for two kits; four exclusive reservations, four consumed identities, two completed kits and four audit events. Exact completion retry returned 200; invalid upload 422, missing auth 401 and viewer upload 403. Scenario value 17,500 cents is synthetic, not commercial uplift. Artifact: `var/mission02-acceptance/run-btavldmf/`. Mobile evidence capture was visually inspected; no AI-result screenshot reached a successful result.

Real GPU smoke passed two requests. The Task 5 API acceptance using **v1** passed its workflow checks but repeated the unsupported adapter/A hypothesis. **Four AI-browser attempts failed**, one initial attempt followed by the three permitted repairs:

| Attempt | Prompt / output cap | Actual failure | Artifact directory |
| --- | --- | --- | --- |
| Initial | v1 / 384 | Candidate and additional-view records omitted required image_indices. | run-ai-jiwykyk_ |
| Repair 1 | v2 / 384 | Candidate still lacked image_indices; output hit 384 tokens and truncated inside an additional-view reason. | run-ai-kxmilqsw |
| Repair 2 | v3 / 512 | Complete JSON, but revision A was paired with null revision_marking; copied example wording. | run-ai-zpfefrhu |
| Repair 3 | v4 / 512 | Complete JSON with forbidden top-level image_indices; generic uncertainty and weak additional-view request. | run-ai-ngy_f2t6 |

All four directories are under ignored `var/mission02-acceptance/`; each retains `inference-results.json`, failure diagnostics and `runner-result.json`. Every failed outcome was `invalid_output`, with zero applied model events and evidence version unchanged at 3. All owned temporary database/image/credential state and child services were cleaned; runner cleanup/report error lists were empty. No output was repaired, no schema or assertion was weakened, and no replacement model was downloaded.

Repairs were evidence-based prompt changes: full source-reference example; shorter records and the pre-existing 512-token ceiling after observed truncation; then removal of copied placeholders and an explicit optional-revision pair rule. Final working-tree configuration is **rekit-inspection-v4 / 512 tokens / 120-second generation deadline**, with the unchanged 150-second service deadline. It is **not qualified** by a passing real browser/API scenario. Published Task 4 remains v1/384. The final v4 inspection-prompt SHA-256 was `6d4fb1690f7f50e36fba647e31944d4d67eb8bb4217ecbc704089ad77742a7ec`.

Each attempt stopped at the first two-image inspection. Therefore the new browser's ambiguous second GPU request, AI-linked human correction, and subsequent recovery sequence were **not reached**. A separate ambiguous-image API result and the separate default recovery regression do not establish that combined gate. No v4 API acceptance was run after the final failure.

The mission explicitly says: “If three evidence-based repairs cannot resolve a critical gate, stop safely rather than bypassing the test.” That threshold was reached. No Task 5 commit, push or CI pass exists; the completion report could not be included in a successful final commit. It is saved locally for independent review.

Exact uncommitted files (12 modified, one new report):

- `README.md`
- `backend/src/rekit/inference/provider.py`
- `deploy/amd/README.md`
- `docs/architecture.md`
- `docs/local-inference.md`
- `docs/reports/development-mission-03.md`
- `docs/roadmap.md`
- `evaluation/README.md`
- `evaluation/run_browser_acceptance.py`
- `frontend/e2e/recovery.spec.ts`
- `frontend/playwright.config.ts`
- `tests/backend/test_browser_runner.py`
- `tests/backend/test_inference_provider.py`

## Actual model measurements and evaluation

**10 genuine GPU requests** ran in this mission: four descriptive smoke requests, two structured one-image API requests and four structured two-image browser requests. This is **14 image presentations of three distinct synthetic images**: one 768×512 shapes illustration and two 720×440 invented label views. No customer/product-photo dataset was used. Browser fixture generation also creates other images for manual recovery; they were not submitted to this model.

Each request recorded one actual visual-encoder forward call. Two smoke pairs reused their provider/weights on the second call. “Reused” below means no new load; all other rows loaded in a fresh process/provider.

| Request | Prompt | Inputs | Run outcome | Load seconds | Inference seconds | Peak allocated bytes | Peak reserved bytes | Tokens in / out |
| --- | --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| Task1 smoke 1 | smoke | 1 | succeeded | 4.624754 | 34.424170 | 4398954496 | 4460642304 | 474 / 100 |
| Task1 smoke 2 | smoke | 1 | succeeded | Reused | 33.016417 | 4397340672 | 4469030912 | 474 / 100 |
| Task5 smoke 1 | smoke | 1 | succeeded | 3.860661 | 15.181218 | 4398954496 | 4460642304 | 474 / 100 |
| Task5 smoke 2 | smoke | 1 | succeeded | Reused | 14.816123 | 4397340672 | 4469030912 | 474 / 100 |
| Task3 API | v1 | 1 | succeeded | 4.712812 | 43.564893 | 4540146688 | 4559208448 | 852 / 267 |
| Task5 API v1 | v1 | 1 | succeeded | 4.085893 | 19.622786 | 4540146688 | 4559208448 | 852 / 267 |
| Task5 browser | v1 | 2 | invalid_output | 3.921686 | 28.599571 | 4658128384 | 4687134720 | 1086 / 324 |
| Task5 browser | v2 | 2 | invalid_output | 3.776428 | 27.551621 | 4696311808 | 4752146432 | 1167 / 384 |
| Task5 browser | v3 | 2 | invalid_output | 3.763753 | 22.984531 | 4630555136 | 4674551808 | 1036 / 188 |
| Task5 browser | v4 | 2 | invalid_output | 3.776526 | 24.499072 | 4683341312 | 4747952128 | 1145 / 257 |

Largest measured peak: **4,696,311,808 allocated bytes (about 4.374 GiB)** and **4,752,146,432 reserved bytes (about 4.426 GiB)**. These are PyTorch allocator peaks, not total GPU/driver usage or a guarantee for all inputs. Load times were 3.763753–4.712812 seconds; inference 14.816123–43.564893 seconds. Later faster measurements do not establish a code optimization or throughput improvement. Inference includes processing/generation with CUDA synchronization; loading is separate.

Of six structured requests, **two satisfied the schema and four failed it**. Three invalid responses were complete JSON with contract violations; v2 was truncated JSON. This mixes prompt versions and intentionally narrow synthetic inputs; it is not a production failure-rate estimate. All four plain-text smoke requests succeeded; they were not structured-schema tests.

Representative actual results:
- Smoke requests described the red triangle, blue circle, SYNTHETIC heading and illustration footer. They establish image execution, not component recognition.
- Both v1 API requests proposed **adapter / A**, using **SYNTHETIC** as a revision marking, while their uncertainty admitted the illustration did not establish a revision. This is an unsupported, contradictory proposal, not a correct recognition. The single physical item stayed held and unverified, compatibility remained false, and exact replay reused its immutable run.
- The browser responses read invented body/REV A labels but repeatedly violated the output contract. V3 copied “visible support,” “unresolved detail” and “needed photograph.” V4 reused the unknown-example wording and requested VIEW 1 without explaining useful missing evidence. No accepted AI-linked human correction was observed; only the separate manual regression completed correction and execution.
- No confidence percentage, model accuracy, commercial uplift, operator-time reduction, hidden function or safety claim is supported by this evaluation.

Full ignored smoke/API artifacts: `var/mission03-qualification.json`, `var/mission03-api-acceptance.json`, `var/mission03-final-smoke.json`, `var/mission03-final-api.json`. The initial Task 3 run predates the prompt-digest metadata field; this historical omission is documented rather than backfilled. All later structured runs record their own exact inspection-prompt digest and settings.

No CUDA OOM, CUDA compatibility failure or package installation blocker was observed. A pre-GPU processor preflight required typed text content rather than a plain system-message string; that was fixed in Task 1. Greedy generation emitted the checkpoint's sampling-setting warning; do_sample remained false. The unresolved blocker is **model output-contract reliability in genuine two-image execution**.
