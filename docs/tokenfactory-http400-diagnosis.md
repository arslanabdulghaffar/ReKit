# TokenFactory HTTP 400: offline diagnosis

October 15, 2026 (Asia/Seoul), starting at commit
`e13e65dbe38377d460e43bdea74169a57d03ac6c`. This audit made **zero network
requests**, read no credential, and executed no model. The two original attempts
remain charged. It does not resolve AMD access or qualify visual inference.

## Evidence and reconstruction

The audit opened the existing ledger with SQLite `mode=ro` and `query_only=ON`.
It used the existing provider and original synthetic-image generator with a fake
credential and an injected capture-only transport. A Python audit hook rejected
network-capable socket operations and child execution. No qualification command
was invoked.

The reconstructed **19,251-byte JSON body** has SHA-256
`ed360c24ecc2e25d8a6183625d416b78b2b4daf97e48326cec56dfa5f60160fb`, exactly
matching both immutable attempt rows. All 22 comparisons passed, including
configuration, admissions, source/prompt/schema and response hashes. This binds
the reconstruction to the previously recorded request bytes; it does not prove
that the service accepts their contract.

| Field | Verified value |
| --- | --- |
| Destination | `POST https://developer.amd.com.cn/radeon/api/v1/chat/completions` |
| Model | `MiMo-V2.6-Flash` |
| Generation settings | `stream=false`, `temperature=0`, `max_tokens=512`, `reasoning_effort="none"` |
| Messages | One user message; `image_url` first, inspection text second |
| Image encoding | `data:image/png;base64,`; 14,540 base64 characters decode to the original 10,904-byte PNG, 768 x 512 pixels |
| Image SHA-256 | `cf1a8f595ff3986a947e7160cdb76d7493e9748d2d1f5a03b83d0d23343de38b` |
| Output format | `json_schema`, name `rekit_inspection`, `strict=true` |
| Schema | `rekit-inspection-schema-v2`; canonical schema is 2,065 bytes |
| Schema SHA-256 | `31f7eb7e775cc2d59d4db0d50316773c3adcaf96a512704679fa3232fbe28e92` |
| Identity catalog | None; identity candidates are disallowed |

The two POST receipts, saved catalog receipt and SQLite file all retained their
before/after file hashes. The ledger still contains two HTTP 400 outcomes.
Its file digest is
`1e3e4c02ce1fed59a0b9751dfadd9445283bbd2153922eb2e7dd4f7a9a705577`.
No receipt, ledger, schema, domain validator, prompt, provider setting or local
NVIDIA implementation was changed.

Private audit artifacts are
`var/mission06-offline/http400-diagnosis/audit_request.py` and `audit.json`.
The latter has SHA-256
`49114dfd95b01e93761ed344e4ebd0739d289c5f6cf120cc2fe8487c96d8123c`.
Its command was:

```powershell
.venv\Scripts\python.exe -B -W error var/mission06-offline/http400-diagnosis/audit_request.py
```

That audit writes a new exclusive artifact; do not delete existing evidence to
rerun it. The script and detailed local metadata remain ignored by Git.

## What the error evidence can establish

Both responses were HTTP 400, JSON, 142 bytes, with the same response digest.
The second receipt retained `type=invalid_request_error`,
`message_mentions=[model]`, and no recognized message flags. The mention is a
bounded substring classification, not the exact message or an identified
parameter. An unrecorded code or parameter cannot be inferred to have been absent.

**Neither original raw error body was retained. Its exact wording is unavailable.**
Response size and SHA-256 cannot reconstruct it. The client's `unsupported`
reason is a broad mapping for several rejection statuses, not proof that a
particular model or schema keyword is unsupported. No more precise provider
classification can be established from the saved evidence.

## Schema and documented contract comparison

This comparison uses the published-documentation findings already recorded in
the [Mission 06 report](reports/development-mission-06.md) and the saved live
catalog. No documentation was fetched during this offline diagnosis. The prior
review links the [MiMo model reference](https://amd-aim.github.io/radeon-cloud-docs/models/mimo-v2-6-flash/)
and [chat contract](https://amd-aim.github.io/radeon-cloud-docs/api/chat-completions/).
The retained notes describe image data URLs, strict JSON Schema and reasoning
`none`; they do not preserve a keyword-level compatibility matrix. These are
advertisements, not empirical schema acceptance or a newly fetched contract.

| Feature | Exact request finding | Compatibility conclusion from retained evidence |
| --- | --- | --- |
| Strict format | `response_format.json_schema.strict=true` | Prior MiMo documentation review describes support; saved catalog says `structured_outputs=false`. Unresolved. |
| Nested `anyOf` | One occurrence at `#/properties/candidates/items/anyOf`, with two object branches; none at the root | No retained keyword-level provider guarantee or explicit rejection. |
| Empty candidates | `#/properties/candidates` has both `minItems=0` and `maxItems=0`; its item schema is still present | The empty-array rule is deliberate. A provider compiler might still inspect the unused item schema. That is a hypothesis, not this response's established cause. |
| Null alternatives | Branch 0 requires null `revision` and `revision_marking`; branch 1 requires both as strings | No literal `type: ["string", "null"]` union was sent. Nullability is expressed through object alternatives; remote support is unknown. |
| Required properties | All five object schemas require every declared property | No missing-required-property inconsistency was found locally; provider restrictions remain unqualified. |
| Unknown properties | All five objects use `additionalProperties=false` | Closed objects are intentional and stay enforced by independent validation. |
| Other constraints | Eight bounded arrays, integer/string enums, ten bounded string schemas (ten `minLength` and ten `maxLength` constraints) | No retained guarantee for these individual keywords. No `$ref`, `$schema`, `oneOf`, `allOf` or `uniqueItems` was sent. |

The catalog's exact MiMo ID advertises text/image input and `json_output=true`,
but `structured_outputs=false`. All 12 saved entries have the latter flag false.
That may reflect service capability or inaccurate/coarse metadata; the evidence
does not distinguish them. JSON-object support is not strict-schema support.
`free=false` is a separate daily-capacity accounting flag, not proof of paid
billing or an explanation of the rejection.

The required/null/empty-array constraints are internally consistent: candidates
must be empty, so no candidate branch is instantiated in an accepted output.
This observation is not a provider compatibility certificate. No remote-specific
schema reduction has been implemented, and the original local schema and domain
validation must remain intact.

## Ranked diagnostic priorities

The order below is an investigation priority, **not calibrated likelihood**.

| Rank | Hypothesis | Evidence supporting investigation | What remains unknown |
| --- | --- | --- | --- |
| 1 | Model routing, callable alias or account/model access | The preserved error classification mentions `model`; a global catalog is not account eligibility evidence. | The precise model-related complaint, enabled alias, route and account access are unknown. The exact ID matches the saved catalog. |
| 2 | Strict-output capability on this model/route | Published support and the saved `structured_outputs=false` flag conflict. | Neither proves which path the server selected or why it rejected this request. |
| 3 | A schema compiler rejects an individual constraint or combination | Nested `anyOf`, paired null branches and an empty array with a nontrivial item schema need an explicit supported-subset statement. | No keyword is identified in the retained diagnostic. Changing a keyword now would be speculative. |
| 4 | Other multimodal or generation-parameter restrictions | Image data URLs and the conservative settings were documented, but live acceptance has not succeeded. | Route-specific image limits, content-order rules or parameter combinations may differ. |
| 5 | Account/quota handling or malformed input | Account verification is unknown; a gateway could use broad 400 errors. | Positive response capacity and absence of 401/403/429 give no direct exhaustion/authentication finding. Exact JSON/base64 reconstruction and original-byte integrity make a local encoding mistake less supported. |

## Reviewable continuation, not an executable change

The user now confirms external contact with AMD support; do not resend the
[retained support draft](tokenfactory-support-request.md). Record the provider's
answer, source/date, callable model/endpoint and supported image/schema subset.
Prepare a concrete payload diff with the current request and schema hashes.
State whether it changes only remote serialization or any accepted output set.
Do not weaken independent domain validation or the original local schema.

If the provider only supports a weaker format, report the remaining contract gap
for review; do not automatically change to JSON-object output or another model.
No speculative replacement payload is approved by this document.

A later call requires fresh quota evidence, the user's approval of the concrete
change, one approved synthetic image, and **exactly one new bounded attempt** in
the existing six-attempt ledger. Start from two consumed attempts and record the
third before transport; timeout/error also remains charged. Capture sanitized
response, latency, model identity, input/schema hashes and post-call quota, then
stop for review. Only a successful independently validated response can precede
AMD application integration. Mission 06 remains incomplete; Mission 07 is not
started.
