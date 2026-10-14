# ReKit architecture

ReKit recovers complete product kits from incomplete returns. Its planned workflow combines traceable visual evidence, approved product rules, deterministic recovery planning, human decisions, and transactional inventory. AMD Developer Cloud inference is a required part of the hackathon delivery.

## Current implementation status

FastAPI exposes `GET /health`, the [operator workflow API](api-workflow.md), and authenticated visual inspection. SQLite persists intake, immutable managed images and evidence provenance, version-checked human verification, and atomic inventory execution. CPU CP-SAT enforces complete BOMs, approved compatibility, unique components, labor, demand, and explicit scenario economics. The React/TypeScript/Vite workspace supports intake, AI-assisted review, human correction, planning, reservation, completion, and lineage inspection.

Mission 03 adds a real local Transformers provider using the pinned Qwen3-VL-2B-Instruct checkpoint, strict output contracts, append-only inference runs, background execution, polling, rejection, and additional-view uploads. Real CUDA smoke and authenticated API execution have been measured. Model files remain ignored; no AMD runtime, dataset, or container is included. The configured factory explicitly opts into local inference and otherwise preserves manual review. AMD ROCm/vLLM qualification and optional Evolus integration remain future work. See [local inference](local-inference.md), [inference evidence](inference-evidence.md), [domain contracts](domain-contracts.md), [recovery planning](recovery-planning.md), and [inventory execution](inventory-workflow.md).

Mission 03 Tasks 1–4 were committed and pushed. Task 5's local integration qualification now passed current-version API acceptance, two complete real-AI browser runs, and the default browser regression using constrained joint generation. Four earlier browser attempts failed strict parsing and appended no model events; the recovery continuation preserved them and reproduced v4 before changing decoding. These narrow synthetic results do not establish product-recognition accuracy or AMD readiness. The [mission report](reports/development-mission-03.md) tracks commit, push, and CI evidence separately.

### Historical Mission 03 local qualification

The two AI browser runs `run-ai-52823ogs` and `run-ai-73rjz6dy` each retained and explicitly rejected unsupported ambiguity hypotheses, then linked human verification to actual run IDs and original uploaded observations. Each completed two kits from four unique components, with four consumed components and four audit events. A further QA repeat passed after waiting for stable screenshot state. Final checks passed 631 backend tests, a 264-test focused inference selection, 48 frontend tests, TypeScript, production build, the installed dependency graph, and synthetic evaluation. See [evaluation results](../evaluation/README.md#final-local-qualification) for artifact paths and timings.

Mission 04 adds an ignored ABO catalog-image collection and separate pending human-review records, actual local before/after evaluation, and schema v2's no-catalog candidate restriction. A real-product browser/API run preserves one simulated unit as unverified and held; separate synthetic recovery regressions still complete two kits. The implemented `openai-remote` adapter has controlled offline qualification only. Actual AMD execution and independently reviewed semantic accuracy remain unmeasured. See the [Mission 04 report](reports/development-mission-04.md).

Mission 06 adds a narrowly allowlisted `amd-tokenfactory` shared-service profile,
explicitly unattested model/processor revisions, cached discovery and a persistent
six-attempt qualification ledger. Three authenticated GETs and two single-image
synthetic POST attempts have run. Both POSTs returned HTTP 400; the diagnostic
replay yielded `invalid_request_error` mentioning the model, without establishing
the cause. The operator initially reported 1 pt remaining; response headers
separately reported limit 1, used 0 and remaining 1 in provider-labelled units.
These units are not converted, and conflicting reset reports remain unresolved.
The catalog's strict-schema flag conflicts with the model reference. Its
`free=false` flag describes consumption of daily capacity, not a paid-billing
verdict. HTTP 400 does not establish that an AMD model ran. No successful
AMD visual inference, hardware/runtime attestation, ABO request, joint-image
request, AMD browser acceptance or paired comparison is claimed. AMD inference
remains a required delivery gate. Local CUDA and generic remote revision pins,
private credentials, deterministic catalog rules, human approval and inventory
authority are unchanged. See the
[Mission 06 checkpoint](reports/development-mission-06.md) and
[TokenFactory procedure](tokenfactory.md).

The [recording workflow](demo-recording-workflow.md) keeps the demonstrated local
NVIDIA inspection, separate synthetic CPU recovery and pending AMD qualification
explicit. A recording plan or successful launcher run is not a finished video.

## Repository boundaries

The editable [presentation architecture figure](assets/rekit-architecture.svg)
shows the implemented logical decision flow and the pending AMD deployment path.
It distinguishes checked output structure/provenance from unverified visual
claims. It is a module/workflow view, not a claim that each box is a microservice.

| Location | Responsibility |
| --- | --- |
| `frontend/` | React, TypeScript, and Vite operator workbench for image intake, human review, scenario planning, approval, execution, and lineage. |
| `backend/src/rekit/api/` | HTTP routing and request/response translation, wired by `backend/src/rekit/main.py`. Routes delegate to evidence and inventory operations; the default app leaves workflows unconfigured. |
| `backend/src/rekit/inference/` | Model-neutral contracts, strict parsing, immutable runs, provider interface, bounded background service, and human rejection. Separate localization/OCR/matching stages remain planned. |
| `backend/src/rekit/inference/adapters/` | Actual local Transformers/CUDA inference and bounded HTTPS remote transport with offline qualification. Actual AMD ROCm/vLLM execution remains unqualified. Both preserve the same service and evidence contracts. |
| `backend/src/rekit/evidence/` | Physical identities, registered returns, managed image assets, append-only observations/proposals/uncertainty, and human verification. Derived crop lineage remains planned. |
| `backend/src/rekit/catalog/` | Approved products, BOM revisions, allowed substitutions, compatibility constraints, and visible-condition policies. |
| `backend/src/rekit/recovery/` | Deterministic feasibility, CPU OR-Tools CP-SAT allocation, economic assumptions, and comparisons of feasible alternatives. |
| `backend/src/rekit/workflows/` | Planned richer review/rebuild/rework orchestration; current approval and completion operations live with transactional inventory. |
| `backend/src/rekit/inventory/` | Transactional persistence, availability, reservation, consumption, release, and audit records. SQLite is the current storage engine. |
| `backend/src/rekit/integrations/evolus/` | Optional Evolus integration through application contracts; absent by default. |
| `tests/backend/` | Health, domain, auth, assets, inference parsing/lifecycle/provenance, compatibility, recovery correctness, transactional inventory, and HTTP tests. Inference test doubles are explicitly separate from GPU qualification. |
| `frontend/src/` | The operator interface and Vitest/Testing Library component tests with mocked HTTP boundaries. |
| `frontend/e2e/recovery.spec.ts` | Playwright acceptance through the actual UI and loopback backend, with independent HTTP assertions for images, negative cases, two-kit planning, reservations, completion, and audit. Execution results are reported separately. |
| `frontend/e2e/real-product.spec.ts` | One actual joint local inspection of original ABO views through simulated UI intake; verifies source hashes, unverified held state, explicit rejection, duplicate evidence handling and absence of recovery authority. |
| `evaluation/run_synthetic.py` | Synthetic in-process HTTP workflow and controlled CPU CP-SAT/greedy comparisons. |
| `evaluation/run_browser_acceptance.py` | Isolated real-browser acceptance against loopback HTTP, SQLite, and CP-SAT. Default mode excludes inference; explicit real-inference mode adds actual local GPU requests. No browser or model is downloaded. |
| `evaluation/run_vision_smoke.py`, `evaluation/run_api_inference_acceptance.py` | Explicit real local GPU execution through the adapter and authenticated in-process HTTP respectively; excluded from CPU CI. |
| `evaluation/run_structured_qualification.py` | Controlled actual local GPU experiment with fixed-order joint label views and a separate ambiguous image; preserves raw outputs and strict validation results, separately from API/browser acceptance. |
| `evaluation/` | Synthetic fixtures, bounded ABO acquisition/evaluation and independent-review tooling. Representative reviewed perception benchmarks and actual AMD performance qualification remain future work. |
| `deploy/amd/` | Implemented remote configuration contract, deployment activation gates, and runtime/model compatibility requirements; no AMD deployment is claimed. |
| `docs/` | Architecture decisions, implementation sequence, and acceptance gates. |
| `.github/workflows/ci.yml` | CPU-only Python and frontend checks using pinned official Actions. A local pass does not establish the remote CI result. |

Keep one modular backend until measured operational needs justify separate services. Directory boundaries do not require separate processes, databases, queues, or package distributions.

## Dependency direction and authority

The API translates transport inputs and delegates to evidence, asset, inference, catalog, recovery, and inventory services. Future workflow orchestration will coordinate those boundaries through explicit contracts. The frontend and optional Evolus integration use application APIs; neither receives direct database or model-runtime authority.

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

These steps describe the complete target workflow. The API/UI implement image-file intake, local VLM observations and additional-view requests, and the human-confirmed evidence-to-completion path. Camera control, derived crops, separate localization/OCR/matching stages, richer rebuild instructions, external functional tests, and supervised partial-plan recovery remain planned. The health endpoint certifies none of these capabilities.

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

The production boundary targets AMD Developer Cloud with ROCm and vLLM. The actual local provider uses Qwen3-VL-2B-Instruct revision `89644892e4d85e24eaac8bacfd4f463576704203` on one explicit NVIDIA GPU. Its verified files total 4,266,640,306 bytes under the pinned Apache-2.0 model declaration. The remote adapter is implemented and tested offline; no actual AMD hardware/runtime combination is qualified. Verify actual cloud hardware, Linux/ROCm/vLLM versions, model/license, image behavior, memory, and workload quality before claiming AMD readiness.

`openai-remote` uses a server-owned exact HTTPS allowlist, verified TLS, original-byte base64 image inputs, bounded requests/responses and an isolated standard-library worker with an absolute deadline. It requests strict JSON Schema and independently checks the compact output contract. It makes no automatic retries or model fallback. Model/processor revisions are configured declarations; a response model-ID match does not attest weights, runtime or AMD hardware. Input hashes identify the bytes encoded by ReKit, not proof of remote vision execution. Credentials never enter client configuration or run provenance. See the [remote contract and activation gate](../deploy/amd/README.md#remote-configuration-and-provenance).

`InferenceStore.begin()` binds managed inputs to the physical component, return, original hashes, source observations, evidence version, actor and server configuration. `InferenceService` reads integrity-checked bytes through `ImageAssetStore`, calls `VisionProvider.inspect()`, verifies provenance, and strictly parses actual model text. It accepts no client model/path/URL overrides and holds no SQLite transaction during inference. Optional model packages and GPU initialization remain lazy; CPU-only startup works without them.

`InspectionOutput` separates visible observations, identity hypotheses, uncertainties, and additional-view requests with ordered image references. `InferenceStore.finish()` atomically stores the terminal outcome and, only for current successful output, model observations/proposals and a mandatory review flag. Evidence or allocation changes and image integrity failures prevent stale output from being applied. The full run records multi-view lineage; a legacy proposal may link to one observation. Possible visible damage remains an unverified claim; only human verification asserts condition.

The immutable run records model/runtime identity, prompt version and hash, preprocessing, ordered input hashes, generation/decoder settings, schema version/hashes, actual outcome, and bounded raw text. The current local configuration `rekit-inspection-v5-constrained` uses LM Format Enforcer 0.11.3 with `rekit-inspection-schema-v2` and at most 512 generated tokens. Schema v2 forbids candidates when no catalog is supplied; strict parsing independently enforces that admitted permission on untouched output. Historical Mission 03 acceptance used schema v1. The prompt text remains unchanged from v4. Optional LMFE/interegular imports remain lazy and separate from CPU API dependencies. Generation still uses one joint image request, not hidden per-image calls or invented source assignments.

The grammar bounds records and text to fit the generation budget, pairs revision and marking fields, and forbids extra keys. It does not establish semantic truth or replace domain validation. The two-case experiment passed structure but still invented `body/A` on an illustration and produced a bounded, unfinished explanation on the label fixture. Preserve these limitations, original raw output, and explicit human rejection/correction. A future AMD decoder must qualify equivalent contract/error/provenance behavior on its own runtime; local LMFE support is not an AMD compatibility claim.

The local cooperative generation deadline remains 120 seconds and the request deadline 150 seconds. Remote requests have a configured budget of at most 120 seconds, plus 15 seconds for the service deadline; worker cleanup cannot prove server-side cancellation. Historical v1/v2 prompt runs retain their 384-token settings. One process-local slot admits work with no queue; timed-out computation retains its slot until return, late results are discarded, and crash-orphaned pending records are not automatically resumed. Exact retries remain actor-bound. The UI polls and exposes uncertainty, source evidence, and history. Candidate selection only prefills identity; explicit human verification is still required. Rejection records an operator hold without erasing the run.

Historical API qualification exposed an unsupported adapter revision claim from a synthetic shapes image. The current constrained path still produced an unsupported body/revision hypothesis on an illustration; complete browser acceptance rejected that output before separate operator verification against original synthetic fixture evidence. That scripted action does not create independent human truth labels. Structural validation cannot establish semantic truth, calibrated confidence, or product accuracy. Independently labelled product-photo evaluation is still required. See [measured local results](local-inference.md) and the [AMD handoff](../deploy/amd/README.md#exact-integration-points).

Local execution preserves the two RTX 4080 SUPER GPUs and working PyTorch 2.9.0/CUDA 12.8 environment; each request uses one selected GPU. This cannot satisfy the AMD delivery gate. ROCm/vLLM serving dependencies belong in a separate Linux environment and must not replace local CUDA packages. Remote model-service credentials remain separate from operator bearers.

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

Automated checks cover CPU planning, HTTP, SQLite, auth, assets, inference contracts/lifecycle, and frontend interactions. Controlled provider/HTTP doubles test software behavior; real CUDA adapter/API runs establish actual image execution. Browser execution is a separate gate whose observed results must be reported independently. None of these synthetic cases measures representative recognition accuracy or AMD performance. Future evaluation needs independently labelled physical items, return-separated splits, unsupported-claim rates, identity/revision errors, useful recapture, and human correction outcomes alongside deterministic correctness.

`evaluation/run_browser_acceptance.py` manages temporary synthetic state, credentials, images, and loopback services. Default mode exercises the real UI and independent HTTP checks without model execution or hardcoded plans. The explicit real-inference mode adds actual local model requests; generated images remain synthetic and human-role test automation does not establish physical assembly or safety. CPU GitHub Actions jobs do not download/load models or run GPU/browser acceptance. See [evaluation instructions](../evaluation/README.md) for separate runners and artifact handling.

AMD benchmarks must report the actual hardware/runtime/model, request shapes, image sizes, concurrency, latency, memory use, and failure rate under the tested workload. An inference benchmark is separate from an end-to-end decision quality result. The implementation roadmap defines when these measurements become required.

Future operational work includes broader request correlation, sanitized structured logs, deployment access controls, evidence retention/deletion, backup/restore validation, and distributed inference scheduling or pending-run recovery when needed. Current inference already bounds admission, deadlines, and replay. `GET /health` remains API liveness; authenticated `/inference/status` separately reports provider status and busy state. Neither is a product-accuracy or AMD qualification assertion.

Evolus is optional. It may coordinate approved application operations through authenticated, validated APIs, but cannot become a second source of inventory state or bypass human approval, deterministic policy, evidence provenance, or reservation transactions. The complete core workflow must remain operable without it.
