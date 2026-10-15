# ReKit Winning-Quality Improvement Assessment

October 15, 2026 (Asia/Seoul). Assessment baseline:
`86e970ae85d5ab59d264e28d7d5ec0de86b2d854`, the accepted Mission 06 offline
continuation. This is a proposed improvement plan within Missions 01–06, not
Mission 07 or authorization for a major feature, external service or release.

## Recommendation

ReKit has a credible engineering core: uncertain visual claims cannot directly
change compatibility or stock, and recovery plans allocate unique parts under
explicit constraints. Its greatest competitive weaknesses are the absence of
successful AMD execution, limited proof of useful perception, and the gap between
the real-image inspection demonstration and the separate synthetic recovery
demonstration. More screens or models would not resolve those weaknesses.

Prioritize a narrow, reproducible story: show the original evidence, a useful
observation and an honest failure, a human decision, an incompatible alternative,
an economically justified cross-return allocation, and an atomic reservation
with final lineage. Then show that same application's qualified AMD provider
when support and authorization permit it. Independently review the existing
outputs before making quality claims. Preserve the currently working local demo.

The owner expects approximately four days. Use that as a capacity-planning
assumption, with parallel evidence, engineering and recording work; do not treat
it as a verified cutoff or justify rushing consequential changes. The organizer's
[Milan agenda](https://luma.com/AMDHackathon-Milan) explicitly gives an on-site
submission deadline of October 18 at 16:00. Its event metadata uses Europe/Rome,
which converts to **23:00 KST**. Applicability to online submissions is still
unconfirmed. See the [submission checklist](hackathon-submission-checklist.md).

## Judge-focused assessment

The [official event criteria](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii)
are Application of Technology, Presentation, Business Value and Originality;
no numerical weights are published on that page. Meaningful AMD execution in
the demonstrated working product is an eligibility requirement. A failed API
request, local NVIDIA result or offline adapter test cannot satisfy it.
The commerce track is a plausible fit for inventory decisions; final track and
form requirements need owner confirmation. The judgments below are our assessment,
not organizer scores or predictions of winning.

| Perspective | Current strength | Weakness that could limit competitiveness |
| --- | --- | --- |
| Originality | Physical-component allocation across returns combines evidence, approved BOMs and economic alternatives. | Vision, returns routing, human review and audit trails are not individually novel. The precise cross-return decision needs to be demonstrated. |
| AMD integration | Exact provider profile, strict parsing, provenance and persistent attempt guard exist. | Two HTTP 400 results; no successful AMD output or application acceptance. This is the principal eligibility gap. |
| Technical reliability | Domain and transaction boundaries, idempotency, stale-version checks, bounded inference and CPU optimizer are implemented. | Most evidence is local/synthetic; one process-local inference slot and bounded candidate enumeration are prototype limits, not production scale. |
| Commercial value | Explicit cash versus retained value, labor, demand and alternative dispositions are modeled. | No merchant validation, time study, real recovery yield, realized margin or empirical price/test-cost data. USD 175 is fixture output. |
| End-to-end experience | Intake, multiple views, review, correction, planning, reservation, completion and lineage work locally. | Current real-product footage ends in an unverified held component; synthetic kit completion is a separate case. Camera capture, physical testing and rich rebuild work instructions are not implemented. |
| UX and design | Consistent workbench, visible roles/states, original images, model-source references and inventory links. | Key comparisons and superseded decisions require reading detailed text/JSON. This is a review hypothesis, not a measured usability study. |
| Evidence quality | Raw outputs and failures are preserved; original-image hashes and run provenance support audit. | Zero independent semantic reviews. Valid JSON and empty no-catalog candidates do not demonstrate accurate or useful perception. |
| Demonstration | Existing local product and synthetic browser runs, seven-slide deck and a coherent script. | No final movie or judge-accessible app; historical footage and new runs must not share unqualified timings. |
| Differentiation | Deterministic kit allocation can connect uncertain evidence to controlled execution. | No evidence establishes market uniqueness or superiority to commercial reverse-logistics platforms. Compete through a focused proof rather than broad claims. |

## Verified strengths and practical limits

The accepted checkpoint passed 1,449 backend tests and 61 frontend tests,
TypeScript/build, a CPU recovery evaluation and a synthetic browser replay.
Those are prior verified software results, not new measurements from this audit.
The latest synthetic replay reserved four parts and completed two kit records;
the product preflight verified the pinned local environment without inference.

The architecture merits preserving:

- [Evidence contracts](../backend/src/rekit/evidence/models.py) and
  [storage](../backend/src/rekit/evidence/store.py) distinguish physical identity,
  original observations, model assertions and human verification. Corrections
  retain prior events; new views invalidate stale verification.
- [Inference service](../backend/src/rekit/inference/service.py) records bounded
  asynchronous execution without holding a database transaction. Exact replays
  reuse a run; busy/unavailable states remain explicit. The admission slot is
  process-local, so adding web workers would require a separate concurrency design.
- [Compatibility](../backend/src/rekit/catalog/compatibility.py),
  [planner](../backend/src/rekit/recovery/planner.py) and
  [inventory execution](../backend/src/rekit/inventory/execution.py) own decisions
  independently of the LLM. The planner requires one disposition per component,
  enumerates at most 10,000 actions over at most 100 supplied components, and
  reports real solver status/bounds. This is bounded completeness, not a scale claim.
- [Recovery UI](../frontend/src/recovery.tsx) already exposes donor opportunity
  cost, increment versus retention, costs, labor and server explanations.
  [Review UI](../frontend/src/evidence.tsx) already supports explicit supersession
  and role/version checks. These features need a clearer demonstration before
  adding another optimization or workflow framework.
- [Review tooling](../evaluation/product_review.py) already separates independent
  human assessments from model output and reports eligible denominators. Use it
  before building a new evaluation dashboard.

Known omissions are not all hackathon priorities. Dedicated OCR, localization,
catalog-image matching, derived-crop lineage, camera controls, external inventory
connectors, richer assembly instructions and partial-plan rework remain planned.
Completion references are metadata or existing managed assets; the current flow
does not supply post-reservation photo intake or independent functional testing.
A complete software transaction is not proof of a physically safe rebuilt product.

## Relevant approaches and a defensible differentiation claim

The following are current vendor descriptions from primary sources, not
independently verified performance comparisons. These pages cannot prove that
competitors lack a feature or that ReKit is first in the market.

| Approach | Verified public description | Implication |
| --- | --- | --- |
| [Optoro Returns Processing](https://www.optoro.com/returns-processing/) | SmartDisposition routes returned inventory among recovery channels. | Generic recovery optimization is established; show complementary component allocation across returns. |
| [ReverseLogix AI](https://www.reverselogix.com/platform/ai/) | Photo-based proposed grading, rules, human overrides and retained decision history. | Do not claim that vision plus human review plus auditability is unique. |
| [Reconext Repair and Refurbishment](https://www.reconext.com/lifecycle-services/repair-and-refurbishment/) | Parts harvesting, testing, requalification and tracking are described. | Parts reuse is established. ReKit's visual claims cannot replace the physical tests these workflows require. |

A defensible proposition is: **ReKit connects uncertain visual evidence to
BOM-constrained cross-return rebuild alternatives, allocates every physical
component once, explains the economic trade-off and transactionally reserves
the approved parts.** This is a design and demonstration claim, not a patent or
market-uniqueness claim.

An entrant-authored [same-event project page](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii/khlab/why-they-return)
reports an AMD workflow with a labeled benchmark and rule baseline. Its results
were not independently validated here. It illustrates the level of evidence a
competing pitch may present, not that its solution is superior or comparable
on ReKit's task.

## Improvement priorities

Critical means an eligibility, integrity or release gate. High-value means a
substantial improvement to the product proof. Optional work follows those gates.
Estimates below are planning ranges, not promises; owner data, reviewers, hosting
decisions and AMD response time may dominate elapsed time.

| ID / classification | Current weakness and proposed response | Benefit, risk and dependencies | Measurable acceptance criteria |
| --- | --- | --- | --- |
| C1 — Critical | Resolve the AMD contract, qualify exactly one approved synthetic request, then propose application acceptance. | Required AMD evidence; provider-dependent. Never weaken local/domain validation, guess routes, change models or spend the remaining budget speculatively. Integration is not complete after a direct probe alone. | Original 2/6 attempts preserved; provider answer and payload diff recorded; fresh quota and new approval before a call; strict valid response with latency/input/model/quota provenance; separately authorized application run preserves unverified evidence, human authority and inventory rules. |
| C2 — Critical before release | Freeze the exact source/media candidate, confirm form/cutoff and decide license, visibility and judge access. | Avoid an ineligible or inaccessible submission. External hosting/publication and security decisions need owner approval. | Explicit online cutoff/timezone and form limits; approved release SHA/assets/license; no unresolved secret findings within recorded scan scope; source notices; final artifact review and actual submission receipt. |
| C3 — Critical for the required demo URL | Prepare an isolated judge-accessible application based on existing CPU synthetic behavior. | Enables judging without exposing the workstation or credentials. A viewer-only release may be insufficient for the form, so confirm access requirements first. | Approved HTTPS destination, fresh-session access, populated evidence/plan/lineage, 401/403 checks, inference disabled and no provider key; no shared mutable workspace between unrelated judges. No claim this proves AMD execution. |
| H1 — High-value, first product proof | Build one coherent, narrow kit case whose source evidence, human decisions and recovery plan are traceable together. | Bridges the split-demo weakness. Owner supplies non-sensitive physical evidence and an approved parts/BOM/policy interpretation; otherwise use an explicitly synthetic case. This is a substantial case/integration change for review. | One product family, complementary returns, an incompatible or ambiguous item and an evidence correction; every selected component traces to original images and recorded verification; at least one alternative and exclusivity conflict are shown; final kit records reconcile exactly. Claim actual physical rebuilding only if independently performed and evidenced. |
| H2 — High-value, start now | Independently review a frozen subset of existing outputs using current assessment tooling. | Establishes useful quality evidence without another AMD call or model download. Requires a human reviewer; the agent cannot manufacture independence or ground truth. | Proposed first scope: 12 distinct listing groups from the existing review collection, with grouping/split manifest and all eligible judgments completed, including negative cases; rates show numerator, denominator and exclusions. Double-review four groups if a second reviewer is available; disagreements stay visible. Small-sample results remain descriptive. |
| H3 — High-value | Present one exact economic comparison and a controlled assumption change. | Makes commercial value concrete without inventing savings. Existing integer-cent planner and explanations suffice; first improve the demo, then consider a display-only comparison. | Selected modeled value, cash, retained value, donor baseline, incremental value and labor reconcile to the same immutable snapshot; one explicit price/labor scenario change is re-solved; a hold/retention outcome is allowed. Do not call the donor baseline the global best alternative. |
| H4 — High-value | Add a compact previous-to-new verification summary and direct source navigation. | Makes existing auditability visible. A bounded UI change can reuse saved events and existing read endpoints; misattribution across versions is the main risk. | Show previous/new identity, revision and visible condition, actor, reason and source observations; preserve original event/raw output; historical image mapping survives gallery reorder; plan evidence version is distinct from current evidence; stale/locked/role restrictions still pass. Supporting evidence reachable within three user actions. |
| H5 — High-value after evidence work | Summarize why a component is blocked and link its permitted next action. | Reduces navigation effort; existing reasons already exist. Avoid a new rules engine or automatic retries. | Unknown identity, missing evidence, incompatible revision and reserved stock show correct existing reasons and role-appropriate controls; rendering guidance triggers zero inference/mutation requests. Verify with representative user tasks rather than declaring it intuitive. |
| H6 — High-value | Produce and rehearse the evidence-backed video and revised release deck. | Presentation can expose the core design and its limitations clearly. No new model run is needed for a labeled still-based cut. | Actual movie, reviewed audio/captions and source ledger; readable synthetic/local/AMD status; no leaked metadata/credentials; all numbers match receipts; at least one full uninterrupted playback review. Final duration/size matches the authenticated form. |
| O1 — Optional | A short customer/operator interview and a timed manual-workflow comparison. | Grounds the commercial hypothesis. No automatic outreach; obtain explicit messaging authorization or use an owner-arranged interview. | Record role, task and consent; matched inputs and timing boundary; report individual observations, sample size and limitations, not generalized labor savings. |
| O2 — Optional | Automate a sanitized release evidence manifest and notice inventory. | Reduces manual assembly after the desired artifacts are known. Export may expose sensitive data, so review its exact schema before implementation. | Exact source/asset hashes, public attribution and limitations; no tokens, local secrets or private raw receipts; export matches the reviewed release. |
| O3 — Optional, evidence-triggered | Improve an observed OCR or additional-view failure on a bounded local set. | Only useful after H2 identifies a repeatable failure. Keep current model/environment and original remote contract intact; no speculative model or OCR dependency. | Frozen local baseline and held-out groups; predeclared useful-observation and unsupported-claim measures; retain all outputs and failures. No improvement claim from training/example reuse or schema validity alone. |
| N1 — Not recommended now | Evolus track, new model stacks, fine-tuning, broad OCR/localization pipeline, or autonomous inventory agents. | Adds infrastructure and evaluation work before the core AMD and product-proof gaps close. | Reconsider only with a separate purpose, demonstrated need, resource authorization and acceptance plan. |
| N2 — Not recommended now | Multi-tenant SaaS, microservices, new database/queue, anonymous uploads, public GPU access or a workstation tunnel. | Consequential architecture/security exposure, unrelated to a narrow credible demonstration. | Preserve one modular backend and a disposable demo boundary. Do not equate more services with innovation. |
| N3 — Not recommended | More dashboards, confidence percentages, automatic approvals, exaggerated savings, or extra inference solely to obtain a prettier answer. | Cosmetic or misleading, weakens the project's strongest trust boundaries. | Keep authority deterministic, uncertainty explicit and failed evidence visible. |

## Evidence and comparison protocol

Freeze case IDs, source hashes, physical/listing grouping, catalog/policy and
economic assumptions before evaluating. Record the source commit, provider,
prompt/schema version and timing boundary. Reuse the accepted local baseline;
do not rerun it merely to collect a better result. Separate strict-output validity,
semantic support, operational correctness and business value into different results.

H2 must include unfinished prose, repeated observations, unsupported identity,
unreadable marking and useful/useless additional-view judgments where present.
Zero eligible judgments means unknown, not zero error. A 12-group review is a
bounded demonstration of measurement, not a representative accuracy estimate.
If changes are later proposed, freeze the held-out groups before tuning and
report all results; model confidence remains uncalibrated text.

For optimization, use the existing synthetic CP-SAT/greedy and exhaustive-small-
case checks. In the pitch, compare feasible alternatives under identical inputs,
not a deliberately weak or infeasible baseline. Report objective, status/bound,
labor, constraint violations and component uniqueness. No realistic industrial
scale or revenue improvement follows from a four-part fixture.

For AMD, the six-attempt ceiling is not permission to perform a benchmark. The
first two attempts remain consumed; support clarification and fresh approval
govern the next call. A later paired comparison needs its own reviewed scope
and quota. One or a few calls cannot support p95, throughput or reliability rates.
Use provider-attested metadata only; the shared service may not expose revisions,
GPU model, ROCm/vLLM versions or memory. Do not fabricate those fields.

## Phased implementation plan for review

| Phase | Work and estimated focused effort | Exit / decision |
| --- | --- | --- |
| A — Assess and freeze, current phase | Complete this assessment, asset audit, recording plan, release review and support-status corrections. Preserve accepted artifacts. | Documentation review complete; no new runtime feature, model execution or external deployment. Owner chooses the next product proof and release scope. |
| B — Evidence and coherent case, next work block | H1 case design (roughly 4–8 engineering hours, plus owner evidence); H2 independent review (roughly 2–4 reviewer hours). In parallel, prepare H3's economic scene and rehearse the existing recording. | Approved case/catalog provenance and frozen review set; actual reviewer judgments or explicit dependency. No claim that customer evidence exists merely because a case is designed. |
| C — Focused UX proof, following block | Prefer H4 over a new dashboard (roughly 3–6 engineering hours); add H5 only if a task-based walkthrough exposes a real gap (roughly 2–4 hours). Do not rebuild existing next-step/economic logic. | Relevant backend/frontend tests, source/version association regressions and a browser walkthrough pass; no authority change. Compare task completion with the prior UI and report observations honestly. |
| D — AMD, parallel when reply arrives | Review supported contract and proposed payload, current quota and exact one-call approval. After a successful qualified response, prepare the separately authorized ReKit acceptance scope. | Actual AMD output and application evidence, or precise unresolved blocker with prior attempts preserved. No automatic use of the other remaining calls. Duration depends on support, not an engineering promise. |
| E — Demonstrate and release, after scope review | H6 capture/edit/rehearsal (roughly 4–8 hours); C3 isolated demo preparation and acceptance (roughly 4–8 hours after host/access approval); C2 final rights/security/form review. | Owner approves concrete artifacts and release destination. Reserve a review/upload buffer before the verified cutoff; no publication or submission from a plan alone. |

These ranges are not all additive: human review, recording preparation and AMD
clarification can run in parallel. Reassess after each block, not after four days
have elapsed. If AMD remains blocked, continue evidence and demo work and report
the eligibility gap honestly; do not replace it with a claim based on NVIDIA.
If real kit evidence is unavailable, deliver a rigorous labeled synthetic proof
and keep the real-world case as a limitation. If a proposed change threatens the
working demo, keep the accepted checkpoint and drop optional scope.

## Change control and next decisions

Before a substantial feature, prepare its concrete weakness, solution, competitive
benefit, touched modules, risks and acceptance criteria. Preserve input/output
contracts, append-only evidence, uniqueness, transaction checks, existing tests
and the working CUDA environment. Isolate changes, inspect diffs, run relevant
tests and verify the actual user flow. Commit/push only validated work to private
main under the existing mission authority, with successful CI; no visibility change.

Small documentation corrections and recording-plan improvements were completed
in this review. The application/schema/model environment is unchanged. Runtime
proposals above are not presented as implemented or measured improvements.

Ready for owner review: this prioritized plan, the [asset audit](submission-asset-audit.md),
[recording workflow](demo-recording-workflow.md), [release proposal](submission-release-review.md)
and [readiness checklist](hackathon-submission-checklist.md).

Owner action: confirm online cutoff/form; select and supply the narrow non-sensitive
kit case and an independent reviewer; review the title/deck changes and next
implementation block; choose release licensing/access only when concrete proposals
are ready. AMD-dependent: support's contract/quota clarification, then explicit
approval for a bounded attempt and successful application acceptance. The support
email is already sent externally; do not send a duplicate. Mission 06 stays open,
with both original attempts preserved. Mission 07 has not started.
