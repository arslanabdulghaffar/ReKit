# ReKit Development Mission 06 checkpoint report

October 15, 2026, Asia/Seoul. **Partial checkpoint; not a completion report.**
Repository: `A:\hackathon\ReKit`, private GitHub `arslanabdulghaffar/ReKit`.
Missions 01–05 remain accepted. The starting commit was
`c88e7f6271e75df776b593af4364b564e9989089`.

Task 1 is committed, pushed and CI-verified. Task 2 has made **two authenticated
discovery GETs** and remains blocked on usable quota evidence and conflicting
capability declarations. **Generation attempts: 0 of the authorized maximum 6.**
No image has been transmitted to AMD, and no AMD visual inference, local GPU
regression or browser acceptance has run during this mission. Tasks 3–6 are pending.

## Authorization and credential handling

The user confirmed revocation/replacement of the potentially exposed key and
authorized bounded free-service discovery and at most six generation attempts.
The approved image scope is non-sensitive synthetic illustrations and the two
existing public ABO fan views from listing `B07XGQ9QJF`, image IDs
`71rr7OjqWqL` and `812Xgtrv0EL`. This does not authorize customer-private images,
paid resources, dedicated instances, publication or repository visibility changes.

Local key setup is complete. The replacement is stored as a Windows-user-bound
DPAPI encrypted SecureString under ignored `.secrets/tokenfactory/`, with access
restricted to the current user, SYSTEM and Administrators. It is not recorded
in this report, examples, process arguments, frontend configuration or diagnostic
logs. The discovery wrapper supplies the decrypted value only to its owned
Python child's environment, removes its temporary environment entry, disposes
the SecureString and drains child output without echoing it.

The [official usage documentation](https://amd-aim.github.io/radeon-cloud-docs/api/usage/)
names a different host from the approved API host.
**Explicit authorization for that additional destination is pending:**
`https://radeon-global.anruicloud.com/api/profile/model-usage?include_recent=true`.
It has not been contacted. Neither a redirect nor a guessed alternate route is
used to forward credentials. See [TokenFactory setup and gates](../tokenfactory.md).

## Stage status

| Task | Current evidence |
| --- | --- |
| 1. Capability and code audit | Complete. Added the exact TokenFactory endpoint profile, narrowly scoped unattested revisions, honest UI provenance, credential setup and offline regression coverage. |
| 2. Safe discovery | Validated implementation and live-discovery checkpoint. Two actual GETs; valid catalog obtained, usable quota unavailable. The account/allowance gate remains open. |
| 3. AMD visual qualification | Pending. No generation, image upload to the service or schema-execution result. A persistent six-attempt gate must precede generation. |
| 4. AMD application integration | Pending live acceptance. Existing managed evidence, roles, strict parsing, human decisions and deterministic inventory boundaries remain. |
| 5. AMD/NVIDIA comparison | Pending. No recognition-accuracy or hardware-throughput comparison is claimed. Existing local measurements are historical evidence, not new mission runs. |
| 6. Final demonstration and reporting | Pending. No AMD browser demonstration, final validation or Mission 06 completion receipt yet. |

## Actual authenticated discovery

Both requests used the exact host `developer.amd.com.cn`, verified HTTPS and
the rotated credential. These were metadata requests, not model generations.
Failed or interrupted discovery receipts are cached; repeating the command does
not silently retry. The separate catalog request followed explicit review of
the unusable usage response and retained the prior receipt's digest.

| Request | Measured result |
| --- | --- |
| `GET https://developer.amd.com.cn/radeon/api/v1/usage?include_recent=true` | HTTP 200, **invalid_response**, 0.531 seconds. No usable quota or quota headers. Raw response was not stored. HTTP success did not establish a usable usage contract. |
| `GET https://developer.amd.com.cn/radeon/api/v1/models` | HTTP 200, valid sanitized catalog of **12 models**, 0.406 seconds, 11,572 response bytes. No quota headers. |

Catalog response SHA-256:
`f8cb716534d7b1c42c43b2718d594405af840291f38706c5f19c5482099964a0`.
Sanitized private receipts are `discovery.json` and `catalog-discovery.json`
under `.secrets/tokenfactory/qualification/`; account data and credentials are
not copied into Git. **Remaining quota is unknown, not zero or unlimited.**

This is an actual catalog response, not account qualification. The official
catalog documentation says the catalog is identical for every key and is not
account-scoped. HTTP 200 on this credential-bearing request therefore does not
establish account verification, usable quota or free-service entitlement.
[Catalog reference](https://amd-aim.github.io/radeon-cloud-docs/api/models/).

The first candidate is advertised with the exact ID **`MiMo-V2.6-Flash`**.
Its catalog declares image/text input, `json_output=true`,
`structured_outputs=false` and `free=false`. All 12 advertised models have
`structured_outputs=false` and `free=false` in this response.

The [MiMo reference](https://amd-aim.github.io/radeon-cloud-docs/models/mimo-v2-6-flash/)
documents strict JSON Schema, image data URLs and `reasoning_effort: "none"`.
That conflicts with the catalog's structured-output flag; neither declaration
is proof that ReKit's actual schema or joint two-image request works. The
catalog's `free=false` flag must not be equated with paid billing: the documented
flag concerns whether calls consume the daily allowance at zero cost.
[Catalog field definitions](https://amd-aim.github.io/radeon-cloud-docs/api/models/).
No credits were
purchased and no billable infrastructure was created. Usable allowance and
schema support still require confirmation before generation.

## Implemented software and preserved boundaries

The explicit provider is `amd-tokenfactory`, with exactly
`https://developer.amd.com.cn/radeon/api/v1/chat/completions` in its trusted
singleton allowlist. Generic `/v1` endpoints retain their original restrictions.
No operator request can override destination, provider or credentials; redirects,
proxy inheritance, retries and local NVIDIA fallback remain disabled.

Only this shared-service profile permits null model/processor revisions, paired
with `device=remote` and `revision_verification=shared_service_unattested`.
Local CUDA and generic remote configurations still require their immutable
40-character revision pins. The UI identifies the actual configured provider
and each historical run separately, without inventing missing revisions.
Matching a future response model ID will establish the service's advertised
identity, not attest its weights, processor, GPU model, ROCm or runtime version.

Original managed-image ownership, byte hashes, input ordering, version checks,
immutable inference provenance, independent schema/domain parsing and human
review remain mandatory. A schema-valid observation cannot verify identity,
approve compatibility, reserve inventory or establish hidden function/safety.
ABO catalog photographs remain simulated intake, not actual returned stock.

Discovery uses bounded, fixed-resource GETs and saves only allowlisted metadata.
Authentication rejection, rate limiting, incomplete account status and explicit
exhausted quota block progress. Positive headers cannot override an explicit
zero quota. The wrapper checks Git exclusion for each private path separately
and validates credential/receipt ACLs. Cancellation cleanup is implemented;
its interruption path has **not** been empirically qualified.

## Validation recorded so far

All software tests below were offline; controlled responses are not AMD vision
execution. GitHub Actions remains CPU-only.

| Check | Result |
| --- | --- |
| Task 1 full backend, warnings as errors | 1,185 passed in 41.42 seconds. |
| Task 1 focused backend | 406 passed in 13.57 seconds. |
| Task 1 full frontend | 61 passed in 29.10 seconds. |
| Task 1 focused inference UI | 32 passed in 6.53 seconds. |
| Task 1 TypeScript, build, `pip check`, `npm ls --all`, local Markdown links | Passed. |
| Task 1 synthetic recovery | OPTIMAL; 2 kits, 4 consumed physical components, 17,500 cents modeled value. This is a synthetic scenario estimate, not realized savings. |
| Current Task 2 full backend | 1,306 passed in 38.86 seconds, including 33 discovery tests. |
| Current transport/provider/inference API checks | 380 passed in 11.18 seconds. |
| Isolated wrapper checks | 67 offline assertions; 27 files and 5 ACLs checked, including controlled output-drain failure. No real key used in these checks; dynamic cancellation not exercised. |

Task 2 validation commands, from the repository root:

```powershell
.venv\Scripts\python.exe -W error -m pytest -q
.venv\Scripts\python.exe -B -W error -m pytest tests/backend/test_remote_transport.py tests/backend/test_remote_provider.py tests/backend/test_inference_api.py -q
.venv\Scripts\python.exe -W error -m pytest -q tests/backend/test_tokenfactory_discovery.py
.venv\Scripts\python.exe -B -W error var/mission06-offline/check_tokenfactory_wrapper.py
```

The isolated wrapper harness and `wrapper-check.json` receipt are private local
validation artifacts, not requirements for running the tracked test suite.
The receipt SHA-256 is
`129d284b2a56d6d8520ff2a4ae2b8cec1e0369b07a8f582abfc57d588fcf4581`.

Task 1 also used these commands from the repository root:

```powershell
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe evaluation/run_synthetic.py
```

And these commands with `frontend` as the working directory:

```powershell
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
npm.cmd ls --all
```

Task 1's private receipt is `var/mission06-offline/task1-validation.json`.
It is a historical stage snapshot: its zero authenticated-call count and absent
key-file state describe that earlier point, before the setup and two GETs above.
No dependencies, models, datasets, containers, browsers or global software were
installed/downloaded. The working NVIDIA PyTorch/CUDA environment was preserved.

## Git and changed files

Task 1 commit **`dff7dcd432fcf6ab041bde717053445b2b82e93f`** was pushed to
private `main`, with matching heads verified. Both jobs in
[Actions run 38591287189](https://github.com/arslanabdulghaffar/ReKit/actions/runs/38591287189)
succeeded. This report accompanies the subsequent Task 2 checkpoint; it does
not embed its own commit SHA. Its post-push head verification and CI outcome
are to be recorded separately in the private
`var/mission06-offline/task2-final-verification.json` receipt and checkpoint
handoff. No final Mission 06 completion SHA or successful Task 2 CI is inferred
from the local test results.

Task 1 added `docs/tokenfactory.md` and `scripts/configure_tokenfactory.ps1`.
It modified `.env.example`, `README.md`,
`backend/src/rekit/inference/adapters/openai_remote.py`,
`backend/src/rekit/inference/models.py`, `backend/src/rekit/inference/service.py`,
`backend/src/rekit/main.py`, `docs/amd-activation.md`,
`frontend/src/inference.test.tsx`, `frontend/src/inference.tsx`,
`frontend/src/types.ts`, `tests/backend/test_inference_api.py`,
`tests/backend/test_inference_models.py` and `tests/backend/test_remote_provider.py`.

The Task 2 checkpoint modifies these seven existing files:
`backend/src/rekit/inference/adapters/https_worker.py`,
`backend/src/rekit/inference/adapters/remote_transport.py`,
`docs/tokenfactory.md`, `docs/architecture.md`, `docs/pitch-deck.md`,
`docs/submission-content.md` and `tests/backend/test_remote_transport.py`.
It adds four files: `evaluation/tokenfactory_discovery.py`,
`scripts/run_tokenfactory.ps1`, `tests/backend/test_tokenfactory_discovery.py`
and this report. These are source/docs/tests; encrypted credentials and private
receipts remain ignored. The PowerPoint generator, private PowerPoint and
submission field counts were not changed; documentation notes distinguish
catalog discovery from pending quota and vision qualification.

## Next gate and remaining work

Obtain explicit approval for the documented alternate usage host or a permitted
sanitized current quota reading. Resolve the catalog/documentation discrepancy
without inventing supported capabilities. Then qualify the single synthetic
image before attempting a joint pair, using a persistent attempt record written
before each network generation and never refunding failed/unknown attempts.

Actual API/browser integration, evidence-linked comparison, final software/local
regressions and the final mission report remain to be completed. Independent
human labels and visual accuracy remain unestablished. Public repository/license
decisions, hosted demo, final video, submission review and confirmed portal
requirements remain separate hackathon gates. No private PowerPoint, video,
application publication or repository visibility was changed in this mission.
