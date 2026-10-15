# MI300X access verification and approval packet

This is a **fillable decision checklist, not permission to provision or infer**.
Accepted baseline: `258b169f952bc5cfe1bd71e0ed1a0c1b7867fafd`.
ReKit's MI300X entitlement, capacity, quote, grant and enforceable spending limit
are unverified. No new account evidence has arrived. Existing TokenFactory support
status is unchanged: portal referral/account-support submission, no definitive
API resolution. Preserve its two failed attempts, receipts and credentials.

Use an owner-held copy outside Git for answers. Record only nonsecret facts,
source descriptions and verification timestamps. Do not include account/team IDs,
email addresses, payment details, redemption links, tokens or complete dashboard
screenshots. A checkmark means the named evidence was actually inspected; blank
or `unverified` means stop before dependent action. No account login, grant
redemption, new message, resource creation, download or generation is performed
by this document.

## Public facts checked October 15, 2026

AMD advertises a one-MI300X option with 192 GB GPU memory and ADP/AMD SSO access.
Its FAQ describes conditional complimentary credit, automatic charging when an
attached payment method exists, continued billing for powered-off VMs and charges
ending when the instance is destroyed. It excludes attached storage/backups from
the advertised grant. These public terms do not prove this account's entitlement,
price, availability or cap. [AMD Developer Cloud](https://www.amd.com/en/developer/resources/cloud-access/amd-developer-cloud.html).

The ADP resource page describes verification and a redemption link, with a normal
30-day expiry unless the grant specifies otherwise. Do not activate a grant or
infer its expiry/timezone from this summary; use the actual award and account
terms. [ADP credit terms](https://developer.amd.com/resources/).

The vLLM recipe includes Qwen3-VL on MI300X, but its worked AMD example uses a
large model and multiple GPUs. This does not qualify ReKit's pinned 2B snapshot.
Select a mutually compatible hardware/OS/driver/ROCm/vLLM stack, not unrelated
`latest` releases. [Qwen3-VL recipe](https://docs.vllm.ai/projects/recipes/en/stable/Qwen/Qwen3-VL.html),
[AMD compatibility matrix](https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html).

## 1. Owner account and allocation facts

For each row, record **answer; source; checked-at timestamp with timezone**.
Existing console/grant evidence can be transcribed privately. If a required fact
is absent, record the specific missing fact; do not contact support or activate
anything automatically.

| Required fact | Nonsecret answer |
| --- | --- |
| ADP membership approved and existing ADC access usable through the documented sign-in route? | Unverified — source/time: ____ |
| Actual infrastructure provider, service/offer and region? | Unverified — source/time: ____ |
| Owner authorized to accept this allocation's terms? Terms version/date and permitted private qualification use? | Unverified — source/time: ____ |
| One MI300X available to this account now, or waitlist/quota/approval still required? Offer/reservation expiry? | Unverified — source/time: ____ |
| Exact instance SKU, GPU count, VRAM, CPU/RAM, included disks and network resources? | Unverified — source/time: ____ |
| Is this an awarded allocation or only public advertising? Any remaining application/verification steps? | Unverified — source/time: ____ |
| Allowed model files, synthetic image transfer and execution telemetry collection? | Unverified — source/time: ____ |
| Private operator-run demo permitted? Any separate third-party/judge access restriction? | Unverified — source/time: ____ |

- [ ] Entitlement and capacity are evidenced, not inferred from TokenFactory login.
- [ ] Required terms and workload permission have been reviewed by the owner.
- [ ] No activation, deployment or credit consumption has occurred during this check.

## 2. Complete price, credit and liability worksheet

Get a current quote for the **specific account, region and SKU**. “Included” or
“zero” needs supporting terms; unknown items remain unknown. Credit is a funding
source, not a hard limit. TokenFactory's historical daily allowance is unrelated.

| Cost or billing rule | Rate/unit, currency, minimum/rounding and evidence |
| --- | --- |
| GPU instance, including provision/startup/model-load/idle time | ____ |
| Powered-off or suspended instance, and exact event that stops charging | ____ |
| Included versus additional boot/scratch/persistent volumes | ____ |
| Snapshots, backups, object storage and retained logs/artifacts | ____ |
| Internet egress, inter-region traffic and any ingress/transfer charge | ____ |
| Reserved/public IPs, load balancer, gateway, DNS/domain/certificate service | ____ |
| Monitoring/log retention, support/service fees, minimum charges, taxes/FX | ____ |
| Other automatically created or retained billable resources | ____ |
| Quote timestamp/timezone and validity window | ____ |

Record the grant separately:

| Grant/payment fact | Nonsecret answer and evidence |
| --- | --- |
| Award issued and redeemed? Actual usable balance and units? | Unverified: ____ |
| Activation event and actual activation time? Do not redeem to find out. | Unverified: ____ |
| Exact expiry **date, time and named timezone/UTC offset**, plus UTC equivalent? | Unverified: ____ |
| Which SKU/region/cost categories are credit-eligible; which are excluded? | Unverified: ____ |
| Payment method attached: yes/no? No card details. | Unverified: ____ |
| Automatic top-up/overage enabled, disabled, or unavailable to control? | Unverified: ____ |
| What happens at credit exhaustion or expiry, including retained resources/data? | Unverified: ____ |
| Usage reporting delay, smallest billed unit and final reconciliation delay? | Unverified: ____ |
| Provider-enforced hard cap: exact scope, amount/currency, enforcement behavior and proof? | **Not established:** ____ |

Estimate the maximum exposure, not only expected GPU runtime:

`upper-bound cost = rounded billable instance time × rate + bounded ancillary charges + applicable taxes/fees`

Record proposed total credit use `____`, maximum cash liability `____`, maximum
allocation lifetime `____`, teardown reserve `____`, and the calculation/quote
source `____`. Startup, failures, idle time and delayed destruction belong inside
that bound. An unknown/unbounded charge prevents a defensible no-charge proposal.

- [ ] Every cost category is bounded or explicitly confirmed absent/included.
- [ ] Expiry is a verified instant, not “30 days” without an activation timestamp.
- [ ] Hard-cap proof covers **all** chargeable resources, not just GPU usage.
- [ ] Alerts, estimated balances, manual timers and a plan to stop the VM are not
  being presented as provider-enforced caps.
- [ ] If no enforceable boundary exists, stop and present that fact for a new
  owner decision. Current authority permits no paid provisioning or credit use.

## 3. Runtime compatibility before a deployment proposal

The candidate remains the existing [model manifest](../configs/inference/qwen3-vl-2b.json):
`Qwen/Qwen3-VL-2B-Instruct`, revision
`89644892e4d85e24eaac8bacfd4f463576704203`. Its local NVIDIA success does not
establish ROCm compatibility. Do not copy Windows/CUDA wheels or substitute a
different model to make the checklist pass.

| Item to pin and justify | Proposed value / evidence / unresolved test |
| --- | --- |
| Actual MI300X allocation topology and supported Linux image/kernel/driver | ____ |
| Compatible ROCm, PyTorch/HIP, vLLM and vision-processor versions | ____ |
| Container registry and immutable digest, model/processor hashes and license | ____ |
| Exact served model ID, dtype, attention implementation and measured memory gate | ____ |
| JSON-schema decoder and support for unchanged nested `anyOf`, null unions, required fields and `maxItems: 0` | ____ |
| One approved synthetic image and original hash; no customer data | ____ |
| Proposed request/token/context/time limits and concurrency; exact admission guard | ____ |
| Private authenticated HTTPS ingress, exact `/v1/chat/completions` route and allowed destination | ____ |
| Disable body/key logging; keep management, notebook and metrics routes private | ____ |
| Evidence of exact keyword support still needed before generation | ____ |

vLLM documents structured-output support, but a framework feature does not prove
support for ReKit's exact schema/backend combination. Its API key also does not
protect all server routes. Preserve strict validation and an independently
restricted endpoint. [Structured outputs](https://docs.vllm.ai/en/stable/features/structured_outputs/),
[server security](https://docs.vllm.ai/en/stable/usage/security/).

Actual device/runtime/load checks can only be collected **after** separately
authorized access and provisioning. Before that, distinguish documentation-based
compatibility from measured compatibility. The [existing activation guide](amd-activation.md)
contains historical candidate commands, not permission to run them or to make its
two-request smoke sequence. The next request count requires an explicit proposal.

## 4. Teardown and evidence plan before approval

Fill the plan now; execute only for specifically authorized new resources later.

- [ ] Responsible operator `____`; maximum lifetime and scheduled teardown instant
  with timezone `____`; backup operator/escalation route `____`.
- [ ] Resource inventory covers VM, volumes, snapshots, backups, IPs, network
  services, logs and any other chargeable dependency; destruction authority is
  limited to this new allocation, never existing projects/resources.
- [ ] Provider's exact destruction steps and irreversible data-loss warning reviewed;
  approved receipts/model configuration exported privately before destruction.
- [ ] Stop conditions include missing cost visibility, credit uncertainty, unsafe
  ingress, incompatible schema/model, failure to prove AMD execution or expired approval.
- [ ] Teardown verification records deletion/completion timestamps, absence of all
  authorized resources, final usage/billing reconciliation and any residual charges.
  “Powered off” alone is insufficient. Keep the task open while billing is unresolved.
- [ ] ReKit rollback disables the new remote profile and clears its process secrets;
  original NVIDIA environment, two TokenFactory receipts and persistent ledger remain intact.

Required execution evidence, if later authorized: sanitized hardware/runtime record
from the actual serving environment; immutable container/model/processor hashes;
request-correlated serving-process and AMD GPU activity; approved image/prompt/schema
hashes; untouched response; validation result; UTC timing/resource use; and the
linked ReKit application run. Device inventory alone does not prove the image
request used the accelerator. Standalone inference alone does not close Mission 06.

## 5. Packet for an explicit owner decision

Submit one concise proposal containing:

1. Account entitlement/capacity evidence and actual quote/grant terms, with timestamps.
2. Maximum credit consumption and cash liability, enforceable cap evidence, complete
   cost calculation, expiry and teardown plan. State unresolved facts prominently.
3. Exact one-instance runtime/model/processor/decoder pins, image/hash, private endpoint
   and configuration diff. No speculative model or schema changes.
4. Separately enumerated permissions sought: provisioning, installation/downloads,
   approved-image transfer, **exact generation-attempt count**, telemetry and teardown.
5. A reviewed persistent accounting plan linking any new AMD attempt to the original
   2/6 history. No reset, duplicate ledger, new budget or implied six-call allowance.
6. Success/failure criteria, receipt destinations, rollback and a separate application
   integration gate after successful inference.

**Current outcome: preparation only.** No allocation, grant, capacity, rate or hard
cap is verified for ReKit. Credible new facts lead to this concrete packet for
review; they do not themselves authorize deployment, image transfer, spending or
generation. No public judge deployment, licensing change, support contact or
submission is included. See the [Block D options comparison](amd-contingency-options.md)
for alternatives if this contingency cannot meet the gate.
