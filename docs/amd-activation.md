# Activate ReKit on an authorized AMD endpoint

**Mission 06 update, 2026-10-15:** the shared TokenFactory profile now has real
catalog discovery and two single-image POST attempts, both HTTP 400. Successful
AMD inference remains unqualified. Use the [TokenFactory procedure](tokenfactory.md)
and [current report](reports/development-mission-06.md) for its exact endpoint,
explicitly unattested revisions, quota evidence and blocked qualification.
The pinned owned-deployment procedure below is a separate path; no allocation
or billable infrastructure has been authorized or created.

**Status, 2026-10-14:** the remote adapter exists and has offline qualification.
Actual AMD requests, an allocation and a qualified AMD serving image remain
**unverified**. Execute this handoff only after the owner authorizes access,
image transfer and a bounded resource budget. No cloud request, allocation,
installation or deployment was performed for this guide.

The shortest path is to obtain endpoint facts, record AMD deployment evidence,
configure the existing remote provider, then inspect one and two managed images
through the authenticated UI. Keep the Windows CUDA environment intact.

## 1. Obtain the facts that require access

Use the event's [TokenFactory entry point](https://notebooks.amd.com/tokenfactory)
or an authorized [Developer Cloud allocation](https://www.amd.com/en/developer/resources/cloud-access/amd-developer-cloud.html).
The [event FAQ](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii)
describes TokenFactory without the cloud-credit/card prerequisite. It does not
publicly establish ReKit's vision/structured-output contract. The public
[AMD Notebooks page](https://notebooks.amd.com/) exposes sign-in; no authenticated
catalogue was inspected. Record actual values privately:

| Required fact | Source |
| --- | --- |
| Approved account, image data and request/resource budget | Owner and provider terms. |
| HTTPS base URL ending `/v1`, bearer authentication, exact served model ID | Account-specific endpoint documentation. |
| Real model and processor revisions, each 40 lowercase hexadecimal characters | Actual deployment files or provider attestation; never a fabricated hash. |
| One/two images, original JPEG/PNG/WebP data URLs, JSON Schema support | Actual endpoint qualification; JSON-object mode alone is insufficient. |
| GPU model/count/VRAM, driver/ROCm and serving versions | Allocation records and runtime probes. |
| Immutable container digest, decoder and processor settings | Selected deployment; these values are currently unknown. |

**UNKNOWN is a blocker, not a configuration value.** If TokenFactory cannot
supply these facts or the contract, leave inference disabled and qualify an
authorized owned deployment. Do not infer its capabilities from another AMD
service. See [access findings](amd-access.md).

## 2. Probe the actual Linux serving environment

Use AMD's [Developer Cloud setup guide](https://www.amd.com/en/developer/resources/technical-articles/2025/how-to-get-started-on-the-amd-developer-cloud-.html)
to select the authorized ROCm/vLLM environment. On that **Linux allocation**,
run these probes inside the actual serving container/environment. Save output
privately with the allocation ID and UTC time; never dump credentials or the
whole environment.

```bash
date -u
uname -a
cat /etc/os-release
amd-smi version
amd-smi list
amd-smi static --asic --vram --driver
rocminfo
python -m pip show torch transformers vllm
python - <<'PY'
import json, platform, torch
assert torch.version.hip, "Not a ROCm PyTorch build"
assert torch.cuda.is_available(), "No usable ROCm device"
print(json.dumps({
    "python": platform.python_version(), "torch": torch.__version__,
    "rocm_build": torch.version.hip,
    "devices": [{"index": i, "name": torch.cuda.get_device_properties(i).name,
                 "memory_bytes": torch.cuda.get_device_properties(i).total_memory}
                for i in range(torch.cuda.device_count())]
}, indent=2))
PY
```

ROCm PyTorch uses the `torch.cuda` namespace. An absent probe is missing evidence,
not a guessed GPU; consult the installed platform's documented equivalent.
[AMD SMI documents the commands](https://rocm.docs.amd.com/projects/amdsmi/en/latest/how-to/amdsmi-cli-tool.html).
Also record the container registry digest, actual model/processor files,
precision and attention implementation. Correlate this record with request
timestamps and serving-process/GPU telemetry during image execution.

## 3. Pin a vision model and restrict its endpoint

The [vLLM Qwen3-VL recipe](https://docs.vllm.ai/projects/recipes/en/stable/Qwen/Qwen3-VL.html)
documents ROCm support on specific Instinct generations; it does not qualify
ReKit's combination. A candidate is the existing `Qwen/Qwen3-VL-2B-Instruct`
snapshot `89644892e4d85e24eaac8bacfd4f463576704203`, whose weights and processor
files are pinned in the [local manifest](../configs/inference/qwen3-vl-2b.json).
Its Apache-2.0 model license does not license this repository or authorize image
transfer. Check rights and runtime compatibility first.

After authorization, provision one verified snapshot and a pinned ROCm/vLLM
release/container on Linux. Record its **actual** version and immutable digest;
no qualified container pin is known before access. Do not install `latest`, copy
CUDA wheels into ROCm or modify Windows PyTorch. Installation depends on the
actual allocation. Check that release's help before trying this bounded candidate
command. It uses the same verified directory for weights, tokenizer and processor.

```bash
set -euo pipefail
set +x
umask 077
read -r -p 'Verified local model/processor snapshot directory: ' REKIT_MODEL_SNAPSHOT
read -r -p 'Exact served model ID: ' REKIT_SERVED_ID
test -d "$REKIT_MODEL_SNAPSHOT"
vllm serve --help
trap 'unset VLLM_API_KEY' EXIT
read -r -s -p 'Private model-service bearer token: ' VLLM_API_KEY
printf '\n'
test -n "$VLLM_API_KEY"
export VLLM_API_KEY
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
export VLLM_DEBUG_LOG_API_SERVER_RESPONSE=False VLLM_NO_USAGE_STATS=1
vllm serve "$REKIT_MODEL_SNAPSHOT" \
  --tokenizer "$REKIT_MODEL_SNAPSHOT" --served-model-name "$REKIT_SERVED_ID" \
  --host 127.0.0.1 --port 8001 --tensor-parallel-size 1 --dtype bfloat16 \
  --max-model-len 8192 --max-num-seqs 1 \
  --limit-mm-per-prompt '{"image":2,"video":0}' \
  --generation-config vllm --override-generation-config '{"max_new_tokens":512}' \
  --structured-outputs-config '{"backend":"xgrammar"}'
unset VLLM_API_KEY
```

This is a **candidate qualification command**, not a tested AMD configuration.
Confirm decoder/option support and record processor pixel/token limits; two
original images may exceed the selected context. Reject oversize inputs rather
than silently dropping an image. The command enables neither remote model code
nor request/response debug logging. See vLLM's [serving arguments](https://docs.vllm.ai/en/latest/cli/serve/),
[credential environment variable](https://docs.vllm.ai/en/latest/configuration/env_vars/)
and [schema interface](https://docs.vllm.ai/en/latest/features/structured_outputs/).

Before remote access, have the authorized operator configure TLS ingress with a
valid hostname/certificate trusted by ReKit; expose only authenticated
`POST /v1/chat/completions`. Set a 30 MiB request ceiling, bounded admission and
queueing, and deadlines consistent with 120 seconds. Disable body/Authorization
logging. Keep the upstream private and restrict network access. vLLM's API key
does not protect every route; see its [security boundary](https://docs.vllm.ai/en/latest/usage/security/).
Do not expose the whole service, disable certificate checks or publish ReKit to
test it. No account-specific ingress product or command is assumed here.

## 4. Configure the existing ReKit backend

Use a dedicated PowerShell terminal at `A:\hackathon\ReKit`, outside transcript
or screen recording. Reuse an existing private operator configuration, or follow
[operator provisioning](operator-auth.md) privately. The operator token and
model-service key are separate credentials.

The example refuses an existing qualification directory. It checks the exact
workspace path and its ancestors for reparse points, then protects the new
directory for the current Windows user, SYSTEM and Administrators before any
database or image is written. Descendants inherit that ACL. Ignoring `var/` in
Git alone does not make its contents private. Preserve any existing qualification
data; review a different fresh path instead of deleting it to rerun this example.

```powershell
$ErrorActionPreference = 'Stop'
try {
    $workspacePath = [IO.Path]::GetFullPath('A:\hackathon\ReKit')
    if ((Get-Location).Path -ne $workspacePath) { throw 'Run from the exact ReKit workspace.' }
    $varPath = [IO.Path]::GetFullPath((Join-Path $workspacePath 'var'))
    $qualificationPath = [IO.Path]::GetFullPath((Join-Path $varPath 'amd-qualification'))
    if (-not $qualificationPath.StartsWith($varPath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Qualification output must remain under the workspace var directory.'
    }
    $ancestor = Get-Item -LiteralPath $varPath -Force
    while ($null -ne $ancestor) {
        if ($ancestor -isnot [IO.DirectoryInfo] -or ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Qualification ancestors must be real directories, not reparse points.'
        }
        $ancestor = $ancestor.Parent
    }
    if (Test-Path -LiteralPath $qualificationPath) { throw 'Refusing to reuse existing qualification data.' }
    New-Item -ItemType Directory -Path $qualificationPath | Out-Null
    $privateAcl = [Security.AccessControl.DirectorySecurity]::new()
    $privateAcl.SetAccessRuleProtection($true, $false)
    $privateIdentities = @(
        [Security.Principal.WindowsIdentity]::GetCurrent().User,
        [Security.Principal.SecurityIdentifier]::new('S-1-5-18'),
        [Security.Principal.SecurityIdentifier]::new('S-1-5-32-544')
    )
    foreach ($identity in $privateIdentities) {
        $privateAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
            $identity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow'))
    }
    Set-Acl -LiteralPath $qualificationPath -AclObject $privateAcl

    $env:REKIT_DATABASE_PATH = Join-Path $qualificationPath 'rekit.sqlite3'
    $env:REKIT_EVIDENCE_DIR = Join-Path $qualificationPath 'evidence'
    $env:REKIT_CATALOG_PATH = Join-Path $workspacePath 'tests\fixtures\synthetic_catalog.json'
    $env:REKIT_DISPOSITION_POLICY_PATH = Join-Path $workspacePath 'tests\fixtures\synthetic_disposition_policy.json'
    $env:REKIT_AUTH_CONFIG_PATH = Join-Path $workspacePath '.secrets\operators.json'
    $env:REKIT_INFERENCE_PROVIDER = 'openai-remote'
    $env:REKIT_INFERENCE_BASE_URL = Read-Host 'Actual HTTPS base URL ending /v1 (no trailing slash)'
    $env:REKIT_INFERENCE_ALLOWED_ENDPOINTS = $env:REKIT_INFERENCE_BASE_URL + '/chat/completions'
    $env:REKIT_INFERENCE_MODEL = Read-Host 'Exact served model ID'
    $env:REKIT_INFERENCE_MODEL_REVISION = Read-Host 'Verified model commit (40 lowercase hex)'
    $env:REKIT_INFERENCE_PROCESSOR_REVISION = Read-Host 'Verified processor commit (40 lowercase hex)'
    $env:REKIT_INFERENCE_MAX_IMAGES = '2'
    $env:REKIT_INFERENCE_TIMEOUT_SECONDS = '120'
    $env:REKIT_INFERENCE_API_KEY = [System.Net.NetworkCredential]::new('', (Read-Host 'Private model-service bearer token' -AsSecureString)).Password

    # Configuration validation only: no request, GPU work or database opening.
    .\.venv\Scripts\python.exe -c "from rekit.inference.adapters.openai_remote import RemoteVisionSettings; RemoteVisionSettings.from_environment(); print('Settings validated; endpoint execution remains unverified.')"
    if ($LASTEXITCODE -ne 0) { throw 'Stop: remote settings are invalid.' }
    .\.venv\Scripts\python.exe -m uvicorn rekit.main:create_configured_app --factory --host 127.0.0.1 --port 8000 --workers 1
} finally {
    Remove-Item Env:\REKIT_INFERENCE_API_KEY -ErrorAction SilentlyContinue
}
```

The synthetic catalogue/policy provide a **test container**, not real-product
identity. A different approved catalogue requires a separate database: stored
catalogue/policy snapshots cannot silently change. Do not verify a real product
against synthetic `body`/`adapter` identities to make a demonstration pass.

The allowlist is exact: no wildcard, redirect, query or embedded credential.
Only HTTPS is supported; `.env` is not loaded automatically. Keep the key in this
backend process environment, never `VITE_*`, URLs, command-line arguments, the
frontend terminal, tracked files, screenshots or logs. The remote provider has
no automatic retry, model substitution or local CUDA fallback.

The adapter sends original-byte data URLs, `stream=false`, temperature 0,
512 output tokens and `response_format.type=json_schema`. Bounds are two static
JPEG/PNG/WebP images, 10 MiB each, 16 million pixels and 8192 pixels/side; 30 MiB
encoded request and 128 KiB response. Transport is limited to 120 seconds; service
supervision adds 15 seconds. One ReKit worker preserves its process-local slot.

## 5. Qualify managed-image execution and the review boundary

In a **separate terminal without the model key**, start the installed frontend:

```powershell
Set-Location A:\hackathon\ReKit\frontend
npm run dev
```

Open `http://127.0.0.1:5173`, sign in privately and perform these two explicitly
budgeted requests. Use approved images of one physical object, preserving image
rights/attribution and original hashes. Catalog imagery is simulated intake,
not actual returned stock.

1. Register one batch, return and physical component; upload two original views.
   Inspect **Views & provenance** before reading model output.
2. Select one image and **Analyze images**; wait for its terminal result. Retain
   the run ID, actual status, untouched raw text, ordered input hashes,
   schema/prompt provenance and observed latency, including any failure.
3. Make one new two-image request. Check claims against recorded source-image
   indices, unknowns, readable markings, revision support and requested views.
   Valid JSON is not proof of visual accuracy.
4. Keep the object unverified/held until a human has sufficient evidence. Reject
   unsupported suggestions with a reason. Confirm failed/stale output applies
   no eligible identity and manual review remains available. AI cannot approve
   compatibility, reserve stock or prove hidden function or safety.

Keep private run records under ignored `var/` with the separate deployment
evidence. Status/runs identify `openai-remote`, `device=remote` and the configured
revision. Matching the response model ID is checked; deployed weights, processor
and AMD hardware are **not attested by the response**. Local hashes establish
sent bytes, not remote encoder execution. Correlate serving telemetry and inspect
the actual responses before claiming AMD execution.

Two requests are a smoke gate, not an accuracy or throughput benchmark. Broader
failure/race and repeated-latency qualification is in the
[deployment checklist](../deploy/amd/README.md#actual-amd-acceptance-still-required).
Record sample counts and failures; independent human-labelled accuracy is still
unestablished. An incompatible or inaccessible endpoint remains a blocker.

`evaluation/run_browser_acceptance.py --real-inference` and
`evaluation/run_api_inference_acceptance.py` explicitly construct the local
NVIDIA provider. They **cannot qualify AMD** through environment variables.
Use the configured application above. Existing
[offline regression commands](../deploy/amd/README.md#remote-configuration-and-provenance)
contact no model endpoint; their results are separate evidence.

Afterward stop local services, clear the process key and follow the authorized
cloud shutdown procedure. AMD's cloud FAQ notes that powered-off allocations
can still be billed; the owner decides destruction after preserving approved
artifacts. This guide grants no spending, publication, repository visibility,
licensing or submission permission.
