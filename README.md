# ReKit

ReKit is an AMD-powered multimodal product-return recovery system for the AMD
Developer Hackathon ACT III. Its intended workflow turns incomplete returns into
recoverable kits through evidence capture, layered perception, approved BOM and
compatibility checks, economic recovery planning, human approval, exclusive
component reservation, rebuild instructions, and completed-kit verification.

## Current scope

Task 1 provides a modular repository foundation and a functioning FastAPI
`GET /health` endpoint returning HTTP 200 with `{"status":"ok"}`. The automated
test covers the public response contract. This is process liveness only; it does
not certify inference, database, or deployment readiness.

The other modules are documented boundaries with docstring-only package files.
There is no AI inference, optimizer, database schema, inventory behavior, frontend
application, or Evolus integration yet. The environment example is a future
configuration contract and is not loaded by the current application.

## Run in the existing Windows environment

Run these commands from `A:\hackathon\ReKit` in PowerShell. Use the existing
Python 3.12 `.venv`; activation is optional. Do not recreate this environment or
reinstall its working PyTorch/CUDA packages.

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m uvicorn rekit.main:app --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/health
```

The development API documentation is at `http://127.0.0.1:8000/docs`. Stop the
server with Ctrl+C. No secrets, GPU, external service, or `.env` file are required
for the health endpoint and test.

The test uses [HTTPX's ASGI transport](https://www.python-httpx.org/advanced/transports/#asgi-transport)
with Python's standard event loop, so no async pytest plugin is needed. It
exercises HTTP routing and serialization in process. The app currently has no
startup/shutdown resources; add explicit lifespan testing when those exist.

## Repository boundaries

| Path | Responsibility |
| --- | --- |
| `backend/src/rekit/main.py` | FastAPI composition root |
| `backend/src/rekit/api/` | HTTP request and response contracts |
| `backend/src/rekit/inference/adapters/` | Planned perception providers; AMD ROCm/vLLM is the primary inference path |
| `backend/src/rekit/evidence/` | Physical-component identity links, captures, observations, and provenance |
| `backend/src/rekit/catalog/` | Approved BOMs, revisions, compatibility, and visible-condition policy |
| `backend/src/rekit/recovery/` | CPU CP-SAT planning, economics, and alternatives |
| `backend/src/rekit/workflows/` | Human review, approvals, orchestration, rebuilds, and verification |
| `backend/src/rekit/inventory/` | Authoritative physical inventory, atomic reservations, and audit |
| `backend/src/rekit/integrations/evolus/` | Optional integration through validated workflow commands |
| `frontend/` | Reserved React + TypeScript + Vite boundary |
| `tests/backend/` | Backend automated tests |
| `evaluation/` | Evaluation and benchmarking plan |
| `deploy/amd/` | AMD Developer Cloud qualification and deployment plan |
| `docs/` | Architecture, roadmap, and foundation validation record |

## Architectural commitments

- AMD Developer Cloud, ROCm, vLLM, and a compatible open vision-language model
  form the production hackathon inference path. Model, runtime, and GPU choices
  require qualification; none is selected or downloaded in this foundation.
- Local PyTorch/CUDA development stays separate from the AMD inference runtime.
  The API package has no PyTorch, vLLM, ROCm, or OR-Tools dependency.
- Models produce evidence-linked observations and hypotheses. Deterministic
  policies control compatibility; transactional services control inventory.
- One physical component has one persistent identity and at most one active
  allocation. Additional photos and detections never create additional stock.
- Human approval applies to a versioned proposal; reservation revalidates current
  policy and availability atomically, with an audit record.
- Model confidence statements are not calibrated probabilities. Visual evidence
  describes visible condition and cannot establish hidden function or safety.

## Dependencies and configuration

`pyproject.toml` is the Python dependency source: FastAPI, Pydantic, and base
Uvicorn at runtime; pytest and HTTPX for development tests. Direct versions and
the build backend are pinned. Transitive dependencies are resolved by pip and
are not a complete deployment lock; create platform-specific locks during AMD
qualification. Do not use a freeze of the CUDA development environment as an AMD
requirements file.

Node.js and npm were detected, but no frontend dependencies or generated scaffold
are installed. Frontend test tooling will be chosen with the first UI slice.

[`.env.example`](.env.example) contains blank secret values and a deliberately
invalid inference hostname. Actual keys belong in ignored local configuration or
deployment secret storage. Never put them in `VITE_*` variables or client code.
`.gitignore` excludes local environments, secrets, databases and journals,
customer evidence, model weights, and generated output. Review files before
staging; ignore rules do not detect secrets embedded in ordinary source files.

## Design and next steps

- [Architecture and invariants](docs/architecture.md)
- [Implementation roadmap and acceptance gates](docs/roadmap.md)
- [AMD deployment boundary](deploy/amd/README.md)
- [Evaluation and benchmarking](evaluation/README.md)
- [Frontend boundary](frontend/README.md)
- [Foundation inspection and validation record](docs/foundation-report.md)

Stop at Task 1 for review. The next proposed implementation is the evidence and
catalog domain contracts with invariant tests, alongside early AMD runtime/model
qualification. Product functionality starts only after that review.
