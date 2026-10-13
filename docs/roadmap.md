# ReKit implementation roadmap

## Completed local workflow

Overnight Mission 01 developed and validated the existing foundation, domain and
compatibility contracts, SQLite evidence history, CPU CP-SAT recovery planning,
transactional inventory, operator-confirmed APIs, and synthetic integration and
economic evaluation. Each mission task has its own reviewed commit and verified
push. The original foundation-only stop gate was superseded by that mission.

Mission 02 adds named human/service actors and explicit roles, bounded
JPEG/PNG/WebP ingestion with immutable provenance, integrity-checked private
image retrieval, and the connected React/TypeScript/Vite operator workspace.
The UI supports intake, multiple views, human verification and correction,
explicit economic assumptions, actual CPU planning, approval/reservation,
completion, inventory, and audit inspection, plus real-browser acceptance. It
does not preload successful planner output.

Mission 03 Tasks 1–4 implement one real local Transformers/CUDA provider using
Qwen3-VL-2B-Instruct revision `89644892e4d85e24eaac8bacfd4f463576704203`,
bounded output contracts, immutable inference provenance, authenticated background
execution and polling, and the AI-assisted review interface. Model-source
observations, hypotheses, uncertainty and additional-view requests remain
unverified. Operators can add views, prefill identity for explicit manual
verification, reject unsupported claims, and preserve correction history.

Two actual CUDA smoke requests and a separate authenticated API request have
been measured. The API result included an unsupported adapter revision claim
from a synthetic illustration; the authority boundary kept inventory held.
Task 4's local gates passed 574 backend and 48 frontend tests. Test doubles,
actual GPU execution, browser acceptance, and remote CI are separate evidence;
none establishes representative recognition accuracy or AMD readiness. See
[local results](local-inference.md) and [evaluation procedures](../evaluation/README.md).

## Local integrated acceptance recovery and remaining quality work

Mission 03 Task 5's local integrated gate passed. It exercised actual inference
through the browser with two labelled views and a separately ambiguous additional
view, explicit human rejection and correction, and the deterministic two-kit
workflow. Current-version API acceptance, two complete AI browser runs, and the
default browser regression passed. Generated errors and the earlier blocked
attempts below remain preserved. No additional model, dataset, or container was
needed for this bounded gate. Commit, push, and CI evidence is tracked separately
in the [mission report](reports/development-mission-03.md).

The first three attempts failed strict parsing: v1 omitted source indices; v2
also exhausted its 384-token budget and returned truncated JSON. The v3 repair
used a shorter source-linked template and 512-token limit, but returned revision
`A` with a null revision marking and copied placeholder prose. All applied zero
model events. Schema and timeouts remain unchanged. Preserve those failures and
record subsequent actual results rather than treating a prompt change as
acceptance.

The final bounded repair, `rekit-inspection-v4`, also failed: its complete
257-token output added a forbidden top-level `image_indices` field. Thus all
four attempts stopped on the first two-image request, before the intended
ambiguous second request and integrated recovery sequence. No model evidence
was applied. Those v4/512-token settings were unqualified; the strict schema
and deadlines were not relaxed.

At the earlier stop, local checks passed 588 backend tests and 48 frontend tests, TypeScript
validation, production build, and the default browser regression. Those passes
do not satisfy the failed real-inference browser gate. The three original prompt
repairs were exhausted, and work stopped. This history remains intact.

A separately authorized recovery continuation reproduced the v4 failure, then
implemented schema-constrained joint generation using optional LM Format Enforcer
0.11.3 and interegular 0.3.3, without changing the model or CUDA environment.
The two direct-provider cases in `var/mission03-recovery/approach1.json` passed
JSON and strict domain validation under `rekit-inspection-v5-constrained` and
`rekit-inspection-schema-v1`. The actual prompt text is unchanged from v4;
the implementation filters tokens and retains the independent domain checks.

The labelled views were attributed to the correct sources, but the ambiguous
illustration still produced an unsupported `body/A` hypothesis. The completed
browser runs retained it, required explicit rejection, and linked subsequent
human verification to actual run IDs and original uploaded observations.

### Final local qualification

Current API reports `api-current.json` and `final-api.json` passed. Complete AI
browser runs `run-ai-52823ogs` and `run-ai-73rjz6dy` each completed two kits with
four consumed components and four audit events; an additional QA repeat
`run-ai-2qrs3sdt` also passed. The default regression `run-ugm19txq` passed in
4.5 seconds. Final checks passed 631 backend tests, a 264-test focused inference
selection, 48 frontend tests, TypeScript, production build, dependency graph,
and synthetic evaluation. The [mission report](reports/development-mission-03.md)
records artifact paths, timings, and screenshot review. This is narrow
integration evidence, not reliable product recognition or a completed AMD
demonstration.

Independently labelled real product photographs are still missing. Establish
held-out evaluation for unsupported identities/revisions, readable markings,
unknown cases, uncertainty, useful additional views, and human corrections.
Literal agreement between a proposed revision and model-quoted text cannot
establish that either was actually visible. Preserve raw output and the human
gate when improving prompts or schemas. Local NVIDIA success supports this
work but does not satisfy the AMD delivery requirement.

## 1. AMD inference qualification: required delivery gate

When cloud access and resource use are authorized, qualify a specific AMD GPU,
Linux/ROCm/vLLM runtime, and compatible open vision-language model. Verify access,
license, immutable model revision, image request format, memory fit, and real
request behavior. Keep the current Windows CUDA environment separate.

Configure and qualify the implemented `openai-remote` provider against the selected
actual AMD endpoint, retaining `InferenceService`, parsing, and `InferenceStore`
authority boundaries. Its offline transport qualification does not establish AMD execution.
Record timeouts, malformed outputs, refusal/uncertainty, runtime/model provenance,
and representative measured results. No model may set compatibility, calculate
financial results, reserve inventory, or grant human approval.

Qualify structured generation on that specific serving stack while preserving
strict domain validation, schema and decoder provenance, original raw outputs,
and exact image attribution. Do not assume the local LMFE integration works on
AMD or that a different decoder proves visual claims correct.

Run this qualification as soon as access and resource use are authorized; do not
leave it until the end of the hackathon. Acceptance: real image requests succeed
on the selected AMD deployment and enter the evidence review workflow with a
reproducible manifest and measured smoke benchmark. A mock, CPU planner, or
NVIDIA-only result cannot pass this gate.
See [AMD deployment](../deploy/amd/README.md).

## 2. Layered perception and evidence requests

Extend qualified adapters with localization, OCR, visual matching, and VLM
interpretation where each layer improves measured outcomes. The existing VLM
already returns structured additional-view requests and the UI supports
recapture on the same physical identity. Measure whether those requests are
useful; camera control, derived crop lineage, and separate OCR/localization/
matching stages remain unimplemented.

Acceptance: multiple views preserve physical identity, ambiguity is actionable,
corrections retain provenance, and visual evidence is never presented as proof of
hidden function or safety. Raw model confidence remains an uncalibrated score.

## 3. Execution, evidence custody, and operational completeness

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

## 4. Representative evaluation and integrated AMD demonstration

Collect reviewed evidence with splits by physical item and return. Measure
perception errors, uncertainty handling, human corrections, and workflow outcomes
separately from constraint correctness. Record actual AMD hardware/runtime/model,
request shapes, memory, latency, and failures. Compare assumptions using scenario
values until real economic outcomes are measured.

Acceptance: the complete workflow runs with real AMD inference, deterministic
catalog/financial decisions, human approval, atomic execution, and reproducible
quality/performance evidence. Do not infer business uplift from synthetic cases.

## 5. Optional Evolus integration

After the core workflow works, connect Evolus through authenticated application
commands for bounded orchestration. It cannot bypass operator roles, policy,
evidence provenance, or transactional inventory checks. The core workflow must
remain usable without Evolus, and this work cannot delay the required AMD demo.

## Implementation discipline

Keep one modular backend unless measured needs justify separate infrastructure.
Add dependencies only for real use cases; preserve the working local environment.
Every future increment needs focused tests and a reviewable scope. This roadmap
is a plan, not authorization to download additional models, spend cloud credits,
or begin another mission. AMD inference remains required for the complete
hackathon system.
