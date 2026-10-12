# ReKit implementation roadmap

This roadmap describes the original delivery sequence. Overnight Mission 01 now authorizes seven sequential, separately tested and published increments: foundation validation, domain contracts, evidence persistence, CPU optimization, transactional inventory, API integration, and final evaluation. The foundation and domain contracts are implemented. The mission explicitly allows CPU backend development while AMD cloud credits are pending; its ordering supersedes the earlier requirement below to qualify AMD before implementing the optimizer. AMD qualification remains mandatory before claiming inference readiness or completing the AMD demonstration. No paid cloud use or model download is authorized in this mission.

## 1. Foundation: current task

- Inspect the real repository, Git state, existing Python virtual environment, and Node.js availability before choosing files or dependencies.
- Establish separated backend packages, frontend placeholder documentation, evaluation and AMD deployment boundaries, optional Evolus integration boundary, and safe environment examples.
- Implement `GET /health` and its automated test using the existing `.venv`.
- Document identity, evidence, deterministic policy, transaction, human review, and AMD delivery invariants.
- Preserve the working PyTorch/CUDA environment. Add only dependencies needed by the minimal API and its test.

Acceptance: the health test and a local HTTP smoke check pass in `.venv`; the dependency state remains consistent; no model/dataset/container is downloaded; no frontend product screen or later domain feature is implemented. The completion report records validation commands, created files, dependency changes, blockers, and Git status. Stop for review before Task 2.

## 2. Evidence and approved catalog contracts: recommended next task

Define typed domain contracts for physical-component identity, capture/evidence references, provenance, observations, human corrections, and explicit ambiguity. Define approved BOM/revision, compatibility, substitution, and visible-condition policy contracts with version identifiers. Keep storage and perception mocked so the invariants can be validated independently of model quality.

Use a small synthetic fixture to demonstrate one physical component with several observations, ambiguous candidates requiring a further capture, and an explicitly rejected incompatible revision. Establish that an additional image does not create additional stock and that unknown facts cannot silently become approved facts.

Acceptance: meaningful domain tests cover uniqueness, evidence lineage, correction history, versioned deterministic compatibility, unresolved ambiguity, and the inability of model output to override policy. Do not introduce a database schema, solver, or full UI merely to define these contracts.

## 3. AMD inference qualification: mandatory early integration gate

Begin this separate workstream alongside the contract work, once authorized. Confirm the available AMD Developer Cloud GPU and qualify a specific open vision-language model with ROCm/vLLM. Check model access/license terms, exact runtime and model revisions, image input behavior, memory fit, and a representative request before expanding the inference integration.

Create a narrow inference adapter against the evidence contracts, bounded timeouts/errors, redacted configuration examples, a reproducible deployment record, and a measured smoke benchmark. Keep local CUDA development and AMD serving environments independent.

Acceptance: a real image request succeeds on the chosen AMD deployment and produces a traceable observation through the adapter, with recorded hardware, runtime/model versions, latency, memory measurements, and known limitations. Local CUDA success or a mock response does not pass this gate. If access or compatibility is blocked, record the blocker explicitly; do not claim the AMD path is ready.

This gate must pass before committing to recovery optimizer integration and before the final demonstration. Model and runtime selection remains open until qualification evidence exists.

## 4. Layered capture and perception

Implement intake and original-evidence preservation, derived crop lineage, component localization, OCR, candidate visual matching, and vision-language observations through the qualified adapter boundary. Add targeted requests for additional views and human correction of uncertain associations.

Add the first frontend capture/review screens only after the capture and evidence API contracts stabilize. Select frontend testing tools based on the actual interaction and accessibility requirements.

Acceptance: multiple views of the same component preserve its identity; each observation is traceable to source evidence and a model/human actor; ambiguity remains actionable; no score is mislabeled as a calibrated probability. Describe visible condition without asserting hidden function or safety.

## 5. Transactional inventory and policy enforcement

Design the initial SQLite schema from the approved contracts. Implement deterministic eligibility checks, availability, explicit state transitions, and atomic reservation/release commands with audit records. Add input version checks, database-enforced active-allocation uniqueness, foreign-key checks, idempotency, bounded lock handling, and clear conflict responses.

Acceptance: integration tests with competing database connections prove that a component cannot enter two active allocations, a failed reservation leaves no partial allocation/audit state, stale snapshots are rejected, and retries cannot double-apply commands. Demonstrate backup/restore before relying on persisted demonstration data.

## 6. CPU recovery planning and economic comparisons

After the AMD qualification gate, implement OR-Tools CP-SAT against versioned inventory/catalog/evidence snapshots. Add complete-kit BOM constraints, component exclusivity, approved substitutions, operational capacity limits, and explicit integer-scaled economic inputs. Produce feasible alternatives with deterministic explanations.

Acceptance: small cases with known answers validate feasibility and economic accounting; no input identity is consumed twice; solver status, bound, gap, time limit, and reproducibility metadata are reported honestly. An infeasible or time-limited run produces an appropriate result instead of an unsupported optimum claim. Sensitivity examples show how documented costs or constraints change preferred plans.

## 7. Human review, approval, and rebuild execution

Implement review and correction views, plan comparisons, and approval bound to a specific input/plan version. Add role-aware application commands and revalidate current facts inside the reservation transaction. Generate rebuild instructions from the approved BOM and committed reservations, including holds and rework paths.

Acceptance: evidence/catalog/inventory changes invalidate or force revalidation of affected approvals; a stale plan cannot reserve stock; instructions refer to the actual reserved identities. Neither a language model nor an optional workflow agent can bypass these checks.

## 8. Completion verification and closed-loop inventory

Capture completion evidence and any separately required functional/safety test results. Verify kit content and approved policy requirements, then atomically record component consumption, completed-kit inventory, and audit history. Define release, failed verification, and interrupted-work behavior.

Acceptance: completion is idempotent, records full component-to-kit lineage, and cannot simultaneously leave consumed parts available. Visual confirmation alone cannot satisfy a required hidden-property test.

## 9. Evaluation, AMD deployment hardening, and demonstration

Build a versioned evaluation set with realistic ambiguity and cross-return scenarios, separating items/returns across evaluation splits. Evaluate perception quality, correction burden, deterministic policy outcomes, solver results, and concurrency separately. Measure the integrated system on the actual AMD deployment and document observed limits.

Add necessary logging/correlation, secret management, access control, retention, failure handling, and deployment/restore documentation. Prepare a repeatable end-to-end demo that shows evidence capture through verified kit inventory, including at least one ambiguity and review path.

Acceptance: the complete core workflow runs with real AMD inference, deterministic decisions, an auditable approval/reservation chain, and measured performance. Demonstration claims match evaluation evidence. There are no hardcoded secrets or unsupported claims of confidence calibration, compatibility, functionality, or safety.

## 10. Optional Evolus integration

Only after the core workflow is usable, connect Evolus to documented application commands for bounded orchestration. Preserve human approvals and the same policy/transaction guards used by the UI/API.

Acceptance: the workflow remains usable without Evolus; duplicate/retried agent actions are safe; no agent has direct inventory mutation or policy-override authority. This increment is optional and cannot delay the required AMD core demonstration.

## Implementation discipline

Each increment should add only the dependencies and tests its behavior requires. Record changes to assumptions and architecture as they become concrete. Keep infrastructure, broad abstractions, and extra services deferred until an actual use case justifies them. Model downloads, cloud provisioning, broader environment changes, and publishing belong to explicitly authorized future work; none are part of the current foundation task.
