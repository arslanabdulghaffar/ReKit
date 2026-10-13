# Inference evidence and provenance

An inference run is evidence about an existing physical component. It never
registers stock, verifies identity, approves condition, changes catalog policy,
or executes a recovery action. The required path remains images, unverified AI
output, human review, deterministic compatibility, planning, approval, and
transactional inventory execution.

This persistence layer is separate from [local GPU qualification](local-inference.md).
Task 2 provides contracts and storage; Task 3 connects the real provider to
authenticated HTTP requests. Task 4 exposes inspection, proposal review, and
human rejection in the existing component-review interface.
CPU-only tests of parsing, persistence, and request handling use controlled
inputs and do not demonstrate real model execution or accuracy.

The contracts live in `rekit.inference.models`, strict output parsing in
`rekit.inference.parsing`, and persistence in `rekit.inference.store`. The
provider boundary is `rekit.inference.provider`; `rekit.inference.service`
owns admission and execution, and `rekit.api.inference` exposes the HTTP routes.

## Inputs and outputs

Each request binds one existing component and its source return to one or two
managed images. The stored input snapshot includes asset IDs, original-byte
SHA-256 hashes, source observation IDs, and the evidence version at admission.
The requesting actor comes from trusted application authentication. Clients do
not supply file paths, remote image URLs, model revisions, or runtime claims.
`InferenceStore.begin()` requires a human actor with the reviewer role and
revalidates the actor, request, and server configuration.

The run records model repository and immutable revision, provider and device,
processor/runtime versions, prompt/template identity, preprocessing and
generation settings, timestamps, execution outcome, and failure details when
applicable. Original image bytes remain in the managed asset store; the database
does not duplicate them.
The local provider records `preprocessing.prompt_sha256`, the SHA-256 of its
exact UTF-8 prompt including the sorted server catalog identity/revision context.
Runtime, preprocessing, and generation maps are required and bounded to 32
entries; optional execution metrics may be empty when no measurement exists.

Validated output distinguishes visible observations, identity hypotheses, and
requests for additional views. Every supported claim retains its input-image
references. Unknown identity and missing visual information remain explicit.
A partial identity does not acquire an invented revision merely to fit a catalog
identity. Model descriptions of visible damage are unverified observations;
only the existing human verification operation can assert visible condition.

`InspectionOutput` allows up to six observations, three identity candidates,
five uncertainty statements, and three additional-view requests. Supporting
`image_indices` are unique, one-based indices into the stored ordered inputs;
they cannot refer to an image that was not supplied. A candidate revision
requires a visible `revision_marking`. Unknown or conflicting identities require
an uncertainty explanation. These checks establish structure, not visual truth.
The [Task 3 API qualification](local-inference.md#task-3-measured-api-execution-and-recognition-error)
demonstrated this limit: the model quoted `SYNTHETIC` as support for revision
`A` while acknowledging that the illustration did not confirm a revision.
That unsupported claim remained an unverified hypothesis with inventory held.
A nonempty `revision_marking` is a source-text assertion, not proof of revision.

Model text is untrusted data. Parsing does not execute text or accept arbitrary
backend commands. No confidence phrase is presented as a calibrated probability,
and images cannot establish hidden function, electrical safety, internal damage,
or approved compatibility.

`parse_output()` accepts one JSON object, optionally inside one complete
`json` code fence, bounded to 32,000 characters. It rejects duplicate keys,
non-finite constants, surrounding prose, extra fields, and invalid references;
it does not repair a model response or invent missing evidence.

## Lifecycle and idempotency

The existing evidence SQLite file holds an immutable request and at most one
immutable terminal outcome per run. An accepted request without an outcome is
pending; this does not prove that model execution started or failed. A crash can
leave a pending request. Replaying it must not invent a terminal result or start
duplicate work.

`InferenceRun.outcome` is `None` while pending. `start.started_at` records server
admission, not a measured GPU start. `begin()` returns `(run, created)` so only
the caller that created the request may schedule execution.

Idempotency binds the request ID to its actor and canonical request contents.
An exact retry returns the existing run. Reusing the ID with different contents
or a different actor conflicts. Authentication and authorization still apply
to retries. A deliberate new attempt uses a new request ID.
An exact retry is recognized before checking fresh evidence versions or image
availability. It preserves the original configuration and outcome. Changed
completion arguments also conflict: `finish()` admits one immutable outcome.
Restart does not automatically resume pending runs. An operator may make a
deliberate new request with a new ID when the service is idle, using the current
evidence version; the old run remains pending without an invented outcome.

An actual execution failure remains a failure with provenance. A valid unknown
answer is a successful execution with unresolved identity, not a fabricated
fallback prediction. Staleness describes whether output can still be applied
to the current evidence; it must not erase the actual execution outcome.
Terminal status is one of `succeeded`, `failed`, `unavailable`, `timed_out`, or
`invalid_output`. `stale` and `stale_reason` separately record applicability.

## Authenticated HTTP lifecycle

All inference routes require the existing bearer authentication. Invocation
requires a human reviewer; status, history, and individual-run reads require
the viewer role. These roles are explicit and have no implicit hierarchy.

| Route | Contract |
| --- | --- |
| `GET /inference/status` | Provider status and busy state; disabled inference reports unavailable with HTTP 200. |
| `POST /components/{component_id}/inference` | Accept `request_id`, one or two `asset_ids`, and `expected_version`; return a stored run with HTTP 202. |
| `GET /inference/{run_id}` | Read a pending or terminal run with HTTP 200. |
| `GET /components/{component_id}/inference` | Read the latest 50 runs for that component. |

The path selects the physical component. Authentication supplies the actor,
and trusted server configuration supplies model settings. Extra body fields,
including actor, model, URL, and file-path overrides, are rejected. Asset IDs
must bind to the component's source observations and original bytes.

The service owns one process-local computation slot and has no queue. A fresh
request while busy returns HTTP 409 without creating a run. An exact retry is
checked first and returns the existing run without starting work, even while
busy. Duplicate request IDs with changed contents or actor, stale evidence
versions, and allocation conflicts also return 409. Authorization errors remain
401/403, absent references return 404, and malformed requests return 422. A
disabled service returns 503 for invocation and run queries while the manual
workflow remains available.

Admission persists the request before starting its worker. The HTTP response
does not claim that execution succeeded: clients inspect `outcome` and poll
while it is null. Runtime failures, invalid model output, and unavailability
are recorded as terminal outcomes without applying evidence. The service
checks provider identity, ordered original-byte hashes, and, for the local
Transformers adapter, a measured visual-encoder forward call before parsing.

The local provider has a 120-second cooperative generation deadline; the
service has a separate 150-second request deadline. Expiration records
`timed_out` without freeing the slot until computation actually returns. Late
results cannot replace that terminal outcome or append evidence. Shutdown
stops new admission and attempts to record failure for a pending active run,
then waits at most one second for the daemon worker. It cannot forcibly stop
a CUDA kernel. Use one serving process and one Uvicorn worker.

If saving an outcome fails, the service attempts to persist a simple failure.
If that also fails, it reports itself unavailable and refuses fresh requests;
the stored run can honestly remain pending. It does not fabricate persistence
success. A process crash can likewise leave a pending run, with no automatic
resume on restart. [Local inference setup](local-inference.md) describes the
opt-in configuration and polling workflow.

## Atomic evidence admission

Model execution happens outside SQLite transactions. At finalization, a short
write transaction checks the current evidence version and physical allocation
before saving the outcome and any resulting evidence events together.
Admission validates immutable asset metadata and its source observation. A
known asset with missing bytes can therefore retain a subsequent failed run;
an unknown asset ID is rejected. The execution caller must use integrity-checked
managed bytes, and successful finalization checks their integrity again.

If a new image or human correction has changed the input evidence, the late run
is retained as stale without appending observations or proposals. It cannot
overwrite a newer verification. Reserved or consumed components cannot receive
new inference evidence through this path.
Changed image availability or integrity also prevents successful output from
being applied. Failed and stale outcomes leave evidence history unchanged.

Current successful output appends one model-source observation per input image,
unverified proposals, and an explicit human-review uncertainty flag through the
existing evidence event model. The evidence version is
one plus the number of events, so one multi-image run can advance it more than
once. New observations or proposals after human verification require a fresh
review; they never inherit that verification.

Model observations retain canonical `asset:{asset_id}` evidence references so
the existing human-verification asset-integrity checks still apply. Their
source references identify the inference run. The run preserves the complete
multi-image provenance even where a legacy identity proposal links to one
observation. Repeated images, predictions, and retries do not create additional
physical components.

The model observation's `captured_at` is the analysis completion time, not an
asserted camera capture time. Its legacy `visible_marking` field contains at
most a 2,048-character excerpt; the run retains the complete validated marking
observations within their contract limits.

`get()` returns one run; `list_for_component()` returns the latest 50. The
corresponding authenticated read routes return these persisted records.

## Authority and provider boundary

An authenticated human reviewer can reject a current successful suggestion with
`POST /inference/{run_id}/reject`, supplying `rejection_id`, `expected_version`,
and a nonempty reason of at most 1,500 characters. The same transaction checks
the current evidence version, the run's applicability, and inventory allocation.
A pending, failed, stale, or superseded result cannot change current review state.
An exact retry is bound to the actor, run, version, and reason. Rejection appends
an operator-source uncertainty event naming the run and reviewer; the original
model output remains immutable. Rejection does not verify a replacement identity.
Use the existing explicit human verification or correction action for that.

Only trusted application code supplies runtime metadata and finalizes runs.
Caller-supplied `source=model` metadata through the existing generic evidence
endpoint is not proof that ReKit executed a model. Actual execution is identified
by its server-recorded run and immutable input links.

These contracts import no CUDA or model runtime. A future AMD ROCm/vLLM provider
must return equivalent validated observations, uncertainty, and provenance while
the catalog, optimizer, approval, and inventory rules remain unchanged. Local
NVIDIA execution does not establish AMD compatibility; AMD qualification and
deployment remain separate work.

SQLite append-only constraints and image hashes protect application integrity.
They are not cryptographic attestation against a privileged local administrator.
Keep the database, images, model caches, credentials, and generated run artifacts
outside Git.
