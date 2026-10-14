"""No-network discovery checks: sanitized caching, stopping and capability gates."""

from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path

import pytest

from rekit.inference.adapters.remote_transport import HttpResponse, RemoteTransportError


TOKEN = "synthetic-discovery-test-token-not-a-credential"
MODEL = {"id": "MiMo-V2.6-Flash", "architecture": {"input_modalities": ["text", "image"], "output_modalities": ["text"]},
         "supported_parameters": ["response_format", "max_tokens"], "json_output": True,
         "structured_outputs": True, "free": True, "providers": [{"providerId": "test-provider", "vision": True}],
         "description": "This arbitrary field must not be retained."}
USAGE = {"status": "ok", "rpm_limit": 20, "daily_cost_remaining_usd": 5.5,
         "today": {"requests": 2, "prompt_tokens": 4}, "recent": [{"private": "drop"}], "account_email": "drop@example.test"}


@pytest.fixture
def discovery():
    spec = spec_from_file_location("tokenfactory_discovery_tests", Path(__file__).parents[2] / "evaluation/tokenfactory_discovery.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def response(data, status=200, **kwargs):
    return HttpResponse(status, json.dumps(data).encode(), "application/json", **kwargs)


def test_discovery_is_cached_sanitized_and_never_generates(discovery, tmp_path):
    calls = []
    def transport(resource, token, **bounds):
        assert token == TOKEN and bounds == {"timeout": 30, "max_response_bytes": 128 * 1024}
        persisted = json.loads((tmp_path / "discovery.json").read_text())
        assert persisted["calls"][-1]["status"] == "pending"
        calls.append(resource)
        return response(USAGE if resource == "usage" else {"data": [MODEL]})
    first = discovery.discover(tmp_path, TOKEN, transport=transport)
    second = discovery.discover(tmp_path, TOKEN, transport=lambda *a, **k: pytest.fail("Cache must avoid another request"))
    assert first == second and calls == ["usage", "models"]
    assert first["status"] == "ready_for_single_image_qualification"
    assert first["generation_attempts"] == 0 and first["maximum_generation_attempts"] == 6
    assert first["candidate"]["joint_two_image_execution"] == "not_tested"
    assert first["candidate"]["weight_revision"] is None
    saved = (tmp_path / "discovery.json").read_text()
    assert TOKEN not in saved and "drop@example.test" not in saved and "description" not in saved and "recent" not in first["quota"]["measurement"]


@pytest.mark.parametrize("status,reason", [(401, "authentication_rejected"), (403, "authentication_rejected"),
                                         (429, "rate_limited"), (400, "request_rejected"), (502, "request_rejected")])
def test_access_failure_stops_without_catalog_or_retry(discovery, tmp_path, status, reason):
    calls = []
    def transport(resource, token, **kwargs):
        calls.append(resource)
        return response({"error": TOKEN}, status, retry_after_seconds=60 if status == 429 else None)
    record = discovery.discover(tmp_path, TOKEN, transport=transport)
    assert calls == ["usage"] and record["status"] == "blocked"
    assert record["calls"][0]["status"] == reason
    assert TOKEN not in (tmp_path / "discovery.json").read_text()
    discovery.discover(tmp_path, TOKEN, transport=lambda *a, **k: pytest.fail("No implicit retry after failure"))


def test_unverified_alias_can_use_same_host_catalog_quota_headers(discovery, tmp_path):
    def transport(resource, token, **kwargs):
        if resource == "usage":
            return response({"detail": "Not found"}, 404)
        return response({"data": [MODEL]}, quota_headers={"daily_usd_remaining": 3.75, "user_rpm_remaining": 18})
    record = discovery.discover(tmp_path, TOKEN, transport=transport)
    assert record["status"] == "ready_for_single_image_qualification"
    assert record["usage_alias_verified"] is False and record["other_host_contacted"] is False
    assert record["quota"]["source"] == "models_headers"


@pytest.mark.parametrize("usage", [{"status": "not_configured"}, {"status": "not_available", "daily_cost_remaining_usd": 0}])
def test_incomplete_account_or_quota_status_stops(discovery, tmp_path, usage):
    calls = []
    def transport(resource, token, **kwargs):
        calls.append(resource)
        return response(usage)
    record = discovery.discover(tmp_path, TOKEN, transport=transport)
    assert calls == ["usage"] and record["status"] == "blocked"
    assert record["calls"][0]["data"] == {"status": usage["status"]}


def test_missing_actual_quota_never_uses_documentation_examples(discovery, tmp_path):
    record = discovery.discover(tmp_path, TOKEN, transport=lambda resource, *a, **k:
                                response({"data": [MODEL]}) if resource == "models" else response({}, 404))
    assert record["status"] == "blocked" and record["quota"] is None
    assert record["candidate"]["catalog_requirements_met"] is True


def test_explicit_exhaustion_cannot_be_overridden_by_positive_headers(discovery, tmp_path):
    calls = []
    def transport(resource, token, **kwargs):
        calls.append(resource)
        return response({**USAGE, "daily_cost_remaining_usd": 0}, quota_headers={"daily_usd_remaining": 10})
    record = discovery.discover(tmp_path, TOKEN, transport=transport)
    assert calls == ["usage"] and record["status"] == "blocked"
    assert record["calls"][0]["status"] == "quota_exhausted"


@pytest.mark.parametrize("headers,status", [({"daily_usd_remaining": 0}, "quota_exhausted"),
                                           ({"user_rpm_remaining": 0}, "minute_capacity_exhausted")])
def test_later_header_exhaustion_blocks_prior_positive_quota(discovery, tmp_path, headers, status):
    def transport(resource, token, **kwargs):
        return response(USAGE) if resource == "usage" else response({"data": [MODEL]}, quota_headers=headers)
    record = discovery.discover(tmp_path, TOKEN, transport=transport)
    assert record["status"] == "blocked" and len(record["calls"]) == 2
    assert record["calls"][-1]["status"] == status


@pytest.mark.parametrize("field,value", [("free", False), ("structured_outputs", False),
                                        ("id", "MiMo-V2.6-Flash-Other"), ("supported_parameters", [])])
def test_candidate_requires_exact_free_schema_contract(discovery, field, value):
    model = deepcopy(MODEL)
    model[field] = value
    assert discovery._catalog_candidate(discovery.sanitize_catalog({"data": [model]}))["catalog_requirements_met"] is False


@pytest.mark.parametrize("data", [{"status": "ok", "rpm_limit": True}, {"status": "ok", "daily_cost_remaining_usd": float("nan")},
                                {"status": "ok", "daily_cost_used_usd": -1}, {"status": "ok", "daily_reset_at": "2026-10-15"}])
def test_bad_usage_values_rejected(discovery, data):
    with pytest.raises(ValueError):
        discovery.sanitize_usage(data)


@pytest.mark.parametrize("data", [{"data": [MODEL, MODEL]}, {"data": [{**MODEL, "free": 1}]},
                                {"data": [{**MODEL, "id": "bad\nidentifier"}]}])
def test_ambiguous_or_malformed_catalog_rejected(discovery, data):
    with pytest.raises(ValueError):
        discovery.sanitize_catalog(data)


def test_credential_echo_never_saved_even_in_dropped_fields(discovery, tmp_path):
    record = discovery.discover(tmp_path, TOKEN, transport=lambda *a, **k: response({**USAGE, "dropped": TOKEN}))
    assert record["calls"][0]["status"] == "invalid_response"
    assert TOKEN not in (tmp_path / "discovery.json").read_text()
    assert "response_sha256" not in record["calls"][0]
    with pytest.raises(ValueError):
        discovery.discover(tmp_path, TOKEN, transport=lambda *a, **k: pytest.fail("Echo must stop testing"),
                           catalog_after_unusable_usage=True)


def test_transport_timeout_is_saved_without_retry(discovery, tmp_path):
    def transport(*args, **kwargs):
        raise RemoteTransportError("timeout")
    record = discovery.discover(tmp_path, TOKEN, transport=transport)
    assert len(record["calls"]) == 1
    assert record["calls"][0]["transport_code"] == "timeout"
    assert record["status"] == "blocked"


def test_interrupted_attempt_does_not_restart(discovery, tmp_path):
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        discovery.discover(tmp_path, TOKEN, transport=interrupted)
    record = discovery.discover(tmp_path, TOKEN, transport=lambda *a, **k: pytest.fail("Interrupted attempts require review"))
    assert record["status"] == "incomplete" and record["calls"][0]["status"] == "pending"


def test_missing_key_has_no_receipt_or_network(discovery, tmp_path):
    with pytest.raises(ValueError):
        discovery.discover(tmp_path, "", transport=lambda *a, **k: pytest.fail("No credential"))
    assert not list(tmp_path.iterdir())


def test_reviewed_catalog_operation_never_retries_usage_and_preserves_prior(discovery, tmp_path):
    prior = discovery.discover(tmp_path, TOKEN, transport=lambda *a, **k: HttpResponse(200, b"<html>portal</html>", "text/html"))
    assert prior["status"] == "blocked"
    assert prior["calls"][0]["content_kind"] == "text/html"
    assert prior["calls"][0]["validation_stage"] == "size_or_content_type"
    original = (tmp_path / "discovery.json").read_bytes()
    calls = []
    def transport(resource, token, **kwargs):
        calls.append(resource)
        return response({"data": [MODEL]}, quota_headers={"daily_usd_remaining": 3.75})
    result = discovery.discover(tmp_path, TOKEN, transport=transport, catalog_after_unusable_usage=True)
    assert calls == ["models"] and result["status"] == "ready_for_single_image_qualification"
    assert (tmp_path / "discovery.json").read_bytes() == original
    assert len(result["reviewed_prior_receipt_sha256"]) == 64
    assert discovery.discover(tmp_path, TOKEN, transport=lambda *a, **k: pytest.fail("No repeat GET"),
                              catalog_after_unusable_usage=True) == result


@pytest.mark.parametrize("status", [401, 403, 429, 502])
def test_catalog_followup_cannot_bypass_rejected_access_or_limits(discovery, tmp_path, status):
    discovery.discover(tmp_path, TOKEN, transport=lambda *a, **k: response({}, status))
    with pytest.raises(ValueError):
        discovery.discover(tmp_path, TOKEN, transport=lambda *a, **k: pytest.fail("Must stop authenticated testing"),
                           catalog_after_unusable_usage=True)
    assert not (tmp_path / "catalog-discovery.json").exists()


def _catalog_receipt(directory, **changes):
    call = {"endpoint": "https://developer.amd.com.cn/radeon/api/v1/models", "status": "succeeded", "http_status": 200}
    call.update(changes)
    (directory / "catalog-discovery.json").write_text(json.dumps({"status": "blocked", "calls": [call]}))


def test_separately_authorized_quota_is_one_cached_sanitized_get(discovery, tmp_path):
    _catalog_receipt(tmp_path)
    calls = []
    def transport(token, **bounds):
        assert token == TOKEN and bounds == {"timeout": 30, "max_response_bytes": 128 * 1024}
        receipt = json.loads((tmp_path / "quota-discovery.json").read_text())
        assert receipt["calls"][0]["status"] == "pending"
        calls.append(1)
        return response(USAGE)
    first = discovery.discover_quota(tmp_path, TOKEN, transport=transport)
    second = discovery.discover_quota(tmp_path, TOKEN, transport=lambda *a, **k: pytest.fail("One authorized GET only"))
    assert first == second and calls == [1]
    assert first["status"] == "quota_available"
    assert first["schema_execution"] == "not_tested" and first["generation_attempts"] == 0
    assert first["calls"][0]["endpoint"] == "https://radeon-global.anruicloud.com/api/profile/model-usage?include_recent=true"
    assert first["quota"]["daily_cost_remaining_usd"] == 5.5
    assert "drop@example.test" not in (tmp_path / "quota-discovery.json").read_text()


@pytest.mark.parametrize("status,reason", [(401, "authentication_rejected"), (403, "authentication_rejected"),
                                         (429, "rate_limited"), (502, "request_rejected")])
def test_official_quota_failure_stops_and_is_never_retried(discovery, tmp_path, status, reason):
    _catalog_receipt(tmp_path)
    first = discovery.discover_quota(tmp_path, TOKEN, transport=lambda *a, **k: response({"error": TOKEN}, status))
    assert first["status"] == "blocked" and first["calls"][0]["status"] == reason
    assert TOKEN not in (tmp_path / "quota-discovery.json").read_text()
    assert discovery.discover_quota(tmp_path, TOKEN, transport=lambda *a, **k: pytest.fail("No retry")) == first


@pytest.mark.parametrize("usage,reason", [({"status": "not_configured"}, "account_or_quota_unavailable"),
                                         ({"status": "not_available"}, "account_or_quota_unavailable"),
                                         ({"status": "ok", "daily_cost_remaining_usd": 0}, "quota_exhausted"),
                                         ({"status": "ok"}, "quota_unknown"),
                                         ({"status": "ok", "daily_cost_remaining_usd": 2}, "quota_unknown"),
                                         ({"status": "ok", "daily_cost_remaining_usd": 2, "rpm_limit": 0}, "minute_capacity_exhausted")])
def test_official_quota_requires_actual_capacity(discovery, tmp_path, usage, reason):
    _catalog_receipt(tmp_path)
    record = discovery.discover_quota(tmp_path, TOKEN, transport=lambda *a, **k: response(usage))
    assert record["status"] == "blocked" and record["quota"] is None
    assert record["calls"][0]["status"] == reason


def test_official_quota_credential_echo_rejected(discovery, tmp_path):
    _catalog_receipt(tmp_path)
    record = discovery.discover_quota(tmp_path, TOKEN, transport=lambda *a, **k: response({**USAGE, "discarded": TOKEN}))
    assert record["calls"][0]["validation_stage"] == "credential_echo"
    assert TOKEN not in (tmp_path / "quota-discovery.json").read_text()


def test_official_quota_cannot_bypass_failed_catalog(discovery, tmp_path):
    _catalog_receipt(tmp_path, http_status=401, status="authentication_rejected")
    with pytest.raises(ValueError):
        discovery.discover_quota(tmp_path, TOKEN, transport=lambda *a, **k: pytest.fail("Stop after rejection"))
    assert not (tmp_path / "quota-discovery.json").exists()


def test_official_quota_interrupted_attempt_stays_charged(discovery, tmp_path):
    _catalog_receipt(tmp_path)
    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        discovery.discover_quota(tmp_path, TOKEN, transport=interrupted)
    result = discovery.discover_quota(tmp_path, TOKEN, transport=lambda *a, **k: pytest.fail("No uncertain repeat"))
    assert result["status"] == "incomplete" and len(result["calls"]) == 1


def test_official_quota_transport_failure_stays_charged(discovery, tmp_path):
    _catalog_receipt(tmp_path)
    def transport(*args, **kwargs):
        raise RemoteTransportError("timeout")
    result = discovery.discover_quota(tmp_path, TOKEN, transport=transport)
    assert result["calls"][0]["transport_code"] == "timeout"
    assert result["status"] == "blocked" and result["quota"] is None
