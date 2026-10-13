# ReKit Development Mission 04 — Recovery and completion

October 14, 2026, Asia/Seoul. Repository: `A:\hackathon\ReKit`.

The four local development tasks passed their acceptance checks: cached-data recovery, real-image evaluation, offline AMD transport preparation, and the two separate demonstrations. Independent human semantic review and actual AMD execution remain outstanding. This is not a production-readiness or hackathon-eligibility claim.

The final Task 4 commit contains this report. Its own SHA and post-push Actions result cannot be embedded in that same commit; they will be recorded in the completion addendum and ignored `var/mission04-final/final-verification.json` after independent remote verification. Earlier exact commits and CI outcomes are below.

## 1. Recovery, source integrity and dataset acceptance

Before changes, six uncommitted files, crash/download ledgers and all 73 cached objects were preserved under `var/recovery/mission04-20261014-031112/`. No valid image or metadata object was removed, replaced or downloaded again.

The earlier native failure was exit `-1073741819` / `0xC0000005`, with Windows identifying `python312.dll`; a diagnostic stack reached `json.decoder.raw_decode`. Its **root cause remains unknown**. The evidence does not establish source corruption, a Python defect, hardware failure, a Unicode trigger or a responsible native extension.

Only recovery Approach A was needed. All 16 shards parsed successfully in fresh standard-library interpreters. The finalizer now uses serial isolated child processes with `-I -S -X utf8 -X faulthandler`, bounded records/decompressed data/output/time, compact retained fields, and original shard/hash/source-line validation. It streams relevant image-index entries and delays native application imports. Failed parsing cannot publish a successful manifest or rewrite receipts.

Cached finalization exited 0 twice, in 8.1 and 8.8 seconds. Repetition reproduced every manifest field except the top-level finalization timestamp. Independent acceptance verified all 52 image-to-listing/source associations, index URLs/dimensions and original hashes. A separate all-shard diagnostic passed in 40.13 seconds, with a 2,752,844-byte tracemalloc peak; that is traced Python allocation, not total process RAM. This is a working mitigation, not a crash explanation.

| Preserved assets | Count | Bytes | Original budget |
| --- | ---: | ---: | ---: |
| JPEG image objects | 52 | 9,809,702 | 200 MiB |
| Metadata, index and source documents | 21 | 93,897,585 | 150 MiB |

These are receipted acquisition totals, not exact total network traffic: earlier small documentation reads and three 32-KiB range probes were outside that ledger. Recovery downloaded no additional assets.

The final manifest has **52 images, 48 listing groups, four additional same-listing views, 34 development images and 18 holdout images**, across six categories. Group splits prevent the same listing from entering both splits. Listing identity does not establish a unique physical returned unit.

Source and license: [official Amazon Berkeley Objects distribution](https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/index.html), [CC BY 4.0 distribution license](https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/LICENSE-CC-BY-4.0.txt). Credit: Amazon Berkeley Objects data and images © Amazon.com; dataset-builder credit is retained in the manifest and [source guide](../real-product-evaluation.md#source-license-and-attribution). Original bytes are unchanged; shared crops/overlays must be identified and attribution retained.

The collection includes catalog photographs, composites, a logo (`61OnkGVhMWL`) and reference charts (`51ajqjMk6hL`, `51a0DlkplcL`). It is not 52 independently certified product photographs, representative return damage, or verified kit inventory.

Final read-only audit: `var/mission04-final/cache-integrity-audit.json`. All **73/73** originals match preserved records and current receipts; all nine backup copies and the original download, transfer and crash ledgers remain unchanged. The manifest SHA-256 is `4c04cbf85ba9fe0d025b2f1dfd0c0d3c6dbd22a67f82daeb506f9c7b925758bc`.

## 2. Actual local evaluation and targeted repair

The existing model remains **Qwen/Qwen3-VL-2B-Instruct**, Apache-2.0, revision `89644892e4d85e24eaac8bacfd4f463576704203`. No additional model or dependency was installed.

Measured runtime: Python 3.12.10, PyTorch 2.9.0+cu128, torchvision 0.24.0+cu128, CUDA 12.8, Transformers 4.57.6, LM Format Enforcer 0.11.3, and NVIDIA RTX 4080 SUPER on `cuda:1`. The two-GPU environment, drivers and CUDA installation were preserved.

Settings: EXIF-aware RGB input, maximum side 768, processor area bounds 65,536–589,824, maximum 8,192 input tokens and 512 generated tokens, greedy decoding, bfloat16/SDPA, 120-second cooperative generation and 150-second service deadlines. Prompt `rekit-inspection-v5-constrained` and its SHA-256 `3fdef4495d4eba03cc6af53e9b1778afc7821d46d6d22460e0422bb5a9846fe2` stayed unchanged.

Task 2 ran the same preselected **13 development cases** before and after the change: 12 single-image requests and one joint two-image request per pass. That is **26 real-image GPU requests, 28 image presentations, 13 unique images and 12 listing groups**. Holdout images were not evaluated.

| Result | Baseline schema v1 | Catalog-scope schema v2 |
| --- | ---: | ---: |
| Attempted/completed requests | 13/13 | 13/13 |
| Accepted schema/provenance responses | 13/13 | 13/13 |
| Responses proposing candidates without a supplied catalog | 9/13 | 0/13 |
| Instructed/constrained abstention | 4/13 | 13/13 |
| Observation records / marking records | 23 / 5 | 23 / 5 |
| Identity / revision candidates | 9 / 9 | 0 / 0 |
| Additional-view records | 13 | 13 |
| Source-reference records / individual links | 45 / 45 | 36 / 36 |
| Independently reviewed cases | 0 | 0 |

The baseline proposed catalog identities/revisions despite receiving no catalog. Schema v2 now forbids candidates in that mode; catalog-backed requests retain unverified hypotheses. Strict parsing rejects a violation with raw text preserved and no applied model events.

Actual decoder tests exposed that LM Format Enforcer 0.11.3 permits a first array member despite `maxItems: 0`: the first focused gate had two failures and 90 passes. A narrow immutable character-parser guard now enforces an empty top-level candidate array, including escaped/reordered JSON, without patching the installed package or deleting generated claims. The corrected focused and full gates passed.

The measured 9/13-to-0/13 change demonstrates **catalog-scope enforcement, not improved recognition accuracy or semantic abstention**. Free-text claims can still be incorrect, contradictory or clipped at their field limit; view suggestions can repeat existing information. Both original outputs remain available, with no failed cases silently removed:

- `var/evaluation/abo/qwen-baseline-v1.json` — SHA-256 `f731569d02617dd077843516a3a44d76c609c46ccf56908bf4c186a8a54aa128`.
- `var/evaluation/abo/qwen-after-v2.json` — SHA-256 `791dac0795263fc5e42978baf93cd568be177c484fd9b48111cc592a032730ea`.

| GPU measurement | Baseline, n=13 | After, n=13 |
| --- | ---: | ---: |
| Inference seconds: minimum / median / nearest-rank p95 / maximum | 33.314 / 50.594 / 90.833 / 90.833 | 15.599 / 20.942 / 35.416 / 35.416 |
| Wall seconds: minimum / median / p95 / maximum | 33.404 / 50.717 / 90.998 / 90.998 | 15.658 / 21.022 / 35.513 / 35.513 |
| Cold inference, n=1 / warm median, n=12, seconds | 55.105 / 50.519 | 24.763 / 20.269 |
| One cold model load, seconds | 4.694 | 3.879 |
| Model-load peak allocated bytes | 4,256,128,000 | 4,256,128,000 |
| Maximum inference allocated / reserved bytes | 4,904,651,776 / 4,980,736,000 | 4,904,651,776 / 4,980,736,000 |

These are single sequential passes with different generated text, not repeated controlled performance trials. Lower observed latency does not establish a causal speedup or production guarantee. Load metrics repeated in request metadata describe one cold load per process.

## 3. Human review and valid denominators

Independent human labels remain **0**. All **52 image reviews are pending** in `var/evaluation/abo/reviews.json`. Both output queues contain **13 pending, zero reviewed cases**:

- `var/evaluation/abo/review-baseline-v1/index.html`
- `var/evaluation/abo/review-after-v2/index.html`

The queues display original inputs before collapsed predictions, preserve source/raw-result hashes, require an explicit independent reviewer declaration, and export separate assessments. Editing assessments does not grant inventory authority. Browser QA loaded 13 cards/14 images, checked desktop/mobile display and confirmed a pending-only export; artifacts are in `var/mission04-review-qa/run-2026-10-13T18-46-32-219Z/`.

Unsupported identity, unsupported revision, unsupported marking, incorrect visual source attribution, useful additional views, exact transcription and human-correction metrics each have **null numerator, denominator 0, null rate, and 13 excluded cases per queue**. Absence, uncertainty, pending and missing assessments are excluded as documented. Recognition accuracy is **not yet measurable**, not 0% error. Valid image indices and matching byte hashes do not establish visually correct attribution.

## 4. AMD provider preparation

The existing `VisionProvider` boundary now supports trusted `disabled`, `local-transformers` and `openai-remote` selection. Remote credentials remain server-only. The adapter uses an exact HTTPS endpoint allowlist, verified TLS, original-byte base64 transport for one/two images, strict requested/advertised model-ID matching, versioned configuration/schema provenance, bounded bodies and explicit errors. There is no automatic retry, model substitution or local fallback.

Limits include 10 MiB per image, 16 million pixels, 8,192-pixel dimensions, 30 MiB request, 128 KiB response and a maximum 120-second request budget. An isolated standard-library worker and deadline timer bound DNS/TLS/slow I/O, including blocked stdin. On timeout the worker is killed/reaped; OS spawn/cleanup overhead may exceed the nominal wall budget, and remote GPU cancellation is not guaranteed.

Offline qualification covers valid/invalid JSON and schema, unsupported requests, 401/403, 429, unavailable/oversized/malformed responses, incorrect model/provenance/image attribution, stale evidence, authorization and absence of inventory authority. Final focused gate: **237 passed**, comprising 64 transport, 104 provider and 69 inference-API cases. These are controlled transport simulations and local subprocess tests, not AMD results.

The first Task 3 Linux CI run exposed two failures after 967 passes/25 skips: killed-worker stdin remained open, followed by its delayed ResourceWarning in another test. The parent now explicitly closes all subprocess pipes. The first local repair run also exposed two incomplete process test doubles; they were updated to expose real pipe attributes, without relaxing assertions. The next 237-case gate passed, and corrective Linux CI passed. Diagnostic log: `var/mission04-ci/task3-initial-backend.log`.

A response model-name match does not attest weights or hardware. Configured model/processor revisions remain explicitly server-declared and unverified; remote runtime, schema-enforcement and hardware proof are unknown. Client image hashes prove encoded inputs, not remote visual processing.

[AMD access research](../amd-access.md) distinguishes official Developer Cloud, event TokenFactory and separate Radeon documentation. The [event page](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii) describes TokenFactory access without the $100 voucher; the [public portal](https://notebooks.amd.com/tokenfactory) did not establish an authenticated vision model, exact API contract, two-image/schema support, immutable revisions or AMD execution evidence for ReKit. Generic vLLM capability is not deployment qualification.

**Actual AMD requests: 0. Credits spent: 0. Deployments: 0.** The [activation checklist](../../deploy/amd/README.md#activation-checklist) requires authorization/access, exact model and endpoint capabilities, real deployment/runtime/hardware provenance, and bounded actual one/two-image and application tests. AMD remains on the delivery path.

## 5. Demonstrations and final validation

The real-product run used original images `71rr7OjqWqL` and `812Xgtrv0EL`, one listing's development views, with one simulated physical-unit record and no matching inference catalog. It passed actual browser/API acceptance on the first attempt in **49.8 seconds**, Chrome 154.0.8037.98.

Artifacts: `var/mission02-acceptance/run-ai-_hto37ic/`, including `product-inference-results.json`, `runner-result.json`, `desktop-product-inspection.png`, `mobile-product-inspection.png` and `product-review-held.png`. All three screenshots were inspected. The run verified original hashes, actual joint visual execution, visible unverified output, scripted operator rejection, a readable-label/detail request, duplicate-upload identity preservation, 401/403 rejection, zero page errors and cleanup. Inventory stayed held with zero verifications, plans, reservations or kits. Scripted review did not create human ground truth.

Its **one actual request** returned two appearance observations, no candidates, one uncertainty and one back-view request. The uncertainty ended mid-sentence; the output remains unchanged and unverified. Inference took **38.313 s**, whole provider request **46.990 s**, model load **3.822 s**, with **4,901,876,736 allocated / 4,949,278,720 reserved peak bytes**, 1,503 input tokens and 156 output tokens.

Mission 04 totals are **27 actual real-image requests**, **30 image presentations**, still **13 unique images / 12 listing groups**. The browser/API request is counted once. Two additional genuine GPU requests used synthetic illustrations in the existing AI regression; total local GPU requests across these Mission 04 checks are **29**.

The separate synthetic recovery gates passed:

| Run | Outcome and artifact directory |
| --- | --- |
| Existing AI browser regression | Passed, about 1.2 minutes; `var/mission02-acceptance/run-ai-n2j7_p4b/`. Two actual synthetic-image requests succeeded; their inference times were 35.052 and 22.262 seconds. The second reused loaded weights. |
| Default browser recovery | Passed, 4.4 seconds; `var/mission02-acceptance/run-qz_ybush/`. No GPU request. |
| Actual CPU synthetic evaluation | OR-Tools 9.15.6755 returned OPTIMAL: three returns, four unique components, two completed kits, four consumed components, 60 labor minutes, four audit events and USD 175 modeled value. |

The AI regression still proposed unsupported `body/A` identity on ambiguous shapes; explicit operator rejection preserved that defect. Subsequent synthetic verification used original fixture evidence and linked the runs. Both recovery browser modes exercised four exclusive reservations and two explicit completions. Their USD 175 is an illustrative scenario estimate, not realized savings. No unrelated retail photos were converted into a real recovered kit. All three browser runs removed temporary credentials/state and reported no cleanup errors. All 13 AI/default regression screenshots were independently inspected: no layout blockers or visible credentials, and reservation/final-inventory states matched the records. Audit: `var/mission04-final/browser-artifact-audit.json`.

Commands executed from the repository root, using the existing environment unless noted:

| Validation command/check | Result |
| --- | --- |
| `.venv\Scripts\python.exe -W error -m pytest -q` | **1,007 passed in 30.97 s** on the final implementation tree. |
| Focused acquisition tests / manifest-review tests | Task 1: **44 / 49 passed**; full Task 1 **724 passed**. |
| Task 2 focused/full backend gates | **185 / 806 passed**. |
| `.venv\Scripts\python.exe -W error -m pytest tests/backend/test_remote_transport.py tests/backend/test_remote_provider.py tests/backend/test_inference_api.py -q` | **237 passed in 8.67 s**, after the pipe fix. |
| Browser-runner CPU tests | **30 passed in 1.34 s**; no downloaded corpus or GPU required. |
| `npm.cmd test`, in frontend | **51 passed in 27.98 s**. |
| `npm.cmd run typecheck`; `npm.cmd run build`, in frontend | Passed. |
| `.venv\Scripts\python.exe -m pip check`; `npm.cmd ls --all` | Passed; npm lists unused optional peers without a dependency failure. |
| `evaluation/prepare_abo.py --cached-only`, original/repeat destinations | Both actual finalizations passed without downloads. |
| `evaluation/product_data.py check --manifest evaluation/fixtures/abo-manifest.json --root var/evaluation/abo` | 52 images/48 groups verified; zero reviewed. |
| `evaluation/product_review.py check`, exact saved-queue commands below | Both digest-bound assessments valid; 13 pending each. |
| `.venv\Scripts\python.exe -I -S var/mission04-final/audit_cache.py` | All 73 originals and preserved ledgers verified. |
| `evaluation/run_product_evaluation.py`, exact baseline/after commands below | Two real 13-request GPU passes completed; immutable artifacts listed above. |
| `evaluation/run_browser_acceptance.py --check --real-inference --real-product-images` | Original-pair setup passed without GPU/services. |
| `evaluation/run_browser_acceptance.py --real-inference --real-product-images` | Actual real-image browser/API gate passed. |
| `evaluation/run_browser_acceptance.py --real-inference` | Existing actual-AI synthetic browser regression passed. |
| `evaluation/run_browser_acceptance.py` | Default browser regression passed. |
| `evaluation/run_synthetic.py` | End-to-end CPU recovery and both greedy comparisons passed. |
| Scoped secret/artifact scan; `git diff --check` | 134 source/document files and 18 final browser JSON/log files scanned without flagged secrets; no forbidden tracked/unignored assets; whitespace check passed. Pattern scans are not a comprehensive secret audit. |

The two historical GPU commands and final review checks were:

```powershell
.venv\Scripts\python.exe evaluation/run_product_evaluation.py --output var/evaluation/abo/qwen-baseline-v1.json
.venv\Scripts\python.exe evaluation/run_product_evaluation.py --output var/evaluation/abo/qwen-after-v2.json
.venv\Scripts\python.exe evaluation/product_review.py check --result var/evaluation/abo/qwen-baseline-v1.json --assessments var/evaluation/abo/review-baseline-v1/case-assessments.json
.venv\Scripts\python.exe evaluation/product_review.py check --result var/evaluation/abo/qwen-after-v2.json --assessments var/evaluation/abo/review-after-v2/case-assessments.json
```

The baseline used its original schema-v1 implementation; current code does not recreate that historical configuration. Existing result destinations cannot be overwritten by the runner.

The evaluation, browser and synthetic commands above use `.venv\Scripts\python.exe`. Exact CLI examples and metric definitions are in the evaluation guides. No database schema, optimizer policy or inventory authority was changed to make the demonstrations pass.

## 6. Exact source changes and dependencies

Compared with accepted baseline `02fedeb4f9e966960cec7a8ef94e6999a5f3ee80`, the mission creates these 20 files:

```text
backend/src/rekit/inference/adapters/https_worker.py
backend/src/rekit/inference/adapters/openai_remote.py
backend/src/rekit/inference/adapters/remote_transport.py
docs/amd-access.md
docs/demo-script.md
docs/hackathon-submission-checklist.md
docs/real-product-evaluation.md
docs/reports/development-mission-04.md
evaluation/fixtures/abo-manifest.json
evaluation/prepare_abo.py
evaluation/product_data.py
evaluation/product_review.py
evaluation/run_product_evaluation.py
frontend/e2e/real-product.spec.ts
tests/backend/test_abo_acquisition.py
tests/backend/test_product_data.py
tests/backend/test_product_evaluation.py
tests/backend/test_product_review.py
tests/backend/test_remote_provider.py
tests/backend/test_remote_transport.py
```

It modifies these 20 existing files:

```text
.env.example
README.md
backend/src/rekit/inference/constrained.py
backend/src/rekit/inference/parsing.py
backend/src/rekit/inference/provider.py
backend/src/rekit/inference/service.py
backend/src/rekit/main.py
deploy/amd/README.md
docs/architecture.md
docs/roadmap.md
evaluation/README.md
evaluation/run_browser_acceptance.py
frontend/playwright.config.ts
frontend/src/inference.test.tsx
frontend/src/inference.tsx
frontend/src/types.ts
tests/backend/test_browser_runner.py
tests/backend/test_constrained.py
tests/backend/test_inference_api.py
tests/backend/test_inference_provider.py
```

No new source directory was needed. Ignored recovery, dataset, review, CI and browser artifacts remain under the `var/` paths listed above. Image bytes, metadata archives, weights, credentials and databases are excluded from Git.

**Dependencies added/upgraded: none. Installation blockers: none.** Python/frontend manifests and locks remain unchanged. No global software, model, dataset or container was installed during recovery/continuation. Node 26.3.1/npm 11.16.0 and the existing browser were used.

## 7. Commits, pushes and GitHub verification

Each listed commit was normally pushed to private `main` and independently matched with `git ls-remote origin refs/heads/main`. No history rewrite, force push or visibility change occurred.

| Stage | Exact commit | CPU GitHub Actions |
| --- | --- | --- |
| Task 1 — Finalize bounded real-product evaluation dataset | `5506b69bb827ef2b4c836d0adac8c1577b10a997` | [38446001965](https://github.com/arslanabdulghaffar/ReKit/actions/runs/38446001965): backend/frontend success |
| Task 2 — Evaluate real-product visual evidence | `662d3354bbb341357fb88ca8e734cb86df4f2b48` | [38450291059](https://github.com/arslanabdulghaffar/ReKit/actions/runs/38450291059): backend/frontend success |
| Task 3 — Prepare AMD remote visual inference | `a53a482e88ed156d6cc96c2a401896fdd5a281b7` | [38452216288](https://github.com/arslanabdulghaffar/ReKit/actions/runs/38452216288): backend failed, frontend passed; preserved and repaired |
| Task 3 correction — Close remote worker pipes after deadline cleanup | `6dd805ee44b132c83a24e7471a187a2e9c512e25` | [38453167659](https://github.com/arslanabdulghaffar/ReKit/actions/runs/38453167659): backend/frontend success |
| Task 4 — Final local demonstration/report | Commit containing this report | Exact final SHA, clean-tree status and post-push CI will be recorded in the completion addendum. |

GitHub API checks confirm private visibility and default branch `main`. Actions remain CPU-only; they neither execute the local model nor download the evaluation corpus. This report distinguishes local GPU/browser results from CI.

## 8. Remaining limits and next action

Human review is still required before measuring semantic accuracy. The dataset is small and selected, includes non-photographic imagery, lacks reviewed return-condition labels and has no approved real-product BOM. Model prose and catalog-backed revision hypotheses remain unreliable; string/schema validity does not prove evidence, function or safety. Confidence wording is not a calibrated probability.

The native crash root cause is unresolved despite successful bounded recovery. Local generation deadlines are cooperative; remote transport cannot prove server cancellation. Remote identity, revision and AMD hardware need deployment evidence, not API-name echoes. Existing production limits, including multi-user deployment, catalog migration and supervised partial-plan recovery, remain as documented.

The [demo script](../demo-script.md) provides separate real-image inspection and synthetic recovery tracks plus a 4:40 recording plan. The [submission checklist](../hackathon-submission-checklist.md) records required assets and approval gates. Actual AMD qualification, public release/hosting, final video/slides and submission are not completed. The official public-GitHub requirement does not authorize changing this private repository. The observed event end is not a verified portal submission cutoff.

Recommended next implementation task, after user review and explicit cloud authorization: qualify the selected AMD vision endpoint using the documented activation checklist and the same source hashes. Independent human annotation can proceed separately. **No Mission 05 work has started.**
