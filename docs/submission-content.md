# ReKit submission content

Prepared October 14, 2026 for NeuralFoundry. This is editable submission copy,
not a submission receipt. **Actual AMD execution is pending.** The requested
title describes the intended deployment; retain this qualification wherever it
is presented until the AMD gate passes.

Mission 06 checkpoint, October 15: TokenFactory's exact remote profile and
read-only discovery are implemented. An actual catalog response lists MiMo as
image-capable, but quota and strict-schema execution remain unqualified. No
image has been sent to the service. This does not change the pending-inference
claims in the submission fields below; see the
[Mission 06 report](reports/development-mission-06.md). Nothing was submitted.

## Identity and form limits

| Field | Copy | Count |
| --- | --- | ---: |
| Project title | ReKit — AMD-Powered Visual Recovery Intelligence | 48 characters |
| Team | NeuralFoundry | 13 characters |
| Team tagline | Forging Intelligent Systems. | 28 characters |
| Proposed challenge | Reinvent Commerce | Confirm in the event form |

The [general lablab guide](https://lablab.ai/ai-articles/hackathon-guidelines)
specifies at most 50 title characters, at most 255 summary characters and at
least 100 words for the long description. Counts exclude headings and formatting;
characters include spaces and punctuation, and words use whitespace separation.
The authenticated event form has not been inspected.

## Short description

<!-- short-description:start -->
ReKit links visual evidence, human review and deterministic planning to recover compatible kits from incomplete returns. Local AI and transactional workflows work today; AMD cloud inference is planned and remains unverified.
<!-- short-description:end -->

224 characters. Suitable for the general 255-character summary field.

## Full description

<!-- full-description:start -->
ReKit helps returns operators assess incomplete products and plan compatible kits across multiple returns. A missing adapter in one return may be available in another, but visual similarity alone cannot establish identity, revision, condition or permission to reuse it.

The working prototype connects photographic evidence to an accountable recovery workflow. Operators register physical components, add multiple views to the same identity and inspect the original images before AI suggestions. Qwen3-VL-2B-Instruct runs on a local NVIDIA GPU through PyTorch and Transformers. Constrained generation and strict validation preserve observations, suggested identities, uncertainty and requests for additional views, with original image hashes and model provenance. Model output remains unverified; a separate human decision records identity, visible condition, supporting observations and a reason.

Approved catalog, BOM, revision and condition rules determine compatibility. A CPU OR-Tools CP-SAT optimizer compares complete rebuilds, donor retention, permitted liquidation, salvage and holds using explicit cost, labor and demand assumptions. Each physical component receives one disposition. Approval rechecks the current evidence and atomically reserves the selected components. Explicit completion records preserve kit lineage and audit history.

Two demonstrations separate image inspection from reconstruction. A real-image browser run inspected two original Amazon Berkeley Objects catalog views in one simulated intake record. The component remained unverified and held, with no reservations or completed kits. A separate synthetic scenario used three returns and four components to produce two operator-confirmed kit records with USD 175 of modeled recovery value. That figure is an estimate from supplied assumptions, not realized revenue or measured customer savings.

AMD Developer Cloud with ROCm and vLLM is the intended production inference path. A bounded remote adapter is implemented and tested offline, but no actual AMD inference has been completed. The project remains a local prototype with zero independent human semantic reviews. Recognition accuracy and business impact are therefore unmeasured. ReKit's contribution is a traceable connection from uncertain visual evidence to deterministic planning and controlled execution, with humans retaining verification and approval authority.
<!-- full-description:end -->

323 words, exceeding the general 100-word minimum. This is the complete field
copy; the following sections support optional portal fields and the pitch.

## Problem and manual inefficiency

An incomplete return contains items whose identity, revision, visible condition
and compatibility must be established before recovery. Operators must compare
markings with product records, search other returns, track allocated parts and
calculate costs while preserving reasons for their decisions. If images, notes,
catalogs and stock records are disconnected, these lookups and reconciliations
can be repeated. This is the workflow problem ReKit addresses; no customer time
study or measured labor reduction has been completed.

## Solution and actual AI

ReKit connects managed image intake, an operator workbench, bounded inference,
versioned evidence, catalog checks, economic planning and transactional execution.
Multiple views stay attached to one physical ID. Human corrections append
evidence rather than erasing earlier assertions.

The actual local model is pinned **Qwen/Qwen3-VL-2B-Instruct**, using Transformers
4.57.6 and PyTorch 2.9.0+cu128 on one selected RTX 4080 SUPER. LM Format Enforcer
0.11.3 constrains output shape; independent parsing rejects invalid results.
Requests use one or two managed images and retain ordered source hashes, raw
output, settings and measured execution metadata. Schema validity does not
establish visual truth. Separate localization, dedicated OCR, catalog-image
matching and automatic camera capture remain future work.

## Deterministic optimization and human verification

The model cannot approve compatibility, allocate stock or confirm completion.
Server-approved policies decide admissibility. CP-SAT searches feasible actions
under physical uniqueness, BOM quantities, revision, condition, labor and demand
constraints. Money uses integer cents; retained donor value is noncash. Results
expose solver status, bounds and comparisons with retaining components.

Authorized people verify or correct identities, reject unsupported suggestions
and approve a plan snapshot. Transactions reserve components exclusively and
reject stale or conflicting actions. Completion is a separate explicit operator
confirmation, not a claim of automatic assembly or hidden functional testing.

## AMD use: planned, not qualified

The intended production path is AMD Developer Cloud, ROCm and a compatible vLLM
vision endpoint behind the existing provider contract. The implemented remote
adapter uses an exact HTTPS allowlist, bounded original-image transport and strict
response validation, with no automatic retry or fallback. Its qualification uses
controlled offline endpoints only.

**Actual AMD requests: 0.** No AMD performance, deployed model revision or remote
hardware claim is supported yet. A configured remote model ID is not hardware
attestation. Follow the [activation gate](../deploy/amd/README.md#activation-checklist)
before claiming completion of the event's AMD workload.

## Technical novelty

The distinctive design choice is the boundary between visual claims and
operational decisions: immutable multi-view evidence feeds human verification,
approved compatibility rules, constrained allocation and atomic inventory
updates. A plausible AI label cannot silently become a reserved part. Failed,
stale and rejected runs remain auditable. This is a design contribution, not a
claim of patent novelty or market uniqueness.

## Business value and future potential

Potential users include merchant returns teams, refurbishment operators and
service-parts teams. ReKit could help them compare recovery options, coordinate
scarce donor components and explain why an item remains held. A pilot needs
approved real catalogs, independent product review and measured labor, recovery
yield, exception and cost outcomes before any savings claim.

Future work includes AMD qualification, representative held-out evaluation,
broader BOM/revision coverage, dedicated OCR/localization/matching, inventory
integration and guided rebuilding. Optional Evolus workflows could coordinate
approved APIs later; no Evolus integration or award eligibility is claimed.
Deployment access controls, retention and backup practices also need operational
qualification.

## Verified demonstration and limitations

| Evidence | Observed result | What it does not establish |
| --- | --- | --- |
| Real-product browser/API, `run-ai-5p7lbguu` | 49.8-second gate; one two-image request; 38.568-second local inference; one held component; zero identity verifications, reservations or kits | Independent visual truth, actual returned-unit identity or AMD execution |
| Separate synthetic recovery, `run-g563yhm_` | 5.4-second gate; 3 returns, 4 physical components, 2 confirmed kit records; USD 175 modeled value | Real rebuilt merchandise, revenue or customer savings |
| Synthetic AI regression, `run-ai-kny95rau` | Two actual local requests; unsupported ambiguous identity rejected before separate fixture-based verification | Autonomous identification accuracy |
| Mission 05 Task 3 checks | 1,121 backend tests; 57 frontend tests; TypeScript/build/dependency gates passed | Production readiness or inference quality |
| Independent review preparation | 52 cached catalog images; selected gallery 19 images/18 groups; all pending; zero independent reviews | Accuracy or unsupported-claim rates; these remain unmeasurable |
| Mission 04 fixed-sample comparison | 26 local requests; no-catalog candidate violations 9/13 before, 0/13 after an explicit restriction | Recognition improvement or spontaneous model abstention |

Local run artifacts above are under `var/mission02-acceptance/`. Catalog images
are not verified photographs of customer returns; the cache includes composites,
charts and a logo. Model output has included unsupported identities and bounded,
unfinished prose. Confidence language is not a calibrated probability. Images
cannot establish hidden function or safety. The demo catalog and kit-recovery
economics are synthetic.

## Assets and release status

Use the [recording script](demo-script.md), [architecture](architecture.md),
[local demo guide](local-demo.md), [review instructions](real-product-evaluation.md)
and [submission checklist](hackathon-submission-checklist.md) with this copy.
An editable seven-slide PowerPoint, seven rendered slides and a candidate cover
are prepared under ignored `var/mission05-submission/deck-20261014-152027-67d97c/`.
The [deck guide](pitch-deck.md) records the actual files and validation. The
[architecture SVG](assets/rekit-architecture.svg) is editable source. The final
video has not been recorded or uploaded. No public application URL is deployed,
and the GitHub repository remains private. Publication and licensing need
explicit owner decisions; this document makes neither decision.

Retain Amazon Berkeley Objects / Amazon.com CC BY 4.0 attribution and the pinned
Qwen model's Apache-2.0 notice using the project source guides. Do not accidentally
include tokens, weights, source datasets, databases or private execution records
in a public release.
