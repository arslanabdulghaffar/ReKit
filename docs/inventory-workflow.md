# Transactional inventory and execution

`InventoryStore` coordinates recovery proposals and execution in the same SQLite
file as `EvidenceStore`. Catalog and disposition policy are pinned to that file.
Changing either requires an explicit migration and revalidation, which are not
implemented. These stores use concrete SQLite read helpers to share one consistent
snapshot and transaction; they do not operate independent identity registries.

## Proposal, approval, and execution

Planning reads all unallocated components and their current evidence. Held items
remain visible to the solver but cannot enter consuming actions. Full registered
return membership is preserved even when some members are reserved or consumed,
so an available subset cannot masquerade as a whole return for liquidation.
CP-SAT runs outside the database write transaction. The persisted proposal retains
the exact catalog, policy, evidence versions, economic assumptions, input hash,
actions, solver status, and scenario totals.

Approval checks the expected plan version, current evidence, membership, policy,
and availability in a short `BEGIN IMMEDIATE` transaction. Reservations and the
audit event commit together. Database uniqueness prevents two active allocations
of a physical component. Only rebuild, salvage, and liquidation consume stock;
retention and holds do not create exclusive reservations. All reported monetary
amounts remain scenario estimates, including after completion.

An approved action requires a separate operator completion command containing
the exact physical-component IDs, an explicit confirmation, and final evidence
references. A rebuild also requires a completed-kit ID. The transaction rechecks
the relevant evidence and reservations, records consumption, creates the kit with
component lineage, and appends audit history. Salvage and liquidation completion
only record dispositions; there is no payment, order, or merchant integration.

New evidence may be recorded while components are reserved. It cannot silently
inherit the old approval: changed evidence blocks completion. Cancel the plan,
review the evidence, and generate a new proposal. Cancellation releases reserved
stock and retains history. Once any action is completed, cancellation is rejected
because it cannot undo a physical rebuild or disposition.

## Retries and consistency

Mutation commands carry a global operation ID, operator ID, reason, and expected
plan version. An exact retry returns the current plan state without applying the
operation again. Reusing an operation ID with different content is a conflict.
This also holds when a successful command is retried after a later transition.

Each connection enables foreign keys and a five-second busy timeout. Failed
checks, uniqueness violations, and execution errors roll back the entire write,
including reservations, completed inventory, and audit records. Audit updates
and deletes are rejected by database triggers. This supports application
auditability; a privileged database editor can still alter the database.

## Current limits

- The HTTP API binds named actors and roles from server-configured bearer credentials.
  Internal Python store methods are trusted application calls, not a separate API.
  Use loopback deployment; bearer theft and local administrators remain trusted-boundary risks.
- Evidence references are metadata. The system does not fetch, hash, inspect, or
  independently authenticate their underlying files.
- Completion confirms the recorded assembly/disposition. It does not establish
  hidden functionality, electrical safety, or compliance with external testing.
- Labor and demand limits apply to each scenario plan. There is no shared labor
  calendar or demand ledger across different plans.
- Reservations have no automatic expiry. Explicit cancellation is required.
- Partial physical work, failed functional tests, post-completion corrections,
  and dismantling/rework need a separate workflow before real warehouse use.
  If new evidence blocks a remaining action after another action has completed,
  the plan stays reserved: supervised partial-plan recovery is not implemented.
- SQLite supports this bounded local workflow. Backup/restore, migrations,
  multi-tenant authorization, and operational hardening remain future work.

Run `.\.venv\Scripts\python.exe -m pytest tests/backend/test_inventory.py -q -W error`
to exercise real SQLite reservations, races, rollback, cancellation, completion,
idempotency, and stale evidence. No external services are required.
