"""Opt-in, cached shared-service discovery; never generates or retries requests.

Run through scripts/run_tokenfactory.ps1 so the key stays in a backend process
and sanitized receipts inherit a restricted, Git-ignored directory ACL.
"""

import argparse
from datetime import UTC, datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time

from rekit.inference.adapters.openai_remote import (
    TOKENFACTORY_BASE, TOKENFACTORY_MIMO_MODEL, _contains_secret,
)
from rekit.inference.adapters.remote_transport import RemoteTransportError, get_tokenfactory
from rekit.inference.parsing import _invalid_constant, _unique_object


ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / ".secrets" / "tokenfactory" / "qualification"
MAX_BYTES = 128 * 1024
RESOURCES = {"usage": TOKENFACTORY_BASE + "/usage?include_recent=true", "models": TOKENFACTORY_BASE + "/models"}


def _now():
    return datetime.now(UTC).isoformat()


def _number(value, *, integer=False):
    allowed = (int,) if integer else (int, float)
    if type(value) not in allowed or not 0 <= value <= 2**53 - 1 or not math.isfinite(value):
        raise ValueError("Invalid bounded counter")
    return value


def _identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}", value):
        raise ValueError("Invalid model identifier")
    return value


def _strings(value, allowed=None):
    if not isinstance(value, list) or len(value) > 32:
        raise ValueError("Invalid capability list")
    items = [_identifier(item) for item in value]
    if len(set(items)) != len(items) or (allowed is not None and not set(items) <= allowed):
        raise ValueError("Invalid capability list")
    return items


def sanitize_catalog(data):
    if not isinstance(data, dict) or not isinstance(data.get("data"), list) or not 1 <= len(data["data"]) <= 256:
        raise ValueError("Invalid catalog envelope")
    result = []
    for item in data["data"]:
        if not isinstance(item, dict):
            raise ValueError("Invalid model entry")
        architecture = item.get("architecture", {})
        if not isinstance(architecture, dict):
            raise ValueError("Invalid model architecture")
        entry = {"id": _identifier(item.get("id"))}
        for field in ("input_modalities", "output_modalities"):
            if field in architecture:
                entry[field] = _strings(architecture[field])
        if "supported_parameters" in item:
            entry["supported_parameters"] = _strings(item["supported_parameters"])
        for field in ("free", "json_output", "structured_outputs"):
            if field in item:
                if type(item[field]) is not bool:
                    raise ValueError("Invalid capability flag")
                entry[field] = item[field]
        if "context_length" in item:
            entry["context_length"] = _number(item["context_length"], integer=True)
        if "stability" in item:
            if item["stability"] not in ("stable", "beta", "unstable", "experimental"):
                raise ValueError("Invalid stability flag")
            entry["stability"] = item["stability"]
        providers = item.get("providers", [])
        if not isinstance(providers, list) or len(providers) > 32:
            raise ValueError("Invalid provider list")
        entry["providers"] = []
        for provider in providers:
            if not isinstance(provider, dict):
                raise ValueError("Invalid provider entry")
            safe = {}
            for field in ("providerId", "externalId"):
                if field in provider:
                    safe[field] = _identifier(provider[field])
            for field in ("vision", "reasoning", "tools", "streaming"):
                if field in provider:
                    if type(provider[field]) is not bool:
                        raise ValueError("Invalid provider capability")
                    safe[field] = provider[field]
            entry["providers"].append(safe)
        result.append(entry)
    if len({entry["id"] for entry in result}) != len(result):
        raise ValueError("Duplicate model ID")
    return result


def sanitize_usage(data):
    if not isinstance(data, dict) or data.get("status") not in ("ok", "not_configured", "not_available"):
        raise ValueError("Invalid usage status")
    result = {"status": data["status"]}
    if data["status"] != "ok":
        return result  # A zeroed unavailable response is not zero actual usage.
    for field in ("rpm_limit", "daily_cost_limit_usd", "daily_cost_used_usd", "daily_cost_remaining_usd"):
        if field in data:
            result[field] = _number(data[field], integer=field == "rpm_limit")
    if "daily_reset_at" in data:
        value = data["daily_reset_at"]
        if not isinstance(value, str) or len(value) > 64:
            raise ValueError("Invalid reset timestamp")
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError("Unzoned reset timestamp")
        result["daily_reset_at"] = parsed.isoformat()
    today = data.get("today", {})
    if not isinstance(today, dict):
        raise ValueError("Invalid usage aggregate")
    result["today"] = {field: _number(today[field], integer=field != "cost")
                       for field in ("requests", "errors", "total_tokens", "prompt_tokens", "completion_tokens", "cost")
                       if field in today}
    return result  # No account identity, recent-call list, arbitrary messages or headers.


def _save(path, record, *, initial=False):
    encoded = json.dumps(record, indent=2, ensure_ascii=True, allow_nan=False) + "\n"
    if initial:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
    else:
        temporary = path.with_suffix(".pending")
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)


def _catalog_candidate(models):
    candidate = next((item for item in models if item["id"] == TOKENFACTORY_MIMO_MODEL), None)
    ready = (candidate is not None and candidate.get("free") is True
             and "image" in candidate.get("input_modalities", [])
             and "text" in candidate.get("output_modalities", [])
             and candidate.get("structured_outputs") is True
             and "response_format" in candidate.get("supported_parameters", []))
    return {"model_id": TOKENFACTORY_MIMO_MODEL, "catalog_requirements_met": bool(ready),
            "single_image_execution": "not_tested", "joint_two_image_execution": "not_tested",
            "rekit_schema_execution": "not_tested", "weight_revision": None,
            "processor_revision": None, "gpu": "not_attested", "runtime": "not_attested"}


def discover(directory, token, *, transport=get_tokenfactory, catalog_after_unusable_usage=False):
    """One cached operation: quota alias then catalog, at most two GETs, no POST.

    Existing receipts (including interrupted or failed attempts) never trigger an
    implicit retry. A fresh live qualification requires an explicit operator decision.
    """
    prior_digest = None
    if catalog_after_unusable_usage:
        prior_path = directory / "discovery.json"
        if prior_path.is_symlink() or prior_path.stat().st_size > 256 * 1024:
            raise ValueError("Invalid prior discovery receipt")
        prior_raw = prior_path.read_bytes()
        prior = json.loads(prior_raw, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        calls = prior.get("calls", [])
        if (prior.get("status") != "blocked" or len(calls) != 1
                or calls[0].get("endpoint") != RESOURCES["usage"]
                or calls[0].get("status") != "invalid_response" or calls[0].get("http_status") != 200
                or calls[0].get("validation_stage") == "credential_echo"):
            raise ValueError("Catalog-only discovery requires reviewed unusable usage alias evidence")
        prior_digest = hashlib.sha256(prior_raw).hexdigest()
    path = directory / ("catalog-discovery.json" if catalog_after_unusable_usage else "discovery.json")
    if path.exists():
        if path.is_symlink() or path.stat().st_size > 256 * 1024:
            raise ValueError("Invalid discovery receipt")
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    if not token or len(token) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ValueError("Missing private credential")
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("A protected output directory must already exist")
    record = {"format_version": 1, "started_at": _now(), "status": "incomplete", "calls": [],
              "generation_attempts": 0, "maximum_generation_attempts": 6,
              "usage_alias_verified": False, "other_host_contacted": False}
    if prior_digest:
        record["reviewed_prior_receipt_sha256"] = prior_digest
    _save(path, record, initial=True)
    quota = None
    models = []
    for resource in (("models",) if catalog_after_unusable_usage else ("usage", "models")):
        call = {"method": "GET", "endpoint": RESOURCES[resource], "started_at": _now(), "status": "pending"}
        record["calls"].append(call)
        _save(path, record)  # Persist the attempted call before network work.
        started = time.monotonic()
        try:
            response = transport(resource, token, timeout=30, max_response_bytes=MAX_BYTES)
            content_type = response.content_type.split(";", 1)[0].strip().lower()
            call.update(http_status=response.status, retry_after_seconds=response.retry_after_seconds,
                        quota_headers=response.quota_headers or {}, response_bytes=len(response.body),
                        content_kind=content_type if content_type in ("application/json", "text/html") else "other")
            if response.status in (401, 403):
                call["status"] = "authentication_rejected"
            elif response.status == 429:
                call["status"] = "rate_limited"
            elif response.status == 404 and resource == "usage":
                call["status"] = "usage_alias_unavailable"
            elif response.status != 200:
                call["status"] = "request_rejected"
            else:
                call["validation_stage"] = "size_or_content_type"
                if content_type != "application/json" or len(response.body) > MAX_BYTES:
                    raise ValueError("Invalid discovery response")
                call["validation_stage"] = "json_decoding"
                decoded = response.body.decode("utf-8")
                if _contains_secret(decoded, token):
                    call["validation_stage"] = "credential_echo"
                    raise ValueError("Credential echo")
                data = json.loads(decoded, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
                if _contains_secret(data, token):
                    call["validation_stage"] = "credential_echo"
                    raise ValueError("Credential echo")
                call["validation_stage"] = resource + "_schema"
                sanitized = sanitize_usage(data) if resource == "usage" else sanitize_catalog(data)
                call.update(status="succeeded", response_sha256=hashlib.sha256(response.body).hexdigest(), data=sanitized)
                call.pop("validation_stage", None)
                if resource == "usage":
                    record["usage_alias_verified"] = True
                    if sanitized["status"] != "ok":
                        call["status"] = "account_or_quota_unavailable"
                    elif sanitized.get("daily_cost_remaining_usd") == 0:
                        call["status"] = "quota_exhausted"
                    elif sanitized.get("daily_cost_remaining_usd", 0) > 0:
                        quota = {"source": "usage", "measurement": sanitized}
                else:
                    models = sanitized
                headers = response.quota_headers or {}
                if quota is None and headers.get("daily_usd_remaining", 0) > 0:
                    quota = {"source": resource + "_headers", "measurement": headers}
            headers = response.quota_headers or {}
            if call["status"] in ("succeeded", "usage_alias_unavailable"):
                if headers.get("daily_usd_remaining") == 0:
                    call["status"] = "quota_exhausted"
                elif headers.get("user_rpm_remaining") == 0:
                    call["status"] = "minute_capacity_exhausted"
        except RemoteTransportError as error:
            call.update(status="transport_failed", transport_code=error.code)
        except (ValueError, TypeError, UnicodeError, KeyError, RecursionError, AttributeError):
            call["status"] = "invalid_response"
        call["duration_seconds"] = round(time.monotonic() - started, 6)
        call["finished_at"] = _now()
        if call["status"] not in ("succeeded", "usage_alias_unavailable"):
            record["status"] = "blocked"
            _save(path, record)
            return record
        _save(path, record)
    record["candidate"] = _catalog_candidate(models)
    record["quota"] = quota
    record["status"] = "ready_for_single_image_qualification" if quota and record["candidate"]["catalog_requirements_met"] else "blocked"
    record["finished_at"] = _now()
    _save(path, record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--authorized-discovery", action="store_true")
    mode.add_argument("--catalog-after-unusable-usage", action="store_true")
    arguments = parser.parse_args()
    try:
        token = os.environ.pop("REKIT_INFERENCE_API_KEY", "")
        result = discover(DIRECTORY, token, catalog_after_unusable_usage=arguments.catalog_after_unusable_usage)
        receipt = "catalog-discovery.json" if arguments.catalog_after_unusable_usage else "discovery.json"
        print(json.dumps({"status": result["status"], "authenticated_get_attempts": len(result["calls"]),
                          "generation_attempts": 0, "receipt": str(DIRECTORY / receipt)}))
        return 0 if result["status"] == "ready_for_single_image_qualification" else 2
    except Exception:
        print('{"status":"discovery_failed","detail":"Inspect sanitized local receipt; no automatic retry."}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
