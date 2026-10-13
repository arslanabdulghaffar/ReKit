# ReKit architecture

ReKit recovers complete product kits from incomplete returns. Its planned workflow combines traceable visual evidence, approved product rules, deterministic recovery planning, human decisions, and transactional inventory. AMD Developer Cloud inference is a required part of the hackathon delivery.

## Current implementation status

FastAPI exposes `GET /health` and the [operator-confirmed workflow API](api-workflow.md). Catalog/BOM/compatibility and evidence/identity/eligibility domain contracts are implemented and tested. SQLite persists intake and append-only evidence history, with authenticated, version-checked human verification. Managed JPEG/PNG/WebP assets have immutable provenance and integrity-checked private retrieval. CPU CP-SAT recovery planning enforces complete BOMs, compatibility, component uniqueness, labor, demand, and disposition policy using integer scenario economics. SQLite inventory execution supports versioned proposals, atomic approval/reservation, cancellation, and operator-confirmed completion. The React/TypeScript/Vite operator workbench calls these same APIs for intake, review, planning, execution, and lineage inspection. No model, dataset, container, or inference deployment is included. The configured app factory reads local catalog, policy, database, credential, and evidence-storage paths; inference and Evolus variables remain future configuration. See [domain contracts](domain-contracts.md), [evidence persistence](evidence-provenance.md), [recovery planning](recovery-planning.md), and [inventory execution](inventory-workflow.md) for the current boundaries.

## Repository boundaries

| Location | Responsibility |
| --- | --- |
| `frontend/` | React, TypeScript, and Vite operator workbench for image intake, human review, scenario planning, approval, execution, and lineage. |
| `backend/src/rekit/api/` | HTTP routing and request/response translation, wired by `backend/src/rekit/main.py`. Routes delegate to evidence and inventory operations; the default app leaves workflows unconfigured. |
| `backend/src/rekit/inference/` | Planned perception contracts and orchestration for localization, OCR, visual matching, and vision-language interpretation. |
| `backend/src/rekit/inference/adapters/` | Planned provider-specific implementations. Production targets AMD Developer Cloud with ROCm, vLLM, and a qualified open vision-language model; local PyTorch/CUDA will support development. No inference adapter or mock service is implemented. |
| `backend/src/rekit/evidence/` | Physical-component identity, registered returns, managed image assets, append-only observations, proposals, uncertainty, and human verification. Structured requests for additional views and derived crop lineage remain planned. |
| `backend/src/rekit/catalog/` | Approved products, BOM revisions, allowed substitutions, compatibility constraints, and visible-condition policies. |
| `backend/src/rekit/recovery/` | Deterministic feasibility, CPU OR-Tools CP-SAT allocation, economic assumptions, and comparisons of feasible alternatives. |
| `backend/src/rekit/workflows/` | Planned richer review/rebuild/rework orchestration; current approval and completion operations live with transactional inventory. |
| `backend/src/rekit/inventory/` | Transactional persistence, availability, reservation, consumption, release, and audit records. SQLite is the current storage engine. |
| `backend/src/rekit/integrations/evolus/` | Optional Evolus integration through application contracts; absent by default. |
| `tests/backend/` | Health, domain, authentication, image handling, compatibility, evidence persistence, recovery correctness, transactional inventory, and API workflow tests. |
| `frontend/src/` | The operator interface and Vitest/Testing Library component tests with mocked HTTP boundaries. |
| `frontend/e2e/recovery.spec.ts` | Playwright acceptance through the actual UI and loopback backend, with independent HTTP assertions for images, negative cases, two-kit planning, reservations, completion, and audit. Execution results are reported separately. |
| `evaluation/run_synthetic.py` | Synthetic in-process HTTP workflow and controlled CPU CP-SAT/greedy comparisons. |
| `evaluation/run_browser_acceptance.py` | Isolated synthetic fixture and service lifecycle for real-browser acceptance against loopback HTTP, SQLite, and actual CP-SAT. It generates no model output and downloads no browser. |
| `evaluation/` | Evaluation fixtures and instructions; representative perception datasets and AMD performance qualification remain future work. |
| `deploy/amd/` | Planned reproducible AMD deployment instructions and runtime/model compatibility records. |
| `docs/` | Architecture decisions, implementation sequence, and acceptance gates. |
| `.github/workflows/ci.yml` | CPU-only Python and frontend checks using pinned official Actions. A local pass does not establish the remote CI result. |

Keep one modular backend until measured operational needs justify separate services. Directory boundaries do not require separate processes, databases, queues, or package distributions.

## Dependency direction and authority

The API translates transport inputs and currently delegates to evidence, asset, catalog, recovery, and inventory services. Future workflow orchestration will coordinate those same boundaries through explicit contracts. The frontend and optional Evolus integration use application APIs; neither receives direct database or model-runtime authority.

Evidence and catalog domain rules stay independent of FastAPI, a specific inference SDK, and database details. Inference adapters return observations through perception contracts. Recovery consumes explicit component snapshots and approved catalog/policy versions; it does not infer compatibility by calling a language model. Inventory owns the final transactional checks and state transitions. Concrete runtime and persistence implementations are wired at the application boundary rather than imported into domain rules.

Introduce typed contracts and narrow interfaces when a concrete use case requires them. A generic framework, event bus, or speculative abstraction is not needed for the current local workflow. Keep model runtime packages separate from the API dependency set.

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

These steps describe the complete target workflow. The current API and UI implement image-file intake and the operator-confirmed evidence-to-completion path. Camera control, derived crops, automated perception, structured additional-view requests, richer rebuild instructions, external functional tests, and supervised partial-plan recovery remain planned. The health endpoint certifies none of these capabilities.

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

The production inference boundary targets AMD Developer Cloud with ROCm and vLLM. AMD cloud credits remain pending; no adapter, serving process, or selected GPU/runtime/model combination is implemented or qualified. Qualify the actual available AMD GPU, runtime versions, open model revision, multimodal request behavior, licensing/access conditions, memory budget, and measured latency before claiming compatibility.

The concrete integration starts at `ImageAssetStore.read(asset_id)`, which returns registered metadata and integrity-checked bytes. A future adapter binds those inputs to the component, return, asset hashes, source observations, and evidence version. It must not fetch arbitrary user URLs, consume operator bearer credentials, create physical stock from detections, or run while holding an inventory write transaction.

Existing `Observation`, `IdentityProposal`, and `UncertaintyFlag` contracts can record bounded model-source markings, hypotheses, and uncertainty through append-only evidence methods. They do not yet provide a full inference-run manifest, localization/crop lineage, structured model-condition evidence, or additional-view request contract. In particular, today's visible condition in `OperatorVerification` is a human assertion; it is not a field a VLM can populate with authority. One proposal links to one observation, so future multi-view runs need explicit input lineage rather than invented fields in current schemas.

The next adapter must record immutable model/runtime identity, preprocessing and prompt/schema versions, input hashes, generation settings, outcome, and failure details before its results can be audited. Human review still chooses catalog identity and visible condition against the current evidence version. New model evidence after verification returns the component to review and cannot inherit approval. See the [exact AMD integration points](../deploy/amd/README.md#exact-integration-points) for the current entry points and required future contracts.

Local development may use the existing two RTX 4080 SUPER GPUs and working PyTorch 2.9.0/CUDA 12.8 environment. That path supports development and comparison; it cannot satisfy the AMD production integration gate. Model-serving dependencies belong in their own deployment environment, and must not replace or reinstall the working local CUDA/PyTorch stack merely to run the API.

AMD qualification is required early and again for the integrated hackathon demonstration. Synthetic CPU and domain fixtures keep the deterministic workflow testable while access is pending; they are not model inference and cannot complete the AMD objective. Credentials and private evidence stay out of source control; endpoint configuration and deployment records must contain no secret values.

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

An approval binds an actor and decision to a specific plan version, component allocation, evidence state, catalog/policy versions, and economics. A later change does not inherit approval automatically. The API authenticates server-configured named actors and explicit roles. Verification, approval/cancellation, and completion require human principals; service credentials cannot exercise those gates. Request bodies cannot override audit actor identity. Bearer possession does not prove physical human presence; this remains a local deployment with the limits documented in [operator authentication](operator-auth.md).

Optimization runs outside the inventory write transaction against a versioned snapshot. On reservation, a short transaction checks that the approved plan remains current and each required component is eligible and available, reserves all required identities, and appends the audit record. Any failed check rolls back the entire reservation. Never partially reserve a kit or hold a write lock while invoking a model or solver.

SQLite persistence must enforce at most one active allocation for a physical component using database constraints and guarded state transitions, not application prechecks alone. Implemented safeguards include explicit transactions, enabled foreign-key enforcement, a bounded lock/busy policy, checked affected-row counts, and stale-version/conflict responses. The schema uses exclusive component allocations and append-only audit records; default SQLite journaling is retained.

Inventory mutations and their audit records commit together. State transitions should support idempotency keys for retried commands, actor/time/reason attribution, and explicit reservation expiry/release behavior. The rebuild/verification flow rechecks the actual reserved identities before consumption, creates completed-kit inventory once, and preserves component lineage. A failed completion must not both consume components and leave them available.

Database concurrency tests must demonstrate that competing reservations cannot allocate the same identity, stale approvals fail, retries do not duplicate mutations, and failure rolls back both inventory and audit state. An application-level append-only audit policy aids traceability; it is not a claim of cryptographic tamper evidence or immunity to privileged database edits.

## Evaluation and operational boundaries

Current automated checks cover synthetic CPU planning, API integration, SQLite consistency, authentication, image integrity, and frontend interactions. Mocked HTTP component tests and real-browser checks against the local backend are different evidence; record which actually ran and their results. Neither measures perception accuracy or AMD performance. Future perception evaluation will track localization, OCR, candidate matching, identity association, evidence-request usefulness, visible-condition limitations, and human correction rates on appropriately labeled evidence. Separately test compatibility rules, solver feasibility/economics, reservation concurrency, and completed-kit lineage. Avoid evaluation leakage across views of the same physical item or return. Record dataset, policy, model, and runtime versions with results.

`evaluation/run_browser_acceptance.py` manages temporary synthetic state, credentials, generated test images, and local services for `frontend/e2e/recovery.spec.ts`. The spec uses the real browser UI and independent authenticated HTTP assertions, without mocked routes or hardcoded planner responses. Generated imagery and human-role test automation are explicit test fixtures, not an AI prediction or proof of physical assembly. CPU GitHub Actions jobs run backend and frontend component/type/build/dependency checks; they do not imply that a browser or AMD benchmark ran. See [evaluation instructions](../evaluation/README.md) for the distinct runners and artifact handling.

AMD benchmarks must report the actual hardware/runtime/model, request shapes, image sizes, concurrency, latency, memory use, and failure rate under the tested workload. An inference benchmark is separate from an end-to-end decision quality result. The implementation roadmap defines when these measurements become required.

Future operational work includes request/correlation IDs, structured logs without secrets or raw private evidence, deployment access controls beyond local bearer roles, evidence retention and deletion policy, backup/restore validation, and bounded inference failure/retry handling. Keep health semantics narrow: `GET /health` reports that the API process can respond. Future inference readiness and database readiness checks require distinct contracts and must not be implied by today's health result.

Evolus is optional. It may coordinate approved application operations through authenticated, validated APIs, but cannot become a second source of inventory state or bypass human approval, deterministic policy, evidence provenance, or reservation transactions. The complete core workflow must remain operable without it.
