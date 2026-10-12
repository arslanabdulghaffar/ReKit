# Domain contracts

The catalog is approved input, not an inference result. Its versioned families,
types, revisions, configurations, BOM quantities, and compatibility policies are
validated together. A configuration must contain its family's mandatory types;
every BOM type and allowed revision must exist and belong to the right family.
Each configuration has one explicit approved compatibility policy. Policy checks
return deterministic reasons for rejection.

`tests/fixtures/synthetic_catalog.json` is an invented test catalog, explicitly
labeled synthetic. Its approvals and prices (when added) are not merchant data.

Evidence models distinguish physical registration, an observation, a proposed
identity, and an operator verification. A photograph does not register another
physical item. The physical ID remains stable when a part label is corrected.
Identifiers are nonblank strict strings; timestamps must include a time zone.
Models reject extra fields and are immutable, with tuple collections.

`validate_intake` checks duplicate identifiers and batch/return/component/catalog
references. `CurrentEvidence` distinguishes unresolved, review-required, and
verified state. Review-required state preserves earlier verification but blocks
eligibility. Human verification records its operator, reason, linked observation
IDs, identity, and visible condition. These are assertions, not authentication
or proof of hidden functional/safety properties.

`InventoryItem` defaults to held. Eligibility requires current human verification
without unresolved evidence and a known visible condition. `validate_inventory`
then checks unique physical IDs and catalog identities. Eligibility alone does
not establish suitability for a particular kit: `check_compatibility` applies
that configuration's approved revisions and allowed visible conditions.

Call collection validation at use-case boundaries. Individual Pydantic models
cannot validate references to an external catalog or database. Never use
`model_construct` or unvalidated `model_copy(update=...)` for untrusted input or
state transitions. The [evidence store](evidence-provenance.md) now checks that
referenced observations exist and belong to the verified physical item, and
enforces evidence-version checks. Atomic allocation remains outside this slice.

No model confidence scores are interpreted as probabilities. There is no visual
inference or automatic approval in these contracts.
