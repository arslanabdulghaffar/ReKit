# ACT III submission checklist

Public sources checked October 14, 2026. This is a preparation checklist, not a
submission receipt or eligibility claim. ReKit remains private. No publication,
hosting, cloud spending or submission is authorized by this document.

## Confirm the deadline and current form

- [ ] Confirm the submission cutoff and timezone in the authenticated event portal.
  The [event page](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii)
  lists October 12–18, 2026. Observed
  [live-page](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii/live)
  data has `endAt=2026-10-18T15:00:00.000Z`: October 19, 00:00 Korea time.
  This is the event end, **not a confirmed submission cutoff**.
- [ ] Verify enrollment, team details and the actual form's required fields before
  preparing final uploads. Account-specific form requirements have not been inspected.

## Event-listed deliverables and remaining gates

The [official event page](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii)
lists title, short/long descriptions, challenge/tags, working prototype, cover,
demo video, pitch slides, public GitHub, demo platform and application URL.

- [ ] Prepare those fields and assets; verify every external link as a judge would.
  The local loopback workbench is not a publicly accessible application URL.
- [ ] Complete actual, meaningful AMD execution in the demonstrated product; the
  event makes AMD use an eligibility requirement. ReKit's remote adapter has only
  offline qualification. Local NVIDIA results do not satisfy this gate. Follow
  [activation](../deploy/amd/README.md#activation-checklist) and preserve real
  endpoint, hardware/runtime, revision and image-execution evidence.
- [ ] Prepare a reviewed release and obtain **explicit user approval before changing
  repository visibility or publishing**. The event lists public GitHub; the current
  private repository must remain private until approved. Check staged content and
  history for credentials, personal data, operational images and generated artifacts.
- [ ] Verify applicable originality and licensing rules against the
  [event notice and linked rule book](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii).
  Resolve the stated MIT-compliance requirement without changing third-party
  dataset/model licenses or assuming a code license has already been chosen.

## General lablab guidance: recheck against the actual portal

The linked [submission guidelines](https://lablab.ai/ai-articles/hackathon-guidelines)
give a title limit of 50 characters, summary limit of 255, long description of at
least 100 words, recommended 16:9 cover, and video within five minutes and below
300 MB. These are general guidance, not a verified reading of this event's form.

- [ ] Fit the final copy and media to the live form's limits; prepare the
  [demo script](demo-script.md) as an actual screen recording, not fabricated output.
- [ ] Prepare concise slides covering user/problem, evidence workflow, deterministic
  decisions, measured results and limitations. An architecture diagram is recommended
  for clarity; no inspected source explicitly makes a separate diagram mandatory.
- [ ] Confirm accepted media formats, hosting permissions and access settings in
  the submission form. A generated screenshot set is not a submitted video or deck.

## Evidence and honest claims

- [x] Real-product browser/API gate passed on its first attempt: 49.8 seconds,
  Chrome 154.0.8037.98, one actual joint request. The component stayed held with
  zero verification, plans or kits; auth, byte integrity, duplicate-upload and
  cleanup checks passed. Evidence: `var/mission02-acceptance/run-ai-_hto37ic/`;
  see [demo results](demo-script.md#completed-real-product-acceptance).
- [x] Corrective Task 3 CPU CI passed both jobs in
  [run 38453167659](https://github.com/arslanabdulghaffar/ReKit/actions/runs/38453167659)
  at `6dd805ee44b132c83a24e7471a187a2e9c512e25`. This is not a future Task 4
  commit/CI result.
- [x] Task 4 synthetic regressions passed: actual-AI `run-ai-n2j7_p4b` in about
  1.2 minutes and default `run-qz_ybush` in 4.4 seconds. Their 13 screenshots were
  inspected; all three browser runs passed cleanup. Final local checks passed
  1,007 backend tests, 51 frontend tests, typecheck, build and dependency checks.
  Exact commands and artifacts are in the
  [Mission 04 report](reports/development-mission-04.md); final Task 4 commit/push
  and post-push CI are separate release evidence.
- [ ] Label ABO image intake as a simulated, unverified physical-unit workspace.
  Catalog/listing membership does not establish a returned unit, BOM, revision,
  functional condition or safety. Preserve actual model outputs and source hashes.
  The completed one-request photo demonstration left its single component
  held, with no verification, reservation or kit. Reuploading the originals is a
  deduplication check, not newly captured evidence.
- [ ] Keep synthetic recovery separate: three returns, four unique components,
  two kits and USD 175 modeled net value. Do not call this real recovery revenue,
  customer savings or a recognition benchmark.
- [ ] State zero independently human-reviewed semantic labels. Accuracy and
  unsupported-claim rates are unmeasurable, not 0% error. Task 2's 26 local requests
  and 9/13-to-0/13 no-catalog candidate change establish constraint compliance only.
  The separate real-product browser/API run adds one request, counted once:
  27 real-catalog-image requests total. The clipped uncertainty and appearance
  claims remain unverified despite the software gate passing.
- [ ] Retain [ABO source/license attribution](real-product-evaluation.md#source-license-and-attribution)
  and [Qwen model attribution](local-inference.md); identify image modifications.
  Do not publish image bytes, weights or private execution records accidentally.
- [ ] Review screenshots/video for tokens and private data, preserve actual
  unverified/held states, and distinguish CPU tests, local GPU execution and any
  later AMD measurements. Model confidence wording is not a calibrated probability.

## Optional Evolus award

The [Evolus track](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii)
requires an event workspace, an open model through the team's own vLLM endpoint on
AMD Developer Cloud, at least two Evolus building blocks, application API
integration, a containerized app and runnable public repository. ReKit has not
implemented this integration; shared TokenFactory access alone does not meet it.

- [ ] Claim this award only after implementing and demonstrating its actual
  requirements. It remains optional and separate from the core AMD gate.
- [ ] After release, media and submission actions receive approval, submit through
  the portal and preserve the receipt, timestamp and exact submitted URLs. Until
  then, report the project as prepared or incomplete, never submitted.
