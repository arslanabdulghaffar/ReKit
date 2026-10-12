# Operator-confirmed backend API

The API exposes the implemented catalog, evidence, planner, and inventory logic.
It performs no image inference. Workflow routes require a named operator/service
bearer credential and explicit roles. See [authentication](operator-auth.md) for
provisioning and threat limits. Run locally with loopback binding.

## Start a configured local server

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts/create_operator.py --operator alice
$env:REKIT_AUTH_CONFIG_PATH = '.\.secrets\operators.json'
$env:REKIT_EVIDENCE_DIR = '.\var\evidence'
$env:REKIT_DATABASE_PATH = '.\var\synthetic-rekit.sqlite3'
$env:REKIT_CATALOG_PATH = '.\tests\fixtures\synthetic_catalog.json'
$env:REKIT_DISPOSITION_POLICY_PATH = '.\tests\fixtures\synthetic_disposition_policy.json'
.\.venv\Scripts\python.exe -m uvicorn rekit.main:create_configured_app --factory --host 127.0.0.1 --port 8000
```

The catalog and disposition policy are explicitly synthetic local test inputs.
Review and approve real catalog data separately before using real return records.
The server owns these policies; planning requests cannot supply replacement
catalogs, policies, inventory snapshots, or precomputed allocations. SQLite pins
the complete configured catalog and policy. Changing their files does not migrate
an existing database.

Use `http://127.0.0.1:8000/docs` for the exact Pydantic request and response schemas.
No `.env` file is loaded automatically. `create_app(inventory=..., auth=..., assets=...)`
supports explicitly injected stores and credentials for tests. The default `rekit.main:app` opens no database and
returns 503 from workflow routes until a configured factory is used. Its
`GET /health` response remains HTTP 200 with `{"status":"ok"}`; this is liveness,
not database or inference readiness.

## Workflow

| Route | Operation |
| --- | --- |
| `GET /auth/me` | Read the authenticated actor and explicit roles. |
| `GET /catalog` | Read the server's approved catalog and compatibility rules. |
| `GET /batches`, `GET /returns` | Read registered intake records. |
| `GET /plans?limit=50` | Read up to 100 compact plan summaries, newest first. |
| `POST /batches` | Register a return batch. |
| `POST /returns` | Register a return under an existing batch and approved family. |
| `POST /components` | Register a unique physical component under a return. |
| `POST /components/{id}/images?return_id=...` | Upload one bounded raw image, creating a managed observation. |
| `GET /components/{id}/images`, `GET /assets/{id}` | Read image metadata and availability. |
| `GET /assets/{id}/content` | Retrieve authenticated, integrity-checked image bytes. |
| `POST /components/{id}/evidence` | Record an observation, identity proposal, or uncertainty flag. |
| `POST /components/{id}/verification` | Record a version-checked human verification or correction. |
| `GET /components/{id}/history` | Retrieve the complete evidence history and current state. |
| `GET /components/{id}/compatibility?configuration_id=...` | Check current verified evidence against the server catalog. |
| `POST /plans` | Generate and persist a real CP-SAT proposal from current unallocated stock. |
| `GET /plans/{id}` | Inspect the complete proposal, scenario estimates, solver status, and workflow version. |
| `POST /plans/{id}/approve` | Atomically approve and reserve consuming actions. |
| `POST /plans/{id}/cancel` | Cancel a proposed or uncompleted approved plan and release reservations. |
| `POST /plans/{id}/actions/{action_id}/complete` | Explicitly confirm a physical action and record final evidence. |
| `GET /plans/{id}/audit` | Retrieve the chronological execution audit. |
| `GET /inventory` | Retrieve held, available, reserved, consumed, and completed-kit inventory. |

An evidence command uses `kind` (`observation`, `proposal`, or `uncertainty`) and a
corresponding typed `payload`. A verification command carries `verification` and
`expected_version`. The path component ID must match the body ID.

A plan request supplies `scenario` and optional solver `settings`. Include
component valuations for every currently unallocated item, including held items.
If reservations change that pool, refresh inventory and update the assumptions.
Hold values remain zero regardless of an input donor valuation. Each scenario
identifies its currency, valuation date, labor rate, prices, and noncash donor
values. Reported recovery amounts are estimates, never actual receipts.

Approval, cancellation, and completion carry `operation_id`,
`expected_version`, and `reason`. The server binds the authenticated actor; client
`operator_id` fields are rejected in verification and execution requests. Approval performs reservation in the same
transaction, so there is no separate reservation endpoint or approval bypass.
Completion additionally requires `confirmed: true`, exact `component_ids`, final
`evidence_references`, and a `completed_kit_id` for rebuilds. Merely approving a
plan does not create completed kits. After each mutation, use the returned plan
version for the next command. An exact operation retry remains idempotent.

## Error behavior and limits

- 401: missing or invalid bearer credentials.
- 403: wrong role or a service principal attempting a human action.
- 404: an entity or evidence reference ID is unknown.
- 409: an identity, idempotency key, version, policy, allocation, or state conflicts.
- 422: malformed contracts or invalid business input, including absent explicit
  completion confirmation or attempts to inject planner authority.
- 503: the workflow has no configured store.

The local API includes [managed image uploads and authorized retrieval](image-evidence.md).
The [operator workbench](../frontend/README.md) uses these same routes. There is
no rate limiting or external service integration yet.
Local bearer credentials identify configured actors; they do not
prove a human is physically present or that submitted evidence is true. Unknown or
conflicting evidence still requires review and cannot enter a rebuild. Approved
visible-condition rules do not establish hidden functionality or safety.

See [inventory execution](inventory-workflow.md) for transaction guarantees,
partial-completion limits, and the distinction between evidence eligibility and
stock availability. The API tests use a labeled synthetic three-return scenario
and exercise the real SQLite stores and CP-SAT solver.
