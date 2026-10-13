# Local visual inference qualification

ReKit's first local provider uses the official
[Qwen/Qwen3-VL-2B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct)
checkpoint. Task 1 qualified image-to-text execution on one existing NVIDIA
GPU. The backend now connects that provider to authenticated inspection requests
and [unverified evidence storage](inference-evidence.md). The operator interface
integration is separate work. The model has no catalog, approval, or inventory
authority.

## Pinned model and download budget

The immutable revision is
`89644892e4d85e24eaac8bacfd4f463576704203`. Its
[official model card at that revision](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct/blob/89644892e4d85e24eaac8bacfd4f463576704203/README.md)
declares Apache-2.0. Preserve the license and attribution when redistributing;
the [Apache license text](https://www.apache.org/licenses/LICENSE-2.0) defines
its conditions. The repository is public and ungated. There is no separate
`LICENSE` file in this revision. This is model-license qualification, not a
claim about hackathon eligibility or AMD deployment readiness.

The [tracked manifest](../configs/inference/qwen3-vl-2b.json) records the exact
allowlist and official file hashes from the
[pinned repository metadata](https://huggingface.co/api/models/Qwen/Qwen3-VL-2B-Instruct/revision/89644892e4d85e24eaac8bacfd4f463576704203?blobs=true).

| Required file | Bytes |
| --- | ---: |
| `chat_template.json` | 5,502 |
| `config.json` | 1,505 |
| `generation_config.json` | 269 |
| `merges.txt` | 1,671,839 |
| `preprocessor_config.json` | 390 |
| `tokenizer.json` | 7,032,403 |
| `tokenizer_config.json` | 10,868 |
| `video_preprocessor_config.json` | 385 |
| `vocab.json` | 2,776,833 |
| `model.safetensors` | 4,255,140,312 |
| **Total** | **4,266,640,306** |

The total is about 3.974 GiB, below the authorized 6 GiB limit
(6,442,450,944 bytes). The single weight file has official SHA-256
`7de1838c87a5349b016c26a1c3f7d2bc400a3d485f95ef39a7059ffd734977a0`.
The tiny video configuration is needed to construct the official processor,
whose attributes include a video processor; ReKit still accepts only images.
No second checkpoint, quantization, dataset, or sample image is downloaded.

From the repository root:

```powershell
.\.venv\Scripts\python.exe evaluation/download_vision_model.py
```

The standard-library downloader stores one copy under ignored
`models/Qwen3-VL-2B-Instruct/<revision>/`. It checks exact lengths, the official
weight SHA-256, and Git blob hashes for the small files. It computes SHA-256 for
every file and writes the ignored `rekit-download.json` verification receipt
only after all ten files pass. Completed files are verified and reused. An
interrupted `.part` file resumes only if the server confirms its exact byte
range; an invalid existing file is preserved and reported rather than silently
replaced. An exclusive lock prevents two downloader processes sharing a target.
After an abnormal process termination, inspect any remaining lock and partial
files before restarting; the tool does not guess whether another process owns
them. Model paths must stay in the ignored repository model directory without
symlinks or junctions. Local administrators and the host filesystem are trusted.

The initial download completed successfully on 2026-10-13 at
06:07:23 UTC: 4,266,640,306 bytes transferred, with all ten official size/hash
checks passing and no retry. The downloader measured 541.125 seconds including
transfer and verification. The ignored receipt preserves these observed values;
this is download timing, not GPU loading or inference latency.

## Runtime choice

Use the existing Python 3.12.10 environment and preserve
PyTorch `2.9.0+cu128` and torchvision `0.24.0+cu128`.
[PyTorch's official version table](https://pytorch.org/get-started/previous-versions/)
lists that pairing with CUDA 12.8 for Linux and Windows. This documents package
compatibility; actual model execution still needs the local qualification.

The selected inference dependencies are Transformers `4.57.6`,
Hugging Face Hub `0.36.2`, tokenizers `0.22.2`, and safetensors `0.6.2`, plus their
required small dependencies. These stay separate from the lightweight backend's
default installation. The
[Transformers patch release](https://github.com/huggingface/transformers/releases/tag/v4.57.6)
contains native Qwen3-VL support. The model card's original recommendation to
install an unreleased 4.57 development version is historical; this qualification
uses a pinned release instead of the moving development branch.

The exact optional package pins are in
[requirements-inference.txt](../requirements-inference.txt). For this existing
environment, review the dry-run plan before installation:

```powershell
.\.venv\Scripts\python.exe -m pip install --dry-run --only-binary=:all: -r requirements-inference.txt
.\.venv\Scripts\python.exe -m pip install --only-binary=:all: --no-deps -r requirements-inference.txt
.\.venv\Scripts\python.exe -m pip check
```

Proceed only when the plan preserves the existing environment, particularly
torch, torchvision, and CUDA. The `--no-deps` command relies on the already
verified base environment and the explicit missing-package pins; it is not a
fresh-machine installation recipe. The actual qualification added ten packages,
downloaded 16,558,685 wheel bytes (about 15.79 MiB), and replaced no existing
package. This is below the separate 2 GiB package-download budget.

Existing Pillow, torchvision, and Jinja2 provide image processing and template
support. Windows wheels exist for the tokenizer and safetensors versions. No
PyTorch reinstall, Accelerate, qwen-vl-utils, FlashAttention package, CUDA
extension, compiler, or custom remote model code is required. Load only verified
local files with `local_files_only=True` and `trust_remote_code=False`.

The provider uses BF16 and PyTorch SDPA on one explicit CUDA device. It does not
combine the GPUs' memory or use automatic CPU/offload placement. Weight storage
is about 3.96 GiB. The official configuration has 28 text layers, eight KV heads,
and head dimension 128: BF16 KV storage is approximately 112 KiB per sequence
token, before visual activations, allocator overhead, and other runtime memory.
With bounded image/input/output sizes, this is a reasonable candidate for one
16 GiB GPU; it is an estimate, not a measured peak or a guarantee of free memory.

## Reproduce actual GPU execution

Inspect free GPU memory before selecting the device. The initial qualification
uses GPU 1 when it has sufficient free memory; `--device` is an explicit CUDA
index, not a request for automatic placement.

```powershell
.\.venv\Scripts\python.exe evaluation/run_vision_smoke.py --device 1 --repeat 2
```

The command generates a clearly labeled synthetic illustration locally and
passes its real PNG bytes to the provider. It writes an ignored UTF-8 report at
`var/mission03-qualification.json` and the generated image beside it. An optional
`--image` accepts an already-authorized local image for this command-line test;
this is not a client-controlled HTTP path interface.

The implementation currently limits each request to one or two static
JPEG/PNG/WebP images, 10 MiB per input, 16 million original pixels, and 8,192
pixels per original side. It applies EXIF orientation, converts to RGB, bounds
the image within 768 by 768, then uses the official processor with 65,536 to
589,824 pixels. The
[official processor implementation](https://github.com/huggingface/transformers/blob/v4.57.6/src/transformers/models/qwen3_vl/processing_qwen3_vl.py)
handles image tensors and the chat template. Text plus visual tokens are bounded
to 8,192; generated output defaults to 256 tokens and cannot exceed 512.

Only one request can use a provider instance at a time. Repeated requests reuse
loaded weights. The smoke test checks the selected CUDA device, actual image
tensors, a real visual-encoder forward call, source-image hashes, and nonempty
generated text. It records loading time, inference latency, peak allocated GPU
memory, runtime versions, settings, and the immutable model revision. Two runs
on the same provider check that the second request does not reload weights.
Unavailable GPU, invalid input, loading failure, or inference failure is explicit;
there is no fabricated answer or hidden CPU fallback.
The generation deadline is cooperative: it is checked during generation and
after return, and cannot interrupt a blocked GPU kernel or model loading. The
HTTP service adds the separate request lifecycle described below; neither
deadline can forcibly cancel a CUDA kernel.

## Enable authenticated backend inspection

First configure the database, catalog, disposition policy, managed image
directory, and operator credentials as described in
[API setup](api-workflow.md) and [authentication](operator-auth.md). The factory
reads environment variables explicitly; it does not load `.env` automatically.
Then opt in to the already downloaded, verified local checkpoint:

```powershell
$env:REKIT_INFERENCE_PROVIDER = 'local-transformers'
$env:REKIT_MODEL_DIR = '.\models\Qwen3-VL-2B-Instruct\89644892e4d85e24eaac8bacfd4f463576704203'
$env:REKIT_CUDA_DEVICE = '1'
.\.venv\Scripts\python.exe -m uvicorn rekit.main:create_configured_app --factory --host 127.0.0.1 --port 8000 --workers 1
```

Use exactly one worker and one serving process for this configuration. Admission
is protected by a process-local slot, not a distributed GPU scheduler. Keep
credentials, managed images, model files, and run artifacts out of Git. Clients
cannot select a model, GPU, prompt, local file, or remote image URL.

The default `REKIT_INFERENCE_PROVIDER=disabled` leaves the manual workflow
available. Imports and application construction do not load model weights or
initialize CUDA. With local inference enabled, the first admitted request loads
the model lazily; later requests reuse it. Missing runtime packages, unavailable
GPU, or model loading failure produce explicit unavailability without a
fabricated prediction or CPU fallback. Invalid server configuration, such as an
unsupported provider name or absent `REKIT_MODEL_DIR`, is a startup error.

An authenticated viewer can call `GET /inference/status`. The response includes
`status`, `busy`, `provider`, `model_repository`, `model_revision`, and `device`;
a configured service also reports `request_timeout_seconds`. A disabled service
returns HTTP 200 with `status: "unavailable"` and null provider fields. The
configured local adapter reports `unloaded`, `loading`, `ready`, or
`unavailable`; `busy` separately describes ownership of the computation slot.

A human actor with the reviewer role submits
`POST /components/{component_id}/inference` using existing managed asset IDs:

```json
{
  "request_id": "inspection-example-001",
  "asset_ids": ["asset-0123456789abcdef0123456789abcdef"],
  "expected_version": 2
}
```

Replace the example ID and version with the component's real uploaded image and
current evidence version. Supply the existing bearer credential through the
Authorization header. The server binds the authenticated actor; the body has
no `operator_id`. One or two distinct images must belong to that component.

HTTP 202 returns the stored `InferenceRun`, with `start.run_id` and normally
`outcome: null`. Poll `GET /inference/{run_id}` as a viewer until `outcome` is
present. `GET /components/{component_id}/inference` lists the latest 50 runs.
An exact POST retry returns the same run, including a terminal run, and does
not schedule another computation. Reusing its request ID with changed contents
or a different actor returns HTTP 409.

A fresh request while the slot is busy returns HTTP 409 without admission;
there is no queue. Missing credentials return 401, insufficient role returns
403, unknown references return 404, and malformed input returns 422. A disabled
inference service returns 503 for invocation and run queries. Once a request
is accepted, execution failures are terminal outcomes in the stored run, not
invented successful HTTP payloads; polling that existing run still returns 200.

The backend prompt requests bounded structured observations, candidate
identities, uncertainty, and additional views. It supplies catalog labels as
untrusted context, not as visual proof or compatibility decisions. Generation
uses at most 384 new tokens and a 120-second cooperative deadline. A separate
150-second request deadline records `timed_out` and discards any late result.
The slot remains busy until the actual worker returns, even after timeout.
Shutdown stops admission, records failure for an active pending run, and waits
up to one second for its daemon thread; it cannot interrupt a blocked kernel.

An abrupt crash can leave a run pending. Restart and exact replay do not resume
it or invent a failure. If the restarted service is idle, a deliberate new
request can use a new ID after checking the current evidence version. Manual
inspection remains available. See [inference evidence](inference-evidence.md)
for stale-result handling and the required human review boundary.

## Task 1 measured qualification result

The real smoke command passed on 2026-10-13, finishing at 06:08:52 UTC. Both
requests used the same provider instance on `cuda:1`, an NVIDIA GeForce
RTX 4080 SUPER, with BF16 weights and PyTorch SDPA. The recorded runtime was
Python 3.12.10, torch 2.9.0+cu128, torchvision 0.24.0+cu128, CUDA 12.8,
Transformers 4.57.6, Qwen3VLProcessor, and Pillow 12.3.0.

| Measurement | First request | Second request |
| --- | ---: | ---: |
| Model load time | 4.624754 s | Reused; no reload |
| Inference time | 34.424170 s | 33.016417 s |
| Peak PyTorch allocated GPU bytes | 4,398,954,496 | 4,397,340,672 |
| Peak PyTorch reserved GPU bytes | 4,460,642,304 | 4,469,030,912 |
| Input tokens | 474 | 474 |
| Generated tokens | 100 | 100 |
| Observed visual-encoder forward calls | 1 | 1 |

Inference timing includes processor preparation and generation, measured with
CUDA synchronization; model loading is measured separately. The largest
allocated peak was about 4.097 GiB and the largest reserved peak about 4.162 GiB.
These are PyTorch allocator measurements, not total device usage including the
driver and other processes. They establish fit for this bounded request, not
for every permitted image or the model's full advertised context length.

The input was a locally drawn, 10,904-byte PNG with SHA-256
`cf1a8f595ff3986a947e7160cdb76d7493e9748d2d1f5a03b83d0d23343de38b`.
The official processor produced a `[1536, 1536]` image tensor and
`[[1, 32, 48]]` image grid in each request. The visual-encoder hook and image
hash check establish that the supplied image was actually processed; the result
was not a canned text response.

Both requests returned identical model text. A representative exact excerpt is:

> A red triangle on the left side.
> A blue circle on the right side.

The generated response also read the visible `SYNTHETIC` heading and illustration
footer. This observation describes one synthetic example and is not a measured
recognition-accuracy result. The full text and per-request manifest remain in
ignored `var/mission03-qualification.json`. No raw generated image or model
weights are committed.

Transformers reported that sampling-only `temperature`, `top_p`, and `top_k`
settings from the checkpoint are ignored during greedy generation. The observed
run used `do_sample=False`; no sampling or CPU fallback was silently introduced.

An earlier processor preflight raised `TypeError` when the system message used
a plain-string content value. Supplying the multimodal processor's typed text
content list resolved it before GPU execution. Neither of the two recorded GPU
requests failed; no CUDA or model replacement was needed.

Task 1's final CPU backend suite passed 409 tests, including 34 local-provider
tests and 13 downloader tests; `pip check` also passed. Provider test doubles
exercise failure and boundary behavior and are not AI execution results. The
existing frontend baseline passed 25 tests, TypeScript validation, and its
production build. The real GPU evidence is the separate two-request report
above; local checks do not imply a completed GitHub Actions run.

## Task 3 measured API execution and recognition error

The authenticated API acceptance completed on 2026-10-13 at 06:36:44 UTC.
It used real ASGI HTTP requests against an in-process application, managed image
storage, SQLite, and one actual local GPU inference request. It did not exercise
a browser or a separately listening Uvicorn server. Reproduce it with:

```powershell
.\.venv\Scripts\python.exe evaluation/run_api_inference_acceptance.py --device 1
```

The ignored `var/mission03-api-acceptance.json` records the complete request,
raw response, parsed output, evidence history, and inventory state. The supplied
image was the same 10,904-byte synthetic PNG used above, with SHA-256
`cf1a8f595ff3986a947e7160cdb76d7493e9748d2d1f5a03b83d0d23343de38b`.
The managed asset and admitted inference input retained that exact hash.
Execution used the pinned Qwen revision on `cuda:1`, an RTX 4080 SUPER, with
the same Python, PyTorch, CUDA, and Transformers versions as Task 1.

| Measurement | Actual API request |
| --- | ---: |
| Model load time | 4.7128118 s |
| Inference time | 43.5648928 s |
| Worker elapsed time through provider return | 53.5957470 s |
| Peak PyTorch allocated GPU bytes | 4,540,146,688 |
| Peak PyTorch reserved GPU bytes | 4,559,208,448 |
| Input tokens | 852 |
| Generated tokens | 267 |
| Observed visual-encoder forward calls | 1 |

The worker elapsed measurement includes managed-input handling and provider
execution; it is not browser latency or a throughput benchmark. The model was
loaded for this request. Its terminal result was structurally valid and current
(`succeeded`, `stale: false`), and an exact HTTP retry reused the stored run.

**The software integration passed, but the model made an unsupported identity
and revision claim.** It described the red triangle and blue circle, then
proposed component type `adapter`, revision `A`, using `SYNTHETIC` as its
`revision_marking`. Its reason incorrectly treated that heading as an adapter
marking. The same response acknowledged that this was an illustration, that
the revision could not be confirmed, and that `SYNTHETIC` was not a product
marking. The image provides no support for that component identity or revision.
These contradictions remain in the recorded raw and structured output; they
were not repaired or presented as a correct recognition result.

The authority boundary held: the original single physical-component identity
was preserved, evidence advanced from version 2 to 5 with three unverified model
events, and its state remained `review_required` with no human verification.
Both inventory eligibility and availability remained `held`; no component was
reserved or consumed and no kit was created. Compatibility was not granted.
This run establishes actual image processing and safe workflow integration,
not component-recognition accuracy or proof that the candidate is plausible.

This historical run predates addition of the `preprocessing.prompt_sha256`
field, so its report does not contain that digest. The prompt content was
unchanged when the field was added; subsequent runs record the exact prompt
hash. The synthetic illustration remains unsuitable for a product-recognition
benchmark. Literal matching of a revision against model-quoted text would not
establish that either string is visible or correct; human image review remains
required.

## Limits and AMD boundary

The illustration checks execution, not component-recognition accuracy, hidden
damage, functionality, electrical safety, or compatibility. Model text remains
unverified and can be wrong. Greedy generation improves repeatability, but it
does not guarantee bitwise-identical GPU results or calibrated probabilities.
Prompt instructions alone do not establish an authority boundary. The backend
strictly validates model output and preserves explicit human review before
deterministic catalog, planning, approval, and inventory operations. A valid
schema still does not establish the truth of a model's visual claims.

Local CUDA execution does not qualify AMD hardware, ROCm, or vLLM. Those still
need their own exact runtime/model compatibility checks and measured execution,
while preserving equivalent image, provenance, and unverified-output contracts.
See [AMD deployment](../deploy/amd/README.md). No AMD credits or cloud resources
are used by this qualification. CPU-only CI must not invoke the downloader or
GPU smoke test, download weights, or import/load the optional model at startup.
