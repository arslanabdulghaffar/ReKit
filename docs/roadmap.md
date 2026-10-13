# ReKit implementation roadmap

## Completed local workflow

Overnight Mission 01 developed and validated the existing foundation, domain and
compatibility contracts, SQLite evidence history, CPU CP-SAT recovery planning,
transactional inventory, operator-confirmed APIs, and synthetic integration and
economic evaluation. Each mission task has its own reviewed commit and verified
push. The original foundation-only stop gate was superseded by that mission.

Mission 02 Tasks 1-3 add named human/service actors and explicit roles, bounded
JPEG/PNG/WebP ingestion with immutable provenance, integrity-checked private
image retrieval, and the connected React/TypeScript/Vite operator workspace.
The UI supports intake, multiple views, human verification and correction,
explicit economic assumptions, actual CPU planning, approval/reservation,
completion, inventory, and audit inspection. It does not preload successful
planner output or run a vision model.

These increments preserve the backend authority boundaries. AMD cloud credits
remain pending. Local tests, synthetic images, CPU optimization, and browser
acceptance do not establish AI accuracy or AMD inference readiness. Record local
and GitHub Actions results separately; configuring CI does not mean it ran or
passed. The following items are future work, not additional Mission 02 scope.

## 1. Traceable local perception contracts

Introduce the smallest real perception slice behind the existing inference
boundary, using managed assets and preserving the working local PyTorch/CUDA
environment. Define an inference-run manifest linking exact image hashes,
physical identity, source observations, evidence version, model/runtime revision,
preprocessing, prompt/schema version, settings, and outcome. Add explicit
contracts for localization/crop lineage, model-condition evidence, and useful
additional-view requests as the chosen slice needs them.

Existing model-source observations, identity proposals, and uncertainty flags
remain unverified evidence. Do not put model condition output into human
verification, count detections as new physical stock, or call model scores
calibrated probabilities. Malformed output, insufficient evidence, and late
results need visible failure/review paths.

Acceptance: a real local image request produces traceable hypotheses for human
review, including an ambiguous case and a safe failure. Local NVIDIA success
supports development but does not satisfy the AMD delivery gate. See the
[exact integration points](../deploy/amd/README.md#exact-integration-points).

## 2. AMD inference qualification: required delivery gate

When cloud access and resource use are authorized, qualify a specific AMD GPU,
Linux/ROCm/vLLM runtime, and compatible open vision-language model. Verify access,
license, immutable model revision, image request format, memory fit, and real
request behavior. Keep the current Windows CUDA environment separate.

Implement a narrow adapter that produces traceable observations and hypotheses.
Record timeouts, malformed outputs, refusal/uncertainty, runtime/model provenance,
and representative measured results. No model may set compatibility, calculate
financial results, reserve inventory, or grant human approval.

Run this qualification as soon as access and resource use are authorized; do not
leave it until the end of the hackathon. Acceptance: real image requests succeed
on the selected AMD deployment and enter the evidence review workflow with a
reproducible manifest and measured smoke benchmark. A mock, CPU planner, or
NVIDIA-only result cannot pass this gate.
See [AMD deployment](../deploy/amd/README.md).

## 3. Layered perception and evidence requests

Extend qualified adapters with localization, OCR, visual matching, and VLM
interpretation where each layer improves measured outcomes. Show evidence-linked
hypotheses and request useful close-ups through the existing operator workspace.
Camera control and structured additional-view requests are not implemented yet.

Acceptance: multiple views preserve physical identity, ambiguity is actionable,
corrections retain provenance, and visual evidence is never presented as proof of
hidden function or safety. Raw model confidence remains an uncalibrated score.

## 4. Execution, evidence custody, and operational completeness

Add approved BOM-driven rebuild instructions, required external functional/safety
checks, supervised partial-plan recovery, and explicit post-completion rework.
Define catalog migrations, reservation expiry, shared labor/demand accounting,
authenticated deployment, request limits, logging, and backup/restore procedures
as concrete use cases require them. Add evidence retention/deletion rules,
derived-artifact lineage, and tested database-plus-image backup/restore. Hashes
establish byte identity, not physical-object uniqueness or hidden safety.

Acceptance: failure and interrupted-work paths preserve component custody and
lineage without undoing consumed inventory or silently inheriting stale approval.
Real merchant or payment integrations require separate scope and authorization.

## 5. Representative evaluation and integrated AMD demonstration

Collect reviewed evidence with splits by physical item and return. Measure
perception errors, uncertainty handling, human corrections, and workflow outcomes
separately from constraint correctness. Record actual AMD hardware/runtime/model,
request shapes, memory, latency, and failures. Compare assumptions using scenario
values until real economic outcomes are measured.

Acceptance: the complete workflow runs with real AMD inference, deterministic
catalog/financial decisions, human approval, atomic execution, and reproducible
quality/performance evidence. Do not infer business uplift from synthetic cases.

## 6. Optional Evolus integration

After the core workflow works, connect Evolus through authenticated application
commands for bounded orchestration. It cannot bypass operator roles, policy,
evidence provenance, or transactional inventory checks. The core workflow must
remain usable without Evolus, and this work cannot delay the required AMD demo.

## Implementation discipline

Keep one modular backend unless measured needs justify separate infrastructure.
Add dependencies only for real use cases; preserve the working local environment.
Every future increment needs focused tests and a reviewable scope. This roadmap
is a plan, not authorization to download models, spend cloud credits, or start
Mission 03. AMD inference remains required for the complete hackathon system.
