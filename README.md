# ReKit

ReKit is being built for the AMD Developer Hackathon ACT III to recover complete
product kits from compatible components across incomplete returns. The target
system combines guided capture, AMD multimodal inference, traceable evidence,
approved BOMs, economic planning, human review, and transactional execution.

The current implementation is a local, operator-confirmed Python backend and
React operator workbench. AMD
inference is a required future integration; it has not been deployed or measured.

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

## Run and test locally

From `A:\hackathon\ReKit` in PowerShell, use the existing Python 3.12 `.venv`.
Do not recreate it or reinstall its working PyTorch/CUDA packages.

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

## Repository boundaries

| Path | Responsibility |
| --- | --- |
| `backend/src/rekit/main.py`, `api/` | Composition, local configuration, HTTP contracts and errors |
| `backend/src/rekit/catalog/` | Approved BOM, revision, compatibility, and condition policy |
| `backend/src/rekit/evidence/` | Intake, stable physical identities, observations, corrections, SQLite provenance |
| `backend/src/rekit/recovery/` | CPU CP-SAT, integer economics, actual solver status, deterministic explanations |
| `backend/src/rekit/inventory/` | Proposals, approvals, transactions, reservations, completion, audit |
| `backend/src/rekit/workflows/` | Reserved boundary for richer review, rebuild instructions, and rework orchestration |
| `backend/src/rekit/inference/adapters/` | Planned AMD ROCm/vLLM and local development inference adapters |
| `backend/src/rekit/integrations/evolus/` | Optional future integration through approved application commands |
| `frontend/` | React, TypeScript, and Vite operator workbench and focused UI tests |
| `tests/backend/`, `tests/fixtures/` | Automated contracts, integration tests, labeled synthetic inputs |
| `evaluation/` | Reproducible synthetic CPU evaluation and future perception/AMD measurement plan |
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

Live camera capture, detection/segmentation, OCR, visual matching,
vision-language inference, active recapture guidance, richer rebuild instructions,
and Evolus are not implemented. No AMD benchmark or visual-model
accuracy result is claimed. AMD cloud qualification remains a required delivery
gate once access and resource use are authorized.

## Dependencies and secrets

`pyproject.toml` pins FastAPI, Pydantic, Uvicorn, OR-Tools, and Pillow at runtime, plus pytest
and HTTPX for tests. SQLite comes from Python. No PyTorch, ROCm, or vLLM package is
required by the backend; keep future AMD serving in a separate environment. The
existing local PyTorch 2.9.0+cu128 environment is preserved. Transitive packages are
not fully locked across platforms; AMD deployment needs its own qualified pins.

Frontend runtime and test dependencies are pinned in `frontend/package.json`
and its lockfile; use Node.js 26. No global software was installed.
[`.env.example`](.env.example) has blank secrets and an invalid example
inference host. Real keys belong in ignored local configuration or secret storage,
never frontend variables or Git. `.gitignore` excludes environments, operational
databases, customer evidence, weights, caches, and generated output; review staged
source files for embedded secrets as well.

## Design and next priorities

Read [architecture](docs/architecture.md), [domain contracts](docs/domain-contracts.md),
[evidence persistence](docs/evidence-provenance.md), [recovery planning](docs/recovery-planning.md),
[inventory execution](docs/inventory-workflow.md), and the [roadmap](docs/roadmap.md).
The [foundation report](docs/foundation-report.md) is a historical inspection record.

Mission 02 adds authenticated authority, secure image evidence, a connected operator
workbench, and integration validation. AMD inference remains a separate future task
after local vision work and explicit qualification authorization.
