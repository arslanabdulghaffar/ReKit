# ReKit Development Mission 04 — Task 1 recovery progress

Date: October 14, 2026 (Asia/Seoul).

Mission 04 is incomplete. The separately authorized Task 1 recovery has successfully finalized the existing cached collection, produced its source manifest, and passed independent acceptance checks and updated tests. The Task 1 commit/push is pending at this interim report. Tasks 2–4 remain pending. The earlier stopped attempt and native-crash evidence are preserved; no source data was replaced or downloaded again.

## Current task outcomes

| Task | Outcome |
| --- | --- |
| 1 — Real-product collection | Acceptance passed: 52 images, 48 listing groups, four extra same-listing views; independent verification, deterministic repeat and updated tests passed. Commit/push pending. |
| 2 — Actual GPU evaluation and improvements | Not started. No real-product inference, quality comparison, or model improvement claimed. |
| 3 — AMD remote provider | Not started. No provider switch, transport simulations, or TokenFactory capability verification completed in this mission. |
| 4 — Demonstration and final validation | Not started. Real-image demonstration, submission checklist, demo script and final mission validation remain outstanding. |

## Recovery evidence and scope

Before editing, the accepted HEAD and six uncommitted files were preserved. `var/recovery/mission04-20261014-031112/preservation.json` records their hashes, backups of the crash and download ledgers, and successful verification of all 73 cached assets: 21 metadata/source documents and 52 original JPEGs. Original crash records and byte accounting remain intact.

Only **Approach A: isolated Python parsing** was used. All 16 listing shards parsed successfully in fresh standard-library-only interpreters; their exit codes and read-only diagnostics are in `var/recovery/mission04-20261014-031112/approach-a-shards.json`. The implementation now launches one shard per serial child using `-I -S -X utf8 -X faulthandler`, limits record/decoded/projected size and child time, and validates child results against the original shard hash. It retains compact selection fields and source shard/line, streams the image index for referenced IDs, and imports Pydantic/Pillow only after metadata parsing. A failed child cannot publish a successful manifest or change acquisition receipts.

Actual `evaluation/prepare_abo.py --cached-only` finalization exited **0** twice, with command wall times of 8.1 and 8.8 seconds. The first wrote `evaluation/fixtures/abo-manifest.json`; the repeat matched every manifest field except the top-level `downloaded_at` finalization timestamp. The result records 52 images across 48 listing groups: 34 development images and 18 holdout images. The power-accessory category contains 12 images, including four extra views; each other category contains eight. An independent standard-library audit verified the source shard/line, listing/domain and image membership for all 52 images; official CSV URL/dimensions and original-byte SHA-256 checks also passed 52/52. The integrity CLI verified all images and the separate review template contains 52 pending entries.

A diagnostic across all 16 shards also passed in 40.13 seconds. It reported a `tracemalloc` peak of 2,752,844 bytes and 26,879 currently traced bytes at the last observation. These are traced Python allocations, **not total process RAM**. The production parser's successful isolated execution and lower retained metadata are the acceptance evidence; these measurements do not establish why the earlier process crashed.

This is an effective mitigation, not an established explanation of the native crash. No source corruption, Python defect, hardware fault, specific native extension or Unicode trigger has been proven responsible. No alternate Node parsing approach, new dependency, Python reinstall, CUDA/driver change or model change was needed. No GPU inference has run in this Task 1 recovery.

## Preserved earlier stop history

The first acquisition reached final manifest validation and exposed a schema limit of 16 metadata receipts versus 21 actual receipts. That limit was corrected to 32; image identifiers containing `+` are also supported. Subsequent processing produced inconsistent JSON errors, although a separate parse of all 16 cached listing shards succeeded. Another acquisition exited without output. Instrumented diagnostics reproduced a JSON delimiter error, then a fatal access violation inside `json.decoder.raw_decode`.

Python reported exit `-1073741819` (`0xC0000005`). Windows Application Error records at approximately 01:36 and 01:37 identify `python312.dll`, fault offset `0x00000000000be1b7`. A diagnostic verified cached receipts before parsing. Troubleshooting stopped under the earlier bounded-attempt rule before the new recovery authorization. The prior 703 passing CPU tests did not establish real-data acceptance. No interpreter, driver, CUDA, or hardware configuration was changed. Local crash records remain at `var/evaluation/abo/python-crash-events.json`; the complete earlier stop report is also preserved in the recovery backup.

## Exact source files created

- `evaluation/prepare_abo.py` — official-object acquisition, persistent byte budgets, receipt/hash checks, deterministic selection, and manifest finalization.
- `evaluation/product_data.py` — strict manifest, local image integrity checks, listing-level splits, and separate independent-human-review ledger.
- `tests/backend/test_abo_acquisition.py` — 44 offline acquisition and isolated-parser tests, including synthetic selection and failure boundaries.
- `tests/backend/test_product_data.py` — 49 manifest, integrity, and review tests.
- `docs/real-product-evaluation.md` — source/license evidence, attribution, isolated parsing, cached finalization and independent review instructions.
- `docs/reports/development-mission-04.md` — this report.
- `evaluation/fixtures/abo-manifest.json` — actual source/license, listing/group, image-byte and pending-review manifest; no image bytes.

The six preserved source/documentation files and the new manifest form the current seven-file Task 1 increment. No new source directory was required. The final reviewed staging set, commit and independently verified push will be recorded after acceptance; this interim report claims none of them.

Ignored storage at `var/evaluation/abo/` contains `metadata/`, `images/`, acquisition ledgers and crash evidence. Exact downloaded filenames, source URLs, SHA-256 values, byte sizes and timestamps remain in the original download ledger. The source manifest is now separate from those receipts; human annotations and generated diagnostics remain outside Git.

## Dataset, license, and ground truth

Source: the [official Amazon Berkeley Objects distribution](https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/index.html), using individual public S3 objects rather than archives. The distributed READMEs and [license file](https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/LICENSE-CC-BY-4.0.txt) specify CC BY 4.0. The [AWS registry](https://registry.opendata.aws/amazon-berkeley-objects/) records the 2023 change from CC BY-NC to CC BY.

Attribution: Amazon Berkeley Objects data and images © Amazon.com. Dataset builders: Matthieu Guillaumin, Thomas Dideriksen, Kenan Deng, Himanshu Arora, Arnab Dhua, Xi (Brian) Zhang, Tomas Yago-Vicente, Jasmine Collins, Shubham Goel, and Jitendra Malik. Original downloaded bytes are unchanged. Shared examples must retain appropriate credit, source and license links, identify modifications, and avoid implied endorsement.

Receipted acquisition totals:

| Assets | Count | Exact bytes | Approximate MiB | Mission limit |
| --- | ---: | ---: | ---: | ---: |
| Metadata, index, license, READMEs | 21 | 93,897,585 | 89.55 | 150 MiB |
| Original product-image objects | 52 | 9,809,702 | 9.36 | 200 MiB |

Small preliminary documentation reads and three 32-KiB metadata range probes are outside these acquisition-ledger totals; the totals are not a claim of exact overall network traffic. No image archive, 3D package, additional model, or container was downloaded.

The actual finalized selection contains 48 listing groups across six categories plus four additional same-listing views, totaling 52 images. Photographic versus rendered/composite content, difficult-case coverage and physical identity remain unreviewed. Listing metadata does not establish visible identity or revision, and a listing group is not a unique returned physical unit.

Contact-sheet triage identified a logo-only image (`61OnkGVhMWL`), USB reference charts (`51aqijMk6hL` and `51a0DIkpJcL`), and composites. The acquired set is therefore described as catalog imagery, not 52 verified product photographs. This triage did not create human-reviewed labels or establish image-level truth. Task 2 must retain this limitation and identify the actual product-view subset used for examples. Original download/transfer ledgers and crash JSON were also rechecked and remain hash-identical to the preserved copies.

Independent human reviews: **0**. Images awaiting review: **52**. Accuracy denominator: **0 eligible reviewed images**; accuracy is **not yet measurable**, not 0%. The review tooling binds annotations to original image IDs and hashes and rejects pending annotations that assert reviewed truth. The generated template contains 52 pending entries; generating it did not create any human review.

## Model, runtime, and evaluation metrics

The accepted baseline remains Qwen3-VL-2B-Instruct revision `89644892e4d85e24eaac8bacfd4f463576704203`. Environment inspection found Python 3.12.10, PyTorch 2.9.0+cu128, torchvision 0.24.0+cu128, CUDA 12.8, and two GPUs. Node.js 26.3.1 and npm 11.16.0 were available. No dependency was added, installed, or upgraded.

Mission 04 model requests: **0**. No inference settings were changed or exercised. Schema-valid response rate, unsupported identity/revision/marking rates, abstention behavior, transcription quality, incorrect source attribution, useful recapture requests, and human corrections are all **not measured**. Their evaluation numerators are unavailable and denominators are zero because no inference cases ran; no percentages are calculated. Inference latency distribution and GPU memory usage are also not measured. There is no before/after comparison and no quality gain or regression claim. Additional models downloaded: **0**.

## Validation and Git

The following results belong to the **earlier stopped attempt**. They are retained as history and are not the acceptance gate for the changed parser:

| Command/check | Result |
| --- | --- |
| `.venv\Scripts\python.exe -m pytest -q -W error` before changes | 631 passed in 27.60 seconds. |
| `.venv\Scripts\python.exe -m pytest -q -W error tests/backend/test_product_data.py` | 49 passed in 0.82 seconds. |
| `.venv\Scripts\python.exe -m pytest -q -W error tests/backend/test_abo_acquisition.py` | 23 passed in 0.67 seconds; synthetic files and transport only. |
| `.venv\Scripts\python.exe -m pytest -q -W error` after changes | 703 passed in 25.27 seconds. |
| `.venv\Scripts\python.exe -m pip check` | No broken requirements found. |
| `.venv\Scripts\python.exe evaluation/prepare_abo.py` | Failed real-data acceptance as described above. |
| Read-only cached-shard parsing and `-X faulthandler` diagnostics | Inconsistent parse outcomes; native access violation captured. |
| `git diff --check`, scoped secret-pattern/artifact checks | Passed; no flagged secrets or forbidden unignored artifacts. Pattern checks are not a comprehensive secret audit. |
| `git check-ignore`, `git status --short`, `git diff --cached --stat` | Local assets ignored; six untracked source/documentation files; index empty. |
| `git rev-parse HEAD`, `git rev-parse origin/main`, `git ls-remote origin refs/heads/main` | All match the accepted baseline SHA below. |

Recovery acceptance results:

| Command/check | Result |
| --- | --- |
| Preservation receipt verification | All 73 cached objects match their original byte sizes and SHA-256 values; six source/documentation files and crash/download records backed up. |
| Fresh standard-library listing-shard diagnostics | All 16 shards exited 0. |
| `evaluation/prepare_abo.py --cached-only` and repeat to a fresh manifest path | Both exited 0; 8.1 and 8.8 seconds command wall time; all manifest fields identical except top-level `downloaded_at`. No new downloads. |
| Independent source audit | 52/52 original listing/domain/image associations, 52/52 index URLs and dimensions, and 52/52 original image hashes verified. |
| `evaluation/product_data.py check --manifest evaluation/fixtures/abo-manifest.json --root var/evaluation/abo` | All 52 images verified across 48 groups. |
| `evaluation/product_data.py review-template --manifest evaluation/fixtures/abo-manifest.json --output var/evaluation/abo/reviews.json` | 52 pending entries created; zero human reviews. |
| `.venv\Scripts\python.exe -m pytest -q -W error tests/backend/test_abo_acquisition.py` | 44 passed in 1.91 seconds. |
| `.venv\Scripts\python.exe -m pytest -q -W error` | 724 passed in 35.79 seconds. |

Frontend, GPU evaluation, real-image API/browser acceptance and final mission regression gates remain for later tasks. Existing frontend and inference source files are unchanged by Task 1.

GitHub API verification confirmed the repository remains private with default branch `main`. The accepted baseline's [CPU Actions run 38384727999](https://github.com/arslanabdulghaffar/ReKit/actions/runs/38384727999) succeeded for both **Python backend** and **TypeScript operator workspace**. This is baseline CI evidence only; no Mission 04 commit exists and no new Actions run was triggered.

Accepted starting local HEAD, local `origin/main`, and independently checked remote `main`:

`02fedeb4f9e966960cec7a8ef94e6999a5f3ee80`

Mission 04 commits/pushes: **pending after Task 1 acceptance**. This report does not attempt to contain its own future commit SHA. Later task/final report updates will record the exact Task 1 commit, normal push and independent remote verification. The working tree contains the Task 1 drafts and manifest. No history rewrite, publication, visibility change, authenticated remote inference or cloud deployment occurred.

## Remaining work

Review the accepted seven-file Task 1 increment, then commit and verify a normal push before starting Task 2. Keep the original crash evidence: the successful isolated parser is a mitigation, not a root-cause finding. Human review remains necessary for semantic accuracy; absent labels do not prevent measuring later real inference structure, latency and memory while reporting accuracy as unmeasured.

Tasks 2–4, AMD access-route research and remote adapter, real-image demonstrations, submission checklist, demo script, and final mission validation remain outstanding. AMD execution and hackathon eligibility are **unverified**. No Mission 05 work began.
