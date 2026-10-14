# AMD inference deployment handoff

AMD remains a required part of ReKit's hackathon delivery. Local NVIDIA inference,
immutable run provenance and operator review are implemented. Mission 04 adds the
`openai-remote` transport behind the same provider boundary; its offline tests
exercise simulated endpoints, not AMD GPUs. No AMD allocation, remote model,
serving runtime or actual cloud inference has been qualified. Local CUDA and
transport tests cannot pass the AMD execution gate.

For the shortest authorized setup path, use the
[AMD activation guide](../../docs/amd-activation.md): allocation probes, pinned
Linux serving configuration, restricted TLS, the existing remote-provider
environment and managed-image qualification. Its commands are preparation, not
evidence of an AMD run. Local NVIDIA browser/API runners do not switch to AMD
through environment configuration.

Historical Mission 03 Task 5 qualification passed its recorded API
acceptance, two complete real-AI browser runs, and the default browser regression.
Four earlier browser failures and the reproduced v4 baseline remain preserved.
That implementation used constrained joint generation with independent
strict parsing. No local result qualifies AMD deployment. The
[mission report](../../docs/reports/development-mission-03.md) records artifacts
and separately tracks commit, push, and CI evidence.

```text
Managed images -> InferenceService -> VisionProvider
                                     local: Transformers + CUDA
                                     remote: allowlisted HTTPS endpoint
                                             future AMD Linux, ROCm + vLLM
               -> strict parsing -> unverified evidence -> human review
               -> deterministic compatibility, planning, and inventory
```

## Verified local starting point and historical measurements

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

The Mission 03 local path added optional LM Format Enforcer `0.11.3` and interegular
`0.3.3` to the local Transformers path. A joint two-view request and a separate
ambiguous-image request passed the unchanged domain parser. The latter still
invented `body/A` with marking `A`; constrained generation improves output shape,
not recognition truth. Preserve explicit human rejection and verification. See
[the controlled measurements](../../docs/local-inference.md#approach-1-measured-result).

## Historical Mission 03 qualification

The Mission 03 API and its final repeat passed, as did complete AI browser runs
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

Mission 04's [real-image evaluation](../../docs/real-product-evaluation.md)
subsequently ran the same pinned model on bounded ABO catalog imagery. Its
schema-v2 change forbids identity candidates when no approved catalog was
supplied, while retaining strict parsing and raw output. Catalog-backed requests
still produce unverified hypotheses. There are no independent human semantic
labels, so recognition accuracy remains unmeasured. These local results do not
establish remote model behavior.

## Access routes and qualification status

The [official access research](../../docs/amd-access.md), checked 2026-10-14,
separates event TokenFactory access from an owned Developer Cloud deployment.
The event FAQ says TokenFactory does not require the $100 credit, but the exact
event model catalogue and API contract were behind sign-in. Vision support,
two-image input, JSON Schema support, authentication details, model revisions,
runtime, limits and AMD hardware evidence remain unverified. Do not enable the
remote route by guessing these values.

An owned Linux ROCm/vLLM deployment permits explicit runtime and model selection,
subject to access and resource-use authorization. The optional Evolus award
specifies an owned vLLM endpoint on AMD Developer Cloud; shared API availability
does not establish eligibility for that award. Neither route has been exercised
by ReKit.

## Exact integration points

| Boundary | Existing contract | Remote transport and AMD qualification |
| --- | --- | --- |
| Input | `InferenceStore.begin()` binds component, return, evidence version and one or two assets; `ImageAssetStore.read()` checks original bytes. | Process admitted bytes in order. Never fetch client-controlled URLs/paths or count detections as stock. |
| Provider | `VisionProvider.configuration`, `.status`, and `.inspect(images: list[bytes]) -> dict` in `rekit.inference.provider`. | `openai-remote` sends an OpenAI-compatible chat request over trusted HTTPS; the AMD serving runtime remains separately qualified. |
| Configuration | `InferenceConfiguration` records provider, repository, model/processor revisions, runtime, device, prompt version, preprocessing and generation settings. | Real 40-hex model and processor revisions are required from a trusted deployment record. They are server-configured declarations, not facts established by an HTTP model-name echo. |
| Response | Raw `text`, `provider`, `model_repository`, `model_revision`, `device`, `runtime`, and `metrics`; `metrics.input_sha256` holds ordered original-byte hashes. | Require the response model ID to match the requested ID. Client-computed hashes establish which original bytes were encoded; they do not prove remote encoder execution. Never invent local visual-hook counts or AMD GPU metrics. |
| Parsing | `parse_output()` validates bounded `InspectionOutput`: observations, candidates, uncertainties, and additional-view requests with source indices. | Preserve strict parsing. Serving-side JSON constraints cannot replace validation or establish visual truth. |
| Structured generation | Schema v2 bounds records/source indices and the admitted permission to propose catalog identities; the strict parser independently validates original output. | Request `json_schema`, record the exact schema/version/hash, and qualify the remote server's support. A requested schema is not proof that its decoder enforced it; unsupported requests must fail without a text-only fallback. |
| Persistence | `InferenceStore.finish()` saves one immutable outcome and any current unverified events atomically. | Leave finalization with ReKit. Failed/stale outcomes append no evidence; never write verification, economics, reservations, or kits. |
| Review | Candidate selection prefills identity only; rejection adds an actor-bound hold while retaining raw output. | Preserve explicit human condition, supporting evidence, reason, and verification. Service principals cannot acquire human approval roles. |

Inference occurs outside SQLite write transactions. The service checks admitted
provider metadata and original input hashes before parsing. Finalization rechecks evidence
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
`rekit-inspection-v5-constrained`, now with schema `rekit-inspection-schema-v2` and
a 120-second cooperative deadline. The service adds
a 150-second request deadline. Historical v1/v2 attempts used 384 tokens;
all four failed results remain in the [evaluation record](../../evaluation/README.md).
Mission 03's constrained acceptance used schema v1; its historical output and
measurements are not relabeled as schema-v2 runs.

The local grammar caps observations at two, candidates at one (zero without a
supplied catalog), uncertainties
at one or two, and additional views at one; text/reasons/markings are bounded to
160 characters, view text to 100, and identifiers to 128. Single- and two-image
schemas have distinct recorded hashes. Image indices remain claims about the
actual ordered inputs. Never attach all sources indiscriminately or hide a
change from joint inference to separate image calls.

The remote route encodes one or two original managed image byte strings as
base64 data URLs in the admitted order. It does not fetch image URLs or apply
the local Transformers processor. Remote preprocessing and hardware remain
unknown unless supported by separate deployment evidence. Record any later
transformation and distinguish its hash from the original bytes. Measure actual
image-token and KV-cache behavior; do not assume vLLM and Transformers processing
or memory use are identical.

Remote validation retains the 10 MiB/image, 16-million-pixel and 8,192-pixel-side
bounds and accepts only static JPEG/PNG/WebP. The complete encoded JSON request
is capped at 30 MiB and the response at 128 KiB. It requests one non-streaming
completion with `temperature=0`, `max_tokens=512` and
`response_format.type=json_schema` with `strict=true`. The remote prompt version
is `rekit-remote-inspection-v1`; its exact prompt hash and schema-v2 hashes are
stored. This does not claim an identical tokenizer, processor, latency or GPU
memory profile to the local provider.

Admission permits one process-local computation with no queue. Timeout records
`timed_out` and discards late output but retains the slot until work returns.
Restart does not resume orphaned pending runs. Map remote unavailability,
timeouts, transport failures, and malformed output to the existing honest
outcomes. Remote calls have bounded request/response sizes and a hard network
worker deadline, with no automatic retry or fallback. The isolated worker is
killed and reaped on timeout; OS process creation and cleanup can add elapsed
overhead. Stopping the local network worker does not establish that remote GPU
work stopped. Manual review remains available.
Never hold an inventory transaction across inference.

## Official compatibility checks

The following compatibility sources were checked for Mission 03 on **2026-10-13**;
the [access note](../../docs/amd-access.md) contains the **2026-10-14** research.
These sources identify
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

## Remote configuration and provenance

Use a server-owned endpoint restricted to the backend's network identity, TLS
with certificate verification, and separate model-service credentials. Never
forward operator bearers to vLLM or expose service keys in `VITE_*`, browser
storage, logs, or Git. Restrict routes and payload sizes; do not expose generic
URL fetching, local model files, or model-management operations to operators.

The explicit application factory selects `disabled`, `local-transformers` or
`openai-remote` through `REKIT_INFERENCE_PROVIDER`. Default imports and manual
mode make no remote calls. The remote route requires trusted server configuration
and a separate server-side credential; browser requests cannot override either.
Use [.env.example](../../.env.example) for the supported process variables.
No dotenv file is loaded automatically. API liveness and provider status remain
separate, and configuration alone does not establish endpoint reachability.

| Variable | Required remote setting |
| --- | --- |
| `REKIT_INFERENCE_PROVIDER` | `openai-remote` to opt in; keep `disabled` until configuration and permission are ready. `local-transformers` remains supported. |
| `REKIT_INFERENCE_BASE_URL` | Canonical HTTPS URL ending exactly in `/v1`, such as `https://amd-inference.example.invalid/v1`. No query, fragment, credentials or arbitrary path. The example is intentionally unusable. |
| `REKIT_INFERENCE_ALLOWED_ENDPOINTS` | Comma-separated exact HTTPS completion URLs, including the selected base plus `/chat/completions`; no wildcards, whitespace normalization or redirects. At most eight unique entries. |
| `REKIT_INFERENCE_MODEL` | Exact requested and response-advertised model ID. |
| `REKIT_INFERENCE_MODEL_REVISION` | Real 40-character lowercase hexadecimal revision from the deployment manifest. |
| `REKIT_INFERENCE_PROCESSOR_REVISION` | Real 40-character lowercase hexadecimal processor revision from the deployment manifest. |
| `REKIT_INFERENCE_API_KEY` | Nonempty service bearer held only in trusted process configuration; never substitute an operator token. |
| `REKIT_INFERENCE_MAX_IMAGES` | `1` or `2`; default `2`. Configure only what the selected endpoint supports. |
| `REKIT_INFERENCE_TIMEOUT_SECONDS` | Network/request budget from 1 through 120 seconds; default 120. |

The factory rejects invalid explicitly selected remote settings with a controlled
startup error. A provider that becomes unavailable at runtime leaves manual
workflow routes usable. Its initial `configured` status does not assert that a
network probe or AMD execution has occurred.

The destination is an exact allowlisted HTTPS URL, with certificate verification,
no redirects, no environment-proxy routing and no operator-supplied address.
The adapter never forwards the operator's bearer. Original image bytes are
encoded in the request rather than exposing managed-image URLs to the provider.
Do not persist the API key in run configuration or diagnostics.

Required model/processor revision hashes describe the operator's deployment
configuration. A response must advertise the requested model ID; this check does
not attest loaded weights or hardware. The remote device is recorded as `remote`,
with `revision_source=server_configuration`,
`revision_verification=not_attested_by_response`, `remote_runtime=unknown` and
`hardware_verification=unverified` in runtime metadata. Remote
image preprocessing is not described as the local Qwen processor unless actual
deployment evidence establishes it. Likewise, successful parsing establishes
the returned text's contract, not the truth of its visual claims or proof of
server-side schema enforcement.

Generation records `decoding=json-schema-request` and
`remote_schema_enforcement=unverified`. The adapter checks the requested
compact shape and strict domain contract before the service can apply unverified
events. Malformed envelopes, incorrect/missing model IDs, truncated completions
and invalid model text fail explicitly. Rejection of authentication, images or
structured-output parameters, rate limits and endpoint failures do not trigger
retries or another model. Client-reported transport timing and byte counts are
not remote inference-only latency or AMD GPU measurements.

If an endpoint cannot supply the deployment facts required by this configuration,
leave it disabled. Unknown revisions cannot be replaced with placeholder hashes.
The current TokenFactory documentation review does not supply those missing facts.

Offline regression commands use controlled HTTP/transport fixtures and local
subprocesses. They do not contact a model endpoint:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -W error tests/backend/test_remote_transport.py tests/backend/test_remote_provider.py tests/backend/test_inference_api.py
```

Their results belong to the [Mission 04 report](../../docs/reports/development-mission-04.md).
They cannot establish a remote endpoint's real capabilities or AMD hardware.

Task 3's local gate on 2026-10-14 passed 994 backend tests with warnings treated
as errors, including 64 transport and 104 provider tests plus 20 remote API
cases. It also passed 51 frontend tests, TypeScript, the production build and
dependency checks. These are offline software results; actual AMD requests: zero.

## Activation checklist

1. Obtain user authorization and credentials for the selected event endpoint or
   owned AMD deployment. Record the permitted workload/resource budget before
   making a real request; this preparation has used no credits.
2. Confirm the exact model ID, real model/processor revisions, license and image
   rights, one/two-image support, JSON Schema subset, request/response limits and
   timeout behavior. Keep unsupported or unknown features explicit.
3. Record separate AMD evidence: actual GPU model/count/VRAM, Linux/driver/ROCm,
   serving engine/version, model-file or deployment digest, precision, processor
   and decoder configuration. A model-name echo or `openai-remote` label is not
   hardware proof. Preserve the Windows CUDA environment unchanged.
4. Configure the exact HTTPS allowlist and server-only credential. Run the offline
   transport and existing service tests first. Their simulated responses cannot
   be reported as successful AMD inference.
5. After authorization, run bounded one-image and two-image probes against the
   actual endpoint. Preserve ordered original-byte hashes, untouched model text,
   schema validation, model identity, failures and observed timing. Inspect
   source attribution and unsupported claims independently.
6. Exercise authenticated inspection through human review and the deterministic
   workflow. Confirm missing/corrupt images, stale evidence, reservation races,
   exact retries and late output retain their existing safeguards. Enable the
   provider only after the applicable gates pass; preserve failures without
   automatic model substitution or local fallback.

## Actual AMD acceptance still required

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
