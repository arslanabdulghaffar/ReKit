# ACT III submission checklist

Event dates and general media guidance rechecked October 15, 2026 (Asia/Seoul).
Team: **NeuralFoundry**. This is a
preparation checklist, not a submission receipt or eligibility claim. ReKit
remains private. This document authorizes no publication, hosting, licensing
change, spending or authenticated AMD call.

## Readiness at a glance

Mission 06 remains open. AMD's reply referred the owner to a feedback portal;
access failed and the owner submitted an account-support form under Login.
No definitive API solution is available. Do not duplicate contact or consume another attempt.
The original two HTTP 400 attempts remain charged. The owner's approximately
four-day horizon is a planning assumption, not a confirmed cutoff.

| Completed and ready for review | Evidence |
| --- | --- |
| Working local implementation and synthetic recovery | Accepted checkpoint `86e970a`; 1,449 backend / 61 frontend tests, build, CPU recovery and browser replay passed. These are prior verified results, not new tests in this documentation review. |
| Media/copy audit | All seven existing renders, cover, PPTX package, notes and description counts rechecked in the [asset audit](submission-asset-audit.md). Original deck and counted fields preserved. |
| Concrete recording workflow | [Script](demo-script.md) and [workflow](demo-recording-workflow.md) now distinguish dated stills from fresh footage and identify immediate work, manual capture and AMD dependencies. |
| Judge-access and release assessment | [Release review](submission-release-review.md) proposes a disposable CPU viewer demo and records security/licensing gaps. No host or license selected. |
| Improvement priorities | [Winning-quality assessment](winning-quality-assessment.md) links judge criteria to measured strengths, gaps, proposed improvements and acceptance criteria. No Mission 07 or major new feature started. |
| Block B implementation | [Current implementation report](reports/winning-quality-block-b.md): canonical evidence-to-kit case, complete economic alternatives, focused source/correction/lineage UI and twelve-group pending review package. These are synthetic workflow and software results, not independent visual accuracy or AMD qualification. |
| Block C review candidates | [Block C report](reports/winning-quality-block-c.md): clearer immutable assumptions and selected-action calculations, [reviewer guide](independent-review-guide.md), separate seven-slide [deck/cover](pitch-deck.md#block-c-candidate-for-owner-review), and [recording storyboard](block-c-recording-storyboard.md) with a labeled silent-stills draft. All human assessments remain pending; release approval is still required. |

| Remaining blocker | Owner / dependency | Completion evidence required |
| --- | --- | --- |
| Actual AMD visual inference and integration | AMD support, then owner approval of concrete request and fresh quota | One approved synthetic attempt first, preserving 2/6 history; validated output, application provenance and separately approved acceptance. A successful stand-alone call alone is insufficient. |
| Exact online cutoff, eligibility and form | Owner / organizer | Explicit cutoff and timezone, source/date, track, required fields, limits and judge access expectations from the signed-in form or organizer. |
| Independent visual-quality evidence | Human reviewer | Completed existing assessment records with visible evidence and denominators; no invented labels or accuracy. |
| Title and deck release copy | Owner review of separate Block C candidate | Approve the neutral title, seven-slide deck and cover against the actual form. Candidate renders are inspected; original deck and submission fields are preserved. |
| Final video | Recorder/narrator/editor | Actual captured or clearly labeled still-based movie, readable 16:9 edit, attribution, full playback/privacy review, duration/size/hash and final approval. |
| Judge application URL | Owner authorization plus isolated hosting work | Reviewed host/cost/access proposal and fresh-session deployed acceptance. A recording or static frontend alone does not supply the working API. |
| Public source and rights | Owner license/visibility decisions | Contributor rights, chosen license, third-party notices, exact release/history/media scan and approval. Repository stays private until then. |
| Submission | Owner | Approved final files and URLs, completed form, actual receipt/timestamp. No submission has been made. |

Immediately useful work does not depend on AMD: rehearse the narration, organize
existing evidence, record the local/synthetic segments, perform human review,
prepare attribution, and review the targeted deck changes. Keep the AMD closing
segment replaceable; do not spend this time adding unrelated features.

## Public requirements and unresolved deadline

The [official event page](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii)
lists October 12–18, 2026, and requires meaningful AMD execution in the working
product for prize eligibility. Deliverables include title, descriptions,
challenge, technology tags, prototype, cover, video, slides, public GitHub,
demo platform and application URL. It also states originality and MIT compliance.

- [ ] Confirm the submission cutoff **and timezone** in the portal or with the
  organizer. New authoritative evidence: the organizer's
  [Milan](https://luma.com/AMDHackathon-Milan),
  [Rome](https://luma.com/AMDHackathon-Rome) and
  [Imperia](https://luma.com/AMDHackathon-Imperia) agendas explicitly state a
  Sunday October 18 submission deadline at 16:00. Milan's public event metadata
  specifies `Europe/Rome`; applying that zone gives **October 18, 2026, 16:00
  CEST / 14:00 UTC / 23:00 KST**. This verifies an **on-site agenda cutoff**;
  applicability to ReKit's online submission form remains unconfirmed. The time
  comes from the submission agenda, not event-end metadata. The public
  [live page](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii/live)
  still describes online building as October 12–17, while the landing page says
  October 12–18. Both were freshly read. The live page labels submissions open,
  but its extracted countdown contains zero placeholders, not a usable deadline.
  Neither inspected page establishes the submission cutoff or timezone; the
  landing page's event schedule is still to be announced. Other searches did not
  establish an online-specific official cutoff. Do not substitute an event date,
  venue closing time or the countdown placeholder for the submission deadline.
  Earlier live-page metadata recorded `endAt=2026-10-18T15:00:00.000Z`, equivalent
  to October 19 at 00:00 in Korea. That was **event-end metadata, not a submission
  deadline**. That timestamp was not freshly reverified during this continuation;
  the earlier unauthenticated raw-page request returned HTTP 403. Obtain an
  explicit online cutoff, source and timezone from the portal or organizer.
  This review sent no organizer message; the user's separate AMD support email
  is already sent and must not be duplicated.
- [ ] Confirm enrollment, team membership, challenge and required fields in the
  authenticated form. No account-specific form was inspected. Proposed challenge:
  Reinvent Commerce; confirm its fit before submission.
- [ ] Read the current [rule book](https://lablab.ai/hackathon-rules) and
  [terms](https://lablab.ai/terms-of-use) before release. The public text extractor
  returned no substantive body for these links. Do not treat them as reviewed or
  automatically add an MIT license.

## Copy and media preparation

The [general submission guide](https://lablab.ai/ai-articles/hackathon-guidelines)
states a 50-character title maximum, 255-character summary maximum and 100-word
long-description minimum. It recommends a 16:9 cover and specifies a video within
five minutes and below 300 MB. These are general guidance; verify the event
form's actual limits, required fields and file formats before uploading.

- [x] Draft the title, team/tagline, short/full descriptions, problem, solution,
  AI, deterministic optimization, human authority, AMD status, novelty, business
  potential and limits in [submission content](submission-content.md). The exact
  requested title is 48 characters; the summary is 224 characters.
- [ ] Review final copy against the form. Keep **AMD planned / not yet executed**
  prominent until actual execution evidence changes that status.
- [x] Prepare and inspect the seven-slide editable PowerPoint and its seven PNG
  renders at `var/mission05-submission/deck-20261014-152027-67d97c/`. The first
  slide is a candidate 16:9 cover. Text bounds, editability, original embedded
  image hashes and native crop coordinates passed checks. See the
  [deck guide](pitch-deck.md) and editable [architecture SVG](assets/rekit-architecture.svg).
- [ ] Approve the deck and cover for release against the actual form; these
  private assets have not been uploaded. Follow the [recording script](demo-script.md).
- [ ] Record and inspect the final video using the prepared
  [capture-to-release workflow](demo-recording-workflow.md). **No final video has
  been recorded or uploaded.** Screenshots, scripts and browser runs are not a video.
- [ ] Retain [ABO attribution](real-product-evaluation.md#source-license-and-attribution)
  and [Qwen provenance](local-inference.md), identifying presentation crops or
  overlays. Do not relicense their source material.

## Current implementation evidence

These are Mission 05 Task 3 observations, separate from historical results in the
[Mission 01](reports/overnight-mission-01.md),
[Mission 02](reports/development-mission-02.md),
[Mission 03](reports/development-mission-03.md) and
[Mission 04](reports/development-mission-04.md) reports.

- [x] Local checks: **1,121 backend tests and 57 frontend tests passed**, plus
  TypeScript/build/dependency checks. They test software behavior, not visual
  accuracy, business savings or AMD performance.
- [x] Real-product browser/API: `var/mission02-acceptance/run-ai-5p7lbguu/` passed
  in 49.8 seconds; its one joint two-image local inference took 38.568 seconds.
  One simulated physical unit stayed held, with zero identity verifications,
  reservations or kits. Six actual captures include originals, pending analysis,
  the unverified result and the held state.
- [x] Separate synthetic recovery: `var/mission02-acceptance/run-g563yhm_/` passed
  in 5.4 seconds, with three returns, four unique components, four reservations
  and two confirmed kit records. **USD 175 is modeled scenario value**, not a
  sale, actual recovered merchandise or measured customer savings. Fourteen
  captures cover the workflow and responsive layouts.
- [x] Synthetic AI regression `run-ai-kny95rau` made two actual local requests and
  passed. It preserved and rejected an unsupported `body/A` hypothesis on a
  shapes illustration before separate fixture-based human verification. Keep
  this model limitation visible alongside the successful workflow.
- [x] The verified cache has 52 catalog images across 48 listing groups. The
  selected review gallery has 19 images from 18 groups, all pending. Independent
  human semantic reviews remain **zero**. Accuracy and unsupported-claim rates
  are **not measurable**, rather than zero error.
- [x] Mission 04's fixed-sample before/after test used 26 local requests.
  No-catalog candidate violations changed from 9/13 to 0/13 after an explicit
  restriction: protocol enforcement, not recognition improvement.

Recheck final artifact paths and counts before release. Do not merge historical
and current runs into an unlabeled benchmark or count a browser/API request twice.

Mission 06's HTTP 400 continuation separately reran 1,449 backend tests and 61
frontend tests, TypeScript/build and the CPU synthetic evaluation. A new synthetic
browser replay, `var/mission02-acceptance/run-fc_4k8wo/`, passed in 5.4 seconds,
reserved four components and completed two kits, with state/credentials removed.
No model ran in that replay. Local product preflight verified the ten pinned
model files, original ABO inputs and CUDA device 1 without loading a model or
performing inference. These checks preserve the local demonstration, not AMD
eligibility. See the [current report](reports/development-mission-06.md).

## Remaining release and eligibility gates

- [ ] Qualify AMD execution. **Successful AMD visual inference: unconfirmed.**
  Mission 06 records three GETs and two single-image POST attempts, both HTTP 400;
  those rejections do not prove model execution. Two of six attempts remain
  charged. The [current report](reports/development-mission-06.md) and
  [retained support draft](tokenfactory-support-request.md) describe the blocker.
  The owner reports a reply referring them to a portal they could not access,
  followed by an account-support form under Login. No definitive API solution or
  model-access confirmation is available.
  Further API calls require provider clarification, fresh quota evidence and new
  user approval. Local NVIDIA execution does not verify AMD eligibility. Preserve
  actual model, input, output and failure evidence before application acceptance;
  do not invent GPU/runtime or revision attestations for the shared service.
- [ ] Obtain explicit approval before publishing a reviewed release or changing
  repository visibility. Preserve the private repository until then. Audit
  release content/history for secrets and private assets; resolve code licensing
  and third-party notices separately.
- [ ] Arrange an approved judge-accessible demo and test its URL from a fresh
  session. The loopback launcher is not public hosting. Do not expose a local
  operator token or development server to satisfy this field.
- [ ] Review every capture for tokens and private data. Keep synthetic examples
  separate from original catalog imagery. Such imagery cannot establish an
  actual returned unit, approved BOM, revision, hidden function or safety.
  Model confidence statements are not calibrated probabilities.
- [ ] Submit only after the owner approves the concrete release, media and portal
  content. Preserve its receipt, timestamp and submitted URLs. These documents
  do not submit, host or publish anything.

## Optional Evolus track

The [Evolus track](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii)
adds an event workspace, an owned open-model vLLM endpoint on AMD Developer Cloud,
two or more Evolus building blocks, application API integration, a containerized
app and runnable public repository. ReKit has not implemented Evolus.

- [ ] Claim this optional track only after demonstrating its requirements. A
  generic remote adapter or shared endpoint does not establish completion.
