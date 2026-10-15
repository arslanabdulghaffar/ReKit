# AMD TokenFactory qualification

Mission 06, October 15, 2026. This is a shared-service integration, separate from
an owned AMD Developer Cloud allocation. Successful generation requests would
establish TokenFactory inference usage, not a specific GPU, ROCm release or
immutable deployed weights.
Read-only model discovery returned a real catalog. After the user supplied
**Check Usage** values and explicitly authorized the initial synthetic probe,
two deliberate, identical single-image POST attempts returned **HTTP 400**.
The second request collected bounded diagnostics; it was not an automatic retry.
The cause remains inconclusive and API access remains unverified. **Five
authenticated calls have occurred: three GETs and two POSTs, with 2 of 6
generation attempts charged.** The POSTs presented the same approved synthetic
image twice; no ABO image was sent. No AMD visual/schema success, joint-image
qualification, application/browser acceptance or paired comparison is claimed.
Stop before a third replay. See the current
[Mission 06 checkpoint](reports/development-mission-06.md).
Neither original raw error body was retained; exact provider error wording is
unavailable. See the [offline diagnosis](tokenfactory-http400-diagnosis.md) for
the reproduced request and the limits of the retained error categories.

The HTTP 400 continuation instruction requires **new user approval and fresh
quota evidence before any subsequent AMD API call**. The remaining four attempts
are a ceiling, not permission to use them now. Preserve the two original receipts
and their ledger; do not reset, replay, substitute a model or rotate the configured
key merely to resume. The user confirms that AMD support was contacted externally;
the [prepared request](tokenfactory-support-request.md) remains an archived draft,
not a delivery receipt. The owner reports a reply directing them to an inaccessible
Chinese feedback portal, followed by an AMD Login-category account-support form.
Neither supplies an API-contract solution or verifies access. Do not send a
duplicate. After definitive provider clarification, prepare the exact
request change for review; an approved test may make one new synthetic-image
attempt and then stop. The discovery commands below describe prior authorized
operations and do not reopen this gate.

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
complete. The local `CheckCredential` action also passed: it validates protected
local setup without a network call and does not establish account eligibility.

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
host/path or redirect was used. The later POSTs below followed separate review
of operator-reported allowance and an explicit bounded probe authorization.

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

The operator's subsequent Check Usage report showed **1 pt daily allowance,
0 spent, 1 remaining, 20 RPM**, with reset displayed as **01:00 Asia/Shanghai**.
It was received at `2026-10-14T16:43:27Z`; the first admission expired at
`16:58:00Z`, before its interpreted `17:00:00Z` reset. API-verification status
was not shown and remains null, not true. Successful sign-in/key issuance and
the explicit initial-probe authorization were recorded separately.

The first POST at `16:49:19Z` and diagnostic POST at `16:56:19Z` on October 14 UTC
both returned HTTP 400 with the same 142-byte response digest:
`6aad1a77b10692dafe38cabea0adde38986dd61b5bb42de83d8b7e3364860c8b`.
Bounded diagnostics retained `type=invalid_request_error`,
`message_mentions=[model]` and no recognized message flags. These categories
do not identify an exact rejection reason; no unsupported-model, schema or
credential conclusion is justified. The original arbitrary error text was not
copied into tracked documentation.

POST response headers reported `daily_usd_limit=1`, `daily_usd_used=0`,
`daily_usd_remaining=1`, a 20 RPM limit and 19 remaining requests. Their
`daily_reset_unix=1792080000` represents October 15 at 16:00 UTC / October 16 at
00:00 Asia/Shanghai. This conflicts with the operator's reset display. The
provider's USD-labelled counters are retained as such; **no pt-to-USD conversion
or consumption in points is inferred**. Positive headers admitted only the
reviewed identical diagnostic, not general continuation.

Stop now: request provider/hackathon clarification of this exact model's API
eligibility and accepted request contract, and the quota/reset discrepancy.
No third replay, automatic model switch, schema downgrade, guessed route or
silent local fallback is authorized by these receipts. The user has sent the
support email externally and received a portal referral; the later account-support
submission remains unresolved. Do not duplicate either message or request the
key/account identifiers in chat. No definitive contract solution is recorded.

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

Both attempted requests retained strict JSON Schema, `max_tokens=512`,
`reasoning_effort: "none"` and the exact `MiMo-V2.6-Flash` model/endpoint.
The catalog still advertises `structured_outputs=false` and `free=false`;
these unresolved declarations were retained in the receipts. The synthetic
input SHA-256 was
`cf1a8f595ff3986a947e7160cdb76d7493e9748d2d1f5a03b83d0d23343de38b`.
Only after the access/contract blocker is resolved should the mission consider
further bounded qualification under its remaining budget. Keep strict parsing,
rate-limit handling and the human decision boundary unchanged.
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

The tested
[`tokenfactory_qualification.py`](../evaluation/tokenfactory_qualification.py)
now supplies that accounting component, with no CLI or default live transport.
Its fixed ledger filename is `generation-attempts.sqlite3`; initial creation is
explicit and reopening requires intact existing state. A durable reservation
precedes each injected request, all attempts remain charged, and HTTP
401/403/429 halt the ledger even if an unsafe body must be discarded. Admissions
bind existing mission authority, current quota evidence, approved ordered image
hashes and the exact strict MiMo request. Uncertain attempts require explicit
review before continuation; replaying an admission cannot retry it.

The guard is now connected to the direct qualification runner
[`run_tokenfactory_qualification.py`](../evaluation/run_tokenfactory_qualification.py)
through the private PowerShell launcher's `Qualify` and `Diagnose` actions.
It is not application/browser acceptance. The initial exception allowed one
image on ledger attempt 1 with unknown API status, positive operator-reported
points and explicit initial-probe authorization. The diagnostic exception
allowed only attempt 2 after the sole prior terminal HTTP 400, fresh response
headers and matching prior/admitted/outgoing request-byte digests. It cannot
repeat as attempt 3 or relax the request contract.
Post-request offline hardening also binds receipt status/hash/size and timing
to the immutable outcome, and bounds escaped raw-model diagnostics so terminal
receipts remain readable. The actual two receipts were preserved unchanged.

Private `synthetic-first.json`, `synthetic-diagnostic.json` and
`generation-attempts.sqlite3` preserve the two charged attempts. The runner
caches failed results and retains bounded diagnostics without arbitrary error
text or credentials. The caller must keep this one protected ledger; neither
the component nor its evidence types authenticate dashboard claims or predict
request cost. A later success would still require independent schema/domain
validation and would not automatically qualify image understanding.

See [Mission 05](reports/development-mission-05.md) for the accepted baseline and
[AMD activation](amd-activation.md) for the separate owned-cloud route. The final
Mission 06 report will distinguish implemented software, actual service evidence
and any remaining access or image-transfer blockers.
