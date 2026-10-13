# AMD inference deployment boundary

AMD Developer Cloud is the primary planned production inference target. The
intended request path is:

```text
Backend API -> inference adapter -> AMD Developer Cloud Linux service
                                   ROCm + vLLM + compatible open VLM
```

Missions 01 and 02 implement the local operator workflow around this boundary,
but no inference adapter or service exists yet. AMD cloud credits remain pending.
No cloud resources, inference server, runtime manifest, models, datasets, or
containers have been provisioned or downloaded. The health endpoint is API
liveness only; it does not assert inference readiness. A passing CPU test or
synthetic browser scenario is not an AMD inference benchmark.

## Exact integration points

The following table separates today's application contracts from the work needed
to introduce real model output. These are integration requirements, not a claim
that an inference request or a run-provenance schema already exists.

| Stage | Existing entry point | Required future adapter behavior |
| --- | --- | --- |
| Managed image input | `ImageAssetStore.read(asset_id)` in `backend/src/rekit/evidence/assets.py` returns immutable metadata and integrity-checked bytes. Private HTTP retrieval is `GET /assets/{asset_id}/content`. | Resolve only authorized, registered asset IDs. Bind input to physical component, source return, asset hash, observation ID, and evidence version. Never ask vLLM to fetch a user-supplied URL or local path. |
| Model/runtime identity | No inference-run record is implemented. `Observation.source_reference` can identify an assertion's source but is not a complete run manifest. | Add a versioned run record containing the exact model, runtime, preprocessing, request settings, and linked inputs described below. Use its run ID for model-source assertions. |
| Image observations | `Observation` and `EvidenceStore.record_observation()`; the API accepts an observation at `POST /components/{id}/evidence`. Existing fields include `visible_marking` and `visible_revision`. | Validate bounded OCR/marking output as a new `source="model"` observation using a real `asset:` reference and run ID. Preserve the original upload observation. Localization boxes, crop transforms, and multi-image lineage need explicit new contracts; they are not fields in today's observation. |
| Identity hypotheses | `IdentityProposal` and `EvidenceStore.record_proposal()`; `kind="proposal"` at the same evidence route. | Propose a catalog-shaped type/revision or an unresolved result linked to an existing observation. An unknown label can remain a hypothesis; it cannot become a verified identity or approved substitution. |
| Visible condition | The current authoritative condition is part of human `OperatorVerification`. There is no structured model-condition observation yet. | Add a separate evidence contract for visible attributes and possible damage, with image/region references and limitations. Do not write a model's condition directly into human verification or infer hidden function/safety. |
| Uncertainty | `UncertaintyFlag` and `EvidenceStore.flag_uncertainty()`; `kind="uncertainty"` at the evidence route. An unresolved proposal also carries a reason. | Record ambiguity, insufficient evidence, or a validated inference failure as explicit uncertainty. Never treat confident wording or a raw score as a calibrated probability. |
| Additional views | Operators can add multiple images through the existing upload UI/API. No structured additional-view request or model-driven capture workflow is implemented. | Introduce a bounded request naming the component, source evidence/run, the missing visible distinction, and a useful view such as a connector close-up. New views attach to the same physical identity. |
| Human verification | `POST /components/{id}/verification` binds the authenticated human reviewer, expected version, supporting observation IDs, and any superseded verification. | Present hypotheses and their evidence for review. Preserve the human gate and append-only correction history. Models and service actors never call privileged approval/completion routes. |

The existing upload route binds human captures to the authenticated operator and
service uploads to an import source. An inference service instead needs a narrow
server-owned adapter and, if it uses the HTTP API, a service credential with only
the required viewer/intake roles. Do not send an operator bearer token to vLLM.
No model response may change component IDs, source return membership, catalog or
policy snapshots, economic inputs, reservation state, or audit actor identity.

Read evidence and run inference outside a SQLite write transaction. Validate the
response before recording assertions. Inference runs can finish after new images
or human decisions arrive: retain the input evidence version and handle stale
output explicitly. An appended observation/proposal after verification already
requires review; it never inherits that verification or approval. A single
`IdentityProposal` currently anchors to one observation. Multi-view run inputs
must be represented honestly by a new run/lineage contract, not invented fields
in today's models.

## Future run manifest and output validation

Before accepting model output, preserve these details in a new versioned contract:

- Run ID, requesting service, server start/end times, outcome, and input evidence
  version; all asset IDs, SHA-256 hashes, source observations, component IDs,
  image dimensions, and any crop or normalization transforms.
- Provider/deployment identity, model repository and immutable revision, license,
  tokenizer/processor revision, precision or quantization, prompt/chat-template
  version, output-schema version, and generation settings.
- AMD GPU model and memory, Linux/kernel and driver, ROCm, PyTorch, vLLM, Python,
  adapter code revision, and pinned serving dependencies. Separate OCR,
  localization, and matching models also need their own versioned identities.
- Observed text/attributes, proposed labels, supporting asset/region references,
  uncertainty and additional-view reasons; raw scores retain their source and
  meaning. Preserve bounded raw output separately from validated interpretation.

Treat OCR, image text, and generated output as untrusted evidence, never as
instructions to invoke tools or change policy. Enforce response size/schema
limits, allowed references, timeouts, cancellation, bounded retries, and stable
request identity. Malformed or missing output must not create approval or
eligible inventory. Record the failure for review; do not fabricate observations
or silently fall back to a different runtime while claiming AMD execution.

## Runtime separation

Preserve the existing Windows development `.venv` and its working PyTorch
`2.9.0+cu128` CUDA packages. Future local NVIDIA experiments belong behind a local
inference adapter. They do not replace the AMD demonstration or establish AMD
compatibility. The AMD service needs its own Linux runtime and dependency pins;
do not add ROCm or vLLM to the local backend environment.

The backend will call the inference adapter through a typed application
contract. The adapter owns provider request/response translation, timeouts,
bounded retries, output validation, and model/runtime provenance. Missing or
invalid inference evidence must produce an explicit incomplete or review state.
The inference service cannot approve compatibility, reserve inventory, or
execute workflow transitions directly.

## Compatibility gate for a later deployment task

The AMD GPU, cloud allocation, Linux distribution, driver, ROCm release, vLLM
version, and model are all unselected. Before provisioning, record and verify
the complete combination against the official [AMD compatibility matrix](https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html).
Use the versioned documentation for the selected release in the qualification
record; a link to current documentation is not itself a qualified configuration.

Verify the chosen GPU and runtime against the matching release of the
[vLLM GPU installation documentation](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/).
Check the candidate model's image capabilities and limitations in the
[vLLM supported-model documentation](https://docs.vllm.ai/en/latest/models/supported_models/).
An architecture appearing in a model support list is not evidence that a
particular quantization, attention implementation, or complete deployment
combination has passed ReKit's workload tests.

Then review the model license, immutable revision, input image limits, memory
budget, tokenizer/processor and chat template, output contract, and any remote
code requirement. Qualify the exact combination on representative images,
including multi-image and ambiguous-component cases. Capture the runtime
manifest, quality results, and p95 latency described in the
[evaluation plan](../../evaluation/README.md).

## Planned configuration and operations

The repository [.env.example](../../.env.example) describes future server-side
settings. `REKIT_INFERENCE_PROVIDER=amd_vllm` names the intended provider;
`REKIT_INFERENCE_BASE_URL` is an intentionally unusable example address.
`REKIT_INFERENCE_MODEL` and `REKIT_INFERENCE_API_KEY` remain empty until the
service is selected. The current app does not load these inference settings or call that
endpoint.

Future deployment must keep credentials server-side, use authenticated network
access, and avoid secrets or raw customer imagery in logs. Plan request size
limits, concurrency limits, timeout/cancellation behavior, readiness checks,
and an explicit failure mode when AMD inference is unavailable. API liveness
and inference readiness should remain distinguishable. Hardware changes and
model/runtime upgrades require a new manifest and a repeat of the relevant
quality and performance qualification.

See the [architecture](../../docs/architecture.md) and
[implementation roadmap](../../docs/roadmap.md) for dependent work.
