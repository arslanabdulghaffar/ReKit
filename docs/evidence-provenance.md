# Evidence and physical-component provenance

The evidence store uses Python's `sqlite3` with a local file database. The file
is operational data and belongs outside Git, for example under ignored `var/`.
There is no graph database, image inference, OCR, camera stream, or image upload
processor in this slice. Evidence references are recorded metadata; referenced
bytes are not downloaded, hashed, or automatically inspected.

Register a return batch, its returns, and each physical component once. Recording
another observation links to that component's existing ID. The store checks the
source return and rejects references to missing components or observations.
Registration does not make a component eligible for recovery.

An observation describes its capture, evidence reference, source, and visible
markings. A proposal links a hypothesized identity to an observation. Proposals
may remain unknown or disagree; neither creates human verification. An explicit
uncertainty flag records the reason and source of a review request.

Human verification names an operator, identity, visible condition, supporting
observations, and reason. It must reference the current evidence version. A
correction also names the prior verification it supersedes. New evidence after
verification puts the component back into review while retaining that earlier
assertion. This deliberately favors a new review over silently extending an old
verification to unseen evidence.

The store appends each observation, proposal, uncertainty flag, and verification
as an event. Event sequence and evidence version establish database ordering;
submitted capture timestamps describe the evidence and do not rewrite history.
SQLite triggers reject updates and deletes of evidence-event rows. This is an
application/database integrity safeguard, not cryptographic tamper evidence.

An exact retry with the same event ID and payload is idempotent. Reusing an ID
for different content is a conflict. Retrying a historical verification does
not reinstate it after newer evidence has required review. Failed commands roll
back both event insertion and current-state changes.

Reads of history and inventory use a consistent database snapshot. Writes use
short explicit transactions, enabled foreign keys, and bounded lock waiting.
The implementation follows Python's [explicit SQLite transaction control](https://docs.python.org/3.12/library/sqlite3.html#transaction-control-via-the-isolation-level-attribute)
and SQLite's [transaction semantics](https://www.sqlite.org/lang_transaction.html).
The database pins its catalog contents; opening it against changed catalog
content fails rather than silently changing approved policy. Catalog migration
is not implemented. Operator identifiers are recorded assertions; authentication
and authorization will be needed before serving untrusted users.

`EvidenceStore.inventory_items()` derives held/eligible snapshots from current
evidence. This is not a reservation or stock-consumption operation. Kit-specific
compatibility remains a separate deterministic catalog check. [Inventory execution](inventory-workflow.md) shares the same database to recheck
evidence versions atomically. Use its inventory snapshot for availability; evidence
eligibility alone does not establish that stock is unreserved or unconsumed.

Use file databases for persistence and tests. `:memory:` is intentionally not
supported because each operation opens and closes its own connection.
