# TokenFactory support request — retained preparation draft

**Current status, October 15:** the user confirms that an AMD support email was
sent externally and its reply is being monitored. Do not send a duplicate.
The exact sent text, recipient, timestamp and delivery status were not inspected;
the text below is the original preparation draft, not a sent-message receipt.
The assistant did not send it. No provider reply is recorded yet.

This sanitized draft requests clarification only. It does not
authorize another API request or change ReKit's provider, schema, or safety
boundaries. No credentials, account/team identifiers, private images, local
configuration files, or raw account responses are included.

**Subject:** Hackathon shared API: two HTTP 400 responses for
`MiMo-V2.6-Flash`; model eligibility, image/schema contract and usage questions

Hello AMD TokenFactory support,

We are developing ReKit for the AMD Developer Hackathon. The operator reports
successful sign-in and redemption/issuance of a team API key, but the dashboard
does not show whether API access is enabled. We have stopped after two rejected
synthetic-image requests and would appreciate confirmation of the supported
request contract and how to verify this team's shared-service eligibility.

We have made **five authenticated requests: three GETs and two POSTs**. Both
POSTs returned HTTP 400. There has been **no successful AMD model response,
visual inference qualification, or structured-output qualification**. No product
or customer image was sent; the same non-sensitive synthetic illustration was
presented once in each POST. We made no automatic retries or model fallbacks.

## Recorded request evidence

All times below are UTC on **2026-10-14**.

| Start time | Request | Result |
| --- | --- | --- |
| 15:55:12.970799 | `GET https://developer.amd.com.cn/radeon/api/v1/usage?include_recent=true` | HTTP 200, but no usable quota contract or quota headers; 0.531 seconds. The raw response was not retained. |
| 15:58:53.863594 | `GET https://developer.amd.com.cn/radeon/api/v1/models` | HTTP 200; sanitized catalog of 12 models; 11,572 response bytes; 0.406 seconds. |
| 16:14:52.926999 | `GET https://radeon-global.anruicloud.com/api/profile/model-usage?include_recent=true` | HTTP 404; 22 response bytes; 0.688 seconds; no usable quota headers or Retry-After. This different-host request was separately authorized. |
| 16:49:19.400984 | `POST https://developer.amd.com.cn/radeon/api/v1/chat/completions` | HTTP 400; JSON response, 142 bytes; 0.562 seconds. |
| 16:56:19.246164 | Same POST, deliberately identical request bytes | HTTP 400; JSON response, 142 bytes; 0.547 seconds. This was one explicitly reviewed diagnostic replay. |

The POST times are recorder start times, not provider-side execution timestamps.
The two POST request bodies have the same SHA-256:
`ed360c24ecc2e25d8a6183625d416b78b2b4daf97e48326cec56dfa5f60160fb`.
Both response bodies have SHA-256:
`6aad1a77b10692dafe38cabea0adde38986dd61b5bb42de83d8b7e3364860c8b`.

A later offline reconstruction reproduced the exact 19,251-byte request and
matched both recorded request hashes without making a network call. The image
base64 round-trip retained the original PNG bytes. The requested schema digest
is `31f7eb7e775cc2d59d4db0d50316773c3adcaf96a512704679fa3232fbe28e92`.
This establishes the request shape, not provider compatibility or execution.

**The exact provider error message is UNAVAILABLE: neither original raw error
body was retained.** The initial receipt retained no error category. The
diagnostic receipt retained only `type=invalid_request_error`, a controlled
indicator that the message mentioned `model`, and an empty list of recognized
message flags. The exact error `code` and `param` are also unavailable. These
categories do not establish whether the failure concerns access, the model ID,
image input, JSON Schema, or another parameter. Our client's broad
`unsupported` category is not a provider diagnosis.

## Request shape and schema questions

The exact requested model was `MiMo-V2.6-Flash`. Each POST contained one original
PNG encoded as a base64 image data URL: 768 × 512 pixels, 10,904 bytes. This is
an abbreviated description, **not a runnable request**; image bytes, prompt and
full schema are omitted:

```text
model: MiMo-V2.6-Flash
stream: false
temperature: 0
max_tokens: 512
reasoning_effort: none
messages: one user message
  content[0]: image_url containing an omitted PNG data URL
  content[1]: text containing the omitted inspection instructions
response_format:
  type: json_schema
  json_schema:
    name: rekit_inspection
    strict: true
    schema: omitted bounded object schema
```

The schema has required top-level arrays `observations`, `candidates`,
`uncertainties`, and `additional_views`. Every object lists all its properties
in `required` and uses `additionalProperties: false`. It uses integer enums
for image references, array/string length bounds, and a nested `anyOf` under
candidate array items. Those alternatives pair a string revision with its
string marking, or use `type: null` for both. This probe had no approved product
catalog, so `candidates.maxItems` was **0**, although its item schema remained
present. It did not send a literal `type: ["string", "null"]` union.

Please clarify:

1. Is this team's issued key enabled for shared image-model inference? How can
   the operator verify eligibility without posting account/team identifiers or
   a credential in a support message? A successful global catalog response does
   not appear to establish account-specific eligibility.
2. Is **`MiMo-V2.6-Flash`** the exact callable model ID on the stated endpoint for
   hackathon team keys? Are activation, regional routing, or model-specific
   access requirements involved? Please do not activate paid infrastructure.
3. Are PNG base64 image data URLs supported in the stated `image_url` content
   shape? What image-count, size and content-order limits apply? Is
   `reasoning_effort: "none"` valid with this image request?
4. Does this model/route support `response_format.type=json_schema` with
   `strict: true`? Which JSON Schema subset is accepted, particularly nested
   `anyOf`, `maxItems: 0`, null-valued alternatives/null unions, `required`,
   `additionalProperties: false`, enums, and length bounds? Must an empty array
   use a different equivalent schema? We will not silently weaken validation.
5. The saved catalog advertises image/text input and `json_output=true`, but
   `structured_outputs=false` and `free=false` for this model. The
   [MiMo documentation](https://amd-aim.github.io/radeon-cloud-docs/models/mimo-v2-6-flash/)
   describes image data URLs and strict JSON Schema. Which contract applies to
   this endpoint/key class? Please provide the **minimum compatible synthetic
   image request shape**, without credentials, and identify unsupported fields
   rather than asking us to probe alternative models or routes.

## Usage and reset questions

The operator's Check Usage report at **16:43:27 UTC** showed **1 pt daily
allowance, 0 spent, 1 remaining and 20 RPM**, with reset displayed as
**01:00 Asia/Shanghai**. API-verification status was not shown.

Both POST responses supplied normalized numeric quota fields:

```text
user_rpm_limit: 20
user_rpm_remaining: 19
daily_usd_limit: 1
daily_usd_used: 0
daily_usd_remaining: 1
daily_reset_unix: 1792080000
```

The reset timestamp corresponds to **2026-10-15 16:00 UTC / 2026-10-16 00:00
Asia/Shanghai**. Its midnight time differs from the dashboard's displayed 01:00
reset; the dashboard report supplied no explicit reset date. We have not converted **pt** to the **USD-labelled**
header values or inferred successful execution, cost, or point consumption.

Please confirm the authoritative usage endpoint for this key class, why the
same-host usage route was unusable and the documented different-host route
returned 404, the allowance units and reset timezone/date, and whether HTTP 400
requests consume daily allowance or generation capacity. Which quota evidence
is sufficient to approve one small subsequent test?

## Proposal for a follow-up — requires separate approval

No further request is currently authorized by this draft. After support replies,
the operator will review a written proposal containing: the confirmed exact
endpoint/model; the minimal proposed payload/schema change and its effect on
validation; fresh quota and reset evidence; the already charged **2/6** attempt
count; and the exact approved synthetic input. Any change needs new user
approval before execution.

If approved, the proposal will allow **one new attempt, then stop for review**,
including on HTTP error, timeout or ambiguous result. Existing attempts remain
charged; there will be no automatic retry, fallback, paid resource, or silent
schema relaxation. A future schema-valid response would still be unverified
visual evidence and could not approve compatibility or inventory actions.

Internal preparation source: the [Mission 06 checkpoint report](reports/development-mission-06.md)
and the saved sanitized receipts. Preserve this draft separately from any actual
support reply; the user's external contact does not authorize another API call.
