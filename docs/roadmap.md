# ReKit implementation roadmap

## Completed local backend scope

Overnight Mission 01 developed and validated the existing foundation, domain and
compatibility contracts, SQLite evidence history, CPU CP-SAT recovery planning,
transactional inventory, operator-confirmed APIs, and synthetic integration and
economic evaluation. Each mission task has its own reviewed commit and verified
push. The original foundation-only stop gate was superseded by that mission.

These increments preserve the modular backend architecture. They do not complete
the capture/perception workflow or establish AMD inference readiness. The mission
allowed local CPU development while AMD credits were pending; AMD remains a
required integration gate before the complete hackathon demonstration.

## 1. Authenticated operator authority: smallest next task

Bind verification, correction, approval, cancellation, and completion to an
authenticated operator identity and explicit roles. Preserve the existing
idempotency, version checks, and audit records. Do not accept a request body as
proof of human identity or authorize an inference adapter to approve itself.

Acceptance: unauthorized requests cannot mutate evidence approvals or inventory;
authorized operators can complete the existing synthetic workflow; audit actors
come from the authenticated context. Keep this separate from product UI work.

## 2. Evidence assets and accountable capture

Add bounded evidence ingestion with content hashes, immutable asset references,
capture metadata, and derived crop lineage. Preserve stable physical identities
across multiple views and explicitly review suspected duplicate registration.
Introduce deletion/retention rules and test backup/restore before real evidence is
relied on. Files and customer data stay out of Git.

Acceptance: observations resolve to preserved assets; repeated bytes do not imply
new physical stock; missing or invalid assets require review. Hashes establish
byte identity, not physical-object uniqueness or hidden safety properties.

## 3. AMD inference qualification: required delivery gate

When cloud access and resource use are authorized, qualify a specific AMD GPU,
Linux/ROCm/vLLM runtime, and compatible open vision-language model. Verify access,
license, immutable model revision, image request format, memory fit, and real
request behavior. Keep the current Windows CUDA environment separate.

Implement a narrow adapter that produces traceable observations and hypotheses.
Record timeouts, malformed outputs, refusal/uncertainty, runtime/model provenance,
and representative measured results. No model may set compatibility, calculate
financial results, reserve inventory, or grant human approval.

Acceptance: real image requests succeed on the selected AMD deployment and enter
the evidence review workflow with a reproducible manifest and measured smoke
benchmark. A mock, CPU planner, or NVIDIA-only result cannot pass this gate.
See [AMD deployment](../deploy/amd/README.md).

## 4. Layered perception and the first operator interface

Add localization, OCR, visual matching, and VLM interpretation through qualified
adapters. Request useful close-ups for unresolved identities. Build the first
React/TypeScript/Vite capture and review slice against stable APIs, selecting
frontend test tools when actual interactions exist.

Acceptance: multiple views preserve physical identity, ambiguity is actionable,
corrections retain provenance, and visual evidence is never presented as proof of
hidden function or safety. Raw model confidence remains an uncalibrated score.

## 5. Execution and operational completeness

Add approved BOM-driven rebuild instructions, required external functional/safety
checks, supervised partial-plan recovery, and explicit post-completion rework.
Define catalog migrations, reservation expiry, shared labor/demand accounting,
authenticated deployment, request limits, logging, and backup/restore procedures
as concrete use cases require them.

Acceptance: failure and interrupted-work paths preserve component custody and
lineage without undoing consumed inventory or silently inheriting stale approval.
Real merchant or payment integrations require separate scope and authorization.

## 6. Representative evaluation and integrated AMD demonstration

Collect reviewed evidence with splits by physical item and return. Measure
perception errors, uncertainty handling, human corrections, and workflow outcomes
separately from constraint correctness. Record actual AMD hardware/runtime/model,
request shapes, memory, latency, and failures. Compare assumptions using scenario
values until real economic outcomes are measured.

Acceptance: the complete workflow runs with real AMD inference, deterministic
catalog/financial decisions, human approval, atomic execution, and reproducible
quality/performance evidence. Do not infer business uplift from synthetic cases.

## 7. Optional Evolus integration

After the core workflow works, connect Evolus through authenticated application
commands for bounded orchestration. It cannot bypass operator roles, policy,
evidence provenance, or transactional inventory checks. The core workflow must
remain usable without Evolus, and this work cannot delay the required AMD demo.

## Implementation discipline

Keep one modular backend unless measured needs justify separate infrastructure.
Add dependencies only for real use cases; preserve the working local environment.
Every future increment needs focused tests and a reviewable scope. This roadmap
is a plan, not authorization to download models, spend cloud credits, or continue
beyond the completed overnight mission.
