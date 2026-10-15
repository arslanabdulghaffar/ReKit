# AMD contingency options for Block D

Public documentation checked **October 15, 2026**. This is a feasibility and
approval brief, not a deployment instruction or evidence of AMD execution.
Only public documentation was browsed. No signed-in account, credential,
provider API, instance, model download or generation was accessed by this
research. The existing two attempts remain preserved; no additional budget is
created here. Mission 06 remains open.

**Recommendation:** repair the existing TokenFactory route if AMD supplies a
definitive supported contract. The preferred *contingency* is a small, isolated
Linux/vLLM deployment on one AMD Developer Cloud MI300X, **only if an enforceable
owner-approved spending boundary and actual access are established first**.
ReKit has no verified Developer Cloud allocation, credit grant or hard spending
cap. Free-credit advertising is insufficient authorization to launch anything.

## What is established, and what is not

The [ACT III technology requirement](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii)
accepts AMD Developer Cloud, Instinct, ROCm, Ryzen AI, Radeon and other approved
AMD infrastructure. AMD must perform a meaningful workload in the working
product shown to judges. Its FAQ identifies TokenFactory without a billing/card
or $100-credit prerequisite. This establishes a permitted route, not ReKit's
model eligibility. The Evolus award has the separate requirement of a team's own
vLLM endpoint on Developer Cloud; Evolus remains optional and out of this block.

Local evidence at the accepted Block C checkpoint establishes two HTTP 400
TokenFactory attempts and no successful AMD visual inference. The user reports
that the key was redeemed and configured, and that support referred them to the
Chinese feedback portal before an account-support form was submitted. No
definitive API-contract resolution has arrived. See the
[offline diagnosis](tokenfactory-http400-diagnosis.md) and
[Mission 06 report](reports/development-mission-06.md). This research did not
reopen private receipts or inspect account state.

The current [MiMo reference](https://amd-aim.github.io/radeon-cloud-docs/models/mimo-v2-6-flash/)
still advertises the exact `MiMo-V2.6-Flash` ID, base64 image data URLs,
`reasoning_effort="none"`, SGLang and strict `json_schema`; it labels the service
experimental. It supplies no complete keyword compatibility matrix for ReKit's
schema. Thus the saved catalog's `structured_outputs=false` discrepancy remains
unresolved. Public documentation is not new evidence that the original request
will succeed. Neither original error body's exact wording was retained.

The [regional sign-in guide](https://amd-aim.github.io/radeon-cloud-docs/guides/login/)
says China and Global accounts do not carry across, and instance-verification
holds can coexist with shared-API access. That distinction is a useful support
question, **not a diagnosis** of ReKit's 400s. No alternate hostname or credential
route should be tried speculatively.

## Options assessed against the ten requested criteria

### A. Provider-confirmed repair of existing TokenFactory access

| Criterion | Finding |
| --- | --- |
| 1. Official documentation | [Event access FAQ](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii), [MiMo contract](https://amd-aim.github.io/radeon-cloud-docs/models/mimo-v2-6-flash/), [shared model API guide](https://amd-aim.github.io/radeon-cloud-docs/guides/model-apis/) and [usage reference](https://amd-aim.github.io/radeon-cloud-docs/api/usage/). |
| 2. Account/access prerequisites | Existing redeemed team API access; AMD confirmation that this team may call the exact model and endpoint with the proposed image/schema contract; current allowance evidence. Browser login and a global model list do not meet the callable-model requirement. |
| 3. Existing access versus approval | Key configuration and two failed requests are established locally. Successful inference, model eligibility and usable API quota reporting remain unverified. A third attempt requires the owner's explicit approval of the concrete revised request and fresh quota evidence. |
| 4. Infrastructure | Existing ReKit backend and its explicit `amd-tokenfactory` profile; no owned GPU or deployment. Exact destination remains the already configured route. |
| 5. Card/free/payment | The event describes this shared route as card-free. The model API guide separates free shared access from credit-consuming dedicated instances. The earlier dashboard allowance is historical, not current quota or a request-cost conversion. No paid resource is required by the advertised shared route. |
| 6. Difficulty | **Low integration effort, unresolved provider dependency** (engineering assessment). There is no credible completion estimate until support resolves the rejection. |
| 7. ReKit workflow fit | Best fit with existing qualification code and immutable original ledger. Require schema acceptance without weakening the local schema/domain validation. An enabled JSON-object-only model would leave the strict-output gap unresolved. |
| 8. AMD accelerator proof | Ask for provider attestation linking the actual endpoint/model deployment to AMD acceleration and, preferably, request-correlated execution information. Save the successful run's image/schema hashes, raw output, latency and model provenance. Without hardware evidence, label execution as provider-hosted with accelerator details unverified. An AMD login or model-name echo is insufficient. |
| 9. Risks | Account routing and schema ambiguity; experimental endpoint; quota uncertainty; unattested weights/runtime; incomplete error detail. No retries, substitutions or schema downgrade. Shared requests still transfer approved image bytes externally. |
| 10. Integration/rollback | Review a payload diff after support's answer, then authorize exactly one synthetic-image attempt with before/after quota checks. Preserve both earlier attempts and stop for review on any result. Only after validated success, exercise the application integration. On failure disable this route and retain all evidence; never silently use NVIDIA. |

The [usage reference](https://amd-aim.github.io/radeon-cloud-docs/api/usage/)
describes account-specific allowances and separates shared API accounting from
instance credits; its sample values must not be adopted as ReKit's quota. It
does not explain this team's unusable responses. The owner should preserve
support's answer about the two failed usage routes, units and reset time. No
usage call was repeated for this research.

### B. Owned AMD Developer Cloud MI300X deployment — preferred contingency

| Criterion | Finding |
| --- | --- |
| 1. Official documentation | [Developer Cloud product and FAQ](https://www.amd.com/en/developer/resources/cloud-access/amd-developer-cloud.html), [ADP credit terms](https://developer.amd.com/resources/), [AMD setup guide](https://www.amd.com/en/developer/resources/technical-articles/2025/how-to-get-started-on-the-amd-developer-cloud-.html), [vLLM Qwen3-VL ROCm recipe](https://docs.vllm.ai/projects/recipes/en/stable/Qwen/Qwen3-VL.html). |
| 2. Account/access prerequisites | ADP membership/AMD SSO, an authorized cloud account and accepted applicable terms; a granted and usable allocation with confirmed region/capacity; permission for approved model files and synthetic images; an owner-approved resource limit and endpoint configuration. |
| 3. Existing access versus approval | **Not verified available.** No saved evidence establishes ReKit's account, grant, balance, card state, capacity or hard cap. Owner-supplied nonsecret evidence is needed before any account inspection or provisioning is proposed. |
| 4. Infrastructure | Candidate: one MI300X Linux VM, isolated ROCm/vLLM container, a compatible pinned vision model/processor and private authenticated TLS ingress. AMD advertises a small 1-GPU configuration with 192 GB GPU memory. Actual available VM specification must be checked; this is not a measured model requirement. |
| 5. Card/free/payment | ADP advertises $100 credit following verification and redemption, normally expiring in 30 days unless the grant says otherwise. Current ADC FAQ says an attached payment method is charged after exhaustion; powered-off VMs still consume credit/billing until destroyed, and storage extras are excluded. A safe no-charge boundary is **not established** for this account. See the conflict and approval gate below. |
| 6. Difficulty | **Moderate**, with access lead time and runtime qualification uncertainty. Better control of schema, revision and telemetry than shared service, but requires Linux serving and secure ingress. No timing or cost guarantee. |
| 7. ReKit workflow fit | Existing `openai-remote` adapter can consume an authenticated canonical HTTPS `/v1` endpoint with real pinned revisions. Candidate Qwen3-VL-2B requires fresh ROCm qualification; current CUDA success does not qualify it. Generic framework schema support does not establish ReKit's exact schema support. |
| 8. AMD accelerator proof | Obtain allocation evidence plus the actual serving environment's AMD SMI device/runtime record and request-correlated process/GPU activity, model/processor hashes, container digest, successful image result and ReKit run ID. Keep infrastructure and inference timestamps together. |
| 9. Risks | Automatic charging, grant expiry/data deletion, capacity delays, model/runtime incompatibility, image transfer, insecure public serving and account terms. Do not expose Jupyter or an unauthenticated model service. No customer data. |
| 10. Integration/rollback | Qualify in an isolated deployment and fresh local test database under a separately approved concrete plan. Preserve strict validation and human authority. Default ReKit remains unchanged. On a stop condition, disable the endpoint, export approved receipts, and destroy only the newly authorized resource according to the agreed teardown plan; verify billing has stopped. Preserve original AMD attempts and the working CUDA environment. |

**Credit-documentation conflict:** the current ADC product FAQ and ADP resource
page describe $100/30-day grants, while the older
[AMD cloud-access FAQ](https://www.amd.com/en/developer/resources/cloud-access.html)
still describes 25 hours/10 days and a card prerequisite. The older
[setup article](https://www.amd.com/en/developer/resources/technical-articles/2025/how-to-get-started-on-the-amd-developer-cloud-.html)
also retains the 25-hour offer. Do not blend these into a promise, infer current
hourly pricing, or treat the absence of a card requirement on one page as proof
of card-free access. Use the actual offer/account terms and resource quote.

The ADC product terms also restrict providing the cloud service to third
parties. A judge-facing endpoint needs a separate terms/organizer check; the
contingency should initially be a private operator-run qualification and recorded
demonstration. This document does not authorize public serving or give a legal
eligibility determination.

### C. Radeon Cloud dedicated endpoint using an issued event coupon

| Criterion | Finding |
| --- | --- |
| 1. Official documentation | [Dedicated model API guide](https://amd-aim.github.io/radeon-cloud-docs/guides/model-apis/), [credits](https://amd-aim.github.io/radeon-cloud-docs/guides/credits/), [regional accounts](https://amd-aim.github.io/radeon-cloud-docs/guides/login/) and [launch limits](https://amd-aim.github.io/radeon-cloud-docs/guides/launch/). |
| 2. Account/access prerequisites | Correct regional account with instance verification complete, an appropriate template, sufficient instance credits, actual compatible AMD GPU capacity and permission for deployment. Event coupon must be issued to this account/site and redeemed under its terms. |
| 3. Existing access versus approval | No ReKit coupon, instance balance, verification approval or hardware allocation is established. The existing shared-API key does not establish these. Organizer approval of the exact supplied infrastructure/workload remains to be obtained if offered. |
| 4. Infrastructure | A dedicated vLLM or SGLang template with a suitable ROCm image and actual AMD device. Documentation permits 1, 2 or 4 GPUs and one active instance. Device type/VRAM and compatible small-model serving stack are unknown for this account. |
| 5. Card/free/payment | Credits are separate from shared-API allowance. Documented event/workshop coupons fund instances, but no ACT III entitlement, credit amount, duration, card requirement or overage behavior has been confirmed for ReKit. Do not purchase or assume credits transfer between regional sites. |
| 6. Difficulty | **Moderate to high**: more unknown hardware/account facts than option B, plus an endpoint-shape mismatch. |
| 7. ReKit workflow fit | Documented dedicated base URLs use `/spaces/<instance-id>/8000/v1`; current generic adapter accepts exactly `/v1`. Thus not usable unchanged. A reviewed exact-destination profile or approved authenticated ingress would be needed; no broad URL-validation relaxation. |
| 8. AMD accelerator proof | Same device/runtime/process-to-request chain as option B. The template's name, GPU count, coupon or AMD branding alone does not prove image inference used an AMD accelerator. |
| 9. Risks | Coupon eligibility, regional account separation, unknown quota semantics/hardware, uncertain launch availability, broader server routes and new ingress adaptation. No paid fallback or automatic retry. |
| 10. Integration/rollback | Obtain provider facts and a supported pinned deployment before proposing a bounded adapter/ingress change. Run offline destination/security tests before any approved image call. Retain original provider profile and ledger. Disable the new profile and export evidence before authorized teardown; confirm the actual platform's charging stop behavior. |

The [credit guide](https://amd-aim.github.io/radeon-cloud-docs/guides/credits/)
documents coupons from events and says running instances consume credits while
stopped/destroyed ones do not. This differs from ADC VM billing; they are
different services. Neither rule supplies this team's balance or permission.

### D. Specifically offered organizer-managed AMD hardware

| Criterion | Finding |
| --- | --- |
| 1. Official documentation | The [event technology list](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii) permits Radeon, Ryzen AI and other approved AMD infrastructure. [AMD's Instinct compatibility matrix](https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html) and [Radeon Linux matrices](https://rocm.docs.amd.com/projects/radeon-ryzen/en/latest/docs/compatibility/compatibilityrad/native_linux/native_linux_compatibility.html) are hardware/runtime references, not allocation offers. |
| 2. Account/access prerequisites | A concrete written offer: device identity/VRAM, operator access, time window, network rules, software permissions, allowed workload and event eligibility. Separate owner approval is required to accept or configure it. |
| 3. Existing access versus approval | **Conditional fallback only.** No loan, hosted slot, sponsor endpoint or approved AMD device is evidenced. The known local RTX 4080 SUPER machines do not establish AMD accelerator access. No external request was sent. |
| 4. Infrastructure | Prefer a managed Linux Instinct host compatible with the pinned serving plan. A Radeon or Ryzen AI offer needs its own exact device/OS/backend review; an NPU path is not a drop-in ROCm/vLLM port. |
| 5. Card/free/payment | Unknown until the offer explicitly specifies who pays, usage ceilings, storage/egress, expiry and teardown. No-card, no-charge access must be confirmed, not inferred from hackathon participation. |
| 6. Difficulty | **Variable**. A supported managed Instinct endpoint could reduce setup. A new Radeon/NPU software path would likely exceed a bounded contingency and is not recommended without a concrete benefit. |
| 7. ReKit workflow fit | A qualifying HTTPS image/schema endpoint can use the existing remote boundary. Any new model, backend, schema serialization or transport requires an explicit reviewed proposal. Keep application decisions deterministic. |
| 8. AMD accelerator proof | Provider/operator supplies execution-linked hardware/runtime evidence, then ReKit records approved image hashes, raw response and app provenance. Merely running the optimizer on an AMD CPU would not demonstrate the required visual-inference outcome for Mission 06. |
| 9. Risks | Time-limited access, unclear terms, incompatible hardware, unsupported backend, unavailable telemetry and exposing evidence to a third party. Unknowns block execution. |
| 10. Integration/rollback | Evaluate the offer against the same qualification gate before building anything. Isolate configuration, use synthetic input first, preserve all failures and original attempts, disable the integration on failure, and return/remove only authorized temporary resources. |

## Small visual deployment: exact qualification boundary

The following is a proposed scope for option B, not a tested configuration or a
command to run now:

- Start from the already tracked candidate
  [`Qwen/Qwen3-VL-2B-Instruct` manifest](../configs/inference/qwen3-vl-2b.json),
  revision `89644892e4d85e24eaac8bacfd4f463576704203`, subject to model/processor
  verification, license review and separate authorization to obtain files on the
  approved host. Do not copy CUDA wheels, assume kernel support or repurpose the
  Windows virtual environment. No model substitution has been approved.
- The [vLLM recipe](https://docs.vllm.ai/projects/recipes/en/stable/Qwen/Qwen3-VL.html)
  documents Qwen3-VL on MI300X/MI325X/MI355X, but its worked AMD example is a
  larger MoE model. It does **not** qualify ReKit's 2B snapshot. The
  [supported-model table](https://docs.vllm.ai/en/v0.25.1/models/supported_models/)
  lists the Qwen3-VL architecture with image support; actual runtime compatibility
  remains an acceptance test. Pin the complete known-compatible stack after
  checking the selected release; do not combine moving `latest` packages.
- Keep one serving process, one admitted request, one approved synthetic image,
  the existing 512-output-token bound and 120-second request deadline initially.
  A provisional 8,192-token context is a **design limit**, not a measured memory
  guarantee. Reject an oversized image request rather than silently dropping it.
  Measure GPU memory and verify model loading before requesting execution.
- [vLLM structured-output documentation](https://docs.vllm.ai/en/stable/features/structured_outputs/)
  provides JSON Schema and selectable decoder backends. Require compile-time
  support for ReKit's complete current wire schema, including nested `anyOf`,
  null alternatives, required fields and `maxItems: 0`, before a generation
  attempt. Pin that backend. Successful parsing does not prove enforcement, and
  enforcement does not prove visual truth. Unsupported constraints mean stop
  for review, not discard them.
- The [current remote adapter](../backend/src/rekit/inference/adapters/openai_remote.py)
  sends original-byte data URLs, demands an exact model ID, validates the compact
  wire shape and domain contract, and performs no retry or local fallback. Its
  hardware metadata deliberately remains unverified unless supported by separate
  deployment evidence. Do not turn a configuration string into an attestation.
- Retain human review of visual observations and catalog identity. Compatibility,
  reservation and optimization remain outside model authority. Any successful
  standalone AMD image call must be followed by an approved real application
  run before claiming integration.

The [vLLM security guide](https://docs.vllm.ai/en/stable/usage/security/) warns
that API-key protection is not a boundary for all routes. Proposed ingress must
expose only authenticated required endpoints, constrain request size/admission,
verify TLS, and avoid body/key logging. Keep Jupyter, management and metrics
private. Public judge deployment is not part of this plan.

## Evidence and approval packet before any action

For **TokenFactory repair**, the owner needs a definitive provider answer,
reviewable payload diff and fresh account-specific quota evidence, followed by
explicit approval for one bounded attempt. Existing 2/6 history stays intact;
support referral alone does not unlock an attempt.

For **the preferred cloud contingency**, obtain these facts without posting
credentials, account IDs or redemption links in chat:

1. Confirmation of ADP/cloud access and the actual grant: usable balance,
   expiry/timezone, permitted GPU and region, and present capacity.
2. A current quote and charging terms for the specific instance and every
   ancillary resource. Confirm whether a payment method/automatic top-up exists,
   what happens on exhaustion, and the exact destruction/stop billing rule.
3. An **enforceable** no-charge or owner-approved liability boundary. A balance
   alarm, manual monitoring or advertised credits are not hard caps. If the
   service cannot establish a no-charge allocation, obtain an organizer-funded
   allocation with that guarantee or return a concrete cost/liability proposal
   for new owner approval. Do not launch under the current no-spending scope.
4. Permission for the particular model files, one synthetic image, private
   endpoint and execution-evidence collection; accepted terms and an operator
   responsible for teardown. Do not solicit a new coupon or contact the organizer
   automatically.
5. A reviewed pinned hardware/runtime/model/processor/decoder plan and exact
   trusted endpoint. Any code change must preserve existing strict validation.
6. Explicit owner approval for resource creation, downloads/installations on the
   new host, a bounded first generation attempt and teardown. The concrete plan
   must state how new execution records link to the original two attempts; it
   cannot reset or bypass their ledger or presume a fresh six-call budget.

Collect device/runtime evidence **inside the serving environment**. AMD's
[SMI CLI reference](https://rocm.docs.amd.com/projects/amdsmi/en/latest/how-to/amdsmi-cli-tool.html)
documents device identity, process and monitoring capabilities. Save sanitized
device/runtime information and request-correlated process activity, immutable
model/processor/container hashes, ordered original-image hashes, prompt/schema
hashes, raw output, validation outcome, UTC timings and observed resource use.
Inventory presence alone is not proof a GPU executed the image request. A request
ID linked to the serving process and contemporaneous AMD GPU activity is needed;
if correlation cannot be established, state the limitation.

The existing [AMD activation guide](amd-activation.md) and
[deployment checklist](../deploy/amd/README.md) provide useful handoff structure,
but their candidate commands and historical credit notes must be reconciled
against the selected account and pinned release before execution. No commands
from them were run for Block D research.

## Routes not recommended as automatic substitutes

The [ADP resources page](https://developer.amd.com/resources/) also advertises a
Fireworks credit option. That benefit alone says nothing about the accelerator
used by a particular image request, strict schema compatibility or this team's
event eligibility; it is not a verified AMD contingency. Likewise, a generic
partner API, a new shared model, Evolus platform credits, a text-only benchmark
or an AMD-branded catalog cannot replace the missing visual-inference evidence.
No such substitution has been selected or executed.

The deliverable remains a concrete choice with explicit blockers: keep the
TokenFactory support repair open, prepare option B only when access and a
spending boundary are demonstrated, and preserve all present evidence until
an authorized AMD run and application integration actually succeed.
