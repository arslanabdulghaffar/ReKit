# AMD TokenFactory qualification

Mission 06, October 15, 2026. This is a shared-service integration, separate from
an owned AMD Developer Cloud allocation. Successful service requests will establish
TokenFactory usage, not a specific GPU, ROCm release or immutable deployed weights.
Read-only model discovery has returned a real catalog. Quota and image execution
remain unqualified: the supplied usage alias was unusable, no quota headers were
returned, and the live MiMo catalog advertises `structured_outputs: false` and
`free: false` despite the documentation's strict-schema description. The free
flag describes allowance accounting; it alone does not establish billable use
or free account entitlement. No generation has been attempted. See the current
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

After authorization, cache sanitized `/models` discovery and establish actual
quota before generation. The mission supplies `/usage?include_recent=true`, but
the current [official usage documentation](https://amd-aim.github.io/radeon-cloud-docs/api/usage/)
instead names `https://radeon-global.anruicloud.com/api/profile/model-usage?include_recent=true`.
The supplied alias is unverified. Do not silently forward credentials to this
different host, follow a redirect or guess account limits. Confirm the route and
authorization, or obtain a sanitized current dashboard quota reading. Stop on
rejected access or incomplete verification. Save no keys or sensitive headers.

The [MiMo reference](https://amd-aim.github.io/radeon-cloud-docs/models/mimo-v2-6-flash/)
documents the exact model ID `MiMo-V2.6-Flash`, base64 image data URLs, strict
JSON Schema and `reasoning_effort: "none"`. These are documented capabilities;
ReKit's exact schema and two-image behavior still require live qualification.
The [service terms](https://amd-aim.github.io/radeon-cloud-docs/api/terms/) permit
trials/demos/hackathons, exclude production and confidential inputs, and state
that request/output content is logged. Keep this qualification private/local;
it is not permission to expose shared API access to third parties. Terms describe
AMD accelerators at the service level, not per-request hardware attestation.

Start with one small synthetic image, then two images only when supported. Use
strict JSON Schema and MiMo's documented conservative reasoning configuration
once its model contract is verified. Record actual output, model ID, ordered
hashes, timing, bounded provider usage and quota. Respect rate limiting and
Retry-After; never automatically retry or fall back to NVIDIA.

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
