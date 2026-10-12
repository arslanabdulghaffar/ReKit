# Evaluation and benchmarking boundary

This directory defines the future evaluation scope. Task 1 adds no datasets,
model weights, benchmark runner, or generated results. The executable test in
the foundation covers only the backend health endpoint.

## Evidence and ground truth

Use reviewed annotations linked to capture IDs, unique physical-component IDs,
return IDs, source-image hashes, and annotation versions. Preserve crop and
preprocessing lineage, model and prompt versions, and human corrections. Split
training, calibration, and held-out evaluation by physical item and return so
multiple views of an item cannot leak across splits. Record near-duplicate
checks, catalog revisions, collection conditions, and known coverage gaps.

Include ambiguous, missing, duplicate, occluded, damaged, and out-of-catalog
components, plus closely related revisions. Reviewers must be able to label
identity or condition as unknown. Visible inspection does not establish hidden
functional or safety properties; any required physical or electrical checks
need separate evidence and acceptance criteria.

## Planned evaluation areas

| Area | Measures and failure cases |
| --- | --- |
| Localization and OCR | Detection precision/recall, localization overlap, missed components, and exact label/part/revision extraction with unreadable-text cases. |
| Visual matching and VLM reasoning | Candidate ranking, incorrect accepted identities, unsupported claims, conflicting observations, and evidence references. |
| Additional evidence | Abstention and false-accept rates, coverage versus error, usefulness of requested close-ups, and resolution rate after recapture. |
| Physical identity | Duplicate counting, identity merges/splits, multiple views, cross-return transfers, and full provenance reconstruction. |
| Deterministic catalog policy | Approved BOM quantities, revisions, substitutions, compatibility exclusions, unknown-policy handling, and visible-condition requirements. |
| Recovery optimization | Hard-constraint violations, unique component assignment, solver status, feasible alternatives, objective bounds, runtime, and economic sensitivity. |
| Approvals and inventory | Stale approvals, reservation races, double use, transaction rollback, retry/idempotency behavior, cancellation, and audit completeness. |
| Final verification | Approved BOM reconciliation, required evidence and checks, failed verification handling, and atomic inventory/audit updates. |
| AMD inference | Quality, end-to-end and inference-only latency, p50/p95, throughput, timeout/error rates, memory use, and behavior under concurrency. |

Choose denominators, acceptance thresholds, and representative operating
conditions before evaluating a release. Model-written confidence statements and
raw similarity scores are not probabilities. If probabilistic decisions are
introduced, define a separate calibration method, evaluate it on held-out data,
and report reliability and subgroup limitations.

Economic evaluation must expose currency, valuation date, resale assumptions,
labor, testing, replacement, shipping, holding, and disposal costs. Compare
recovery with alternatives such as resale as-is, holding, or disposal using
explicit assumptions. Unknown failure rates must not be fabricated from model
confidence.

## Reproducible run record

Each future run should record the repository commit, dataset/annotation version
and split manifest, catalog and policy versions, model identifier and immutable
revision, prompt/template version, preprocessing settings, decoding settings,
and raw outputs with evidence references. Record exact AMD GPU model/count/VRAM,
OS/kernel/driver, ROCm, vLLM, Python, serving package or image digest, precision,
quantization, image sizes/counts, warm-up procedure, concurrency, sample count,
and timing boundaries. Compare local CUDA and AMD results on identical inputs
without presenting local timings as AMD measurements.

Keep raw captures, personal/customer data, credentials, and generated benchmark
artifacts outside Git. Use sanitized, intentionally reviewed fixtures when
tests need repository data. Future reports should separate measured results
from targets and untested assumptions.

See [architecture](../docs/architecture.md), [roadmap](../docs/roadmap.md), and
[AMD deployment planning](../deploy/amd/README.md).
