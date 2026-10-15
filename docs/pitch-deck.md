# ReKit pitch deck

Seven slides, 16:9, for **NeuralFoundry — Forging Intelligent Systems.**
The requested title is **ReKit — AMD-Powered Visual Recovery Intelligence**.
Every use must retain **AMD deployment planned; qualification pending** until
actual AMD execution is qualified. This deck is prepared locally, not published
or submitted.

The October 15 [asset audit](submission-asset-audit.md) rechecked all seven renders
and the unchanged package hashes. It proposes targeted updates to the AMD status,
shared-service measurement wording and title/cover treatment before release;
the historical deck below remains intact.

Mission 06 checkpoint: three authenticated GETs and two single-image synthetic
POST attempts have run through the explicit TokenFactory profile. Both POSTs
returned HTTP 400. The diagnostic replay reported `invalid_request_error`
mentioning the model; its cause remains unresolved. The operator initially
reported 1 pt remaining, while response headers independently reported limit 1,
used 0 and remaining 1 in provider-labelled units. No conversion is established;
reset reports remain inconsistent, and the catalog's strict-schema flag conflicts
with the model reference. HTTP 400 does not establish that an AMD model ran.
Successful AMD visual inference is unconfirmed. No ABO, joint-image, AMD browser or paired
comparison run followed. Retain the qualification-pending narrative below.
The private PowerPoint and its Mission 05 evidence snapshot have not been edited;
see the [Mission 06 report](reports/development-mission-06.md).

## Slide content and design

| Slide | Main copy and purpose | Visual and presentation guidance |
| --- | --- | --- |
| 1. ReKit | Incomplete returns still contain useful parts. Recover compatible kits with visual evidence, human decisions and deterministic allocation. Include team, tagline and the visible AMD qualification statement. | Minimal dark green cover with cream type and lime status text. No industry statistic or measured savings claim. This slide is also a candidate 16:9 cover image. |
| 2. One workflow, accountable decisions | Capture: unique physical ID and original bytes. Inspect: visible AI observations, uncertainty and additional-view requests. Review: explicit identity, revision and visible-condition decisions. Recover: approved BOMs, economic alternatives and exclusive allocation. | Actual original-image UI screenshot beside the four steps. Caption it as two catalog views of one simulated intake record. Preserve ABO attribution. |
| 3. Models observe. Rules decide. | Managed images → AI provider → structurally validated, unverified evidence → human review → compatibility → CPU CP-SAT → human approval → inventory execution. Models cannot verify identity, approve compatibility or allocate stock. | Native editable PowerPoint shapes and arrows. Local NVIDIA is measured; the remote adapter is tested offline and AMD deployment is pending. One modular backend, not eight independently deployed services. The standalone [SVG](assets/rekit-architecture.svg) gives the fuller flow. |
| 4. Real images. Unverified AI. | Pinned Qwen3-VL-2B, RTX 4080 SUPER, one joint two-image request. One component held, zero kits. Repeated appearance text and an uncertainty statement ending mid-thought are preserved. No catalog candidates are allowed in this mode; that is a contract constraint, not recognition accuracy. | Actual result screenshot with unverified labels and original wording. Do not replace claims with improved copy. Explain that scripted rejection requests more evidence; it supplies no independent truth label. |
| 5. A separate, controlled recovery example | Three returns → four unique components → two kit records. USD 175 modeled net disposition value. Approved BOMs and real CPU CP-SAT produce a proposal; human approval reserves four components. Two explicit confirmations consume those four components and record kits. | Actual synthetic completed-kit inventory and lineage. Keep “synthetic” visible in slide text. These are software records from fixture-based decisions, not real rebuilt merchandise, sales or customer savings. |
| 6. Measured execution, honest limits | Task 3 snapshot: 1,121 backend and 57 frontend tests passed. Product inference 38.568 s, provider request 47.187 s, peak allocated CUDA memory 4.902 decimal GB. One joint request; provider time includes cold load. Independent human semantic labels: zero. Accuracy is not measurable. | Native editable table. Distinguish inference from request and browser timings. Do not infer p95, throughput, total GPU memory use, safety or business performance from this single observation. |
| 7. AMD is the next execution gate | Qualify authorized hardware, actual VLM/revisions and image/schema support. Connect the existing HTTPS provider with server-only credentials. Measure real images, errors, memory, latency and human-review behavior. Business potential: compatible stock recovery with traceable decisions. | Dark green close. State that successful AMD visual inference remains unconfirmed. Next gates are AMD qualification and independent human review before a measured customer pilot. Evolus remains optional and unimplemented. |

Use Arial, the existing dark green/cream/lime palette, large titles and generous
spacing. Tables, text and the architecture remain editable. Screenshot crops are
native PowerPoint crops of embedded original PNGs; original pixels are retained.
Exact source paths, hashes, crop coordinates, model revision and attribution are
recorded in the source notes and build receipt. There are no fabricated AI screens.

## Local assets and reproduction

The installed Microsoft PowerPoint application creates and renders the deck.
No new package, template framework, model or external service is required.
The presentation skill's bundled artifact runtime was unavailable; installed
PowerPoint provided the authorized local fallback.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build_pitch_deck.ps1
```

Run from the repository root after closing your own PowerPoint session. The
builder refuses to run when PowerPoint is already open, refuses to overwrite an
existing output directory and writes only to a fresh directory under ignored
`var/mission05-submission/`. It validates the supplied successful run receipts and
source files before authoring. Before writing any evidence, it restricts the new
output's Windows access list to the current user, SYSTEM and Administrators;
files and slide renders inherit that restriction. Git ignore rules alone do not
restrict local readers. Its default inputs are:

- Product: `var/mission02-acceptance/run-ai-5p7lbguu/`.
- Recovery: `var/mission02-acceptance/run-g563yhm_/`.

The selected final output directory is
`var/mission05-submission/deck-20261014-152027-67d97c/`:

- `ReKit-NeuralFoundry-pitch.pptx`: seven-slide editable presentation.
- `slides/slide-01.png` through `slides/slide-07.png`: native 1920 × 1080 renders.
  `slide-01.png` is the candidate cover; review the actual submission form before use.
- `build-result.json` and `visual-qa.json`: geometry, source, editability and visual checks.

The deck SHA-256 is
`df4f150be4c6dc562e0b170f2e0c3a173f166e128fbe6a0d03bab0e0f970865a`.
All seven slides were inspected. The three screenshot crops match their source
coordinates and preserve aspect ratio; embedded PNG hashes match their originals.
The final file contains 87 native text shapes, one editable table and seven
architecture connectors. Earlier drafts exposed text-fit and crop-coordinate
issues; use only the selected final directory above. The PowerPoint process
closed successfully. The standalone SVG also passed rendered text-bound checks.

Generated files stay local and ignored. The builder opens its own hidden
presentation, writes native PPTX and PNG renders, checks object/text bounds and
Open XML editability, and closes only the application it started. A successful
build does not replace visual inspection; inspect every exported slide after
any change, including screenshot crops and actual model wording.

## Attribution and limits

Amazon Berkeley Objects (c) by Amazon.com, **CC BY 4.0**. The deck includes source
and license links and full builder credits in the relevant slide notes; on-slide
captions identify screenshot crops. See the [official dataset README](https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/README.md),
[license](https://creativecommons.org/licenses/by/4.0/) and
[project attribution](real-product-evaluation.md#source-license-and-attribution).
Same-listing images do not prove one physical returned unit. Qwen/Qwen3-VL-2B-Instruct
is attributed under Apache-2.0 with the [pinned model provenance](local-inference.md).
No endorsement is implied.

The complete [submission copy](submission-content.md) and
[provisional four-minute recording script](demo-script.md) provide narration and
limitations. Follow the [recording workflow](demo-recording-workflow.md) for
private capture, current provider wording, evidence checks and export review;
no final video has been produced by the launcher or this guide.
The [submission checklist](hackathon-submission-checklist.md) records unconfirmed
cutoff/timezone, publication and licensing decisions, judge-accessible hosting,
final video, actual AMD evidence and submission receipt as outstanding gates.
