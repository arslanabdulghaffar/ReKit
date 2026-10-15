# Submission release and judge-demo review

Reviewed October 15, 2026 (Asia/Seoul), against the accepted Mission 06 checkpoint
`86e970ae85d5ab59d264e28d7d5ec0de86b2d854`. This is a review and proposed release
boundary, not a deployment, license selection or publication authorization.
Mission 06 remains open: two AMD generation attempts returned HTTP 400; neither
establishes successful inference. The user confirms the support email was sent
externally. No duplicate message or further AMD request is authorized here.

## Recommended judge access

The lowest-risk immediate deliverable is the reviewed recording of the working
local workflows. For a judge-accessible application, the proposed first release
is a separate, disposable **CPU synthetic demonstration**, with inference
explicitly disabled and no AMD key, model weights or workstation access. Give
judges viewer access to a populated, clearly labeled demonstration workspace;
show writes through the recorded or presenter-led workflow. Confirm that this
access level satisfies the event before representing it as the required demo.

| Option | What judges actually receive | Status and trade-off |
| --- | --- | --- |
| Recording plus reviewed screenshots | Actual local NVIDIA inspection and separate CPU synthetic recovery, with evidence and limitations | Local capture workflow exists. Final movie and approved hosting are still required. A video URL does not automatically satisfy an application URL field. |
| Isolated CPU viewer application | Existing UI reads synthetic evidence, plans, lineage and audit records through the actual API | Recommended first hosted scope after approval. Backend viewer roles exist; hosting, population/reset procedure, ingress and deployed acceptance are not implemented or verified. No live AI claim. |
| Isolated writable synthetic application | Judges perform intake, human review, planning, reservation and completion | More operational work. Use one disposable instance/database per judging session or a scheduled single-session walkthrough. The current app has no tenant separation or reset endpoint; never give unrelated judges shared write access to the same workspace. |
| Remote live AI application | Real provider execution in ReKit | AMD qualification and application integration are blocked. Local NVIDIA has working demonstration evidence but is not AMD execution. Neither path is approved for public serving. |

The proposed deployment boundary is one HTTPS origin serving the compiled
frontend, with `/api` forwarded to a private single-worker FastAPI service and a
dedicated SQLite database/evidence directory. Keep the backend inaccessible
directly from the Internet. Use only synthetic fixtures; do not copy the local
operational database, `.secrets`, model cache, raw logs or customer imagery.
Disable outbound inference and configure `REKIT_INFERENCE_PROVIDER=disabled`.
No cloud account, paid resource, tunnel or hosting provider was selected.

The frontend already makes same-origin `/api` calls and its local proxy removes
the `/api` prefix. A hosted reverse proxy must preserve that behavior. Serve the
production `frontend/dist` build with an appropriate static server; `vite
preview` is a local preview tool, not the production serving solution described
by [Vite's deployment guide](https://vite.dev/guide/static-deploy.html).
GitHub Pages or any static-only host would not provide the current FastAPI,
SQLite, authentication or inventory workflow by itself.

Before approving this deployment, prepare and review:

- The exact release SHA, sanitized artifact list, chosen host/region, cost ceiling,
  HTTPS URL, owner and removal time. No implicit paid-resource approval.
- Edge access that judges can actually use, plus a separate viewer-only ReKit
  credential delivered through an approved private channel. Never embed a bearer
  in the bundle, source, URL or publicly shared instructions. The current backend
  has no expiring-token issuer; schedule revocation and restart explicitly.
- A controlled population procedure using the real workflow, an isolated data
  directory and an owner-operated reset/recreate procedure. The current replay
  deletes its temporary database and credentials; it is not a persistent hosted
  seed or a hosted reset service. Retain a sanitized receipt of any seeded state.
- Gateway request/body/time/concurrency limits, bounded disk storage, redacted
  logs, least-privilege filesystem access, process supervision, and tested
  restart/cleanup. No aggregate storage quota or public rate limiter exists in
  the application today.
- A fresh-session acceptance: HTTPS and authentication, viewer writes denied,
  API/image access protected, no inference available, clear synthetic labeling,
  intact lineage and page functionality, and usable judge access instructions.
  For writable sessions, also test concurrency and session isolation.

Do not expose the existing workstation, Vite development server, GPU service or
local operator credential through a quick tunnel. The isolated release is
additional work requiring approval, not a capability already deployed.

## Existing security boundaries and remaining gaps

The code review covered [application composition](../backend/src/rekit/main.py),
[authentication](../backend/src/rekit/auth.py),
[image routes](../backend/src/rekit/api/assets.py),
[managed storage](../backend/src/rekit/evidence/assets.py),
[browser transport](../frontend/src/api.ts),
[Vite configuration](../frontend/vite.config.ts), and existing operational docs.

| Inspected behavior | Consequence for release |
| --- | --- |
| Workflow routes enforce bearer roles; human-sensitive operations bind to a human actor. Tokens are high-entropy values stored as digests. | Preserve those checks. A human role is authority, not proof a person is physically present. |
| Browser bearer stays in memory; API requests omit cookies, refuse redirects and avoid caching. Non-health API responses are `no-store`. | Maintain same-origin routing. There is no CORS middleware granting external origins; cross-origin hosting is not currently configured. CORS is not authentication. |
| JPEG/PNG/WebP upload is limited to 10 MiB, 16 million pixels and 8,192 pixels per side, and decoded/verified. | These bound individual images, not aggregate storage or public request rate. Permit only reviewed synthetic content in the proposed hosted scope. |
| Server-owned asset IDs/paths, symlink/junction checks, immutable metadata and content hashes protect managed original bytes; content routes require viewer access. | Do not mount the evidence directory as public static content. Original-byte preservation also retains any source metadata; upload validation is not a privacy sanitizer. |
| Static credentials have no automatic expiry, immediate revocation, MFA or tenant isolation; revocation requires a restart. | Use a disposable scope, least privilege and explicit expiration/removal procedures. Existing bearer authentication alone is insufficient deployment qualification. |
| FastAPI uses its default docs/OpenAPI URLs; no production host middleware or general API rate limiter is configured. | Restrict schema/docs through the reviewed gateway if needed and protect all routes consistently. An open health check is liveness only. |
| The configured app supports separate DB/evidence paths and defaults inference to disabled; the frontend production build exists. | Useful primitives for isolated hosting. No deployment manifest, TLS ingress, production static-serving layer, hosted isolation or operational acceptance was found. |

The latest accepted checkpoint passed 1,449 backend tests, 61 frontend tests,
TypeScript/build and synthetic browser recovery. Those checks establish the
documented local behavior; they are not a public penetration test or proof of
safe hosting. No runtime or NVIDIA environment change was made by this review.

## Security evidence: what was and was not scanned

A full reachable-history review **was performed in Mission 05**. Its final
precommit refresh covered 27 commits, 310 unique blobs, 146 historical paths,
147 current files, 228 artifact text files and 260 deck XML/relationship members.
The [Mission 05 report](reports/development-mission-05.md#security-and-amd-activation)
records zero confirmed exposures/unresolved findings in that scope and its
limitations. It excluded unreachable/reflog objects and was not a universal
secret detector. A presentation-directory ACL issue was corrected then.

The accepted Mission 06 continuation additionally scanned 160 current source
files with zero findings or forbidden paths. That source scan is **not** a new
full-history or selected-media release audit. This review did not rerun the
historical scanner, inspect credentials, publish assets, or contact a dependency
vulnerability service. Dependency graph consistency and passing tests do not
certify vulnerability absence.

Before any public release, scan the exact candidate tree and reachable history
again, review new ignored/generated media selected for sharing, and inspect the
final deck/video for credentials, private browser chrome, Office metadata,
speaker notes, external relationships and source-image restrictions. Record the
release SHA, artifact hashes, scan scope and unresolved findings. Use the
existing private repository as the preserved record; do not rewrite its history
or assume `.gitignore` makes already committed files private. Any separate
sanitized release repository or visibility change needs owner approval.

## Licensing and attribution review

No root `LICENSE`/`NOTICE` or package license declaration was found. The owner
must choose the terms for ReKit code and confirm contributor rights before a
public release is described as open source. Public visibility alone is not an
open-source license, as [GitHub's licensing guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)
explains. No license was selected or added in this task.

| Material | Verified source/status | Required release preparation |
| --- | --- | --- |
| ReKit code, synthetic fixtures, generated presentation | Project-owned scope still needs owner confirmation and license decision. | Approve the code license and exact release assets; keep third-party materials under their own terms. |
| Amazon Berkeley Objects images and metadata | Official [AWS registry](https://registry.opendata.aws/amazon-berkeley-objects/) confirms CC BY 4.0 for all assets, changed from CC BY-NC in 2023. | Retain Amazon/dataset-builder credit, source and license links; identify crops, resizing and overlays. Put usable credit in the delivered video/end card or description, not solely private speaker notes. Preserve the [project attribution](real-product-evaluation.md#source-license-and-attribution). |
| Qwen3-VL-2B-Instruct | The [pinned model card](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct/blob/89644892e4d85e24eaac8bacfd4f463576704203/README.md) declares Apache-2.0. | Credit the model and exact revision for the local NVIDIA segment. Keep weights out of the source release. If redistribution is later proposed, review license/notice obligations separately. |
| Python and browser dependencies | Existing local metadata and npm lockfile inspected; summary below. | Build a release-specific third-party inventory and include required copyright/license notices for material actually shipped. A license name in a lockfile is not the complete notice bundle. |
| GPU runtime, model weights, service terms | Local CUDA software and AMD service access are separate from the ReKit code license. | Do not package the working environment or imply the chosen project license relicenses these components. No new redistribution or AMD model license qualification occurred. |

The [CC BY 4.0 terms](https://creativecommons.org/licenses/by/4.0/) require
appropriate credit, a license link and disclosure of modifications without
suggesting endorsement. The [Apache 2.0 license](https://www.apache.org/licenses/LICENSE-2.0)
sets preservation and redistribution conditions, including applicable notices.
These checks support the release inventory; they do not decide ReKit's license.

### Dependency metadata inspected without installation

The existing `.venv` contains 58 distribution records. This review inspected
metadata for 16 selected runtime, test and AI packages, rather than auditing all
transitive Python license texts. Direct runtime declarations are FastAPI and
Pydantic (MIT), Uvicorn (BSD-3-Clause), OR-Tools (Apache 2.0), and Pillow
(MIT-CMU). HTTPX declares BSD-3-Clause and pytest MIT. Local torch declares
BSD-3-Clause; torchvision's field says BSD. Transformers, tokenizers,
safetensors and huggingface-hub declare Apache licensing; LM Format Enforcer
and interegular declare MIT. Exact versions remain in the existing project pins
and installed metadata; no packages were changed.

The npm lockfile contains 152 non-root entries with license fields: 102 MIT,
28 Apache-2.0, 12 MPL-2.0, two each BSD-2-Clause/BSD-3-Clause/ISC/MIT-0, and one
each BlueOak-1.0.0/CC0-1.0. This includes optional platform packages, not 152
installed or shipped libraries. The three entries marked non-development are
React 19.3.0, React DOM 19.3.0 and scheduler 0.28.0, all MIT. Inspect the actual
built bundle before finalizing a browser notice list.

All 12 MPL entries are the development-only `lightningcss` package and optional
platform variants. This does not establish that MPL code is in the browser
bundle or that ReKit must adopt MPL. If those binaries or modified covered files
are redistributed, review the relevant source/notice obligations against
[Mozilla's MPL guidance](https://www.mozilla.org/en-US/MPL/2.0/FAQ/).
The installed tokenizers metadata declares Apache licensing but lists no
license-named file; its [official v0.22.2 license](https://github.com/huggingface/tokenizers/blob/v0.22.2/LICENSE)
is available for a later approved distribution inventory. Neither observation
is a demonstrated license violation in the current private repository.

## Owner decisions and external dependencies

Ready for review now: this concrete demo boundary, the existing local workflow
and recording instructions, source/model attribution, and the list of release
checks above. Still requiring owner action: the code-license decision,
contributor/asset approval, concrete hosting and budget approval, judge-access
requirements, final media approval, and explicit publication/submission approval.

AMD support must clarify the callable model, image/schema support and quota
behavior before a revised request is proposed. Fresh quota evidence and new
user authorization remain mandatory before exactly one subsequent bounded
attempt. Successful AMD execution and ReKit application integration remain
uncompleted gates; the CPU demo and NVIDIA recording cannot satisfy them.
See the [current Mission 06 report](reports/development-mission-06.md),
[submission checklist](hackathon-submission-checklist.md), and
[recording workflow](demo-recording-workflow.md).
