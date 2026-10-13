# AMD access: confirmed facts and open questions

Public documentation checked **2026-10-14**. No authenticated model request,
instance creation, credit use, or AMD inference was performed. Offline transport
tests do not establish access, model quality, or hackathon eligibility.

## Event TokenFactory route

The [official ACT III page](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii)
identifies [notebooks.amd.com/tokenfactory](https://notebooks.amd.com/tokenfactory)
as an event API route. Its FAQ says billing/card information and the $100 cloud
credit are not required for this route. A meaningful AMD workload must still be
part of the working product shown to judges.

An anonymous page request returned the AMD AI Notebooks sign-in screen, without
a model catalogue or API contract. The [public landing page](https://notebooks.amd.com/)
offers AMD SSO. This confirms the access entry point, not the inference contract:

| Required fact | Event endpoint status |
| --- | --- |
| Available image-capable model and exact served model ID | Unverified behind sign-in. |
| One-image and two-image requests; accepted media/encoding | Unverified. |
| JSON Schema enforcement, supported schema subset and output bounds | Unverified; JSON-only output would not establish schema enforcement. |
| API base URL, path and machine-authentication headers | Unverified; browser SSO is not an API authentication specification. |
| Immutable model and processor revisions | Unverified. |
| Serving runtime, preprocessing and AMD hardware evidence | Unverified. |
| Image, byte, token, concurrency, rate and timeout limits | Unverified. |

Do not fill these gaps with another platform's examples or enable an endpoint
using invented revision hashes. Obtain the account-specific documentation and
authorization before any real request.

## Separate Developer Cloud deployment

[AMD Developer Cloud](https://www.amd.com/en/developer/resources/cloud-access/amd-developer-cloud.html)
documents Instinct MI300X access and credit applications. AMD's
[setup guide](https://www.amd.com/en/developer/resources/technical-articles/2025/how-to-get-started-on-the-amd-developer-cloud-.html)
describes configurable ROCm environments, vLLM quick-start images and an
OpenAI-compatible serving endpoint. Those are deployment options, not an existing
ReKit allocation or a qualified model/runtime combination. Keep the Linux serving
environment separate from the working Windows CUDA environment.

Upstream vLLM documents [Qwen3-VL](https://docs.vllm.ai/projects/recipes/en/stable/Qwen/Qwen3-VL.html),
[multiple-image inputs](https://docs.vllm.ai/en/stable/features/multimodal_inputs/)
and [JSON-schema responses](https://docs.vllm.ai/en/stable/features/structured_outputs/).
Pin and test the actual deployed release, model revision, processor, decoder and
hardware. Generic framework support does not qualify the event's shared service.

## Services and awards must not be conflated

The separate [Radeon Cloud model API documentation](https://amd-aim.github.io/radeon-cloud-docs/guides/model-apis/)
uses `developer.amd.com.cn/radeon`. It documents shared and dedicated endpoints.
Its [experimental vision-model page](https://amd-aim.github.io/radeon-cloud-docs/models/deepseek-v4-flash-vision-exp/)
describes base64 image input and JSON-object output. This does not establish that
the same model, limits, authentication, two-image behavior or schema support is
available at `notebooks.amd.com`. ReKit does not silently select that model or
endpoint.

The [ACT III Evolus award requirements](https://lablab.ai/ai-hackathons/amd-developer-hackathon-act-iii)
specifically require the main agent's open model through the team's own vLLM
endpoint on AMD Developer Cloud, plus at least two Evolus building blocks and
application API integration. Evolus is optional. Shared TokenFactory access is
not evidence that these narrower award requirements are met.

Use the [deployment activation checklist](../deploy/amd/README.md#activation-checklist)
once credentials, endpoint facts and permission are available. An echoed model
name is not proof of loaded weights, processor revision, or AMD execution.
