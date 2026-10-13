# Evaluation and benchmarking boundary

The current runner exercises synthetic backend recovery and compares CPU planning
with a simple greedy baseline. It performs no perception inference, downloads no
data, and measures no AMD performance or operator time savings.

## Reproduce the synthetic evaluation

From the repository root in the existing environment:

```powershell
.\.venv\Scripts\python.exe evaluation/run_synthetic.py
.\.venv\Scripts\python.exe -m pytest -q -W error
.\.venv\Scripts\python.exe -m pip check
```

The runner uses [synthetic recovery inputs](../tests/fixtures/synthetic_recovery.json)
and [controlled comparison cases](fixtures/recovery_cases.json). It creates a
temporary SQLite database, exercises real HTTP application routes in process,
uses actual CP-SAT results, validates expected outputs, prints JSON, and removes
the temporary database. Re-running does not reuse or mutate operational inventory.

Expected fixture results (all amounts are scenario estimates in USD cents):

| Case | CP-SAT modeled value | Greedy modeled value | Modeled difference |
| --- | ---: | ---: | ---: |
| Two-kit operator workflow | 17,500 | Not compared | Not compared |
| Scarce components across competing BOMs | 4,000 | 2,800 | 1,200 |
| Uneconomic rebuilds | 400 | 400 | 0 |

The workflow starts with three individually incomplete returns: two bodies in
one return and one adapter in each of the other two. Explicit synthetic operator
verifications permit two rebuilds. Each contributes 10,000 sale estimate minus
750 labor and 500 other costs = 8,750 cents. Approval reserves four physical
components; only the two subsequent confirmations create completed kits.

For the allocation comparison, two bodies and two adapters can make two standard
kits worth 2,000 cents each, or one larger kit needing two bodies and one adapter
worth 2,700 cents. Each donor has a retained asset estimate of 100 cents. Greedy
selects the greatest positive incremental value relative to retaining its donors,
then rejects overlapping actions and respects labor/demand limits. It fills
remaining stock with retain/hold actions. Its larger kit contributes 2,700 cash
estimate plus a 100-cent retained adapter. CP-SAT instead selects the two standard
kits for 4,000 modeled cents. The 1,200-cent difference is specific to this
constructed case and is not evidence of business uplift.

Both algorithms retain all four donors in the uneconomic case, so their 400-cent
modeled values contain zero cash recovery. All greedy allocations pass the same
deterministic feasibility validation; greedy shares candidate generation with
CP-SAT but uses a different allocation strategy. Independent exhaustive subset
oracles in tests verify tiny-case optima. This is a correctness check, not an
independent implementation of every catalog rule or a production-scale benchmark.

## Real-browser acceptance

The separate browser runner exercises the React workbench and FastAPI together
over loopback HTTP, using the actual SQLite stores and CPU CP-SAT solver:

```powershell
.\.venv\Scripts\python.exe evaluation/run_browser_acceptance.py
```

First install the pinned frontend packages with `npm ci` in `frontend`, and use
the existing Python environment. Chrome or Edge must already be installed. The
runner does not download a browser, model, dataset, or container. Stop your own
ReKit development servers first: the runner refuses occupied IPv4 loopback ports
8000 and 5173 and does not attach to or terminate unrelated services.

Each run creates an empty database, server-approved synthetic catalog/policy,
random test credentials, and two distinct PNG views for each of the four fixture
components. Every generated image is labeled as synthetic test evidence, not a
product photograph. Registration, upload, human-review controls, scenario entry,
planning, approval, and completion are exercised through the browser; independent
authenticated HTTP reads check the resulting records. No browser route is mocked
and no successful planner output is supplied by the test.

The acceptance spec covers native file validation, multiple views of one identity,
duplicate reuse, invalid image feedback, authorization, unresolved/incompatible
stock, identity correction, compatible two-kit planning, reservation, explicit
completion, lineage, and audit. Test assertions use the invented fixture's
17,500-cent modeled outcome; they do not force the solver to return it. Software
automation of a human-role review form does not establish an actual physical
assembly, real product identity, functionality, or safety.

The private fixture manifest, database, and image state exist only for the run.
The runner stops its child services and removes that state on exit. Sanitized
results, screenshots taken after sign-in, and service logs remain in a unique
ignored directory under `var/mission02-acceptance/`. Traces, videos, and automatic
failure screenshots are disabled so a sign-in failure cannot capture a token.
Do not commit generated artifacts or copy private fixture manifests into reports.

`browser.log` is redacted UTF-8, and `runner-result.json` records the browser exit
status plus actual credential/state cleanup and reporting failures. Both are
written independently of best-effort console output; legacy Windows encodings
display unsupported characters as escapes. A failed run retains any safe
milestone screenshots already taken. Reporting or cleanup failures make the
runner fail even when the browser test passed.

The spec is `frontend/e2e/recovery.spec.ts`; the fixture lifecycle is
`evaluation/run_browser_acceptance.py`. Vitest runs only component/unit tests
under `frontend/src`. The GitHub Actions workflow runs backend tests and frontend
unit, type, build, and dependency checks on CPU; it does not claim a remote browser
run. Local browser results and actual GitHub job status are reported separately
in the [Mission 02 report](../docs/reports/development-mission-02.md).

## Executable coverage

| Required behavior | Tests |
| --- | --- |
| Valid reconstruction and final confirmation | `test_api.py`, `test_evaluation.py` |
| Incompatible revision, unknown identity, insufficient stock | `test_api.py`, `test_catalog.py`, `test_recovery.py` |
| Repeated observations and corrected identity | `test_api.py`, `test_evidence_store.py` |
| Uneconomic rebuild and price/labor sensitivity | `test_api.py`, `test_recovery.py`, `test_evaluation.py` |
| Conflicting reservations, stale approvals, cancelled plans | `test_api.py`, `test_inventory.py` |
| Transaction rollback, idempotency, audit and lineage | `test_inventory.py`, `test_evidence_store.py` |
| Exhaustive optimizer oracle and greedy comparison | `test_recovery.py`, `test_evaluation.py` |

The solver timeout test uses a real zero-second limit. Additional non-optimal/error
status branches are explicitly simulated to test reporting behavior; they are not
represented as observed production solver outcomes. The tests do not fabricate
visual-model outputs or replace the end-to-end planner with a hardcoded plan.

The sections below describe future evidence collection and AMD/perception
measurement requirements, not results already obtained.

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
