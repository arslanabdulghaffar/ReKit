# AMD inference deployment boundary

AMD Developer Cloud is the primary planned production inference target. The
intended request path is:

```text
Backend API -> inference adapter -> AMD Developer Cloud Linux service
                                   ROCm + vLLM + compatible open VLM
```

Task 1 documents this boundary only. No cloud resources, inference server,
deployment manifests, models, datasets, or containers are provisioned or
downloaded. The health endpoint is an API liveness check and does not assert
inference readiness.

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
the complete combination against the official [AMD Linux system requirements](https://rocm.docs.amd.com/projects/install-on-linux/en/latest/reference/system-requirements.html)
and the compatibility matrix for the selected ROCm release; the
[ROCm 7.2.0 matrix](https://rocm.docs.amd.com/en/docs-7.2.0/compatibility/compatibility-matrix.html)
is a versioned reference, not a selected runtime.

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
service is selected. The Task 1 app does not load these settings or call that
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
