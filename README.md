# ReKit

ReKit is being built for the AMD Developer Hackathon ACT III to recover complete
product kits from compatible components across incomplete returns. The target
system combines guided capture, AMD multimodal inference, traceable evidence,
approved BOMs, economic planning, human review, and transactional execution.

The current implementation is a local, operator-confirmed Python backend and
React operator workbench. Local GPU inference and a server-configured remote
vision adapter are implemented. The remote adapter has offline qualification;
actual AMD deployment and inference remain required, uncompleted gates.

## What works

- Validated product families, configurations, BOM quantities, revisions, and
  deterministic compatibility and visible-condition policies.
- Stable physical-component IDs, return provenance, multiple observations per
  item, unverified hypotheses, uncertainty flags, and versioned human corrections.
  SQLite preserves evidence history instead of replacing earlier assertions.
- Real CPU OR-Tools CP-SAT planning for rebuilds, whole-return liquidation,
  donor retention, salvage, and holds. It enforces component exclusivity, complete
  BOMs, compatibility, policy, labor, and demand using integer scenario economics.
- Persisted proposals, atomic human approval and exclusive reservations,
  cancellation, explicit completion confirmation, completed-kit lineage, and audit.
- FastAPI routes connecting intake through completion, with validated contracts,
  conflict responses, and idempotent execution commands.
- Authenticated operators and explicit roles, plus bounded JPEG/PNG/WebP intake,
  immutable asset records, content hashes, private retrieval, and multiple views.
- A connected workbench for intake, human evidence review, explicit scenario
  economics, real planning, approval, execution, and audit inspection.
- A synthetic three-return example producing two kits, negative API scenarios,
  exhaustive-search planner checks, real SQLite race/rollback tests, and a small
  greedy comparison. These are software tests, not customer or model benchmarks.
- An optional, qualified local Qwen3-VL-2B GPU provider with bounded image inputs,
  serialized requests, cached weights, and measured real image-to-text execution.
  [Local qualification](docs/local-inference.md) records its pinned model, license,
  download budget, commands, actual measurements, and limits. Authenticated API
  inspection uses managed image bytes, saves immutable run provenance, and adds
  only unverified evidence. [Inference contracts](docs/inference-evidence.md)
  explain schema validation, stale results, failures, and human review.
- AI-assisted component review selects one or two managed images, displays actual
  model observations and uncertainty, and supports another-view uploads and
  accountable rejection. Proposal review only prefills identity fields; explicit
  human verification, condition review, and evidence selection remain required.
- A verified cache of 52 ABO catalog images, source/license/hash manifests, and
  separate human-review queues. All image labels and output assessments remain
  pending; no independent human reviews or recognition-accuracy results exist.
  Mission 04 Task 2 made 26 actual local GPU requests over the same 13-case sample
  before and after a catalog-scope correction. No-catalog candidate violations
  changed from 9/13 to 0/13: a protocol improvement, not a visual-accuracy result.
- An optional `openai-remote` adapter with an exact HTTPS allowlist, original-byte
  image transport, bounded execution, strict output validation, and no automatic
  retry or fallback. Offline tests do not attest remote weights, runtime, or AMD
  hardware. See the [AMD activation gate](deploy/amd/README.md#activation-checklist).

## Run and test locally

From `A:\hackathon\ReKit` in PowerShell, use the existing Python 3.12 `.venv`.
Do not recreate it or reinstall its working PyTorch/CUDA packages.

For an isolated demonstration with a visible browser, follow the
[local demo guide](docs/local-demo.md) and run its prerequisite checks first.
Choose the real-image inspection or separate synthetic recovery replay:

```powershell
.\.venv\Scripts\python.exe evaluation/run_demo.py --mode product-ai --headed --slow-mo-ms 100 --hold-seconds 60 --device 1
.\.venv\Scripts\python.exe evaluation/run_demo.py --mode synthetic-recovery --headed --slow-mo-ms 100 --hold-seconds 60
```

Run one at a time. The launcher uses existing software, temporary loopback-only
state and automatic cleanup; it downloads nothing. The guide also covers
headless acceptance and the difference between real image inspection and the
USD 175 synthetic recovery estimate.

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe -m pytest -q -W error
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe evaluation/run_synthetic.py
```

The example uses a temporary SQLite database and real HTTP application logic in
process. It needs no GPU, credentials, external service, or model download. It
prints JSON containing the synthetic workflow and controlled optimizer/greedy
comparisons. Expected outputs and assumptions are in [evaluation](evaluation/README.md).

To run the persistent local API with the synthetic catalog and policy:

```powershell
.\.venv\Scripts\python.exe scripts/create_operator.py --operator alice
$env:REKIT_AUTH_CONFIG_PATH = '.\.secrets\operators.json'
$env:REKIT_EVIDENCE_DIR = '.\var\evidence'
$env:REKIT_DATABASE_PATH = '.\var\synthetic-rekit.sqlite3'
$env:REKIT_CATALOG_PATH = '.\tests\fixtures\synthetic_catalog.json'
$env:REKIT_DISPOSITION_POLICY_PATH = '.\tests\fixtures\synthetic_disposition_policy.json'
.\.venv\Scripts\python.exe -m uvicorn rekit.main:create_configured_app --factory --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for request/response schemas. See
[API workflow](docs/api-workflow.md) for the route sequence. Stop with Ctrl+C.
The policy and catalog files are trusted server inputs, not client overrides.

The default `rekit.main:app` opens no database: `/health` returns HTTP 200 with
`{"status":"ok"}`, and workflow routes return 503. Health reports process
liveness only. Use the configured factory above for the working recovery API.
No `.env` file is loaded automatically. Workflow requests need an operator bearer
token; the provisioning command refuses to overwrite existing credentials.

In another PowerShell terminal, start the operator interface:

```powershell
Set-Location A:\hackathon\ReKit\frontend
npm.cmd ci
npm.cmd run dev
```

Open `http://127.0.0.1:5173` and enter the private token printed at provisioning.
It stays in memory and is cleared on sign-out or refresh. The local Vite proxy
forwards `/api` to the loopback backend; no credential belongs in a `VITE_*`
variable. See [frontend instructions](frontend/README.md) for the workflow and
frontend checks. Both servers remain local; a successful build is not a deployment.

For the isolated real-browser acceptance scenario, close your own local ReKit
servers and run the command below from the repository root. It uses an installed
Chrome or Edge browser, generates labeled synthetic images, and starts temporary
loopback services. It does not reuse operational inventory or download a browser.

```powershell
.\.venv\Scripts\python.exe evaluation/run_browser_acceptance.py
```

To exercise actual local GPU inspection inside the same isolated recovery flow,
use the already qualified checkpoint and explicitly opt in:

```powershell
.\.venv\Scripts\python.exe evaluation/run_browser_acceptance.py --real-inference --device 1
```

This adds two real inspections, including an ambiguous illustration, before
explicit human review and normal recovery execution. It downloads nothing.
The default browser command remains a manual recovery regression without AI.

A separate Mission 04 mode uses two original ABO product views in one simulated
intake record and makes one real joint local inspection:

```powershell
.\.venv\Scripts\python.exe evaluation/run_browser_acceptance.py --real-inference --real-product-images --device 1
```

It supplies no matching identity catalog, leaves the component unverified and
held, and exercises an explicit operator-role rejection and additional-view
request. The photographs are catalog sources, not an actual returned kit;
automation does not create independent human labels. Its first actual browser/API
acceptance passed in 49.8 seconds, with one joint GPU request, held inventory,
zero page errors and successful cleanup. Artifacts are in
`var/mission02-acceptance/run-ai-_hto37ic/`; see the
[Mission 04 report](docs/reports/development-mission-04.md) for the recorded outcome.
Together with Task 2, this totals 27 local requests on real catalog imagery; the
browser/API request is counted once. Keep it separate from the synthetic two-kit recovery
demonstration in the [demo script](docs/demo-script.md).

Check the existing image cache without downloading or running a model:

```powershell
.\.venv\Scripts\python.exe evaluation/product_data.py check --manifest evaluation/fixtures/abo-manifest.json --root var/evaluation/abo
```

[Real-product evaluation](docs/real-product-evaluation.md) documents the source
limitations, actual before/after outputs, independent-review workflow, and
reproduction commands. Pending reviews contribute zero semantic denominators,
so accuracy remains unmeasured rather than 0% error.

The pinned local provider uses schema-constrained generation followed by strict
domain validation. Two complete real-AI browser runs passed during Mission 03,
including explicit rejection of an unsupported revision claim and separate human
verification. These synthetic cases qualify execution and evidence handling;
they do not measure recognition accuracy. See the
[Mission 03 report](docs/reports/development-mission-03.md) for actual outcomes,
preserved failures, settings, and limitations.

See [browser acceptance](evaluation/README.md#real-browser-acceptance) for the
checks, prerequisites, generated artifacts, and limits. The CPU-only GitHub
Actions workflow runs backend and frontend checks; local browser results are
reported separately.

## Repository boundaries

| Path | Responsibility |
| --- | --- |
| `backend/src/rekit/main.py`, `api/` | Composition, local configuration, HTTP contracts and errors |
| `backend/src/rekit/catalog/` | Approved BOM, revision, compatibility, and condition policy |
| `backend/src/rekit/evidence/` | Intake, stable physical identities, observations, corrections, SQLite provenance |
| `backend/src/rekit/recovery/` | CPU CP-SAT, integer economics, actual solver status, deterministic explanations |
| `backend/src/rekit/inventory/` | Proposals, approvals, transactions, reservations, completion, audit |
| `backend/src/rekit/workflows/` | Reserved boundary for richer review, rebuild instructions, and rework orchestration |
| `backend/src/rekit/inference/adapters/` | Local Transformers GPU inference and bounded remote HTTPS transport; actual AMD qualification pending |
| `backend/src/rekit/inference/` | Provider boundary, bounded worker, validated results, immutable run provenance |
| `backend/src/rekit/integrations/evolus/` | Optional future integration through approved application commands |
| `frontend/` | React, TypeScript, and Vite operator workbench and focused UI tests |
| `tests/backend/`, `tests/fixtures/` | Automated contracts, integration tests, labeled synthetic inputs |
| `evaluation/` | Synthetic CPU recovery, real-image source integrity, local GPU evaluation, human-review queues, and browser acceptance |
| `deploy/amd/` | AMD qualification and deployment boundary |
| `docs/` | Architecture, contracts, workflow limits, and roadmap |

## Limits and unimplemented work

This is not production-ready. [Named operator credentials and roles](docs/operator-auth.md)
protect workflow routes and bind audit actors. Keep the printed token private,
enter it at local sign-in, and bind to loopback. Service credentials cannot perform
human verification or approval. Stolen human tokens can still impersonate operators.
Managed [image evidence](docs/image-evidence.md) is decoded and hashed; legacy
text references remain unmanaged. Images are not proof of scene authenticity.
Human-visible assembly confirmation does not prove
hidden functionality or safety. Model confidence statements are not calibrated
probabilities.

Planning is bounded to 100 supplied components and 10,000 exhaustive candidate
actions. Oversized inputs fail explicitly. Labor and demand limits apply per
scenario, not across a shared schedule or order ledger. Holds have zero value;
retained donors are noncash assets; all economic outputs remain scenario estimates.
A feasible solver result is never labeled optimal unless CP-SAT reports `OPTIMAL`.

Catalog and disposition policy are pinned to each database. There is no catalog
migration, reservation expiry, supervised partial-plan recovery, backup/restore
qualification, authenticated multi-user deployment, or external warehouse/payment
integration. A plan cannot be cancelled after partial completion. If new evidence
blocks its remaining work, a future supervised recovery operation is needed.

Live camera capture, detection/segmentation, dedicated OCR, visual matching,
automatic multi-view inspection, richer rebuild instructions, and Evolus are not
implemented. Local VLM output can contain unsupported identity and revision
claims even when its JSON is valid; see the measured example in
[local inference](docs/local-inference.md). No AMD benchmark or visual-model
accuracy result is claimed. AMD cloud qualification remains a required delivery
gate once access and resource use are authorized.

## Dependencies and secrets

`pyproject.toml` pins FastAPI, Pydantic, Uvicorn, OR-Tools, and Pillow at runtime, plus pytest
and HTTPX for tests. SQLite comes from Python. No PyTorch, ROCm, or vLLM package is
required by the backend; keep future AMD serving in a separate environment. The
existing local PyTorch 2.9.0+cu128 environment is preserved. Transitive packages are
not fully locked across platforms; AMD deployment needs its own qualified pins.
Optional local inference dependencies are pinned in `requirements-inference.txt`;
CPU-only CI and the default API do not install or import the model runtime.

Frontend runtime and test dependencies are pinned in `frontend/package.json`
and its lockfile; use Node.js 26. No global software was installed.
[`.env.example`](.env.example) has blank secrets and an invalid example
inference host. Real keys belong in ignored local configuration or secret storage,
never frontend variables or Git. `.gitignore` excludes environments, operational
databases, customer evidence, weights, caches, and generated output; review staged
source files for embedded secrets as well.

## Design and next priorities

Mission 05 presentation materials include [submission copy](docs/submission-content.md),
a [seven-slide pitch outline](docs/pitch-deck.md), the [four-minute recording script](docs/demo-script.md)
and an [editable architecture figure](docs/assets/rekit-architecture.svg).
The deck guide identifies locally generated private assets and how to recreate
them. These materials are prepared for review; the repository remains private,
no video or submission is claimed, and actual AMD qualification remains pending.
See the [release-readiness assessment](docs/release-readiness.md) and
[AMD activation commands](docs/amd-activation.md) for the security findings and
the remaining authorized deployment work.

Read [architecture](docs/architecture.md), [domain contracts](docs/domain-contracts.md),
[evidence persistence](docs/evidence-provenance.md), [recovery planning](docs/recovery-planning.md),
[inventory execution](docs/inventory-workflow.md), and the [roadmap](docs/roadmap.md).
The [foundation report](docs/foundation-report.md) is a historical inspection record.

Mission 03 added real local GPU inspection, immutable inference provenance, and
AI-assisted human review. The [mission report](docs/reports/development-mission-03.md)
separates actual execution measurements, software checks, and observed model errors.
Task 5 resolved the earlier output-contract blocker with constrained decoding.
Its recorded API, repeated real-AI browser acceptance, and the original
recovery regression passed; the report preserves the earlier failed attempts.
Mission 04 adds bounded real catalog-image evaluation and review queues, a
qualified offline remote transport, and a separate product-image browser mode.
Independent human semantic review and actual AMD execution remain outstanding.
Use the [Mission 04 report](docs/reports/development-mission-04.md),
[AMD activation checklist](deploy/amd/README.md#activation-checklist),
[demo script](docs/demo-script.md), and
[submission checklist](docs/hackathon-submission-checklist.md) to distinguish
completed evidence from remaining delivery gates.
