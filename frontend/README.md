# ReKit operator workspace

This React and TypeScript client connects to the ReKit FastAPI backend. Operators
can register returns and physical components, upload image evidence, record human
verification or corrections, enter economic assumptions, request a real CPU
CP-SAT plan, approve reservations, and confirm recovery actions. Inventory,
completed-kit lineage, and audit history come from the backend.

No vision model runs in this interface. Images remain evidence for human review.
AMD ROCm/vLLM integration is a future backend capability; the browser never
connects to an inference service. Visible appearance does not establish hidden
functionality or safety, and scenario estimates are not realized profit.

## Requirements and installation

Use Node.js 26 or newer and npm. Development was checked with Node.js 26.3.1 and
npm 11.16.0. React/React DOM 19.3.0, TypeScript 7.0.2, and Vite 8.3.4 are pinned;
the lockfile fixes dependency resolution. Vitest, Testing Library, and jsdom
support component tests. Playwright supports real-browser checks with an
already-installed Chrome or Edge browser. No browser download is needed here.

From `A:\hackathon\ReKit\frontend`:

```powershell
$env:PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD = '1'
npm ci
```

Use the repository's existing Python `.venv` for the backend. Do not reinstall
PyTorch or change CUDA to run the interface.

## Run locally

From the repository root, provision an operator if you do not already have one:

```powershell
.\.venv\Scripts\python.exe scripts/create_operator.py --operator local-operator
```

The helper prints a random token once and stores only its digest in ignored
`.secrets/operators.json`. Keep the token private. The default human operator has
all six roles. The helper refuses to overwrite existing configuration; reuse an
existing credential instead of replacing it. See [operator authentication](../docs/operator-auth.md)
for narrower roles and credential management.

In the same terminal, configure and start the backend:

```powershell
$env:REKIT_DATABASE_PATH = '.\var\rekit.sqlite3'
$env:REKIT_CATALOG_PATH = '.\tests\fixtures\synthetic_catalog.json'
$env:REKIT_DISPOSITION_POLICY_PATH = '.\tests\fixtures\synthetic_disposition_policy.json'
$env:REKIT_AUTH_CONFIG_PATH = '.\.secrets\operators.json'
$env:REKIT_EVIDENCE_DIR = '.\var\evidence'
.\.venv\Scripts\python.exe -m uvicorn rekit.main:create_configured_app --factory --host 127.0.0.1 --port 8000
```

These catalog and policy files are explicitly synthetic. They create no inventory
on startup. Catalog and disposition policy snapshots are pinned to the database;
changing their files does not silently migrate existing records. No `.env` file
is loaded automatically. The default `rekit.main:app` exposes health but does not
configure the authenticated workflow.

In a second terminal:

```powershell
Set-Location A:\hackathon\ReKit\frontend
npm run dev
```

Open `http://127.0.0.1:5173` and enter the operator token. Vite binds to loopback
with a strict port. Requests use same-origin `/api/...`; the development proxy
forwards them to `http://127.0.0.1:8000` and removes `/api`. No permissive CORS
setting is needed. If a port is occupied, resolve the conflict rather than
exposing either server publicly.

## Operator workflow

1. **Intake:** register a batch, then a return with its approved family, then a
   unique physical component belonging to that return. New intake IDs use
   letters, numbers, hyphens, and underscores. Attach the ID to the physical
   object; another photograph is not another component.
2. **Image evidence:** choose an existing component and select one or more
   JPEG, PNG, or WebP files. Each authenticated upload creates immutable asset
   metadata and an observation for that original component and return. Limits
   are 10 MiB, 16,000,000 pixels, and 8,192 pixels per side; animated files are
   rejected. An identical file for the same component reuses its observation.
   Identical bytes assigned to another component are rejected. Multiple files
   are uploaded sequentially, not as one all-or-nothing transaction.
3. **Component review:** inspect images and history, then select the catalog
   type, revision, visible condition, supporting observations, and a reason.
   Verification uses the current evidence version. A correction explicitly
   supersedes the previous verification while preserving its history. Check
   compatibility to see the server's approved-policy decision and reasons.
   Unknown condition remains held.
4. **Recovery planning:** enter a description, date, labor cost and capacity,
   kit estimates, donor values, and any salvage/liquidation values. All money
   inputs are whole cents: 100 cents per selected USD, EUR, or GBP unit. Donor
   values cover every unallocated component, including held stock. Entering a
   value does not make stock eligible or grant policy permission. Optional
   capacity and demand limits may be blank for no limit. Visible zero defaults
   value salvage and liquidation options at zero.
5. **Execution:** inspect actual solver status, physical IDs, source returns,
   evidence versions, labor, value estimates, bound, and gap. Cash estimates
   and retained donor asset value are separate. Each action compares its value
   with retaining those donors; backend exclusions explain unavailable options.
   Change assumptions and create another proposal to compare scenarios. The
   client does not invent solver actions or assume a unique optimum.
6. **Approval and completion:** an authorized human enters a reason and approves
   the proposal, atomically reserving all consuming actions. For each action,
   check every reserved ID, enter completion evidence references and a reason,
   provide a kit ID for a rebuild, and explicitly confirm the physical work.
   Completion consumes the allocation and records lineage. It does not process
   payment or certify functionality. Inspect the audit trail and **Inventory**.

Image intake and identity changes are disabled for reserved or consumed stock.
A new observation after verification requires fresh review; after reservation
it also invalidates the approved evidence snapshot. Cancel and replan before
changing reserved evidence. Uploads are not a completion-photo workflow.
Cancellation is forbidden after an action has completed; supervised recovery
from partially completed plans is not implemented.

Managed `asset:` completion references must belong to a component in that action
and pass integrity checks. Other references remain metadata only and are never
fetched. Missing or corrupt required assets block new verification, approval,
and completion decisions. Refresh after a conflict and inspect the current
version before retrying. The backend remains authoritative for roles and all
compatibility, financial, reservation, and completion decisions.

## Supplied synthetic catalog and policy

The example policy names three returns. For a fresh manual demonstration,
register one batch and all three returns below with family `demo-kit` and
declared configuration `standard-kit`. Register these four components:

| Return ID | Physical component IDs | Synthetic identity for manual review |
| --- | --- | --- |
| `synthetic-return-bodies` | `synthetic-body-001`, `synthetic-body-002` | `body`, revision `A` |
| `synthetic-return-adapter-001` | `synthetic-adapter-001` | `adapter`, revision `A` |
| `synthetic-return-adapter-002` | `synthetic-adapter-002` | `adapter`, revision `A` |

Use explicitly synthetic images and identify the demonstration in review
reasons. The BOM requires one body and one adapter, both revision `A` with
acceptable visible condition. Adapter revision `B` exists but is not approved
for this configuration. The policy's named returns must exist before planning;
the UI does not register them or rewrite the policy automatically.

The [synthetic recovery fixture](../tests/fixtures/synthetic_recovery.json)
contains invented economic inputs: kit selling price 10,000 cents, labor 30
minutes, other cost 500 cents, demand 2, labor cost 25 cents/minute, and plan
capacity 60 minutes. Body donor values are 600 cents and adapter donor values
are 200 cents. These are test assumptions, not merchant prices. Enter them
deliberately if following the fixture; the UI does not preload results.

## Session and storage limits

The bearer token stays in memory. The input clears after sign-in; sign-out,
page reload, and an active-session 401 clear the session. There are no
token-bearing URLs, cookies, localStorage, sessionStorage, or frontend secrets.
API requests use fixed local paths, omit cookies, forbid redirects, and disable
caching. Authorized image bytes are displayed through temporary blob URLs,
which are revoked on cleanup.

The workspace requires `viewer` for its shared catalog and inventory context.
Actions additionally require their explicit intake, reviewer, planner, approver,
or executor role. Reviewer, approver, and executor actions require human actors.
One role does not grant another. Bearer possession grants its authority; a
human account does not prove physical presence. Credential changes require a
backend restart. MFA, automatic expiry, and an account-management UI are absent.

Keep both servers on loopback. Browser/process memory and local administrators
are within the trusted boundary. Never put credentials in `VITE_*` variables,
screenshots, logs, or Git. Images and SQLite records stay under the configured
server paths; back them up together. See [managed image evidence](../docs/image-evidence.md)
for integrity checks, duplicate handling, and storage failure limits.

## Checks and build

From `frontend`:

```powershell
npm test
npm run typecheck
npm run build
npm ls --all
```

`npm test` runs Vitest with jsdom and Testing Library. Mocked HTTP component
tests do not replace real-browser acceptance against the actual backend.
`npm run build` also checks TypeScript and writes ignored `dist/` files. With
the backend running, inspect the built client locally:

```powershell
npm run preview
```

Preview binds to `http://127.0.0.1:4173` with the same local API proxy. It is a
build preview, not a production deployment. From the repository root, run the
backend checks in the existing environment:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -W error
.\.venv\Scripts\python.exe -m pip check
```

These commands require no GPU, model downloads, or AMD cloud service. Do not
commit `node_modules/`, `dist/`, credentials, databases, image evidence, browser
profiles, or generated test artifacts.

## Source layout

- `src/App.tsx`: memory-only session, navigation, and server snapshots.
- `src/api.ts`: constrained authenticated JSON/image transport and errors.
- `src/types.ts`: TypeScript mirrors of HTTP contracts.
- `src/evidence.tsx`: intake, uploads, evidence review, and corrections.
- `src/recovery.tsx`: economics, planning, approval, completion, and inventory.
- `src/ui.tsx` and `src/styles.css`: shared controls, image previews, and layout.
- `vite.config.ts`: loopback development/preview proxy and test configuration.

See the [project README](../README.md), [API workflow](../docs/api-workflow.md),
and [implementation roadmap](../docs/roadmap.md) for the wider system boundaries.
