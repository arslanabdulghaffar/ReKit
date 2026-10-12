# ReKit architecture

ReKit recovers complete product kits from incomplete returns. Its planned workflow combines traceable visual evidence, approved product rules, deterministic recovery planning, human decisions, and transactional inventory. AMD Developer Cloud inference is a required part of the hackathon delivery.

## Current implementation status

The FastAPI application implements `GET /health`. Catalog/BOM/compatibility and evidence/identity/eligibility domain contracts are implemented and tested. SQLite now persists intake and append-only evidence history, with version-checked human verification. CPU CP-SAT recovery planning enforces complete BOMs, compatibility, component uniqueness, labor, demand, and disposition policy using integer scenario economics. Reservation/execution workflows and product screens are not yet implemented. No model, dataset, container, or inference deployment is included. Environment examples describe future configuration and are not proof of a working integration. See [domain contracts](domain-contracts.md) [evidence persistence](evidence-provenance.md), and [recovery planning](recovery-planning.md) for the current boundaries.

## Repository boundaries

| Location | Responsibility |
| --- | --- |
| `frontend/` | Planned React, TypeScript, and Vite operator interface for capture, evidence review, recovery comparison, approval, rebuilding, and verification. |
| `backend/src/rekit/api/` | HTTP routing and request/response translation, wired by `backend/src/rekit/main.py`. The health route is the only implemented application endpoint. |
| `backend/src/rekit/inference/` | Planned perception contracts and orchestration for localization, OCR, visual matching, and vision-language interpretation. |
| `backend/src/rekit/inference/adapters/` | Provider-specific implementations. Production targets AMD Developer Cloud with ROCm, vLLM, and a qualified open vision-language model; local PyTorch/CUDA and mock adapters support development. |
| `backend/src/rekit/evidence/` | Physical-component identity, return/capture relationships, immutable source evidence, observations, provenance, and requests for additional evidence. |
| `backend/src/rekit/catalog/` | Approved products, BOM revisions, allowed substitutions, compatibility constraints, and visible-condition policies. |
| `backend/src/rekit/recovery/` | Deterministic feasibility, CPU OR-Tools CP-SAT allocation, economic assumptions, and comparisons of feasible alternatives. |
| `backend/src/rekit/workflows/` | Human corrections and approvals, application use cases, rebuild instructions, and completion verification orchestration. |
| `backend/src/rekit/inventory/` | Transactional persistence, availability, reservation, consumption, release, and audit records. SQLite is the initial planned storage engine. |
| `backend/src/rekit/integrations/evolus/` | Optional Evolus integration through application contracts; absent by default. |
| `tests/backend/` | Health, domain, compatibility, evidence persistence, and recovery correctness tests. |
| `evaluation/` | Planned evidence datasets/manifests, perception and decision quality checks, performance measurements, and AMD qualification records. |
| `deploy/amd/` | Planned reproducible AMD deployment instructions and runtime/model compatibility records. |
| `docs/` | Architecture decisions, implementation sequence, and acceptance gates. |

Keep one modular backend until measured operational needs justify separate services. Directory boundaries do not require separate processes, databases, queues, or package distributions.

## Dependency direction and authority

The API translates transport inputs and delegates future use cases to workflows. Workflows coordinate evidence, catalog, recovery, and inventory through explicit contracts. The frontend and optional Evolus integration use application APIs; neither receives direct database or model-runtime authority.

Evidence and catalog domain rules stay independent of FastAPI, a specific inference SDK, and database details. Inference adapters return observations through perception contracts. Recovery consumes explicit component snapshots and approved catalog/policy versions; it does not infer compatibility by calling a language model. Inventory owns the final transactional checks and state transitions. Concrete runtime and persistence implementations are wired at the application boundary rather than imported into domain rules.

Do not add a generic framework, event bus, shared `utils` layer, or speculative abstract base classes during the foundation task. Introduce typed contracts and narrow interfaces as the first real domain use cases require them. Keep model runtime packages separate from the lightweight API dependency set.

## End-to-end workflow

1. **Capture returns.** Associate images, close-ups, or camera captures with a return/intake session and operator context. Preserve the original evidence asset and derive crops as linked artifacts.
2. **Observe components.** Run localization, OCR, visual matching, and vision-language interpretation through inference adapters. Record candidate labels, visible attributes, text, and their supporting evidence separately from catalog decisions.
3. **Resolve ambiguity.** Request a specific additional view, marking, scale reference, or human review when available evidence cannot distinguish candidates. New evidence augments the record instead of silently replacing an earlier observation.
4. **Establish physical identities.** Maintain one stable identity for each tracked physical component. Multiple views, detections, or model runs do not create additional physical stock. Potential duplicates remain unresolved until reconciled; they are not counted as independent available items.
5. **Validate against approved rules.** Check identified components against versioned BOMs, revisions, substitution/compatibility rules, and visible-condition policies. Unknown or conflicting facts remain explicit and may prevent planning or require review.
6. **Plan cross-return recovery.** Solve constrained allocation with CPU CP-SAT using available identities, required kit contents, capacity and handling limits, and versioned economic assumptions.
7. **Explain alternatives.** Present feasible recovery alternatives, objective values, costs, scarce-component use, unresolved evidence, and sensitivity to assumptions. Each explanation links back to concrete constraints and observations.
8. **Review and approve.** Allow authorized people to correct observations, resolve identity questions, and approve a specific plan snapshot. Corrections retain provenance, actor, time, and reason. A correction that changes feasibility invalidates affected plans and approvals.
9. **Reserve and rebuild.** Revalidate the approved plan against current evidence, policies, and inventory, then atomically reserve all required components and record the audit event. Generate instructions from the approved BOM and actual reservations.
10. **Verify and close.** Verify the assembled kit using required evidence and policy checks, record human confirmation where required, then atomically record consumption/output inventory and audit history. Failed or interrupted work follows an explicit hold/release/rework path.

These steps describe planned behavior. The health endpoint does not exercise or certify any step in this workflow.

## Evidence, identity, and provenance invariants

- A physical component has a stable identity independent of image filenames, bounding boxes, candidate part labels, return membership changes, and inference retries. Bulk-looking identical parts still require distinct physical identities before individual allocation.
- Evidence assets, capture events, inference runs, observations, catalog identities, and physical identities are different concepts. Linking an observation to a component is an accountable assertion, not a stock increment.
- Evidence owns the physical-identity registry; inventory references those same identities for custody and allocation. Neither inference nor inventory creates a parallel identity namespace for the same physical stock.
- Preserve the original evidence reference and content hash, capture time and source where available, derived-artifact lineage, component association, and the actor or run that made an assertion. Content hashes identify identical bytes; they do not prove two different images show different physical objects.
- Model observations retain runtime/model identifiers and revisions where available, prompt/preprocessing versions, inference settings, and timestamps. Human corrections supersede or qualify assertions without erasing their history.
- Identity merge/split corrections require an explicit recorded operation and revalidation of affected reservations and plans. They must not leave the same physical object allocatable under multiple identities.
- Missing provenance, unresolved identity, conflicting evidence, and unknown condition remain explicit states. No silent fallback may convert an unknown fact into an approved compatibility or inventory decision.

## Perception and AMD inference

Layered perception produces evidence-backed hypotheses. Localization proposes regions; OCR provides observed text; visual matching supplies candidates; the vision-language model interprets visible evidence and can propose the next useful capture. Each layer must retain its evidence references and distinguish raw output from validated interpretation.

The production inference boundary targets AMD Developer Cloud with ROCm and vLLM. Qualify the actual available AMD GPU, runtime versions, chosen open model revision, multimodal request behavior, licensing/access conditions, memory budget, and measured latency before claiming compatibility. No particular GPU/runtime/model combination is selected or certified by this foundation.

Local development may use the existing two RTX 4080 SUPER GPUs and working PyTorch 2.9.0/CUDA 12.8 environment. That path supports development and comparison; it cannot satisfy the AMD production integration gate. Model-serving dependencies belong in their own deployment environment, and must not replace or reinstall the working local CUDA/PyTorch stack merely to run the API.

AMD qualification is required early and again for the integrated hackathon demonstration. Mocks keep domain work testable while qualification proceeds, but a mock/local-only demonstration does not complete the production objective. Credentials and private evidence stay out of source control; endpoint configuration and deployment records must contain no secret values.

## Deterministic catalog and decision policy

Only approved, versioned catalog data defines a product BOM, required quantities, valid revisions, allowed substitutions, and compatibility. Visual resemblance, a model's prose, or an optimizer score cannot create an approved substitution. Every plan records the exact input, catalog, policy, and economic versions used.

Visible-condition rules may act only on supported observations. Images cannot establish hidden functionality, electrical safety, internal integrity, or other unobserved properties. Where a policy requires a functional or safety check, the workflow must obtain the relevant external test/review result or keep the component ineligible for that use.

Model confidence language and raw scores are not calibrated probabilities. Store their source and meaning without relabeling them as a probability of correctness. Any future calibrated score requires a stated target, representative held-out evaluation, a method, and a version; it still does not replace compatibility policy or required review.

Models and agents may propose observations, questions, summaries, or draft explanations. They cannot directly approve compatibility, reserve stock, override policy, or authorize kit completion. Explanations are checked against deterministic results and must expose missing information instead of inventing evidence.

## Recovery optimization and economics

The CPU CP-SAT model chooses assignments of unique eligible components to candidate kits. Hard constraints cover component exclusivity, complete BOM quantities, approved revisions/substitutions, visible-condition eligibility, current availability, and applicable operational capacities. Economic preference is an objective, never a mechanism for bypassing those constraints.

Economic inputs should make recovered value, repair/inspection/assembly labor, replacement parts, logistics, disposal or alternative recovery value, and capacity assumptions explicit where relevant. Distinguish measured prices/costs from estimates, state currency and units, and avoid double-counting common costs when comparing alternatives.

Use documented integer units and rounding for CP-SAT quantities and money, with range checks on coefficients and accumulated values. Capture input snapshot hashes/versions, solver version, configuration, seed, worker count, and time limit. Report solver status, feasible objective value, best bound, and a clearly defined absolute/relative gap when available. A time-limited feasible solution is not a proven optimum; infeasible, unknown, and failed runs need distinct handling. Parallel search and time limits can affect reproducibility even with a fixed seed.

Alternatives must remain feasible against the same stated input snapshot. Show the operational trade-offs and changes in assumptions that lead to different allocations. Record the candidate plan and deterministic explanation data before requesting approval.

## Approvals, inventory, and audit

An approval binds an actor and decision to a specific plan version, component allocation, evidence state, catalog/policy versions, and economics. A later change does not inherit approval automatically. Define roles and authorization when workflow endpoints are implemented; a local health endpoint is not an authorization system.

Optimization runs outside the inventory write transaction against a versioned snapshot. On reservation, a short transaction checks that the approved plan remains current and each required component is eligible and available, reserves all required identities, and appends the audit record. Any failed check rolls back the entire reservation. Never partially reserve a kit or hold a write lock while invoking a model or solver.

SQLite persistence must enforce at most one active allocation for a physical component using database constraints and guarded state transitions, not application prechecks alone. Planned safeguards include explicit transactions, enabled foreign-key enforcement, a bounded lock/busy policy, checked affected-row counts, and stale-version/conflict responses. The exact schema and journal configuration are intentionally deferred.

Inventory mutations and their audit records commit together. State transitions should support idempotency keys for retried commands, actor/time/reason attribution, and explicit reservation expiry/release behavior. The rebuild/verification flow rechecks the actual reserved identities before consumption, creates completed-kit inventory once, and preserves component lineage. A failed completion must not both consume components and leave them available.

Database concurrency tests must demonstrate that competing reservations cannot allocate the same identity, stale approvals fail, retries do not duplicate mutations, and failure rolls back both inventory and audit state. An application-level append-only audit policy aids traceability; it is not a claim of cryptographic tamper evidence or immunity to privileged database edits.

## Evaluation and operational boundaries

Evaluation will track localization, OCR, candidate matching, identity association, evidence-request usefulness, visible-condition limitations, and human correction rates on appropriately labeled evidence. Separately test compatibility rules, solver feasibility/economics, reservation concurrency, and completed-kit lineage. Avoid evaluation leakage across views of the same physical item or return. Record dataset, policy, model, and runtime versions with results.

AMD benchmarks must report the actual hardware/runtime/model, request shapes, image sizes, concurrency, latency, memory use, and failure rate under the tested workload. An inference benchmark is separate from an end-to-end decision quality result. The implementation roadmap defines when these measurements become required.

Future operational work includes request/correlation IDs, structured logs without secrets or raw private evidence, access control, evidence retention and deletion policy, backup/restore validation, and bounded failure/retry handling. Keep health semantics narrow: `GET /health` reports that the API process can respond. Future inference readiness and database readiness checks require distinct contracts and must not be implied by today's health result.

Evolus is optional. It may coordinate approved application operations through authenticated, validated APIs, but cannot become a second source of inventory state or bypass human approval, deterministic policy, evidence provenance, or reservation transactions. The complete core workflow must remain operable without it.
