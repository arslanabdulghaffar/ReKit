"""One-shot synthetic TokenFactory qualification actions; no automatic retry.

Run only through the private PowerShell launcher. Dashboard evidence authorizes
the first probe, not subsequent consumption. A response must supply new usable
quota evidence or the caller must stop and obtain a changed dashboard reading.
The separate diagnostic action can replay the sole HTTP 400 once, with identical
request bytes and fresh quota evidence. Neither action has a provider fallback.
"""

import argparse
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import time

from pydantic import SecretStr

from rekit.inference.adapters.openai_remote import (
    OpenAICompatibleVision, RemoteVisionSettings, TOKENFACTORY_BASE,
    TOKENFACTORY_ENDPOINT, TOKENFACTORY_MIMO_MODEL, _contains_secret, _usage_metrics,
)
from rekit.inference.adapters.remote_transport import post_https
from rekit.inference.parsing import MAX_OUTPUT_CHARACTERS, _invalid_constant, _unique_object
from rekit.inference.provider import VisionInvalidOutput, VisionTimeout, VisionUnavailable
from run_api_inference_acceptance import _image
from tokenfactory_discovery import _save
from tokenfactory_qualification import (
    GuardedQualificationTransport, LEDGER_NAME, QualificationAdmission,
    QualificationLedger, VerifiedQuotaEvidence,
)


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / ".secrets" / "tokenfactory" / "qualification"
SOURCE_SHA256 = "cf1a8f595ff3986a947e7160cdb76d7493e9748d2d1f5a03b83d0d23343de38b"
RECEIPT_NAME = "synthetic-first.json"
DIAGNOSTIC_NAME = "synthetic-diagnostic.json"
MAX_RAW_DIAGNOSTIC_BYTES = 64 * 1024


def _error_diagnostics(envelope):
    """Controlled categories only; never copy arbitrary provider error text."""
    if not isinstance(envelope, dict):
        return {"classification": "unrecognized"}
    error = envelope.get("error")
    detail = envelope.get("detail")
    if error is None and isinstance(detail, dict):
        error = detail.get("error")
    if not isinstance(error, dict):
        error = {"message": detail} if isinstance(detail, str) else {}
    codes = {"invalid_request_error", "unsupported_parameter", "invalid_api_key", "model_not_found",
             "unsupported_response_format", "invalid_json_schema", "insufficient_quota", "rate_limit_exceeded",
             "token_rate_limit_exceeded", "BadRequestError", "bad_request", "invalid_parameter", "unsupported_model"}
    parameters = {"model", "messages", "image_url", "temperature", "max_tokens", "reasoning_effort",
                  "response_format", "json_schema", "strict", "additionalProperties", "anyOf", "maxItems"}
    result = {field: error[field] for field in ("code", "type", "param")
              if isinstance(error.get(field), str) and error[field] in (parameters if field == "param" else codes)}
    message = error.get("message")
    if isinstance(message, str) and len(message) <= 2048:
        result["message_mentions"] = sorted(value for value in parameters if value.lower() in message.lower())
        result["message_flags"] = [flag for flag in ("not supported", "unsupported", "invalid", "not allowed", "required")
                                   if flag in message.lower()]
    return result or {"classification": "unrecognized"}


def _now():
    return datetime.now(UTC)


def _read(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 256 * 1024:
        raise ValueError("Invalid qualification evidence file")
    raw = path.read_bytes()
    return json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_invalid_constant), hashlib.sha256(raw).hexdigest()


def _dashboard(data, digest):
    required = {"source", "reported_at", "expires_at", "next_reset_at", "reset_display",
                "allowance_unit", "daily_allowance", "spent_today", "remaining_allowance",
                "rpm_limit", "requests_today", "errors_today", "tokens_today",
                "signed_in", "key_issued", "api_verification", "dashboard_error",
                "initial_probe_authorized", "post_probe_quota_check_required"}
    if not isinstance(data, dict) or set(data) != required:
        raise ValueError("Incomplete operator dashboard evidence")
    if (data["source"] != "operator_reported_check_usage" or data["allowance_unit"] != "pt"
            or data["signed_in"] is not True or data["key_issued"] is not True
            or data["api_verification"] is not None or data["dashboard_error"] is not None
            or data["initial_probe_authorized"] is not True or data["post_probe_quota_check_required"] is not True
            or data["reset_display"] != "01:00 Asia/Shanghai"):
        raise ValueError("Dashboard evidence does not authorize the initial probe")
    for field, expected in (("daily_allowance", 1), ("spent_today", 0), ("remaining_allowance", 1),
                            ("rpm_limit", 20), ("requests_today", 0), ("errors_today", 0), ("tokens_today", 0)):
        if type(data[field]) not in (int, float) or data[field] != expected:
            raise ValueError("Initial dashboard values differ from the reviewed report")
    return VerifiedQuotaEvidence(
        source="dashboard", evidence_sha256=digest, verified_by="trusted_qualification_caller",
        status="ok", api_access_verified=None, free_shared_service_confirmed=True,
        allowance_unit="pt", initial_probe_authorized=True, key_issued_reported=True,
        remaining_allowance=float(data["remaining_allowance"]),
        observed_at=datetime.fromisoformat(data["reported_at"]),
        expires_at=datetime.fromisoformat(data["expires_at"]),
        reset_at=datetime.fromisoformat(data["next_reset_at"]),
    )


def _response_evidence(response, token):
    """Selected diagnostics only; never preserve raw error/account envelopes."""
    record = {"http_status": response.status, "response_bytes": len(response.body),
              "content_type": response.content_type, "retry_after_seconds": response.retry_after_seconds,
              "quota_headers": response.quota_headers or {}}
    text = response.body.decode("utf-8", errors="replace")
    if _contains_secret(text, token):
        return {"http_status": response.status, "body_discarded": "credential_echo"}
    record["response_sha256"] = hashlib.sha256(response.body).hexdigest()
    if response.content_type.split(";", 1)[0].strip().lower() != "application/json":
        return record
    try:
        envelope = json.loads(text, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        if _contains_secret(envelope, token) or not isinstance(envelope, dict):
            raise ValueError
        if response.status != 200:
            record["error_diagnostics"] = _error_diagnostics(envelope)
            return record
        record["response_model_matches"] = envelope.get("model") == TOKENFACTORY_MIMO_MODEL
        record["usage"] = _usage_metrics(envelope)
        choices = envelope.get("choices")
        if isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict):
            choice = choices[0]
            if choice.get("finish_reason") in ("stop", "length", "content_filter", "tool_calls"):
                record["finish_reason"] = choice["finish_reason"]
            message = choice.get("message")
            if isinstance(message, dict) and message.get("role") == "assistant":
                raw = message.get("content")
                if isinstance(raw, str) and 0 < len(raw) <= MAX_OUTPUT_CHARACTERS:
                    serialized_bytes = len(json.dumps(raw, ensure_ascii=True).encode("ascii"))
                    record["raw_model_text_characters"] = len(raw)
                    record["raw_model_text_serialized_bytes"] = serialized_bytes
                    try:
                        record["raw_model_text_sha256"] = hashlib.sha256(raw.encode("utf-8")).hexdigest()
                    except UnicodeEncodeError:
                        record["raw_model_text_omitted"] = "invalid_unicode"
                    else:
                        if serialized_bytes <= MAX_RAW_DIAGNOSTIC_BYTES:
                            record["raw_model_text"] = raw
                        else:
                            record["raw_model_text_omitted"] = "serialized_size_limit"
    except (ValueError, TypeError, KeyError, RecursionError):
        record["envelope_diagnostics"] = "invalid_or_unusable"
    return record


def _after_quota(response_evidence):
    headers = response_evidence.get("quota_headers", {})
    remaining = headers.get("daily_usd_remaining")
    reset = headers.get("daily_reset_unix")
    rpm_remaining = headers.get("user_rpm_remaining")
    positive = (type(remaining) in (int, float) and remaining > 0
                and type(reset) is int and reset > _now().timestamp()
                and type(rpm_remaining) is int and rpm_remaining > 0)
    return {"status": "fresh_header_evidence" if positive else "uncertain_stop",
            "source": "response_headers", "reported_units": "provider_USD_label",
            "headers": headers, "conversion_from_dashboard_pt": None,
            "consumption_in_pt": None, "another_request_authorized_by_this_runner": False}


def _diagnostic_outcome(prior, rows):
    """Bind the mutable receipt to its sole immutable HTTP outcome before use."""
    if len(rows) != 1:
        raise ValueError("Diagnostic replay requires exactly one prior charged request")
    row = rows[0]
    response = prior.get("response", {})
    if (row["kind"] != "http_response" or row["http_status"] != 400
            or not isinstance(response, dict) or type(response.get("http_status")) is not int
            or response["http_status"] != row["http_status"]
            or not isinstance(response.get("response_sha256"), str)
            or response["response_sha256"] != row["response_sha256"]
            or type(response.get("response_bytes")) is not int
            or response["response_bytes"] != row["response_bytes"]):
        raise ValueError("Diagnostic receipt does not match the immutable HTTP 400 outcome")
    try:
        finished = datetime.fromisoformat(row["finished_at"])
        recorded = datetime.fromisoformat(prior["finished_at"])
        if finished.utcoffset() is None or recorded.utcoffset() is None:
            raise ValueError
        if not timedelta(0) <= recorded - finished <= timedelta(seconds=60) or recorded > _now():
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValueError("Diagnostic receipt completion time does not match the immutable outcome") from None
    return row, finished


def run(directory: Path, token: str, *, transport=post_https, diagnostic=False):
    path = directory / (DIAGNOSTIC_NAME if diagnostic else RECEIPT_NAME)
    if path.exists():
        return _read(path)[0]  # Interrupted and failed records never implicitly retry.
    dashboard, dashboard_digest = _read(directory / "dashboard-evidence.json")
    quota = _dashboard(dashboard, dashboard_digest)
    prior_digest = None
    prior_request_digest = None
    if diagnostic:
        prior, prior_digest = _read(directory / RECEIPT_NAME)
        ledger = QualificationLedger(directory)
        prior_outcome, observed = _diagnostic_outcome(prior, ledger.records())
        response = prior.get("response", {})
        headers = response.get("quota_headers", {})
        if (prior.get("status") != "unavailable" or prior.get("reason_code") != "unsupported"
                or response.get("http_status") != 400 or prior.get("generation_attempts_after") != 1
                or type(headers.get("daily_usd_remaining")) not in (int, float)
                or not headers["daily_usd_remaining"] > 0
                or type(headers.get("user_rpm_remaining")) is not int or headers["user_rpm_remaining"] <= 0
                or type(headers.get("daily_reset_unix")) is not int):
            raise ValueError("Diagnostic replay requires reviewed rejection and positive fresh header evidence")
        reset = datetime.fromtimestamp(headers["daily_reset_unix"], UTC)
        quota = VerifiedQuotaEvidence(source="response_headers", evidence_sha256=prior_digest,
            verified_by="trusted_qualification_caller", status="ok", api_access_verified=None,
            free_shared_service_confirmed=True, allowance_unit="provider_capacity",
            diagnostic_replay_authorized=True, key_issued_reported=True,
            remaining_allowance=float(headers["daily_usd_remaining"]), observed_at=observed,
            expires_at=min(observed + timedelta(minutes=15), quota.expires_at), reset_at=reset)
        prior_request_digest = prior_outcome["request_sha256"]
    catalog, catalog_digest = _read(directory / "catalog-discovery.json")
    if _contains_secret(catalog, token) or _contains_secret(dashboard, token):
        raise ValueError("Unsafe qualification evidence")
    calls = catalog.get("calls", [])
    if (len(calls) != 1 or calls[0].get("http_status") != 200 or calls[0].get("status") != "succeeded"
            or calls[0].get("endpoint") != TOKENFACTORY_BASE + "/models"):
        raise ValueError("The preserved catalog is not the successful fixed model request")
    models = calls[0].get("data", [])
    candidate = next((item for item in models if item.get("id") == TOKENFACTORY_MIMO_MODEL), None)
    if candidate is None or "image" not in candidate.get("input_modalities", []):
        raise ValueError("The preserved catalog does not advertise the exact image model")
    image = _image()
    if hashlib.sha256(image).hexdigest() != SOURCE_SHA256:
        raise ValueError("Synthetic source bytes differ from the approved local regression image")
    settings = RemoteVisionSettings(provider="amd-tokenfactory", base_url=TOKENFACTORY_BASE,
        allowed_endpoints=(TOKENFACTORY_ENDPOINT,), api_key=SecretStr(token), model_id=TOKENFACTORY_MIMO_MODEL,
        model_revision=None, processor_revision=None, max_images=1, timeout_seconds=120.0)
    # Reading configuration does not invoke transport or initialize a model.
    configuration = OpenAICompatibleVision(settings, catalog=None, transport=transport).configuration
    admission = QualificationAdmission(admission_id="mission06-synthetic-diagnostic" if diagnostic else "mission06-synthetic-first",
        authorization="existing_mission_authorization", catalog_receipt_sha256=catalog_digest,
        input_sha256=(SOURCE_SHA256,), prompt_sha256=configuration.preprocessing["prompt_sha256"],
        schema_sha256=configuration.generation["schema_sha256_1"], allow_candidates=False, quota=quota,
        diagnostic_prior_request_sha256=prior_request_digest)
    record = {"status": "pending", "started_at": _now().isoformat(), "synthetic": True,
        "transport": "real HTTPS direct provider qualification; not application/browser acceptance",
        "configuration": configuration.model_dump(mode="json"), "admission": admission.model_dump(mode="json"),
        "input": {"sha256": SOURCE_SHA256, "bytes": len(image), "width": 768, "height": 512,
                  "source": "existing local synthetic shapes illustration"},
        "catalog_flags": {key: candidate.get(key) for key in ("free", "json_output", "structured_outputs")},
        "generation_attempts_before": 0, "quota_after": {"status": "not_observed"},
        "diagnostic_replay": diagnostic, "prior_receipt_sha256": prior_digest}
    ledger = QualificationLedger(directory) if (directory / LEDGER_NAME).exists() else QualificationLedger.initialize(directory)
    record["generation_attempts_before"] = len(ledger.records())
    _save(path, record, initial=True)
    responses = []
    def observed_transport(*args, **kwargs):
        started = time.monotonic()
        response = transport(*args, **kwargs)
        responses.append((response, time.monotonic() - started))
        return response
    guard = GuardedQualificationTransport(ledger, admission, transport=observed_transport)
    provider = OpenAICompatibleVision(settings, catalog=None, transport=guard)
    started = time.monotonic()
    try:
        result = provider.inspect([image])
        record["status"] = "succeeded"
        record["result"] = result
    except (VisionInvalidOutput, VisionTimeout, VisionUnavailable) as error:
        record["status"] = {VisionInvalidOutput: "invalid_output", VisionTimeout: "timeout",
                            VisionUnavailable: "unavailable"}[type(error)]
        if isinstance(error, VisionUnavailable):
            record["reason_code"] = error.reason_code
    except Exception:
        record["status"] = "failed_closed"
    finally:
        record["request_seconds"] = time.monotonic() - started
        if responses:
            record["response"] = _response_evidence(responses[0][0], token)
            record["transport_seconds"] = responses[0][1]
            record["quota_after"] = _after_quota(record["response"])
        record["generation_attempts_after"] = len(ledger.records())
        record["finished_at"] = _now().isoformat()
        if _contains_secret(record, token):
            raise RuntimeError("Qualification record rejected as unsafe")
        _save(path, record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--authorized-synthetic", action="store_true")
    group.add_argument("--authorized-diagnostic", action="store_true")
    arguments = parser.parse_args()
    token = os.environ.pop("REKIT_INFERENCE_API_KEY", "")
    if not token:
        return 1
    try:
        record = run(DIRECTORY, token, diagnostic=arguments.authorized_diagnostic)
        return 0 if record["status"] == "succeeded" else 1
    except Exception:
        return 1  # No exception text, HTTP body, key or account detail reaches console.


if __name__ == "__main__":
    raise SystemExit(main())
