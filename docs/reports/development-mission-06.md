# ReKit Development Mission 06 checkpoint report

October 15, 2026, Asia/Seoul. **Partial checkpoint; not a completion report.**
Repository: `A:\hackathon\ReKit`, private GitHub `arslanabdulghaffar/ReKit`.
Missions 01–05 remain accepted. The starting commit was
`c88e7f6271e75df776b593af4364b564e9989089`.

Task 1 and the first Task 2 checkpoint are committed, pushed and CI-verified.
Task 2 has made **three authenticated discovery GET attempts** and remains
blocked on usable quota evidence and conflicting
capability declarations. **Generation attempts: 0 of the authorized maximum 6.**
No image has been transmitted to AMD, and no AMD visual inference or browser
acceptance has run during this mission. One local NVIDIA API regression has now
passed. Tasks 3–5 and the AMD-dependent parts of Task 6 remain pending.

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
names a different host from the original approved API host. The user separately
authorized **one GET** to this exact destination:
`https://radeon-global.anruicloud.com/api/profile/model-usage?include_recent=true`.
That authorized attempt returned HTTP 404 and has been consumed. No retry,
redirect or alternate route was attempted. The operator subsequently reported
that allowance and reset time were not displayed or confirmed, sign-in and team
key redemption/issuance succeeded, and API-verification status was not explicit.
These are operator-reported facts, not quota measurements. The user explicitly
requires quota verification before generation and requested inspection of
**Check Usage**. No browser is connected to this agent session, so the signed-in
panel cannot be inspected directly. Only sanitized panel values or error text
have been requested; no key, account IDs or screenshot.
See [TokenFactory setup and gates](../tokenfactory.md).

## Stage status

| Task | Current evidence |
| --- | --- |
| 1. Capability and code audit | Complete. Added the exact TokenFactory endpoint profile, narrowly scoped unattested revisions, honest UI provenance, credential setup and offline regression coverage. |
| 2. Safe discovery | First checkpoint committed and CI-verified; exact official-quota follow-up implemented and attempted once. Three actual GET attempts; valid catalog obtained, usable quota unavailable after official-route HTTP 404. The initial operator dashboard check exposed no quota/reset or explicit API verification; Check Usage inspection remains pending. |
| 3. AMD visual qualification | Pending. No generation, image upload to the service or schema-execution result. The persistent six-attempt guard passes offline tests; verified quota and explicit wiring into the qualification caller must precede generation. |
| 4. AMD application integration | Pending live acceptance. Existing managed evidence, roles, strict parsing, human decisions and deterministic inventory boundaries remain. |
| 5. AMD/NVIDIA comparison | Pending AMD evidence. One new local NVIDIA API regression is recorded below; it is not a paired comparison. No recognition-accuracy or hardware-throughput comparison is claimed. |
| 6. Final demonstration and reporting | Partial offline validation, including a local NVIDIA API regression. No AMD browser demonstration or Mission 06 completion receipt yet. |

## Actual authenticated discovery

The first two requests used the exact host `developer.amd.com.cn`; the third
used only the separately authorized official quota URL. All used verified HTTPS
and the rotated credential. These were metadata requests, not model generations.
Failed or interrupted discovery receipts are cached; repeating the command does
not silently retry. The separate catalog request followed explicit review of
the unusable usage response and retained the prior receipt's digest.

| Request | Measured result |
| --- | --- |
| `GET https://developer.amd.com.cn/radeon/api/v1/usage?include_recent=true` | HTTP 200, **invalid_response**, 0.531 seconds. No usable quota or quota headers. Raw response was not stored. HTTP success did not establish a usable usage contract. |
| `GET https://developer.amd.com.cn/radeon/api/v1/models` | HTTP 200, valid sanitized catalog of **12 models**, 0.406 seconds, 11,572 response bytes. No quota headers. |
| `GET https://radeon-global.anruicloud.com/api/profile/model-usage?include_recent=true` | HTTP 404, **request_rejected**, 0.688 seconds, `application/json`, 22 response bytes. No quota headers or Retry-After. Exactly one authorized attempt; no usable quota and no retry. |

Catalog response SHA-256:
`f8cb716534d7b1c42c43b2718d594405af840291f38706c5f19c5482099964a0`.
Sanitized private receipts are `discovery.json`, `catalog-discovery.json` and
`quota-discovery.json`
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
The [shared Model API terms](https://amd-aim.github.io/radeon-cloud-docs/api/terms/)
describe a free development service whose quotas are capacity controls, not
currency; the [Model APIs guide](https://amd-aim.github.io/radeon-cloud-docs/guides/model-apis/)
distinguishes it from credit-consuming dedicated endpoints. No credits were
purchased and no billable infrastructure was created. Actual usable allowance
remains unknown. A future bounded strict-schema qualification would test the
documented capability without treating the conflicting catalog flag as resolved.

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

The offline-only qualification guard in
[`evaluation/tokenfactory_qualification.py`](../../evaluation/tokenfactory_qualification.py)
adds an explicit one-time SQLite ledger initialization and existing-file-only
reopening. It refuses missing/corrupt state instead of silently starting a new
budget. An immutable admission binds existing mission authorization, verified
quota evidence, catalog digest, exact endpoint/model, ordered image hashes,
prompt and current schema. Quota evidence expires within fifteen minutes and
before its actual reset; a positive allowance is not a request-cost estimate.

An immediate SQLite transaction durably charges an attempt before the injected
transport runs, then releases the transaction before network work. Six is the
fixed ceiling across admissions/restarts using that one ledger. Failed and
uncertain attempts remain charged; an uncertain attempt blocks continuation
until explicit trusted review. Known 401/403/429 statuses halt that ledger even
when the response body is discarded as unsafe. Admission replay never retries.
Receipts contain bounded metadata and digests, not raw prompts, images, outputs
or credentials. Missing safeguards and unsuccessful recording fail closed.

This module has **no executable CLI, default live transport or application
wiring**. No real mission generation ledger/admission has been initialized.
The private caller must preserve one protected ledger location, substantiate
quota/authorization and inject the guarded transport into every qualification
request. It cannot authenticate a caller or verify dashboard evidence itself.
It does not yet replace the needed sanitized generation-output/usage recorder,
nor does an HTTP receipt establish valid schema or correct visual reasoning.

## Validation recorded so far

All software tests below ran without TokenFactory access; controlled responses
are not AMD vision execution. The separately identified NVIDIA regression used
the existing local model and GPU with model downloads disabled. GitHub Actions
remains CPU-only.

| Check | Result |
| --- | --- |
| Task 1 full backend, warnings as errors | 1,185 passed in 41.42 seconds. |
| Task 1 focused backend | 406 passed in 13.57 seconds. |
| Task 1 full frontend | 61 passed in 29.10 seconds. |
| Task 1 focused inference UI | 32 passed in 6.53 seconds. |
| Task 1 TypeScript, build, `pip check`, `npm ls --all`, local Markdown links | Passed. |
| Task 1 synthetic recovery | OPTIMAL; 2 kits, 4 consumed physical components, 17,500 cents modeled value. This is a synthetic scenario estimate, not realized savings. |
| First Task 2 checkpoint full backend | 1,306 passed in 38.86 seconds, including 33 discovery tests. |
| First checkpoint transport/provider/inference API checks | 380 passed in 11.18 seconds. |
| First checkpoint wrapper checks | 67 offline assertions; 27 files and 5 ACLs checked, including controlled output-drain failure. |
| Official-quota follow-up full backend, warnings as errors | 1,342 passed in 38.83 seconds. |
| Latest official-quota discovery tests | 48 passed in 0.55 seconds. |
| Latest transport tests | 173 passed in 1.82 seconds. |
| Latest provider/inference API tests | 228 passed in 10.48 seconds. |
| Latest isolated wrapper checks | 75 offline assertions; 28 files and 6 ACLs checked. No real key used in wrapper checks; dynamic cancellation not exercised. |
| Local NVIDIA authenticated API regression | Passed; one actual local GPU request, exact retry reused the existing run, evidence stayed unverified and inventory stayed held. |
| Qualification guard tests | 55 passed in 1.49 seconds; controlled transports only, including independent SQLite connections, simulated interrupted reservations/reopening, strict payload binding and unsafe-body halt preservation. |
| Latest full backend with qualification guard, warnings as errors | 1,397 passed in 40.72 seconds. |

Task 2 validation commands, from the repository root. The combined focused
command was used for the first checkpoint; the two separate focused commands
were used for the official-quota follow-up:

```powershell
.venv\Scripts\python.exe -W error -m pytest -q
.venv\Scripts\python.exe -B -W error -m pytest tests/backend/test_remote_transport.py tests/backend/test_remote_provider.py tests/backend/test_inference_api.py -q
.venv\Scripts\python.exe -B -W error -m pytest tests/backend/test_remote_transport.py -q
.venv\Scripts\python.exe -B -W error -m pytest tests/backend/test_remote_provider.py tests/backend/test_inference_api.py -q
.venv\Scripts\python.exe -W error -m pytest -q tests/backend/test_tokenfactory_discovery.py
.venv\Scripts\python.exe -B -W error var/mission06-offline/check_tokenfactory_wrapper.py
.venv\Scripts\python.exe -B -W error -m pytest tests/backend/test_tokenfactory_qualification.py -q --tb=short
```

The isolated wrapper harness and receipts are private local validation artifacts,
not requirements for running the tracked test suite. The latest 75-assertion
receipt was preserved without overwrite at
`var/mission06-offline/wrapper-quota-check.json`, with SHA-256
`2d36d216ac919efb9ef4f25ab788e601e1d25f693e4ab5f56f7e5a040757e23b`;
the harness's generic `wrapper-check.json` filename is overwritten between runs.

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
key-file state describe that earlier point, before the setup and three GETs above.
No local dependencies, models, datasets, containers, browsers or global software
were installed/downloaded. CI installed the existing locked CPU dependencies
in its isolated runners. The working NVIDIA PyTorch/CUDA environment was preserved.

### Local NVIDIA regression during the quota block

The existing runner was executed once with a fresh ignored destination:

```powershell
.venv\Scripts\python.exe -B evaluation/run_api_inference_acceptance.py --device 1 --output var/mission06-offline/local-api-acceptance.json
```

Its owned child had `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`, with ReKit and
credential-named environment variables stripped. No credential values were
logged. All ten pinned model files were verified locally before execution;
no download, installation or CUDA change occurred. This runner explicitly
constructs `LocalVisionProvider`; it does not select the AMD provider.

Model: `Qwen/Qwen3-VL-2B-Instruct`, revision
`89644892e4d85e24eaac8bacfd4f463576704203`, `cuda:1`, RTX 4080 SUPER,
PyTorch `2.9.0+cu128`. Actual measurements: 3.967 seconds loading, 24.746 seconds
inference, 43.603 seconds request duration, 911 input / 201 output tokens,
one visual-encoder forward call and 4,563,994,624 bytes peak allocated GPU memory.
These are one-run local measurements, not a hardware comparison.

The 10,904-byte synthetic PNG has SHA-256
`cf1a8f595ff3986a947e7160cdb76d7493e9748d2d1f5a03b83d0d23343de38b`.
The receipt `var/mission06-offline/local-api-acceptance.json` has SHA-256
`c70be9565eb080959071bc90f6ececd1126036ac38d8f7f534b6ff7b03484328`.
The response passed structure checks but proposed unsupported `body` / revision
`A` with marking `A` from a shapes illustration. The automated acceptance
harness recorded an operator-role rejection of that known unsupported proposal;
this is not independent human labeling or measured recognition accuracy.
The immutable run remained preserved, identity unverified, inventory held and
compatibility unapproved. An exact request retry reused the single run; no
reservation or kit was produced. Temporary application state was removed.

## Git and changed files

Task 1 commit **`dff7dcd432fcf6ab041bde717053445b2b82e93f`** was pushed to
private `main`, with matching heads verified. Both jobs in
[Actions run 38591287189](https://github.com/arslanabdulghaffar/ReKit/actions/runs/38591287189)
succeeded.

The first Task 2 checkpoint, **`248c5056a938e410883f8719e831a00bef7d7007`**,
was pushed with matching private heads verified. Both jobs in
[Actions run 38595333838](https://github.com/arslanabdulghaffar/ReKit/actions/runs/38595333838)
succeeded. Its private receipt is
`var/mission06-offline/task2-final-verification.json`.
The official-quota follow-up, **`3170a7d54258b01241b9f68494904490a8adf405`**,
was pushed with matching local, tracking and remote heads and private visibility
verified. Both jobs in
[Actions run 38597834070](https://github.com/arslanabdulghaffar/ReKit/actions/runs/38597834070)
succeeded. Its separate checkpoint receipt is
`var/mission06-offline/quota-final-verification.json`.
This report also records subsequent local-only regression work; no final
Mission 06 completion is inferred from those checks.

Task 1 added `docs/tokenfactory.md` and `scripts/configure_tokenfactory.ps1`.
It modified `.env.example`, `README.md`,
`backend/src/rekit/inference/adapters/openai_remote.py`,
`backend/src/rekit/inference/models.py`, `backend/src/rekit/inference/service.py`,
`backend/src/rekit/main.py`, `docs/amd-activation.md`,
`frontend/src/inference.test.tsx`, `frontend/src/inference.tsx`,
`frontend/src/types.ts`, `tests/backend/test_inference_api.py`,
`tests/backend/test_inference_models.py` and `tests/backend/test_remote_provider.py`.

The first Task 2 checkpoint modified these seven existing files:
`backend/src/rekit/inference/adapters/https_worker.py`,
`backend/src/rekit/inference/adapters/remote_transport.py`,
`docs/tokenfactory.md`, `docs/architecture.md`, `docs/pitch-deck.md`,
`docs/submission-content.md` and `tests/backend/test_remote_transport.py`.
It added four files: `evaluation/tokenfactory_discovery.py`,
`scripts/run_tokenfactory.ps1`, `tests/backend/test_tokenfactory_discovery.py`
and this report. These are source/docs/tests; encrypted credentials and private
receipts remain ignored. The PowerPoint generator, private PowerPoint and
submission field counts were not changed; documentation notes distinguish
catalog discovery from pending quota and vision qualification.

The official-quota follow-up changes eight existing files:
`backend/src/rekit/inference/adapters/https_worker.py`,
`backend/src/rekit/inference/adapters/remote_transport.py`,
`tests/backend/test_remote_transport.py`, `scripts/run_tokenfactory.ps1`,
`evaluation/tokenfactory_discovery.py`,
`tests/backend/test_tokenfactory_discovery.py`, `docs/tokenfactory.md` and
`docs/reports/development-mission-06.md`. No credential or private receipt is
part of that inventory.

The subsequent offline continuation adds
`evaluation/tokenfactory_qualification.py` and
`tests/backend/test_tokenfactory_qualification.py`, and updates this report and
`docs/tokenfactory.md`. It adds no dependency or operational inventory schema.
Its post-push heads/CI verification will be retained separately in
`var/mission06-offline/offline-final-verification.json` and the handoff.

## Next gate and remaining work

Inspect Check Usage for remaining free allowance, reset time and account
API-verification status; the operator's initial dashboard check did not expose
these values. Browser inventory was empty and browser selection returned
"No browser is available", so direct signed-in inspection is blocked in this
session. Public official documentation did not establish this panel's input
requirements or a replacement quota route; public path-prefix behavior alone
does not justify probing an inferred route. The separately authorized
official-quota GET has already failed; no further authenticated request or
alternate route is authorized by repeating that one-attempt permission.
If Check Usage also supplies no usable evidence, the safest next step is to ask
the provider/hackathon support for the correct regional usage route and team API
eligibility, without including a key. No support message has been sent.

Only after usable quota is established, admit a bounded strict-schema experiment
that records the catalog/documentation discrepancy without inventing support.
Qualify one synthetic image before a joint pair, using a persistent attempt
record written before each generation and never refunding failed/unknown
attempts. Do not automatically downgrade the schema, switch models or retry.

Actual API/browser integration, evidence-linked comparison, final software/local
acceptance checks and the final mission report remain to be completed; the local
NVIDIA regression above is already complete. Independent
human labels and visual accuracy remain unestablished. Public repository/license
decisions, hosted demo, final video, submission review and confirmed portal
requirements remain separate hackathon gates. No private PowerPoint, video,
application publication or repository visibility was changed in this mission.
