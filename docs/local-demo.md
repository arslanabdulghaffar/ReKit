# Run a local ReKit demonstration

Use the existing Windows environment from `A:\hackathon\ReKit`. The launcher
replays the actual workbench against temporary loopback services. It registers
each batch, return and component through the UI; it does not seed successful
inventory or reuse an operational database. Choose one mode explicitly.

## Check prerequisites first

```powershell
.\.venv\Scripts\python.exe evaluation/run_demo.py --mode synthetic-recovery --check
.\.venv\Scripts\python.exe evaluation/run_demo.py --mode canonical-recovery --check
.\.venv\Scripts\python.exe evaluation/run_demo.py --mode product-ai --check --device 1
```

All checks require the existing Python 3.12 environment, Node.js 26 or newer,
installed frontend dependencies, Chrome or Edge, and valid synthetic catalog and
policy files. They check the fixed IPv4 addresses `127.0.0.1:8000` and
`127.0.0.1:5173`; a busy port stops the launcher. Stop your own ReKit servers
before retrying. The launcher does not stop an unrelated service.

Only `product-ai` checks the original ABO image pair, all ten pinned model files
and their verification receipt, CUDA availability and at least **7 GiB free VRAM**
on the selected GPU. The default is device 1. It uses the existing
Qwen3-VL-2B-Instruct revision
`89644892e4d85e24eaac8bacfd4f463576704203`; no alternate model is selected.
Hash checks can take time. Synthetic recovery needs no AI packages or GPU.

`--check` loads no model and performs no model generation. It starts no browser or server
and creates no disposable state or credentials. AI preflight queries CUDA device
availability and memory; it is not an inference run or performance measurement.
Missing prerequisites produce a failed check; the launcher does not install
software, fetch images or weights, replace PyTorch/CUDA, or change modes.

## Watch the actual replay

Run one command at a time. These examples show the browser, add 100 milliseconds
between browser actions, and leave the final screen visible for 60 seconds:

```powershell
.\.venv\Scripts\python.exe evaluation/run_demo.py --mode product-ai --headed --slow-mo-ms 100 --hold-seconds 60 --device 1
.\.venv\Scripts\python.exe evaluation/run_demo.py --mode synthetic-recovery --headed --slow-mo-ms 100 --hold-seconds 60
.\.venv\Scripts\python.exe evaluation/run_demo.py --mode canonical-recovery --headed --slow-mo-ms 100 --hold-seconds 60
```

Allow the automated replay to finish before interacting with its final screen.
The final inspection window ends automatically; the launcher then closes its
browser/services and removes its temporary state. It is a bounded demonstration,
not a persistent server. The hold begins after the acceptance assertions; any
manual actions during that window are outside those recorded checks. To interrupt,
press **Ctrl+C in the launching terminal**
and let cleanup finish.

| Option | Meaning |
| --- | --- |
| `--mode` | Required: `product-ai`, `synthetic-recovery` or `canonical-recovery`. There is no automatic fallback. |
| `--headed` | Show the installed browser; without it, acceptance runs headlessly. |
| `--slow-mo-ms` | Browser-action delay from 0 to 500 milliseconds; a nonzero delay requires `--headed`. |
| `--hold-seconds` | Final inspection window from 0 to 120 seconds; a nonzero window requires `--headed`. |
| `--device` | Selected CUDA GPU index, default 1; used by the product-AI mode. |
| `--check` | Read-only preflight without model generation, servers or demo state. |

For headless acceptance, omit the display, pacing and hold options:

```powershell
.\.venv\Scripts\python.exe evaluation/run_demo.py --mode product-ai --device 1
.\.venv\Scripts\python.exe evaluation/run_demo.py --mode synthetic-recovery
```

The existing [browser acceptance runner](../evaluation/run_browser_acceptance.py)
remains available; the launcher adds prerequisite checks and composes that
runner's existing lifecycle. A preflight pass is not a browser acceptance pass.
Mission 05 Task 2 ran both modes in the installed Chrome 154.0.8037.98 on
October 14, 2026, with a visible browser, 75 ms pacing and a three-second final
inspection window. Synthetic recovery passed in 22.3 seconds
(`var/mission02-acceptance/run-jir8_r4c`); product AI passed in 54.6 seconds
(`var/mission02-acceptance/run-ai-d469agf2`). The latter made one actual joint
GPU request: 38.575 seconds of inference and 47.344 seconds for the provider
request, including loading and processing. All eight screenshots were inspected.
Both runs removed their owned state and credentials. A final synthetic replay
with a one-second hold also passed in 5.8 seconds (`run-npu5cp1a`) after the
passing-result write was moved after the hold. These are local demonstration
measurements, not semantic accuracy or AMD qualification.

## What each mode demonstrates

| Mode | Actual workflow and expected end state |
| --- | --- |
| `product-ai` | Upload two original ABO fan-view files into one simulated return/component; make one real joint local NVIDIA inference request; display unverified observations, source hashes and uncertainty; record an operator-role rejection requesting better evidence. The component stays unknown/held, with zero verifications, reservations or completed kits. Reuploading the originals checks deduplication, not newly captured evidence. |
| `synthetic-recovery` | Register three incomplete synthetic returns and four distinct components, upload labeled synthetic images, exercise explicit operator-role verification and compatibility checks, and run actual CPU CP-SAT. Approval reserves four components; two separate completion confirmations produce two kits and four consumed parts with audit/lineage. No AI runs in this mode. |
| `canonical-recovery` | Use the same catalog and physical IDs in a fresh synthetic case. Preserve an incorrect revision B assertion, add an original close-up and correct to A; compare baseline rebuild and higher-labor liquidation plans; reject a competing reservation; complete two kits. Nine original synthetic diagrams and a hash manifest survive cleanup. No AI or ABO images are used. |

The [canonical case](canonical-case.md) is the recommended recovery story for the
next recording. The [Block B report](reports/winning-quality-block-b.md) links
actual browser receipts and screenshots. Its retained source manifest and
`canonical-economics.json` complement the API receipt's three complete feasible
alternatives. Browser-created scenario IDs/descriptions differ; economic inputs
are unchanged except labor rate. The API comparison additionally keeps those
metadata fields identical. None of these synthetic estimates measures savings.

ABO catalog views do not establish an actual customer return or one physical
object. The photo mode supplies no matching identity catalog; empty candidates
are enforced by the contract, not measured recognition accuracy. Model prose can
still be unsupported or incomplete. Scripted operator actions are not independent
human truth labels, and images do not establish hidden functionality or safety.
See [source and model evaluation](real-product-evaluation.md).

The recovery fixture's **USD 175** is modeled net disposition value under supplied
cost assumptions, not realized revenue or savings. Do not combine its invented
parts with the ABO images or describe the photo run as a rebuilt kit. Neither
mode performs AMD inference; the [remote activation gate](../deploy/amd/README.md#activation-checklist)
remains separate.

## Credentials, results and cleanup

The replay creates ephemeral operator credentials in an ignored local manifest
and signs in automatically. Credentials are not printed to the console or saved
in the intended screenshots. Do not open or record the temporary credential
manifest or browser authorization headers.

Each run owns a fresh directory under `var/mission02-acceptance/run-*/` or
`run-ai-*/`. It removes only its own processes and temporary state, including its
database and credential manifest, on completion or handled interruption/failure.
Existing operational data, earlier artifacts and source image bytes are preserved.
Cleanup failures remain explicit in `runner-result.json`; inspect that result
instead of assuming a successful browser result also proves cleanup.

Credential-free results, logs and screenshots remain in the reported directory:

- Both modes: `runner-result.json`, `acceptance-result.json`, and backend,
  frontend and browser logs. A failed browser run may have `acceptance-failure.json`
  instead of a successful acceptance record.
- Product AI: `product-inference-results.json`, `desktop-product-inspection.png`,
  `mobile-product-inspection.png`, and `product-review-held.png`.
- Synthetic recovery: `desktop-evidence.png`, `mobile-evidence.png`,
  `plan-overview.png`, `reserved-plan.png`, and `final-inventory.png`.

Inspect the actual output before presenting it. Keep raw model limitations visible
and retain [ABO attribution](real-product-evaluation.md#source-license-and-attribution)
and [Qwen provenance](local-inference.md). Screenshots are execution evidence,
not a recorded or published presentation video.
