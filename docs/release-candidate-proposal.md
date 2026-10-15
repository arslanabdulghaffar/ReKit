# ReKit release-candidate proposal

Internal proposal, **October 16, 2026, Asia/Seoul**. Source checkpoint:
`bb0edb6f9e9689c338e44a615c629028b68b378f` (accepted Block E).
This is not release approval. Keep the development repository private.

The owner confirmed today that no new AMD resolution/access evidence, genuine
reviewer exports, motion footage, narration or final video has arrived. All
**39 human assessments remain pending**, AMD attempts remain **2/6**, and Mission
06 remains open. Public documentation checked below does not change those facts.

## Proposed release boundary

Prepare a **separate, reviewed source snapshot** and a disposable **CPU-only,
synthetic viewer application**, accompanied by the approved seven-slide story
and an actual recorded demonstration. This preserves the private development
history. Creating a public repository, licensing it, deploying, spending and
submitting each still require owner approval. The CPU viewer would explain the
working recovery system; it would not qualify AMD inference or satisfy an
unconfirmed requirement for judges to perform writes.

The accepted checkpoint has 1,521 backend and 91 frontend passing tests and a
successful synthetic browser replay. These are the dated [Block E results](reports/winning-quality-block-e.md),
not public-host acceptance, independent recognition accuracy or a native-crash
fix. The intermittent Windows access violation remains unresolved.

## Exact source and artifact selection

An ignored, read-only Git inventory records **all 203 checkpoint files**, their
Git blob IDs, and the **168 files proposed for source export**:
[`source-manifest.json`](../var/mission06-offline/block-f-release-inventory-20261016-003629-311d8d/source-manifest.json).
Manifest SHA-256:
`2b6aae0d9b75dbe85bdef1a7d93b591bcdb44fdc11f546ce4ccc7f2f0152ac0a`.
It is an inventory, not an archive, security clearance or published repository.

The proposed set consists of the five tracked root files `.env.example`,
`.gitignore`, `README.md`, `pyproject.toml`, `requirements-inference.txt`; every
checkpoint file under `.github/`, `backend/`, `frontend/`, `tests/`, `evaluation/`,
`configs/`, `deploy/`, `scripts/`; and these documentation files:

```text
docs/architecture.md                 docs/api-workflow.md
docs/domain-contracts.md             docs/evidence-provenance.md
docs/image-evidence.md               docs/inference-evidence.md
docs/inventory-workflow.md           docs/operator-auth.md
docs/recovery-planning.md            docs/local-demo.md
docs/local-inference.md              docs/canonical-case.md
docs/real-product-evaluation.md      docs/amd-activation.md
docs/amd-access.md                   docs/tokenfactory.md
docs/assets/rekit-architecture.svg
```

The other 35 tracked files are internal/history material outside this proposed
export, not deleted. No `.git/`, `.venv/`, `.secrets/`, real `.env`, `var/`,
`models/`, datasets, databases, local logs, credentials or `node_modules/` enter
the source snapshot. Preserve synthetic fixtures and code tests. Optional
evaluation/presentation tools that require private frozen receipts must be
identified as such; they are not runnable evidence on a clean clone by themselves.

Before exporting, prepare a public README and repair selected documentation
links to omitted internal reports or `var/` assets. Add only the owner-approved
license and completed notices. Then record the **new release commit, exact
manifest and clean-checkout results**; those future bytes will differ from the
checkpoint above. Do not describe this proposal's inventory as that final release.

| Deliverable | Exact existing input / remaining action |
| --- | --- |
| Deck | [ReKit-Block-D-candidate.pptx](../var/mission06-submission/block-d-deck-20261015-224720-21fd9f/ReKit-Block-D-candidate.pptx), 385,651 bytes; SHA-256 `a7b203b9297331babe19d6ab5505e198b92246e6390d3ffed41781146f3ba97f`. Preserve the approved content and original. Review notes/metadata/links before a separate release export; inspect every resulting slide. Its 1,485/91 test counts explicitly belong to Block C. |
| Cover | [ReKit-Block-D-cover.png](../var/mission06-submission/block-d-deck-20261015-224720-21fd9f/ReKit-Block-D-cover.png), 1920 × 1080, 39,534 bytes; SHA-256 `f953110121ebbbd96ee700efb0c8934a725b01289735768e7587c2ebfede5445`. Check the actual portal crop preserves the AMD-pending qualifier. |
| Video | Final file **absent**. Proposed export name `ReKit-NeuralFoundry-demo.mp4`; no hash or duration yet. Execute the existing [owner handoff](block-e-owner-handoff.md) and [12-shot specification](block-d-capture-edit-specification.md). Use actual canonical motion and preserved genuine NVIDIA evidence; identify stills. The silent-stills draft is only a pacing reference. |
| Descriptions | Preserve the marked fields in [submission-content.md](submission-content.md): existing requested title 48 characters, summary 224 characters, full description 323 words. Owner can approve the existing neutral alternative **ReKit — Visual Recovery Intelligence** (36 characters) before release; no field was changed here. Review dated tables/asset links before reuse. |
| Optional supporting visual | [Block E comparison](decision-evidence-demo.md), selected package `var/mission06-offline/block-e-decision-demo-20261015-234317-740907/`; manifest SHA-256 `2f13b7d80017f4078794f052dfc610a2ebe30ef8a3d7aa87e4bf4c56fc717f27`. Keep its 16 files together after a separate sharing review. It is a recorded-results explanation, not live planning or a substitute for the application URL. |

## Rights, history and security gates

No root code license or third-party notice bundle exists at the checkpoint.
The owner must confirm contributor rights and choose terms compatible with the
event's stated MIT-compliance requirement. Do not assume that phrase selects a
license automatically. A public GitHub repository is not, by visibility alone,
open source. [GitHub licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)
explains the distinction.

- Prepare a release-specific `THIRD_PARTY_NOTICES.md` and necessary license-text
  files for code actually distributed, using pinned Python metadata and the npm
  lockfile/built bundle. React/React DOM/scheduler and backend dependencies need
  their applicable notices; development-only tooling must be assessed separately
  if shipped. The [prior review](submission-release-review.md#licensing-and-attribution-review)
  is a starting inventory, not a completed notice bundle.
- ABO imagery remains under [CC BY 4.0 according to its official registry](https://registry.opendata.aws/amazon-berkeley-objects/).
  Preserve Amazon/dataset-builder credit and source/license links; disclose
  crops, scaling and overlays in the delivered video/deck/description. Keep the
  [existing credit](real-product-evaluation.md#source-license-and-attribution)
  usable outside private notes. Follow the [attribution terms](https://creativecommons.org/licenses/by/4.0/);
  do not imply endorsement or verified returned-unit identity.
- Credit local Qwen3-VL-2B-Instruct and revision
  `89644892e4d85e24eaac8bacfd4f463576704203`; the
  [pinned model card](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct/blob/89644892e4d85e24eaac8bacfd4f463576704203/README.md)
  declares Apache-2.0. Do not include weights, CUDA/PyTorch installations or
  source datasets in the source release. Future redistribution needs its own review.
- Scan the exact candidate tree, **every reachable commit/blob/ref proposed for
  publication**, author identities, commit messages and selected generated media.
  An approved new snapshot repository can avoid exporting private history; a
  visibility change to the original would expose its reachable history and needs
  a separate full-history decision. Preserve the private repository unchanged.
- Review browser chrome, narration, Office metadata/notes, external relationships,
  image metadata, credentials and log fragments. Run current dependency/security
  checks and record their scope and unresolved findings. Earlier selected-pattern
  scans, `.gitignore`, passing tests and a new snapshot do not constitute clearance.

## One concrete judge-hosting proposal

**Proposed only:** one DigitalOcean Basic **Regular bundled** CPU Droplet,
**1 vCPU / 2 GiB RAM / 50 GiB SSD**, in a region the owner approves; one existing
owner-controlled DNS name; an initial **72-hour** judging window. Account access,
regional capacity, final quote, domain control and judging window are unverified.
No host is provisioned. Do not substitute a differently priced Premium/v5/GPU SKU.
This sizing is a starting hypothesis for a read-only fixture, requiring a Linux
memory/latency smoke test; it is not verified production capacity or AMD execution.

Proposed traffic path: judge browser → HTTPS reverse proxy/static server →
same-origin `/api` with that prefix stripped → one Uvicorn worker bound to
`127.0.0.1`, using `rekit.main:create_configured_app`. Serve the production
`frontend/dist` bundle; do not expose Vite, the workstation or port 8000.
The proposed gateway permits only read methods for the judge route, with existing
ReKit viewer-role authorization retained behind it. Configure
`REKIT_INFERENCE_PROVIDER=disabled`, omit all inference keys/model directories,
and keep managed images behind authenticated API routes.

Seed a **new dedicated synthetic database/evidence directory** through the real
workflow in an owner-controlled preparation job; preserve its provenance receipt.
Remove write-capable credentials before opening judge access. Give the judge a
separate viewer credential through an approved private channel, not a URL, source
file or frontend variable. Revoke by configuration change and restart, then destroy
the disposable environment at the approved removal time. No multi-tenant or shared
write demonstration is proposed. A separate AMD integration, if qualified later,
would require its own concrete scope and budget review.

The following engineering remains **unimplemented and blocks deployment**:

1. Persistent, reproducible synthetic population/reset and a release receipt.
   The local canonical runner deliberately removes its state; it is not a hosted seed.
2. Linux deployment/service files, production static serving, HTTPS/DNS, proxy
   rewrite/method controls, firewall, restricted SSH, filesystem permissions,
   egress controls, bounded logs/storage and tested restart/teardown.
3. Gateway rate/body/time/concurrency limits and a clear viewer-mode entry point.
   Existing upload limits do not provide aggregate storage or public rate limits.
   Static tokens have no built-in expiry; public tenant isolation is absent.
4. Fresh-browser deployed acceptance: valid TLS, private API/assets, viewer writes
   denied, inference unavailable, synthetic labels, evidence/history/kit lineage,
   mobile views, restart and credential revocation. A working local test cannot
   certify this future endpoint.

### Conditional cost, not spending authorization

Official prices rechecked October 16: the proposed bundled SKU is **$0.01786/hour,
$12/month**, with 2,000 GiB monthly transfer. Public IPv4 is included for bundled
plans. [Droplet price table](https://www.digitalocean.com/pricing/droplets).
The service is billed while powered off; billing ends on destruction, with
per-second billing and a 60-second/$0.01 minimum.
[Billing rules](https://docs.digitalocean.com/products/droplets/details/pricing/).

| Conditional 72-hour scenario | Calculation / exclusions |
| --- | --- |
| Compute | `72 × $0.01786 = $1.28592`, approximately **$1.29** before tax. Another 24 hours adds about $0.43. The monthly bundled compute cap is not an all-resource account cap. |
| Transfer | Allowance accrues with lifetime: `2,000 × 72 / 672 ≈ 214.29 GiB`. Assuming only this resource consumes the pool and total outbound traffic is 10 GiB, estimated overage is $0. Actual excess is `$0.01 × max(0, team outbound GiB − accrued pooled allowance)`. [Official bandwidth rules](https://docs.digitalocean.com/platform/billing/bandwidth/). |
| Firewall | Cloud firewall has no additional service charge. [Official price](https://docs.digitalocean.com/products/networking/firewalls/details/pricing/). |
| Not included | Tax/FX/card charges; domain acquisition/renewal if needed; traffic beyond allowance; optional backup, snapshot, extra disk, load balancer, media hosting or AMD inference. This proposal selects none of those paid add-ons; obtain a revised quote before adding one. |
| Residual exposure | Power-off is insufficient. Check volumes, snapshots, IP reservations and backups after deletion; snapshots, if created, have separate storage charges. [Snapshot pricing](https://docs.digitalocean.com/products/snapshots/details/pricing/). Preserve deletion IDs/time and reconcile the final bill. |

Propose an **estimated $2 pre-tax operating budget** for the stated 72-hour CPU
scope, conditional on the actual quote and transfer assumptions. This is not a
guaranteed maximum. DigitalOcean explicitly says spend alerts do **not** cap
usage, and they can arrive after consumption; neither alerts nor promotional
credits establish a hard limit. [Spend-alert documentation](https://docs.digitalocean.com/platform/billing/spend-alerts/).
The owner must approve the payment arrangement and residual exposure, or require
a provider-enforced bound before launch. No credit eligibility, account-specific
quote, funding or enforceable hard cap has been verified. Extend uptime only with
an approved judging window and revised cost; do not promise availability past teardown.

## Form and deadline: verified public guidance versus missing account facts

The [official ACT III page](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii)
requires a meaningful AMD workload in the working product. It lists title,
descriptions, challenge, tags, prototype, cover, video, slides, public GitHub,
demo platform and application URL, and states originality/MIT compliance.
Reinvent Commerce is the proposed track. Optional Evolus requirements are not
claimed. These public requirements do not prove account enrollment or eligibility.

The [general submission guide](https://lablab.ai/ai-articles/hackathon-guidelines)
specifies title ≤50 characters, summary ≤255, long description ≥100 words,
recommended 16:9 cover, video within five minutes and under 300 MB; it requests a
video link and allows additional judge information. Confirm actual event-form
formats, upload limits, required tags, deck/PDF requirements and URL access rules
before preparing the final upload bundle. Use **<300,000,000 bytes** as a
conservative local video-size check, then confirm the portal's definition.

The freshly read [Milan organizer agenda](https://luma.com/AMDHackathon-Milan)
still gives **October 18, 16:00** as its on-site submission deadline. The earlier
[checklist](hackathon-submission-checklist.md#public-requirements-and-unresolved-deadline)
records the `Europe/Rome` metadata evidence: 16:00 CEST corresponds to 14:00 UTC /
23:00 KST. Today's text extraction confirmed the agenda time but did not expose
that timezone field. **Its applicability to ReKit's online submission remains
unconfirmed.** The [live page](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii/live)
still displays online build dates differing from the landing page and zero
countdown placeholders. Neither establishes an online cutoff. Build-end dates
and event-end metadata must not be substituted for submission evidence.

The [rule book](https://lablab.ai/hackathon-rules) and
[terms](https://lablab.ai/terms-of-use) returned no substantive text through the
public extractor again; they are not treated as fully reviewed. The owner needs
to inspect the signed-in form/terms and supply only nonsecret facts: exact cutoff
and timezone/source, enrollment/team/track confirmation, mandatory fields and
formats, acceptable judge access, and how long links must remain available.
No organizer/support message or authenticated portal action was taken.

## Approval packet and completion gates

| Decision still needed | Concrete item to approve / evidence that closes it |
| --- | --- |
| Source rights and publication | Chosen license, contributor/asset rights, finished notices, selected source manifest, clean-checkout/security results, new release SHA, destination public repository and explicit permission to publish. Preserve private main. |
| Judge service and costs | Exact account/SKU/region/DNS, quote including tax/add-ons, credential delivery, approved 72-hour or revised interval, billing exposure/control, engineering acceptance and teardown owner/time. Separate approval before provisioning or opening access. |
| Final media/copy | Release hashes, seven inspected slides/cover preview, actual fully played video with audio/duration/bytes/credits/privacy checks, final counted copy. Keep synthetic recovery, local NVIDIA inspection and AMD-pending status distinct. |
| AMD eligibility | Genuine AMD visual inference **and ReKit integration** under a separately approved qualification. Original 2/6 attempts preserved; no successful response exists. CPU hosting and NVIDIA footage do not close this gate. |
| Human evidence | Preserve and validate actual exports when received; report denominators and variants separately. All 39 remain pending now; do not publish accuracy claims. |
| Submission | Confirm the real online cutoff/form, approved working URLs and final assets; owner authorizes submission and retains the actual portal receipt/time. Documentation completion is not submission completion. |

Ready now: this bounded selection, exact preserved media identities, source
inventory and cost/design proposal. Public release, hosted acceptance, authentic
review, final video, AMD execution/integration and submission remain incomplete.
