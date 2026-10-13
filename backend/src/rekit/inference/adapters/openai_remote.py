"""Server-configured HTTPS vision transport. No claim of AMD execution."""

import base64
import hashlib
from io import BytesIO
import json
import os
import re
import threading
import time
from urllib.parse import urlsplit
import warnings

from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from rekit.catalog.models import Catalog
from rekit.inference.constrained import SCHEMA_VERSION, inspection_schema, schema_digest
from rekit.inference.models import InferenceConfiguration, Revision
from rekit.inference.parsing import MAX_OUTPUT_CHARACTERS, _invalid_constant, _unique_object, parse_output
from rekit.inference.provider import (
    VisionError, VisionInvalidOutput, VisionTimeout, VisionUnavailable, _inspection_prompt,
)
from rekit.inference.adapters.remote_transport import RemoteTransportError, post_https


MAX_IMAGE_BYTES = 10 * 1024**2
MAX_REQUEST_BYTES = 30 * 1024**2
PROVIDER = "openai-remote"
PROMPT_VERSION = "rekit-remote-inspection-v1"


def _endpoint(base_url: str) -> str:
    """Use only a canonical HTTPS /v1 base; no URL/path comes from an operator."""
    if not isinstance(base_url, str) or len(base_url) > 2048:
        raise ValueError("Invalid remote base URL")
    try:
        parsed = urlsplit(base_url)
        port = parsed.port
    except ValueError:
        raise ValueError("Invalid remote base URL") from None
    host = parsed.hostname or ""
    if (parsed.scheme != "https" or parsed.path != "/v1" or parsed.query or parsed.fragment
            or parsed.username is not None or parsed.password is not None
            or not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", host)
            or "." not in host or ".." in host or host.endswith(".")
            or any(character.isspace() or ord(character) < 33 for character in base_url)
            or "\\" in base_url or "%" in base_url or not base_url.isascii()
            or (port is not None and not 1 <= port <= 65535)
            or parsed.netloc != host + (f":{port}" if port is not None else "")):
        raise ValueError("Remote endpoint must be canonical HTTPS with a /v1 base")
    return base_url + "/chat/completions"


class RemoteVisionSettings(BaseModel):
    """Trusted process settings; immutable revisions come from a deployment manifest."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)
    base_url: str
    allowed_endpoints: tuple[str, ...] = Field(min_length=1, max_length=8)
    api_key: SecretStr = Field(repr=False)
    model_id: str = Field(min_length=1, max_length=256)
    model_revision: Revision
    processor_revision: Revision
    max_images: int = Field(default=2, ge=1, le=2)
    timeout_seconds: float = Field(default=120.0, ge=1, le=120)
    max_response_bytes: int = Field(default=128 * 1024, ge=1024, le=128 * 1024)

    @model_validator(mode="after")
    def trusted_destination(self):
        endpoint = _endpoint(self.base_url)
        if endpoint not in self.allowed_endpoints or len(set(self.allowed_endpoints)) != len(self.allowed_endpoints):
            raise ValueError("Remote destination is not explicitly allowlisted")
        for allowed in self.allowed_endpoints:
            if not allowed.endswith("/chat/completions") or _endpoint(allowed[:-17]) != allowed:
                raise ValueError("Allowlist entries must be exact HTTPS chat completion endpoints")
        key = self.api_key.get_secret_value()
        if not 1 <= len(key) <= 4096 or any(ord(c) < 33 or ord(c) > 126 for c in key):
            raise ValueError("A nonempty server authentication token is required")
        if self.model_id != self.model_id.strip() or any(ord(c) < 32 for c in self.model_id):
            raise ValueError("Invalid configured model ID")
        return self

    @property
    def endpoint(self) -> str:
        return _endpoint(self.base_url)

    @classmethod
    def from_environment(cls):
        try:
            return cls(
                base_url=os.environ.get("REKIT_INFERENCE_BASE_URL", ""),
                allowed_endpoints=tuple(os.environ.get("REKIT_INFERENCE_ALLOWED_ENDPOINTS", "").split(",")),
                api_key=SecretStr(os.environ.get("REKIT_INFERENCE_API_KEY", "")),
                model_id=os.environ.get("REKIT_INFERENCE_MODEL", ""),
                model_revision=os.environ.get("REKIT_INFERENCE_MODEL_REVISION", ""),
                processor_revision=os.environ.get("REKIT_INFERENCE_PROCESSOR_REVISION", ""),
                max_images=int(os.environ.get("REKIT_INFERENCE_MAX_IMAGES", "2")),
                timeout_seconds=float(os.environ.get("REKIT_INFERENCE_TIMEOUT_SECONDS", "120")),
            )
        except (ValueError, TypeError):
            raise RuntimeError("Remote inference configuration is missing or invalid; check trusted server settings") from None


def _image_content(raw: bytes) -> dict:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_IMAGE_BYTES:
        raise VisionError("Each remote image must contain at most 10 MiB of bytes")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as image:
                mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}.get(image.format)
                if (mime is None or getattr(image, "n_frames", 1) != 1
                        or max(image.size) > 8192 or image.width * image.height > 16_000_000):
                    raise ValueError("Unsupported image shape")
                image.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise VisionError("Image bytes could not be safely validated for remote transport") from None
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"}}


def _validate_requested_shape(raw: str, count: int, allow_candidates: bool) -> None:
    """Check this specific compact wire contract as well as the broader domain."""
    parsed = parse_output(raw, count, allow_candidates=allow_candidates)
    payload = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    schema = inspection_schema(count, allow_candidates=allow_candidates)
    if set(payload) != set(schema["required"]):
        raise ValueError("The remote response omitted required wire fields")
    for name in schema["required"]:
        values = payload[name]
        bounds = schema["properties"][name]
        if not bounds["minItems"] <= len(values) <= bounds["maxItems"]:
            raise ValueError("The remote response exceeded its requested array bounds")
    required = {
        "observations": {"image_indices", "kind", "text"},
        "candidates": {"image_indices", "component_type_id", "revision", "revision_marking", "reason"},
        "additional_views": {"image_indices", "view", "reason"},
    }
    for name, keys in required.items():
        if any(set(row) != keys for row in payload[name]):
            raise ValueError("The remote response omitted required record fields")
    texts = [item.text for item in parsed.observations] + list(parsed.uncertainties)
    texts += [item.reason for item in (*parsed.candidates, *parsed.additional_views)]
    texts += [item.revision_marking for item in parsed.candidates if item.revision_marking is not None]
    if any(len(text) > 160 for text in texts) or any(len(item.view) > 100 for item in parsed.additional_views):
        raise ValueError("The remote response exceeded its requested text bounds")


def _contains_secret(value, secret: str) -> bool:
    if isinstance(value, str):
        # Scan valid ASCII JSON escapes even when the surrounding model JSON is
        # malformed or has duplicate keys. This check never repairs saved output.
        unescaped = re.sub(r'\\(?:u00[0-9a-fA-F]{2}|["\\/bfnrt])',
                           lambda match: json.loads('"' + match.group() + '"'), value)
        return secret in value or secret in unescaped
    if isinstance(value, list):
        return any(_contains_secret(item, secret) for item in value)
    if isinstance(value, dict):
        return any(_contains_secret(key, secret) or _contains_secret(item, secret) for key, item in value.items())
    return False


class OpenAICompatibleVision:
    """No retries, model substitution, implicit URL fetching, or inventory access."""

    def __init__(self, settings: RemoteVisionSettings, catalog: Catalog | None = None, *, transport=post_https):
        self._settings = RemoteVisionSettings.model_validate(settings.model_dump())
        self._transport = transport
        self._prompt = _inspection_prompt(catalog)
        self._allow_candidates = catalog is not None
        self._lock = threading.Lock()
        self._state = "configured"
        self._configuration = InferenceConfiguration(
            provider=PROVIDER, model_repository=settings.model_id,
            model_revision=settings.model_revision, processor_revision=settings.processor_revision,
            device="remote", prompt_version=PROMPT_VERSION,
            runtime={"protocol": "openai-chat-completions-v1", "remote_runtime": "unknown",
                     "hardware_verification": "unverified", "revision_source": "server_configuration",
                     "revision_verification": "not_attested_by_response",
                     "endpoint_sha256": hashlib.sha256(settings.endpoint.encode()).hexdigest()},
            preprocessing={"transport": "original_bytes_base64", "max_images": settings.max_images,
                           "remote_preprocessing": "unknown", "input_attribution": "client_encoded_original_bytes",
                           "prompt_sha256": hashlib.sha256(self._prompt.encode()).hexdigest()},
            generation={"temperature": 0, "max_new_tokens": 512, "timeout_seconds": settings.timeout_seconds,
                        "decoding": "json-schema-request", "schema_version": SCHEMA_VERSION,
                        "schema_sha256_1": schema_digest(inspection_schema(1, allow_candidates=self._allow_candidates)),
                        "schema_sha256_2": schema_digest(inspection_schema(2, allow_candidates=self._allow_candidates)),
                        "identity_candidates_allowed": self._allow_candidates, "remote_schema_enforcement": "unverified"},
        )

    @property
    def configuration(self) -> InferenceConfiguration:
        return self._configuration.model_copy(deep=True)

    @property
    def status(self) -> str:
        return self._state

    def inspect(self, images: list[bytes]) -> dict:
        if not isinstance(images, list) or not 1 <= len(images) <= 2:
            raise VisionError("Remote inspection requires one or two images")
        if len(images) > self._settings.max_images:
            raise VisionUnavailable("The configured endpoint does not support this image count", reason_code="unsupported")
        images = list(images)  # Bind immutable bytes before transport; callers cannot replace an input later.
        if not self._lock.acquire(blocking=False):
            raise VisionUnavailable("The remote provider already has an active request", reason_code="busy")
        started = time.monotonic()
        self._state = "busy"
        try:
            content = [_image_content(raw) for raw in images]
            schema = inspection_schema(len(images), allow_candidates=self._allow_candidates)
            payload = json.dumps({
                "model": self._settings.model_id, "stream": False, "temperature": 0, "max_tokens": 512,
                "messages": [{"role": "user", "content": [*content, {"type": "text", "text": self._prompt}]}],
                "response_format": {"type": "json_schema", "json_schema": {
                    "name": "rekit_inspection", "strict": True, "schema": schema}},
            }, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode()
            if len(payload) > MAX_REQUEST_BYTES:
                raise VisionError("The encoded remote request exceeds 30 MiB")
            remaining = self._settings.timeout_seconds - (time.monotonic() - started)
            if remaining <= 0:
                raise VisionTimeout("The remote request deadline expired before transport")
            try:
                response = self._transport(self._settings.endpoint, self._settings.api_key.get_secret_value(),
                                           payload, timeout=remaining, max_response_bytes=self._settings.max_response_bytes)
            except RemoteTransportError as error:
                if error.code == "timeout":
                    raise VisionTimeout("The remote HTTPS execution deadline expired") from None
                if error.code in {"oversized", "protocol"}:
                    raise VisionInvalidOutput("The remote response violated the bounded HTTP contract") from None
                raise VisionUnavailable("The remote HTTPS endpoint is unavailable", reason_code="endpoint") from None
            except Exception:
                raise VisionError("Remote transport failed without a usable response") from None
            if time.monotonic() - started >= self._settings.timeout_seconds:
                raise VisionTimeout("The remote execution deadline expired")
            if response.status in (401, 403):
                raise VisionUnavailable("Remote authentication was rejected", reason_code="authentication")
            if response.status == 429:
                raise VisionUnavailable("The remote endpoint is rate limited; no retry was made", reason_code="rate_limited")
            if response.status in (400, 404, 415, 422):
                raise VisionUnavailable("The remote endpoint rejected the model, image, or structured-output contract",
                                        reason_code="unsupported")
            if response.status != 200:
                raise VisionUnavailable("The remote endpoint did not accept the request", reason_code="endpoint")
            if (not isinstance(response.body, bytes) or len(response.body) > self._settings.max_response_bytes
                    or response.content_type.split(";", 1)[0].strip().lower() != "application/json"):
                raise VisionInvalidOutput("The remote response has an invalid size or content type")
            try:
                envelope = json.loads(response.body.decode("utf-8"), object_pairs_hook=_unique_object,
                                      parse_constant=_invalid_constant)
                # Never persist an echoed credential, even from an otherwise trusted endpoint.
                key = self._settings.api_key.get_secret_value()
                if _contains_secret(envelope, key):
                    raise ValueError("Credential echo")
                if not isinstance(envelope, dict) or envelope.get("model") != self._settings.model_id:
                    raise ValueError("Unexpected or missing model identity")
                choices = envelope["choices"]
                if not isinstance(choices, list) or len(choices) != 1:
                    raise ValueError("Exactly one model response is required")
                choice = choices[0]
                message = choice["message"]
                if (type(choice.get("index")) is not int or choice.get("index") != 0 or choice.get("finish_reason") != "stop"
                        or message.get("role") != "assistant" or message.get("tool_calls")
                        or message.get("function_call") or message.get("refusal")):
                    raise ValueError("Incomplete or unsupported model response")
                raw = message["content"]
                if not isinstance(raw, str) or not 0 < len(raw) <= MAX_OUTPUT_CHARACTERS:
                    raise ValueError("Missing or oversized model text")
            except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
                raise VisionInvalidOutput("Remote JSON, model identity, or completion envelope is invalid") from None
            try:
                _validate_requested_shape(raw, len(images), self._allow_candidates)
            except (ValueError, TypeError, RecursionError):
                raise VisionInvalidOutput("Remote model text failed strict schema and domain validation",
                                          raw_output=raw) from None
            if time.monotonic() - started >= self._settings.timeout_seconds:
                raise VisionTimeout("The remote request deadline expired during validation")
            self._state = "ready"
            return {"status": "succeeded", "text": raw, "provider": PROVIDER,
                    "model_repository": self._settings.model_id, "model_revision": self._settings.model_revision,
                    "device": "remote", "runtime": self._configuration.runtime.copy(),
                    "metrics": {"input_sha256": [hashlib.sha256(raw_image).hexdigest() for raw_image in images],
                                "request_bytes": len(payload), "response_bytes": len(response.body),
                                "transport_seconds": time.monotonic() - started,
                                "decoding": "json-schema-request", "schema_version": SCHEMA_VERSION,
                                "schema_sha256": schema_digest(schema), "response_model_id_matched": True}}
        except VisionUnavailable:
            self._state = "unavailable"
            raise
        finally:
            if self._state == "busy":
                self._state = "configured"
            self._lock.release()
