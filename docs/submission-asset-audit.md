# Submission asset audit

October 15, 2026 (Asia/Seoul). Review baseline:
`86e970ae85d5ab59d264e28d7d5ec0de86b2d854`. This audit inspected all seven existing
PNG renders, the PPTX package and notes, the recording script and submission copy.
It did not edit or re-render the PowerPoint, capture video, run inference or publish.

## What is ready for owner review

The seven-slide deck is readable, uses consistent typography and preserves
actual screenshots. The reviewed artifact is
`var/mission05-submission/deck-20261014-152027-67d97c/ReKit-NeuralFoundry-pitch.pptx`
(442,689 bytes), SHA-256
`df4f150be4c6dc562e0b170f2e0c3a173f166e128fbe6a0d03bab0e0f970865a`.
Its seven PNG renders are each 1920 x 1080. Slide 1 is the candidate cover:
46,125 bytes, SHA-256
`a66407bc4b08f83cb43b489948891bf1b8fac4449992f7208a51ef01bfd93846`.
Both match the prior build/QA receipts. All originals remain unchanged.

The existing deck is a dated Mission 05 snapshot. It is ready for content review,
not a claim that the final release assets are approved. These targeted revisions
should precede a new release export; preserve the historical artifact and notes.

| Asset | Audit finding | Proposed release treatment |
| --- | --- | --- |
| Slide 1 / cover | The requested AMD-Powered title is prominently qualified by AMD deployment planned; qualification pending. No successful AMD inference is implied by the qualifier, but a cropped thumbnail or title-only portal field can lose it. | Until AMD succeeds, recommend the neutral portal title **ReKit — Visual Recovery Intelligence** (36 characters). Owner decides whether to retain the requested 48-character title. If retained, keep the pending qualifier adjacent and uncropped; verify the actual portal preview. No title was silently changed. |
| Slide 2 | Original ABO views are correctly identified as one simulated intake record; visible source credit is present. | Keep this distinction. These are catalog views, not evidence of an actual returned unit or a complete approved BOM. |
| Slide 3 | Human authority, physical identity, deterministic CP-SAT and atomic stock changes are clear. AMD: offline tests is historical shorthand that omits the two failed live attempts. | Suggested box text: **Local NVIDIA: measured / AMD: qualification pending**. Explain the two HTTP 400 attempts in the closing status, without claiming model execution. |
| Slide 4 | Actual repeated model text and unfinished uncertainty are preserved; one held component, zero kits and no recognition-accuracy claim are visible. | Retain the observed limitation. A new recording must show its own output; do not replace this screenshot's prose with a stronger answer. |
| Slide 5 | Three returns, four parts, two software kit records and USD 175 modeled value are clearly separated from the real-image track. | Retain synthetic labeling and explicit human-role decisions. Demonstrating an improved integrated case later requires new linked evidence, not relabeling this fixture. |
| Slide 6 | 1,121/57 tests and local inference timings are accurate for the October 14 snapshot, not the current software totals. | Either keep the snapshot date explicit, or update only the test row to the separately validated 1,449/61 checkpoint. Do not merge local timing measurements from different runs. Zero independent semantic labels remains current. |
| Slide 7 | AMD is clearly a future gate. Immutable revisions and GPU memory are currently phrased as future measurements, but the shared TokenFactory route may not expose them. | Use the concrete closing copy below. Preserve unknown hardware/runtime/revisions; actual service response metadata is the limit of any future claim. |
| Script | Previously combined instructions for fresh replay with historical model wording/timings. | The updated [script](demo-script.md) separates dated stills from fresh motion and uses the latter's actual receipts. Recording, voiceover, editing and final playback remain undone. |
| Descriptions | Summary is 224 characters; full field is 323 whitespace-separated words. Both correctly state that AMD inference is unverified and economics are modeled. | Keep the counted fields until owner review. If updated, distinguish the immediate TokenFactory path from a later owned ROCm/vLLM deployment and recount. No actual AMD GPU/runtime performance is known. |

## Proposed closing slide copy

**AMD visual qualification is pending.** Two synthetic-image requests returned
HTTP 400. AMD support has been contacted externally; no successful AMD model
response or ReKit application acceptance is available yet.

1. **Qualify:** confirm the callable model and strict image/schema contract;
   review fresh quota and obtain approval for one bounded attempt.
2. **Integrate:** preserve image hashes, model provenance and unverified output
   in ReKit; demonstrate human rejection/correction and deterministic decisions.
3. **Measure:** report actual latency, errors, quota and supported metadata.
   Keep unreported model revisions, hardware, runtime and GPU memory unknown.

Suggested replacement for the full-description AMD paragraph, for review only:

> AMD TokenFactory is the current qualification path behind the existing remote
> adapter; an owned ROCm/vLLM deployment remains a later option. Two synthetic-image
> requests returned HTTP 400, so no successful AMD visual inference or application
> integration is claimed. Independent human semantic reviews remain zero;
> recognition accuracy and business impact are unmeasured.

The original field is unchanged. If approved, merge this paragraph without losing
the explanation of ReKit's contribution and recalculate the complete field count.

## Package and release checks

The PPTX contains seven slides, seven notes sections and three embedded PNGs.
Notes contain ABO source/license links and the pinned Qwen model-card link.
They also contain relative local `var/` evidence paths. Office creator and
last-modified-by fields are populated; their values were not echoed in this audit.
No Windows absolute path was found in extracted notes. This is a bounded package
inspection, not a complete private-data or secret clearance.

Before release, create a separate sanitized export: review author metadata,
notes, links and embedded originals; retain useful source/license attribution and
move internal-only evidence paths out of public notes where appropriate. Do not
strip provenance from the private original. Check any PDF export and all final
video frames separately. On-screen screenshots carry a generic scripted reviewer
name, which must not be described as an independent human annotation.

Attribution must survive the delivery format. A video has no PPTX notes, so include
ABO/Amazon.com CC BY 4.0 credit, source/license links and crop disclosure in its
end card or accompanying description, plus Qwen's pinned local provenance.
See [release review](submission-release-review.md) for rights/security checks and
[recording workflow](demo-recording-workflow.md) for immediately available work.

No new deck, cover, movie, final release clearance or submission is claimed.
