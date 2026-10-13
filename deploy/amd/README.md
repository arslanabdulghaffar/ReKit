# AMD inference deployment handoff

AMD Developer Cloud remains the required production inference target for the
hackathon. ReKit now implements real local NVIDIA inference, authenticated HTTP
requests, immutable run provenance, and operator review. No AMD allocation,
adapter, serving runtime, or cloud inference run has been qualified. Local
CUDA, CPU tests, and synthetic browser scenarios cannot pass the AMD gate.

Mission 03 Task 5's local integration qualification passed current-version API
acceptance, two complete real-AI browser runs, and the default browser regression.
Four earlier browser failures and the reproduced v4 baseline remain preserved.
The selected implementation uses constrained joint generation with independent
strict parsing. No local result qualifies AMD deployment. The
[mission report](../../docs/reports/development-mission-03.md) records artifacts
and separately tracks commit, push, and CI evidence.

```text
Managed images -> InferenceService -> VisionProvider
                                     local: Transformers + CUDA
                                     future: AMD Linux, ROCm + vLLM
               -> strict parsing -> unverified evidence -> human review
               -> deterministic compatibility, planning, and inventory
```

## Verified local starting point

The only downloaded checkpoint is `Qwen/Qwen3-VL-2B-Instruct`, revision
`89644892e4d85e24eaac8bacfd4f463576704203`. The pinned model card declares
Apache-2.0. Its ten verified files total **4,266,640,306 bytes**; the weight-file
SHA-256 is `7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0`.
Preserve the [manifest](../../configs/inference/qwen3-vl-2b.json), attribution,
and file hashes for future qualification. This is a candidate, not a claim
that its AMD deployment is compatible.

[Initial local qualification](../../docs/local-inference.md) records two real CUDA smoke
requests and a separate authenticated API request. Initial loading took
4.624754 seconds; smoke inference took 34.424170 and 33.016417 seconds on one
RTX 4080 SUPER. API inference later took 43.5648928 seconds and peaked at
4,540,146,688 PyTorch allocated GPU bytes. These are local examples, not AMD
memory budgets, p95 estimates, or recognition accuracy.

The API run also proposed unsupported `adapter` revision `A` from a synthetic
shapes illustration, quoting `SYNTHETIC` as its revision marking. The error and
contradictory uncertainties remain auditable; inventory stayed held. Successful
execution and valid structure do not establish visual truth.

The selected local path adds optional LM Format Enforcer `0.11.3` and interegular
`0.3.3` to the local Transformers path. A joint two-view request and a separate
ambiguous-image request passed the unchanged domain parser. The latter still
invented `body/A` with marking `A`; constrained generation improves output shape,
not recognition truth. Preserve explicit human rejection and verification. See
[the controlled measurements](../../docs/local-inference.md#approach-1-measured-result).

## Final local qualification

The current API and its final repeat passed, as did complete AI browser runs
`run-ai-52823ogs` and `run-ai-73rjz6dy`. Each browser scenario rejected the
unsupported ambiguous-image hypothesis, recorded human verification linked to
actual run IDs and original images, and completed two kits from four unique
components. The default regression `run-ugm19txq` passed in 4.5 seconds, and an
additional AI QA repeat passed. Final local validation passed 631 backend tests,
a 264-test focused inference selection, 48 frontend tests, TypeScript, build,
dependency graph, and synthetic evaluation. See
[artifact paths and timings](../../evaluation/README.md#final-local-qualification).
These results validate the local integration contract; they provide no measured
ROCm/vLLM compatibility, AMD latency, or recognition-accuracy guarantee.

## Exact integration points

| Boundary | Existing contract | AMD adapter obligation |
| --- | --- | --- |
| Input | `InferenceStore.begin()` binds component, return, evidence version and one or two assets; `ImageAssetStore.read()` checks original bytes. | Process admitted bytes in order. Never fetch client-controlled URLs/paths or count detections as stock. |
| Provider | `VisionProvider.configuration`, `.status`, and `.inspect(images: list[bytes]) -> dict` in `rekit.inference.provider`. | Implement this interface using a separate Linux ROCm/vLLM service; retain CPU-only API imports. |
| Configuration | `InferenceConfiguration` records provider, repository, model/processor revisions, runtime, device, prompt version, preprocessing and generation settings. | Record the actual deployment and exact prompt hash; bind model-file hashes to a server-owned manifest. |
| Response | Raw `text`, `provider`, `model_repository`, `model_revision`, `device`, `runtime`, and `metrics`; `metrics.input_sha256` holds ordered original-byte hashes. | Match admitted provenance and return actual model text. The local `vision_forward_calls` requirement applies only to `local-transformers`; never invent AMD encoder-hook counts. |
| Parsing | `parse_output()` validates bounded `InspectionOutput`: observations, candidates, uncertainties, and additional-view requests with source indices. | Preserve strict parsing. Serving-side JSON constraints cannot replace validation or establish visual truth. |
| Structured generation | The local path filters tokens using a versioned schema, records schema hashes, and preserves raw output for independent domain validation. | Qualify a supported decoder on the actual ROCm/vLLM deployment; retain equivalent output/error/provenance behavior without assuming LMFE compatibility. |
| Persistence | `InferenceStore.finish()` saves one immutable outcome and any current unverified events atomically. | Leave finalization with ReKit. Failed/stale outcomes append no evidence; never write verification, economics, reservations, or kits. |
| Review | Candidate selection prefills identity only; rejection adds an actor-bound hold while retaining raw output. | Preserve explicit human condition, supporting evidence, reason, and verification. Service principals cannot acquire human approval roles. |

Inference occurs outside SQLite write transactions. The service checks provider
identity and original input hashes before parsing. Finalization rechecks evidence
version, allocation, and asset integrity. Changed evidence, reservation,
consumption, missing bytes, or corruption prevents late output from replacing a
current decision. Replays retain their original actor and request.

The run records full multi-image provenance although a legacy proposal links to
one observation. Model descriptions of visible damage remain unverified.
Localization/crop lineage, separate OCR and matching stages, and physical
identity merge/split operations remain future work. See
[inference evidence](../../docs/inference-evidence.md).

## Request and lifecycle limits

The local path accepts at most two static JPEG/PNG/WebP images, each at most
10 MiB, 16 million original pixels, and 8,192 pixels per side. It applies EXIF
orientation, RGB conversion, and a 768-pixel side bound; the official processor
uses 65,536–589,824 pixels. Text plus image tokens are bounded to 8,192.
The qualified local configuration uses greedy generation, at most 512 new tokens under prompt
`rekit-inspection-v5-constrained`, with schema `rekit-inspection-schema-v1` and
a 120-second cooperative deadline. The service adds
a 150-second request deadline. Historical v1/v2 attempts used 384 tokens;
all four failed results remain in the [evaluation record](../../evaluation/README.md).

The local grammar caps observations at two, candidates at one, uncertainties
at one or two, and additional views at one; text/reasons/markings are bounded to
160 characters, view text to 100, and identifiers to 128. Single- and two-image
schemas have distinct recorded hashes. Image indices remain claims about the
actual ordered inputs. Never attach all sources indiscriminately or hide a
change from joint inference to separate image calls.

Preserve these limits or introduce a reviewed, versioned change and repeat
qualification. Record transformations so original hashes stay distinct from
normalized payload hashes. Measure actual image-token and KV-cache behavior;
do not assume vLLM and Transformers preprocessing or memory use are identical.

Admission permits one process-local computation with no queue. Timeout records
`timed_out` and discards late output but retains the slot until work returns.
Restart does not resume orphaned pending runs. Map remote unavailability,
timeouts, transport failures, and malformed output to the existing honest
outcomes. Bound response sizes and retries; cancellation must not claim GPU work
stopped without serving-side confirmation. Manual review remains available.
Never hold an inventory transaction across inference.

## Official compatibility checks

The following primary sources were checked on **2026-10-13**. They identify
required checks, not a selected ReKit deployment:

- [AMD ROCm compatibility matrix](https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html)
  ties GPU support to operating systems, kernel drivers, firmware and runtime
  components. Use a versioned matrix for the actual cloud allocation.
- [vLLM GPU installation](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/)
  specifies Linux and separate ROCm wheel, Python, and glibc combinations.
  Pin a mutually supported release instead of copying moving latest examples.
- [vLLM supported models](https://docs.vllm.ai/en/latest/models/supported_models/)
  lists `Qwen3VLForConditionalGeneration` with image support. This does not
  qualify the exact checkpoint, precision, attention backend, or device.
- [vLLM Qwen3-VL recipe](https://docs.vllm.ai/projects/recipes/en/stable/Qwen/Qwen3-VL.html)
  contains AMD instructions for particular Instinct hardware and a larger MoE
  model. Its example does not qualify ReKit's pinned 2B checkpoint.
- [vLLM structured outputs](https://docs.vllm.ai/en/latest/features/structured_outputs/)
  documents JSON-schema generation and backend selection. The current page lists
  xgrammar and guidance and replaces older `guided_*` fields with
  `structured_outputs`. Select and pin the mechanism supported by the actual
  deployed release; do not copy LMFE's older vLLM examples or infer ROCm support
  from its local Transformers integration.

Before deployment, record the actual GPU model/count/VRAM, Linux/kernel,
driver/firmware, ROCm, Python, PyTorch, vLLM, attention implementation, precision,
model/processor revision, and serving package or container digest. Keep this
runtime separate from Windows Python 3.12 and its working PyTorch
`2.9.0+cu128` / torchvision `0.24.0+cu128`. Do not install ROCm/vLLM into that
environment or replace CUDA packages.

Review the model license and redistribution attribution, evidence usage rights,
cloud/hackathon terms, remote-code requirements, and serving dependency licenses
for the intended workload. A hardware or model replacement needs its own
selection and evaluation; it is not an undocumented fallback.

## Network and deployment acceptance

Use a server-owned endpoint restricted to the backend's network identity, TLS
with certificate verification, and separate model-service credentials. Never
forward operator bearers to vLLM or expose service keys in `VITE_*`, browser
storage, logs, or Git. Restrict routes and payload sizes; do not expose generic
URL fetching, local model files, or model-management operations to operators.

The factory currently supports only `disabled` and `local-transformers`.
`REKIT_INFERENCE_BASE_URL`, `REKIT_INFERENCE_MODEL`, and
`REKIT_INFERENCE_API_KEY` in [.env.example](../../.env.example) are reserved;
setting them does not enable AMD. Implement an explicit provider branch when
its adapter and configuration are ready. API health and provider readiness
remain separate.

The AMD gate requires real image execution on the selected deployment while
preserving every human and deterministic decision boundary. Test one/two images,
unreadable labels, unknown/conflicting identities, malformed/truncated output,
unavailability, timeout/late response, exact retry, concurrent admission, new
evidence, and reservation races. Compare identical input hashes and reviewed
labels with the local path, without requiring identical generated wording.

Measure cold load, warm inference and end-to-end latency, p50/p95 with stated
sample counts, throughput, concurrency, errors, GPU memory and KV-cache headroom
at permitted input bounds. Report unsupported claims, human corrections, and
additional-view usefulness separately from software correctness. Independently
labelled real product-photo evaluation is still missing. See
[evaluation](../../evaluation/README.md) and the [roadmap](../../docs/roadmap.md).
