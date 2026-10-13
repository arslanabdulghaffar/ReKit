# Local visual inference qualification

ReKit's first local provider uses the official
[Qwen/Qwen3-VL-2B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct)
checkpoint. Task 1 qualifies image-to-text execution on one existing NVIDIA
GPU. It does not yet connect model output to evidence storage or the operator
interface, and it gives the model no catalog, approval, or inventory authority.

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
after return, and cannot interrupt a blocked GPU kernel or model loading. A
later HTTP integration needs a separate request-lifecycle policy rather than
presenting this setting as a hard process timeout.

## Measured qualification result

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

## Limits and AMD boundary

The illustration checks execution, not component-recognition accuracy, hidden
damage, functionality, electrical safety, or compatibility. Model text remains
unverified and can be wrong. Greedy generation improves repeatability, but it
does not guarantee bitwise-identical GPU results or calibrated probabilities.
Prompt instructions alone do not establish an authority boundary: later tasks
must validate model output and preserve explicit human review before existing
deterministic catalog, planning, approval, and inventory operations.

Local CUDA execution does not qualify AMD hardware, ROCm, or vLLM. Those still
need their own exact runtime/model compatibility checks and measured execution,
while preserving equivalent image, provenance, and unverified-output contracts.
See [AMD deployment](../deploy/amd/README.md). No AMD credits or cloud resources
are used by this qualification. CPU-only CI must not invoke the downloader or
GPU smoke test, download weights, or import/load the optional model at startup.
