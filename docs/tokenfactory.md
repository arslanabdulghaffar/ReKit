# AMD TokenFactory qualification

Mission 06, October 15, 2026. This is a shared-service integration, separate from
an owned AMD Developer Cloud allocation. Successful generation requests would
establish TokenFactory inference usage, not a specific GPU, ROCm release or
immutable deployed weights.
Read-only model discovery has returned a real catalog. Quota and image execution
remain unqualified: the supplied usage alias was unusable, and the separately
authorized one-time official quota GET returned HTTP 404. Neither route nor the
catalog returned quota headers. There have been **three authenticated GET
attempts, zero generation POSTs and zero transmitted images**. The live MiMo
catalog advertises `structured_outputs: false` and
`free: false` despite the documentation's strict-schema description. The free
flag describes allowance accounting; it alone does not establish billable use
or free account entitlement. The operator checked the dashboard: allowance and
reset time were not displayed or confirmed, sign-in and team-key issuance
succeeded, and API-verification status was not explicit. These are operator
reports, not measured quota. The **Check Usage** panel still needs inspection;
no browser is connected to the agent's session. Do not infer missing values or
make generation requests until usable quota is verified. See the current
[Mission 06 checkpoint](reports/development-mission-06.md).

## Mandatory credential and image-transfer gate

The mission states that a screenshot may have exposed part of the previous key:
**rotate it before authenticated testing**. In the TokenFactory dashboard,
revoke the old key, create its replacement and keep it out of chat, screenshots,
shell command arguments, Git and reports. Do not paste it into a command.

From a private PowerShell terminal, outside recording/transcription, run:

```powershell
Set-Location A:\hackathon\ReKit
powershell.exe -NoProfile -File scripts/configure_tokenfactory.ps1
```

Enter the replacement only at the masked local prompt. The helper sends nothing
to AMD and stores a Windows-user-bound DPAPI encrypted SecureString at
`.secrets/tokenfactory/api-key.clixml`, with inherited access restricted to the
current user, SYSTEM and Administrators. It checks real directory ancestors,
requires Git exclusion and refuses to overwrite an existing credential. Existing
operator credentials are separate and are not changed. Do not commit even the
encrypted credential or assume encryption authorizes account sharing.

If a prior configuration already exists, stop and arrange its deliberate
replacement privately; do not print or upload its contents. The helper does not
revoke keys in the provider dashboard and does not prove rotation occurred.

Before any authenticated request, the user must separately confirm:

1. The potentially exposed key was revoked and replaced.
2. Read-only account/quota/model discovery and at most **six generation attempts**
   may use the free shared quota. Failed or uncertain attempts count; no automatic
   retry, paid purchase, dedicated instance or billable infrastructure is allowed.
3. The exact permitted image scope: non-sensitive synthetic illustrations, and
   optionally the existing public ABO front/back fan views from listing
   `B07XGQ9QJF` (`71rr7OjqWqL` and `812Xgtrv0EL`). Catalog imagery is simulated
   intake, not actual returned stock. Customer-private or personal images are
   excluded. The source license remains CC BY 4.0 with attribution.

Configuration alone is not consent. Keep the gate closed while any required
confirmation is missing. Never ask the user to disclose the key in Codex chat.
For this mission, all three confirmations and local replacement-key setup are
complete. They do not remove the remaining quota-evidence gate.

## Cached, read-only discovery

After all three confirmations, the private Windows launcher can perform the
authorized discovery operation:

```powershell
powershell.exe -NoProfile -NonInteractive -File scripts/run_tokenfactory.ps1 -Action Discover -Authorized
```

`-Authorized` records the caller's intent; it does not replace the user's consent.
The launcher validates the existing protected credential directory and file
permissions, decrypts the key only into its Python child environment, and never
changes the parent environment. The discovery process removes that variable
before starting the HTTPS worker, whose credential arrives only through stdin.
No frontend or browser process is started. The launcher does not repair unsafe
permissions or request elevated privileges. It drains child stdout/stderr without
logging their contents, reports only a controlled action/exit/receipt summary,
and attempts to terminate its owned process tree if waiting is interrupted.

The operation makes at most two GET attempts: the mission's same-host usage
alias, then the model catalog. It never generates images/text or retries. An
authentication rejection, unavailable account, exhausted quota, zero remaining
minute capacity or rate limit stops it. A usage-alias 404 may proceed to catalog
discovery, where actual positive quota response headers can establish remaining
capacity. Documentation examples are never used as account measurements.

Sanitized receipts live at
`.secrets/tokenfactory/qualification/discovery.json`, under the restricted,
Git-ignored credential directory. Only selected model capabilities, numeric
usage/quota values, timestamps, HTTP status, duration and response hashes are
retained. Raw account profiles, recent-call lists, arbitrary error bodies and
request headers are discarded. An echoed credential rejects the response.
The request is recorded before network activity; interrupted and failed
receipts are cached too. Re-running reads the receipt without another request.
Refreshing a failed/stale discovery requires a deliberate reviewed operation;
do not delete its audit record to trigger an implicit retry.

If the usage alias returns HTTP 200 with an unusable response, a separately
reviewed `-Action Catalog -Authorized` operation can query the already allowed
model URL once and preserve a linked `catalog-discovery.json` receipt. This
does not repeat the usage request or contact another host. It is unavailable
after rejected authentication, rate limiting, unavailable account status or a
detected credential echo. Its own result is also cached without retries.

The user subsequently authorized one GET to the exact URL in the
[official usage documentation](https://amd-aim.github.io/radeon-cloud-docs/api/usage/):
`https://radeon-global.anruicloud.com/api/profile/model-usage?include_recent=true`.
The reviewed operation was:

```powershell
powershell.exe -NoProfile -NonInteractive -File scripts/run_tokenfactory.ps1 -Action Quota -Authorized
```

It returned HTTP 404 (`request_rejected`, `application/json`, 22 response bytes,
0.688 seconds), without quota headers or Retry-After. Its sanitized receipt is
`.secrets/tokenfactory/qualification/quota-discovery.json`. This was the third
authenticated GET attempt overall. The single authorized attempt is consumed;
the result is cached and must not be deleted to trigger a retry. No guessed
host/path, redirect or further authenticated request followed this failure.

The transport retains only parsed, bounded Retry-After seconds and documented
numeric quota headers. Missing or invalid values remain unknown. No 429 is
automatically retried. Catalog image/schema flags describe advertised support;
single-image execution, joint-image execution and ReKit's exact schema remain
unqualified until their own successful live tests.

## Exact endpoint and provenance boundary

The user supplied `https://developer.amd.com.cn/radeon/api/v1` as the official
base. The narrow profile uses only its exact HTTPS chat endpoint:

```text
https://developer.amd.com.cn/radeon/api/v1/chat/completions
```

It must also be present in a trusted server allowlist. Similar hosts, other
ports, arbitrary base paths, URL credentials, queries, redirects and proxy
inheritance are not alternative destinations. Request bodies cannot select the
provider or destination. Generic `/v1` serving keeps its existing restrictions.

Explicit `amd-tokenfactory` configuration identifies the shared provider.
Model and processor revisions are null and labelled `shared_service_unattested`;
they are not invented hashes. Local CUDA and generic remote deployments retain
their immutable revision requirements. The service's returned model ID must
match the configured model; it cannot attest which weights actually ran.

MiMo-V2.6-Flash is the first candidate named in the mission. Its exact callable
ID, live availability, image count and schema support must be checked against
the real catalog and bounded image requests. Model advertisements are not
completed qualification. Preserve the existing domain parser, image hashes,
input order, unverified evidence and human decision boundary.

## Staged acceptance

The `/models` response is cached, but usable quota remains unknown after both
usage routes failed. The official host was explicitly authorized and attempted;
host authorization is no longer the missing step. Obtain only a sanitized
current Check Usage reading of remaining free allowance, reset time and account
API-verification status. The operator's initial dashboard check did not expose
these values. Successful sign-in and a redeemed/issued team key do not establish
allowance or API verification. Stop on rejected access or incomplete verification.
Do not infer allowance from documentation examples, an HTTP 200 catalog or the
absence of quota headers. Save no keys, account IDs or sensitive headers.

Public documentation inspected on October 15 did not establish the Check Usage
UI's input requirements or a replacement quota route. The official usage API
documents session or API-key authentication, but this is not proof of the UI's
behavior. Inspect that panel in the existing signed-in session and retain only
quota/reset/status values or sanitized error text. If it remains unavailable,
ask the provider or hackathon support to confirm the correct regional usage
route and the team's shared-model API eligibility. Do not send a credential or
infer a route from the public site's `/radeon` routing prefix. No support message
has been sent by ReKit.

The [catalog reference](https://amd-aim.github.io/radeon-cloud-docs/api/models/)
states that the catalog is the same for every key, not account-scoped. Its
`free` flag describes zero-cost accounting against the daily allowance.
The [shared-service guide](https://amd-aim.github.io/radeon-cloud-docs/guides/model-apis/)
describes shared endpoints as free and distinguishes them from credit-consuming
dedicated instances. Therefore `free=false` alone is not a finding of paid
billing; it also cannot establish this account's available allowance.

The [MiMo reference](https://amd-aim.github.io/radeon-cloud-docs/models/mimo-v2-6-flash/)
documents the exact model ID `MiMo-V2.6-Flash`, base64 image data URLs, strict
JSON Schema and `reasoning_effort: "none"`. These are documented capabilities;
ReKit's exact schema and two-image behavior still require live qualification.
The [service terms](https://amd-aim.github.io/radeon-cloud-docs/api/terms/) permit
trials/demos/hackathons, exclude production and confidential inputs, and state
that request/output content is logged. Keep this qualification private/local;
it is not permission to expose shared API access to third parties. Terms describe
AMD accelerators at the service level, not per-request hardware attestation.
They also describe shared-service quotas as capacity controls, not currency.

Once quota is established, a bounded qualification attempt may test the
documented MiMo capability while retaining the contradictory catalog flags as
unresolved evidence. Admission to that experiment is not capability confirmation.
Start with one small synthetic image, review its actual result, then attempt
two images only when justified. Keep strict JSON Schema, independent validation
and `reasoning_effort: "none"`; do not automatically downgrade to `json_object`,
switch models or increase generation limits after failure. Record actual output,
model ID, ordered
hashes, timing, bounded provider usage and quota. Respect rate limiting and
Retry-After; never automatically retry or fall back to NVIDIA.
A schema-conforming response establishes conformance for that response, not
general server-side schema enforcement or correct understanding of the images.

An approved product-image request through the real ReKit browser/API may count
once toward both integration gates. Keep recovery optimization a separate
synthetic scenario. Reuse saved AMD results for comparison; do not repeat calls
just to populate a table. Independent visual accuracy and hardware throughput
are not established by these small, different-model samples.

The current local demo runners explicitly construct the NVIDIA provider. They
must not be described as AMD tests. A remote runner must isolate the key to its
backend process; frontend/browser processes and fixture manifests must never
receive it. A persistent private attempt ledger must enforce the six-generation
ceiling across separate qualification stages, including failed attempts.

See [Mission 05](reports/development-mission-05.md) for the accepted baseline and
[AMD activation](amd-activation.md) for the separate owned-cloud route. The final
Mission 06 report will distinguish implemented software, actual service evidence
and any remaining access or image-transfer blockers.
