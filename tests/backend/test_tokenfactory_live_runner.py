"""Offline tests of the live runner; controlled responses are not AMD execution."""

from datetime import UTC, datetime, timedelta
import hashlib
import importlib
from io import BytesIO
import json
from pathlib import Path

from PIL import Image
import pytest

from rekit.inference.adapters.remote_transport import HttpResponse


TOKEN = "controlled-runner-test-token-not-a-real-credential"
NOW = datetime.fromisoformat("2026-10-14T16:43:27+00:00")
OUTPUT = {"observations": [{"image_indices": [1], "kind": "appearance", "text": "A synthetic colored shape."}],
          "candidates": [], "uncertainties": ["The illustration cannot establish a product identity."], "additional_views": []}


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[2] / "evaluation"))
    module = importlib.import_module("run_tokenfactory_qualification")
    guard_module = importlib.import_module("tokenfactory_qualification")
    monkeypatch.setattr(module, "_now", lambda: NOW)
    monkeypatch.setattr(guard_module, "_now", lambda: NOW)
    with Image.new("RGB", (24, 18), "red") as image, BytesIO() as output:
        image.save(output, format="PNG")
        raw = output.getvalue()
    monkeypatch.setattr(module, "_image", lambda: raw)
    monkeypatch.setattr(module, "SOURCE_SHA256", hashlib.sha256(raw).hexdigest())
    return module


@pytest.fixture
def evidence(runner, tmp_path):
    dashboard = {
        "source": "operator_reported_check_usage", "reported_at": "2026-10-14T16:43:27Z",
        "expires_at": "2026-10-14T16:58:00Z", "next_reset_at": "2026-10-14T17:00:00Z",
        "reset_display": "01:00 Asia/Shanghai", "allowance_unit": "pt", "daily_allowance": 1,
        "spent_today": 0, "remaining_allowance": 1, "rpm_limit": 20, "requests_today": 0,
        "errors_today": 0, "tokens_today": 0, "signed_in": True, "key_issued": True,
        "api_verification": None, "dashboard_error": None, "initial_probe_authorized": True,
        "post_probe_quota_check_required": True,
    }
    catalog = {"status": "blocked", "calls": [{"status": "succeeded", "http_status": 200,
        "endpoint": runner.TOKENFACTORY_BASE + "/models", "data": [{"id": runner.TOKENFACTORY_MIMO_MODEL,
            "input_modalities": ["image", "text"], "output_modalities": ["text"],
            "free": False, "structured_outputs": False, "json_output": True}]}]}
    (tmp_path / "dashboard-evidence.json").write_text(json.dumps(dashboard), encoding="utf-8")
    (tmp_path / "catalog-discovery.json").write_text(json.dumps(catalog), encoding="utf-8")
    return tmp_path


def response(runner, *, raw=None, status=200, headers=None, ensure_ascii=True):
    envelope = {"model": runner.TOKENFACTORY_MIMO_MODEL,
        "choices": [{"index": 0, "finish_reason": "stop", "message": {
            "role": "assistant", "content": json.dumps(OUTPUT) if raw is None else raw}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 25, "total_tokens": 125,
                  "prompt_tokens_details": {"image_tokens": 40}}}
    return HttpResponse(status, json.dumps(envelope, ensure_ascii=ensure_ascii).encode(), "application/json", quota_headers=headers)


def test_strict_success_preserves_real_provider_contract_and_never_repeats_cached_request(runner, evidence):
    calls = []
    def transport(url, token, body, **bounds):
        assert token == TOKEN and url == runner.TOKENFACTORY_ENDPOINT
        payload = json.loads(body)
        assert payload["model"] == runner.TOKENFACTORY_MIMO_MODEL
        assert payload["response_format"]["type"] == "json_schema"
        assert payload["response_format"]["json_schema"]["strict"] is True
        assert payload["reasoning_effort"] == "none" and payload["max_tokens"] == 512
        calls.append(body)
        return response(runner)
    record = runner.run(evidence, TOKEN, transport=transport)
    assert record["status"] == "succeeded" and len(calls) == 1
    assert record["generation_attempts_before"] == 0 and record["generation_attempts_after"] == 1
    assert record["result"]["provider"] == "amd-tokenfactory" and record["result"]["device"] == "remote"
    assert record["result"]["model_revision"] is None
    assert record["result"]["metrics"]["input_sha256"] == [runner.SOURCE_SHA256]
    assert record["result"]["metrics"]["usage_image_tokens"] == 40
    assert json.loads(record["result"]["text"]) == OUTPUT
    assert record["admission"]["quota"]["api_access_verified"] is None
    assert record["catalog_flags"] == {"free": False, "json_output": True, "structured_outputs": False}
    assert record["quota_after"]["status"] == "uncertain_stop"
    assert record["quota_after"]["another_request_authorized_by_this_runner"] is False
    cached = runner.run(evidence, TOKEN, transport=lambda *a, **k: pytest.fail("No second POST"))
    assert cached == record
    assert len(runner.QualificationLedger(evidence).records()) == 1


@pytest.mark.parametrize("raw", ["{invalid JSON", json.dumps(OUTPUT | {"extra": "not allowed"})])
def test_invalid_output_retains_bounded_model_diagnostics_but_is_not_accepted(runner, evidence, raw):
    record = runner.run(evidence, TOKEN, transport=lambda *a, **k: response(runner, raw=raw))
    assert record["status"] == "invalid_output" and "result" not in record
    assert record["response"]["raw_model_text"] == raw
    assert record["response"]["raw_model_text_sha256"] == hashlib.sha256(raw.encode()).hexdigest()
    assert record["response"]["usage"]["usage_total_tokens"] == 125
    assert record["generation_attempts_after"] == 1 and record["quota_after"]["status"] == "uncertain_stop"
    assert runner.run(evidence, TOKEN, transport=lambda *a, **k: pytest.fail("No repair retry")) == record


@pytest.mark.parametrize("raw,ensure_ascii,reason", [
    ("\U0001f7e5" * 30_000, False, "serialized_size_limit"),
    ("\ud800", True, "invalid_unicode"),
], ids=["supplementary-unicode-size", "lone-surrogate"])
def test_unusable_unicode_output_keeps_terminal_receipt_bounded_and_cacheable(
        runner, evidence, raw, ensure_ascii, reason):
    received = response(runner, raw=raw, ensure_ascii=ensure_ascii)
    assert len(received.body) <= 128 * 1024
    record = runner.run(evidence, TOKEN, transport=lambda *a, **k: received)
    assert record["status"] == "invalid_output" and "result" not in record
    diagnostics = record["response"]
    assert diagnostics["raw_model_text_omitted"] == reason
    assert diagnostics["raw_model_text_characters"] == len(raw)
    assert diagnostics["raw_model_text_serialized_bytes"] == len(json.dumps(raw, ensure_ascii=True).encode("ascii"))
    assert diagnostics["response_sha256"] == hashlib.sha256(received.body).hexdigest()
    assert "raw_model_text" not in diagnostics
    if reason == "serialized_size_limit":
        assert diagnostics["raw_model_text_sha256"] == hashlib.sha256(raw.encode("utf-8")).hexdigest()
    else:
        assert "raw_model_text_sha256" not in diagnostics
    path = evidence / runner.RECEIPT_NAME
    saved = path.read_bytes()
    assert len(saved) < 256 * 1024
    assert runner.run(evidence, TOKEN, transport=lambda *a, **k: pytest.fail("Cached failure must not POST")) == record
    assert path.read_bytes() == saved
    assert len(runner.QualificationLedger(evidence).records()) == 1


@pytest.mark.parametrize("status,reason", [(401, "authentication"), (429, "rate_limited")])
def test_authentication_or_rate_limit_response_stops_and_stays_cached(runner, evidence, status, reason):
    record = runner.run(evidence, TOKEN, transport=lambda *a, **k:
        HttpResponse(status, b'{"error":"controlled rejection"}', "application/json", retry_after_seconds=60))
    assert record["status"] == "unavailable" and record["reason_code"] == reason
    assert record["generation_attempts_after"] == 1 and record["response"]["http_status"] == status
    assert record["response"]["retry_after_seconds"] == 60 and "raw_model_text" not in record["response"]
    assert runner.run(evidence, TOKEN, transport=lambda *a, **k: pytest.fail("No rejected-request retry")) == record
    assert runner.QualificationLedger(evidence).records()[0]["http_status"] == status


@pytest.mark.parametrize("escaped", [False, True])
def test_response_credential_echo_never_enters_receipt_or_ledger(runner, evidence, escaped):
    raw = ''.join(f"\\u{ord(char):04x}" for char in TOKEN) if escaped else TOKEN
    body = ('{"ignored":"' + raw + '"}').encode()
    record = runner.run(evidence, TOKEN, transport=lambda *a, **k: HttpResponse(200, body, "application/json"))
    assert record["status"] == "invalid_output"
    assert record["response"] == {"http_status": 200, "body_discarded": "credential_echo"}
    assert TOKEN not in json.dumps(record) and raw not in json.dumps(record)
    assert runner.QualificationLedger(evidence).records()[0]["response_sha256"] is None
    for path in (evidence / runner.RECEIPT_NAME, evidence / runner.LEDGER_NAME):
        assert TOKEN.encode() not in path.read_bytes() and raw.encode() not in path.read_bytes()


def test_expired_dashboard_evidence_cannot_make_actual_post(runner, evidence, monkeypatch):
    expired = datetime(2026, 10, 14, 16, 58, tzinfo=UTC)
    monkeypatch.setattr(runner, "_now", lambda: expired)
    monkeypatch.setattr(importlib.import_module("tokenfactory_qualification"), "_now", lambda: expired)
    record = runner.run(evidence, TOKEN, transport=lambda *a, **k: pytest.fail("Expired quota must not POST"))
    assert record["status"] == "failed_closed" and record["generation_attempts_after"] == 0
    assert "response" not in record and record["quota_after"]["status"] == "not_observed"


def test_provider_usd_label_never_converts_or_spends_dashboard_points(runner, evidence):
    headers = {"daily_usd_remaining": 0.75, "daily_reset_unix": int(datetime(2026, 10, 14, 17, 0, tzinfo=UTC).timestamp()),
               "user_rpm_remaining": 19}
    record = runner.run(evidence, TOKEN, transport=lambda *a, **k: response(runner, headers=headers))
    assert record["admission"]["quota"]["allowance_unit"] == "pt"
    assert record["admission"]["quota"]["remaining_allowance"] == 1.0
    assert record["quota_after"]["status"] == "fresh_header_evidence"
    assert record["quota_after"]["reported_units"] == "provider_USD_label"
    assert record["quota_after"]["conversion_from_dashboard_pt"] is None
    assert record["quota_after"]["consumption_in_pt"] is None
    assert record["quota_after"]["another_request_authorized_by_this_runner"] is False


def rejection_headers():
    return {"daily_usd_remaining": 1.0, "user_rpm_remaining": 19,
            "daily_reset_unix": int(datetime(2026, 10, 14, 17, 0, tzinfo=UTC).timestamp())}


def rejection_response(headers=None):
    return HttpResponse(400, json.dumps({"detail": {"error": {
        "code": "invalid_json_schema", "type": "invalid_request_error", "param": "response_format",
        "message": "Unsupported anyOf in response_format for private-account@example.test",
    }}}).encode(), "application/json", quota_headers=headers)


def test_explicit_diagnostic_replays_identical_body_once_and_preserves_first_receipt(runner, evidence):
    calls = []
    def transport(url, token, body, **bounds):
        assert token == TOKEN and url == runner.TOKENFACTORY_ENDPOINT
        calls.append(body)
        return rejection_response(rejection_headers())
    first = runner.run(evidence, TOKEN, transport=transport)
    assert first["status"] == "unavailable" and first["reason_code"] == "unsupported"
    original = (evidence / runner.RECEIPT_NAME).read_bytes()
    diagnostic = runner.run(evidence, TOKEN, diagnostic=True, transport=transport)
    assert diagnostic["status"] == "unavailable" and diagnostic["diagnostic_replay"] is True
    assert diagnostic["generation_attempts_before"] == 1 and diagnostic["generation_attempts_after"] == 2
    assert len(calls) == 2 and calls[0] == calls[1]
    digest = hashlib.sha256(calls[0]).hexdigest()
    rows = runner.QualificationLedger(evidence).records()
    assert len(rows) == 2 and {row["request_sha256"] for row in rows} == {digest}
    assert diagnostic["admission"]["diagnostic_prior_request_sha256"] == digest
    assert diagnostic["prior_receipt_sha256"] == hashlib.sha256(original).hexdigest()
    assert diagnostic["admission"]["quota"]["diagnostic_replay_authorized"] is True
    assert (evidence / runner.RECEIPT_NAME).read_bytes() == original
    safe = diagnostic["response"]["error_diagnostics"]
    assert safe["code"] == "invalid_json_schema" and safe["type"] == "invalid_request_error"
    assert safe["param"] == "response_format" and safe["message_flags"] == ["unsupported"]
    assert "private-account@example.test" not in json.dumps(diagnostic)
    assert "message" not in safe and "raw_model_text" not in diagnostic["response"]
    assert runner.run(evidence, TOKEN, diagnostic=True, transport=lambda *a, **k: pytest.fail("No third request")) == diagnostic
    assert (evidence / runner.RECEIPT_NAME).read_bytes() == original
    assert len(runner.QualificationLedger(evidence).records()) == 2


@pytest.mark.parametrize("headers", [None, {"daily_usd_remaining": 1.0},
    {"daily_usd_remaining": 0.0, "user_rpm_remaining": 19, "daily_reset_unix": 1791997200},
    {"daily_usd_remaining": 1.0, "user_rpm_remaining": 0, "daily_reset_unix": 1791997200},
])
def test_diagnostic_without_positive_complete_quota_cannot_charge_or_send_second_request(runner, evidence, headers):
    runner.run(evidence, TOKEN, transport=lambda *a, **k: rejection_response(headers))
    original = (evidence / runner.RECEIPT_NAME).read_bytes()
    with pytest.raises(ValueError):
        runner.run(evidence, TOKEN, diagnostic=True, transport=lambda *a, **k: pytest.fail("Quota not established"))
    assert not (evidence / runner.DIAGNOSTIC_NAME).exists()
    assert len(runner.QualificationLedger(evidence).records()) == 1
    assert (evidence / runner.RECEIPT_NAME).read_bytes() == original


@pytest.mark.parametrize("field,value", [
    ("http_status", 200), ("http_status", 400.0),
    ("response_sha256", "0" * 64), ("response_sha256", None),
    ("response_bytes", -1), ("response_bytes", None), ("response_bytes", 1.0),
])
def test_diagnostic_response_mismatch_stops_before_any_second_attempt(runner, evidence, field, value):
    first = runner.run(evidence, TOKEN, transport=lambda *a, **k: rejection_response(rejection_headers()))
    first["response"][field] = value
    path = evidence / runner.RECEIPT_NAME
    path.write_text(json.dumps(first), encoding="utf-8")
    preserved = path.read_bytes()
    rows = runner.QualificationLedger(evidence).records()
    with pytest.raises(ValueError, match="immutable HTTP 400 outcome"):
        runner.run(evidence, TOKEN, diagnostic=True, transport=lambda *a, **k: pytest.fail("Mismatched response must not POST"))
    assert runner.QualificationLedger(evidence).records() == rows
    assert not (evidence / runner.DIAGNOSTIC_NAME).exists()
    assert path.read_bytes() == preserved


def test_receipt_cannot_relabel_a_successful_ledger_outcome_as_http400(runner, evidence):
    first = runner.run(evidence, TOKEN, transport=lambda *a, **k: response(runner, headers=rejection_headers()))
    first.update(status="unavailable", reason_code="unsupported")
    first["response"]["http_status"] = 400
    path = evidence / runner.RECEIPT_NAME
    path.write_text(json.dumps(first), encoding="utf-8")
    preserved = path.read_bytes()
    rows = runner.QualificationLedger(evidence).records()
    assert rows[0]["http_status"] == 200
    with pytest.raises(ValueError, match="immutable HTTP 400 outcome"):
        runner.run(evidence, TOKEN, diagnostic=True, transport=lambda *a, **k: pytest.fail("Ledger was not HTTP400"))
    assert runner.QualificationLedger(evidence).records() == rows
    assert not (evidence / runner.DIAGNOSTIC_NAME).exists()
    assert path.read_bytes() == preserved


@pytest.mark.parametrize("finished,now_offset", [
    ((NOW - timedelta(microseconds=1)).isoformat(), 120),
    ((NOW + timedelta(seconds=61)).isoformat(), 120),
    ((NOW + timedelta(seconds=5)).isoformat(), 0),
    (NOW.replace(tzinfo=None).isoformat(), 120), ("invalid", 120), (None, 120),
])
def test_diagnostic_receipt_timestamp_cannot_refresh_or_predate_ledger_evidence(
        runner, evidence, monkeypatch, finished, now_offset):
    first = runner.run(evidence, TOKEN, transport=lambda *a, **k: rejection_response(rejection_headers()))
    first["finished_at"] = finished
    path = evidence / runner.RECEIPT_NAME
    path.write_text(json.dumps(first), encoding="utf-8")
    preserved = path.read_bytes()
    rows = runner.QualificationLedger(evidence).records()
    later = NOW + timedelta(seconds=now_offset)
    monkeypatch.setattr(runner, "_now", lambda: later)
    monkeypatch.setattr(importlib.import_module("tokenfactory_qualification"), "_now", lambda: later)
    with pytest.raises(ValueError, match="completion time"):
        runner.run(evidence, TOKEN, diagnostic=True, transport=lambda *a, **k: pytest.fail("Invalid receipt time must not POST"))
    assert runner.QualificationLedger(evidence).records() == rows
    assert not (evidence / runner.DIAGNOSTIC_NAME).exists()
    assert path.read_bytes() == preserved


def test_diagnostic_quota_age_uses_ledger_time_not_later_receipt_completion(runner, evidence, monkeypatch):
    first = runner.run(evidence, TOKEN, transport=lambda *a, **k: rejection_response(rejection_headers()))
    first["finished_at"] = (NOW + timedelta(seconds=5)).isoformat()
    path = evidence / runner.RECEIPT_NAME
    path.write_text(json.dumps(first), encoding="utf-8")
    preserved = path.read_bytes()
    later = NOW + timedelta(seconds=6)
    monkeypatch.setattr(runner, "_now", lambda: later)
    monkeypatch.setattr(importlib.import_module("tokenfactory_qualification"), "_now", lambda: later)
    diagnostic = runner.run(evidence, TOKEN, diagnostic=True,
                            transport=lambda *a, **k: rejection_response(rejection_headers()))
    rows = runner.QualificationLedger(evidence).records()
    assert len(rows) == 2 and rows[0]["finished_at"] == NOW.isoformat()
    assert datetime.fromisoformat(diagnostic["admission"]["quota"]["observed_at"]) == NOW
    assert diagnostic["prior_receipt_sha256"] == hashlib.sha256(preserved).hexdigest()
    assert path.read_bytes() == preserved


def test_error_diagnostics_only_copy_controlled_categories_not_provider_message_or_identity(runner):
    envelope = {"error": {"code": TOKEN, "type": "private-account@example.test", "param": "private-path",
                         "message": f"Invalid json_schema anyOf: {TOKEN} private-account@example.test"}}
    safe = runner._error_diagnostics(envelope)
    assert safe == {"message_mentions": ["anyOf", "json_schema"], "message_flags": ["invalid"]}
    assert TOKEN not in json.dumps(safe) and "@" not in json.dumps(safe)
    assert runner._error_diagnostics({"error": {"message": "x" * 2049}}) == {"classification": "unrecognized"}
    assert runner._error_diagnostics({"detail": "response_format is not supported"}) == {
        "message_mentions": ["response_format"], "message_flags": ["not supported"]}


@pytest.mark.parametrize("escaped", [False, True])
def test_nested_error_credential_echo_is_discarded_before_diagnostics_or_replay(runner, evidence, escaped):
    value = ''.join(f"\\u{ord(char):04x}" for char in TOKEN) if escaped else TOKEN
    body = ('{"error":{"code":"invalid_json_schema","message":"private-account@example.test",'
            '"nested":{"ignored":"' + value + '"}}}').encode()
    record = runner.run(evidence, TOKEN, transport=lambda *a, **k: HttpResponse(400, body, "application/json",
                                                                                           quota_headers=rejection_headers()))
    assert record["response"] == {"http_status": 400, "body_discarded": "credential_echo"}
    assert record["generation_attempts_after"] == 1
    assert "error_diagnostics" not in record["response"] and "private-account@example.test" not in json.dumps(record)
    with pytest.raises(ValueError):
        runner.run(evidence, TOKEN, diagnostic=True, transport=lambda *a, **k: pytest.fail("Unsafe response cannot authorize replay"))
    for path in (evidence / runner.RECEIPT_NAME, evidence / runner.LEDGER_NAME):
        saved = path.read_bytes()
        assert TOKEN.encode() not in saved and value.encode() not in saved and b"private-account@example.test" not in saved
