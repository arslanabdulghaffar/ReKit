"""Offline qualification of the real remote adapter, with controlled HTTP bytes."""

import base64
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import threading

from PIL import Image
from pydantic import SecretStr, ValidationError
import pytest

from rekit.catalog.models import Catalog
from rekit.inference.adapters import openai_remote as remote
from rekit.inference.adapters.openai_remote import OpenAICompatibleVision, RemoteVisionSettings
from rekit.inference.adapters.remote_transport import HttpResponse, RemoteTransportError
from rekit.inference.constrained import inspection_schema, schema_digest
from rekit.inference.provider import VisionError, VisionInvalidOutput, VisionTimeout, VisionUnavailable


BASE = "https://vision.example.test/v1"
ENDPOINT = BASE + "/chat/completions"
TOKEN = "controlled-test-token-never-a-real-secret"
MODEL = "test/vision-model"
OUTPUT = {
    "observations": [{"image_indices": [1], "kind": "appearance", "text": "A colored rectangular surface."}],
    "candidates": [], "uncertainties": ["Identity cannot be established from this image."],
    "additional_views": [{"image_indices": [1], "view": "Readable marking close-up", "reason": "A revision is not established."}],
}


def settings(**changes):
    return RemoteVisionSettings(**({
        "base_url": BASE, "allowed_endpoints": (ENDPOINT,), "api_key": SecretStr(TOKEN),
        "model_id": MODEL, "model_revision": "a" * 40, "processor_revision": "b" * 40,
    } | changes))


def envelope(raw=None):
    return {"model": MODEL, "choices": [{"index": 0, "finish_reason": "stop", "message": {
        "role": "assistant", "content": json.dumps(OUTPUT) if raw is None else raw,
    }}]}


def response(payload=None, *, status=200, content_type="application/json"):
    body = json.dumps(envelope() if payload is None else payload).encode() if not isinstance(payload, bytes) else payload
    return HttpResponse(status=status, body=body, content_type=content_type)


class Transport:
    def __init__(self, result=None, error=None):
        self.result = response() if result is None else result
        self.error = error
        self.calls = []

    def __call__(self, endpoint, token, body, **kwargs):
        self.calls.append((endpoint, token, body, kwargs))
        if self.error is not None:
            raise self.error
        return self.result


@pytest.fixture
def image_bytes():
    def make(format="PNG", color="red"):
        with Image.new("RGB", (24, 18), color) as image, BytesIO() as buffer:
            image.save(buffer, format=format)
            return buffer.getvalue()
    return make


@pytest.fixture
def catalog():
    return Catalog.model_validate_json((Path(__file__).parents[1] / "fixtures/synthetic_catalog.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("formats", [("PNG",), ("JPEG",), ("WEBP",), ("PNG", "JPEG")])
def test_original_image_bytes_order_hashes_and_requested_schema(formats, image_bytes):
    transport = Transport()
    provider = OpenAICompatibleVision(settings(), transport=transport)
    originals = [image_bytes(format, color) for format, color in zip(formats, ("red", "blue"))]
    result = provider.inspect(originals)
    assert len(transport.calls) == 1
    endpoint, token, encoded, limits = transport.calls[0]
    assert (endpoint, token) == (ENDPOINT, TOKEN)
    assert 0 < limits["timeout"] <= 120
    assert limits["max_response_bytes"] == 128 * 1024
    request = json.loads(encoded)
    assert request["model"] == MODEL
    assert request["stream"] is False
    assert request["temperature"] == 0
    assert request["max_tokens"] == 512
    content = request["messages"][0]["content"]
    for part, original, format in zip(content[:-1], originals, formats):
        prefix, payload = part["image_url"]["url"].split(",", 1)
        assert prefix == f"data:image/{'jpeg' if format == 'JPEG' else format.lower()};base64"
        assert base64.b64decode(payload, validate=True) == original
    assert content[-1]["type"] == "text"
    schema = inspection_schema(len(originals), allow_candidates=False)
    assert request["response_format"]["json_schema"] == {"name": "rekit_inspection", "strict": True, "schema": schema}
    assert result["metrics"]["input_sha256"] == [hashlib.sha256(raw).hexdigest() for raw in originals]
    assert result["metrics"]["schema_sha256"] == schema_digest(schema)
    assert result["metrics"]["response_model_id_matched"] is True
    assert "vision_forward_calls" not in result["metrics"]
    assert result["text"] == json.dumps(OUTPUT)
    assert (result["provider"], result["device"], provider.status) == ("openai-remote", "remote", "ready")


def test_configuration_is_lazy_secret_free_copied_and_does_not_attest_remote_hardware():
    transport = Transport()
    provider = OpenAICompatibleVision(settings(), transport=transport)
    assert provider.status == "configured"
    assert transport.calls == []
    config = provider.configuration
    assert TOKEN not in config.model_dump_json()
    assert BASE not in config.model_dump_json()
    assert config.runtime["hardware_verification"] == "unverified"
    assert config.runtime["remote_runtime"] == "unknown"
    assert config.runtime["revision_verification"] == "not_attested_by_response"
    assert config.runtime["revision_source"] == "server_configuration"
    assert config.generation["remote_schema_enforcement"] == "unverified"
    config.runtime["hardware_verification"] = "forged"
    config.generation["identity_candidates_allowed"] = True
    assert provider.configuration.runtime["hardware_verification"] == "unverified"
    assert provider.configuration.generation["identity_candidates_allowed"] is False


@pytest.mark.parametrize("base", [
    "http://vision.example.test/v1", "https://vision.example.test/v1/", "https://vision.example.test/v2",
    "https://vision.example.test/v1?x=1", "https://vision.example.test/v1#fragment",
    "https://user:password@vision.example.test/v1", "https://localhost/v1", "https://[::1]/v1",
    "https://Vision.example.test/v1", "https://vision..example.test/v1", "https://vision.example.test./v1",
    "https://vision.example.test:0/v1", "https://vision.example.test:65536/v1",
    "https://vision.example.test:0443/v1", "https://vision.example.test/%76%31",
    "https://vision.example.test\\evil/v1", "https://vision.example.test/v1\n",
])
def test_endpoint_must_be_exact_canonical_https(base):
    with pytest.raises(ValidationError):
        settings(base_url=base, allowed_endpoints=(base + "/chat/completions",))


@pytest.mark.parametrize("changes", [
    {"allowed_endpoints": ("https://other.example.test/v1/chat/completions",)},
    {"allowed_endpoints": (ENDPOINT, ENDPOINT)}, {"allowed_endpoints": (ENDPOINT, BASE)},
    {"api_key": SecretStr("")}, {"api_key": SecretStr("secret\r\nheader")},
    {"api_key": SecretStr("x" * 4097)}, {"model_id": " leading"}, {"model_id": "model\nID"},
    {"model_revision": "main"}, {"processor_revision": "A" * 40}, {"max_images": True},
    {"max_images": "2"}, {"max_images": 3}, {"timeout_seconds": float("nan")},
    {"timeout_seconds": 121.0}, {"max_response_bytes": 128 * 1024 + 1}, {"unknown": "field"},
])
def test_settings_fail_closed_without_exposing_input_values(changes):
    with pytest.raises(ValidationError) as caught:
        settings(**changes)
    assert TOKEN not in str(caught.value)
    assert "input_value=" not in str(caught.value)


def test_settings_environment_and_forged_instance_are_revalidated(monkeypatch):
    values = {
        "REKIT_INFERENCE_BASE_URL": BASE, "REKIT_INFERENCE_ALLOWED_ENDPOINTS": ENDPOINT,
        "REKIT_INFERENCE_API_KEY": TOKEN, "REKIT_INFERENCE_MODEL": MODEL,
        "REKIT_INFERENCE_MODEL_REVISION": "a" * 40, "REKIT_INFERENCE_PROCESSOR_REVISION": "b" * 40,
        "REKIT_INFERENCE_MAX_IMAGES": "1", "REKIT_INFERENCE_TIMEOUT_SECONDS": "20",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    assert RemoteVisionSettings.from_environment() == settings(max_images=1, timeout_seconds=20.0)
    monkeypatch.delenv("REKIT_INFERENCE_API_KEY")
    with pytest.raises(RuntimeError) as caught:
        RemoteVisionSettings.from_environment()
    assert TOKEN not in str(caught.value)
    with pytest.raises(ValidationError):
        OpenAICompatibleVision(settings().model_copy(update={"base_url": "http://untrusted.invalid/v1"}), transport=Transport())


@pytest.mark.parametrize("invalid", ["empty", "three", "tuple", "invalid_bytes", "gif", "oversized"])
def test_invalid_inputs_never_reach_transport(invalid, image_bytes, monkeypatch):
    transport = Transport()
    provider = OpenAICompatibleVision(settings(), transport=transport)
    original = image_bytes()
    images = [original]
    if invalid == "empty":
        images = []
    elif invalid == "three":
        images *= 3
    elif invalid == "tuple":
        images = tuple(images)
    elif invalid == "invalid_bytes":
        images = [b"not an image"]
    elif invalid == "gif":
        images = [image_bytes("GIF")]
    elif invalid == "oversized":
        monkeypatch.setattr(remote, "MAX_IMAGE_BYTES", len(original) - 1)
    with pytest.raises(VisionError):
        provider.inspect(images)
    assert transport.calls == []


@pytest.mark.parametrize("status,code", [(401, "authentication"), (403, "authentication"), (429, "rate_limited"),
    (400, "unsupported"), (404, "unsupported"), (415, "unsupported"), (422, "unsupported"), (500, "endpoint"), (503, "endpoint")])
def test_http_failure_is_controlled_without_retry_fallback_or_body_echo(status, code, image_bytes):
    transport = Transport(response(TOKEN.encode(), status=status))
    provider = OpenAICompatibleVision(settings(), transport=transport)
    with pytest.raises(VisionUnavailable) as caught:
        provider.inspect([image_bytes()])
    assert caught.value.reason_code == code
    assert TOKEN not in str(caught.value)
    assert len(transport.calls) == 1
    assert provider.status == "unavailable"


@pytest.mark.parametrize("code,error_type", [("timeout", VisionTimeout), ("oversized", VisionInvalidOutput),
    ("protocol", VisionInvalidOutput), ("unavailable", VisionUnavailable)])
def test_transport_failures_have_one_attempt(code, error_type, image_bytes):
    transport = Transport(error=RemoteTransportError(code))
    with pytest.raises(error_type):
        OpenAICompatibleVision(settings(), transport=transport).inspect([image_bytes()])
    assert len(transport.calls) == 1


def test_unexpected_transport_exception_is_sanitized(image_bytes):
    with pytest.raises(VisionError) as caught:
        OpenAICompatibleVision(settings(), transport=Transport(error=RuntimeError(TOKEN))).inspect([image_bytes()])
    assert TOKEN not in str(caught.value)


@pytest.mark.parametrize("defect", ["wrong_model", "missing_model", "no_choices", "two_choices", "bool_index", "wrong_index",
    "missing_role", "length_finish", "tool_calls", "function_call", "refusal", "no_content", "list_content", "long_content",
    "malformed", "duplicate_key", "nonfinite", "invalid_utf8", "oversized", "wrong_content_type", "credential_echo"])
def test_untrusted_envelope_is_rejected_without_retaining_raw(defect, image_bytes):
    value = envelope()
    choice = value["choices"][0]
    message = choice["message"]
    media_type = "application/json"
    if defect == "wrong_model": value["model"] = "substituted/model"
    elif defect == "missing_model": del value["model"]
    elif defect == "no_choices": value["choices"] = []
    elif defect == "two_choices": value["choices"] *= 2
    elif defect == "bool_index": choice["index"] = False
    elif defect == "wrong_index": choice["index"] = 1
    elif defect == "missing_role": del message["role"]
    elif defect == "length_finish": choice["finish_reason"] = "length"
    elif defect in ("tool_calls", "function_call", "refusal"): message[defect] = "unsupported action"
    elif defect == "no_content": del message["content"]
    elif defect == "list_content": message["content"] = []
    elif defect == "long_content": message["content"] = "x" * 32001
    elif defect == "malformed": value = b"{"
    elif defect == "duplicate_key": value = b'{"model":"first","model":"second","choices":[]}'
    elif defect == "nonfinite": value = b'{"model":NaN,"choices":[]}'
    elif defect == "invalid_utf8": value = b"\xff"
    elif defect == "oversized": value = b"x" * (128 * 1024 + 1)
    elif defect == "wrong_content_type": media_type = "text/html"
    elif defect == "credential_echo": value["diagnostic"] = TOKEN
    transport = Transport(response(value, content_type=media_type))
    with pytest.raises(VisionInvalidOutput) as caught:
        OpenAICompatibleVision(settings(), transport=transport).inspect([image_bytes()])
    assert caught.value.raw_output is None
    assert TOKEN not in str(caught.value)
    assert len(transport.calls) == 1


@pytest.mark.parametrize("defect", ["missing_array", "extra_authority", "bad_index", "duplicate_index", "bool_index",
    "long_text", "too_many_observations", "no_uncertainty", "missing_view_indices", "revision_without_marking",
    "candidate_missing_pair", "malformed", "duplicate_keys", "nonfinite", "fenced"])
def test_invalid_model_text_is_preserved_without_repair(defect, image_bytes, catalog):
    value = deepcopy(OUTPUT)
    if defect == "missing_array": del value["additional_views"]
    elif defect == "extra_authority": value["compatible"] = True
    elif defect == "bad_index": value["observations"][0]["image_indices"] = [2]
    elif defect == "duplicate_index": value["observations"][0]["image_indices"] = [1, 1]
    elif defect == "bool_index": value["observations"][0]["image_indices"] = [True]
    elif defect == "long_text": value["observations"][0]["text"] = "x" * 161
    elif defect == "too_many_observations": value["observations"] *= 3
    elif defect == "no_uncertainty": value["uncertainties"] = []
    elif defect == "missing_view_indices": del value["additional_views"][0]["image_indices"]
    elif defect in ("revision_without_marking", "candidate_missing_pair"):
        value["candidates"] = [{"image_indices": [1], "component_type_id": "body", "reason": "Unverified appearance."}]
        if defect == "revision_without_marking":
            value["candidates"][0].update(revision="A", revision_marking=None)
    raw = json.dumps(value)
    if defect == "malformed": raw = "{"
    elif defect == "duplicate_keys": raw = raw[:-1] + ',"candidates":[]}'
    elif defect == "nonfinite": raw = raw.replace('"A colored rectangular surface."', "NaN")
    elif defect == "fenced": raw = "```json\n" + raw + "\n```"
    with pytest.raises(VisionInvalidOutput) as caught:
        OpenAICompatibleVision(settings(), catalog, transport=Transport(response(envelope(raw)))).inspect([image_bytes()])
    assert caught.value.raw_output == raw


def test_no_catalog_cannot_emit_identity_even_if_endpoint_ignores_requested_schema(image_bytes, catalog):
    value = deepcopy(OUTPUT)
    value["candidates"] = [{"image_indices": [1], "component_type_id": "body", "revision": "A",
                            "revision_marking": "REV A", "reason": "A marking is visible."}]
    raw = json.dumps(value)
    transport = Transport(response(envelope(raw)))
    with pytest.raises(VisionInvalidOutput) as caught:
        OpenAICompatibleVision(settings(), transport=transport).inspect([image_bytes()])
    assert caught.value.raw_output == raw
    assert OpenAICompatibleVision(settings(), catalog, transport=transport).inspect([image_bytes()])["text"] == raw


def test_echoed_secret_inside_model_text_is_discarded(image_bytes):
    value = deepcopy(OUTPUT)
    value["observations"][0]["text"] = TOKEN
    with pytest.raises(VisionInvalidOutput) as caught:
        OpenAICompatibleVision(settings(), transport=Transport(response(envelope(json.dumps(value))))).inspect([image_bytes()])
    assert caught.value.raw_output is None


@pytest.mark.parametrize("shape", ["valid", "duplicate_key", "malformed"])
def test_unicode_escaped_secret_in_nested_model_json_is_not_retained(image_bytes, shape):
    value = deepcopy(OUTPUT)
    value["observations"][0]["text"] = TOKEN
    raw = json.dumps(value).replace(TOKEN, "".join(f"\\u{ord(character):04x}" for character in TOKEN))
    if shape == "duplicate_key":
        raw = raw[:-1] + ',"candidates":[]}'
    elif shape == "malformed":
        raw = raw[:-2]
    assert TOKEN not in raw
    with pytest.raises(VisionInvalidOutput) as caught:
        OpenAICompatibleVision(settings(), transport=Transport(response(envelope(raw)))).inspect([image_bytes()])
    assert caught.value.raw_output is None


def test_caller_list_mutation_cannot_change_provenance_for_already_encoded_bytes(image_bytes):
    original = image_bytes(color="red")
    images = [original]
    calls = []

    def mutate_after_encoding(endpoint, token, payload, **limits):
        calls.append(json.loads(payload))
        images[:] = [image_bytes(color="blue")]
        return response()

    result = OpenAICompatibleVision(settings(), transport=mutate_after_encoding).inspect(images)
    encoded = calls[0]["messages"][0]["content"][0]["image_url"]["url"].split(",", 1)[1]
    assert base64.b64decode(encoded) == original
    assert images[0] != original
    assert result["metrics"]["input_sha256"] == [hashlib.sha256(original).hexdigest()]


def test_absolute_deadline_after_transport_rejects_even_a_valid_response(image_bytes, monkeypatch):
    readings = iter((0.0, 0.0, 121.0))
    monkeypatch.setattr(remote.time, "monotonic", lambda: next(readings))
    transport = Transport()
    with pytest.raises(VisionTimeout):
        OpenAICompatibleVision(settings(), transport=transport).inspect([image_bytes()])
    assert len(transport.calls) == 1


def test_concurrent_request_has_no_second_transport_call(image_bytes):
    entered, release = threading.Event(), threading.Event()
    transport = Transport()
    results = []

    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        return transport(*args, **kwargs)

    provider = OpenAICompatibleVision(settings(), transport=blocked)
    worker = threading.Thread(target=lambda: results.append(provider.inspect([image_bytes()])))
    worker.start()
    try:
        assert entered.wait(2)
        assert provider.status == "busy"
        with pytest.raises(VisionUnavailable) as caught:
            provider.inspect([image_bytes()])
        assert caught.value.reason_code == "busy"
    finally:
        release.set()
        worker.join(5)
    assert not worker.is_alive()
    assert len(results) == len(transport.calls) == 1
