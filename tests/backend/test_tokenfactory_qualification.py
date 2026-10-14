"""CPU-only mission-budget checks; every response is a controlled test double."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import threading

from PIL import Image
from pydantic import SecretStr, ValidationError
import pytest

from rekit.inference.adapters.openai_remote import (
    OpenAICompatibleVision, RemoteVisionSettings, TOKENFACTORY_BASE, TOKENFACTORY_ENDPOINT,
    TOKENFACTORY_MIMO_MODEL, _image_content,
)
from rekit.inference.adapters.remote_transport import HttpResponse, RemoteTransportError
from rekit.inference.constrained import inspection_schema, schema_digest


TOKEN = "controlled-offline-qualification-token-not-a-real-key"
PROMPT = "Describe visible evidence without asserting verified identity."
NOW = datetime(2026, 10, 15, 5, 0, tzinfo=UTC)


@pytest.fixture
def qualification(monkeypatch):
    spec = spec_from_file_location("qualification_tests", Path(__file__).parents[2] / "evaluation/tokenfactory_qualification.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_now", lambda: NOW)
    return module


@pytest.fixture
def images():
    result = []
    for color in ("red", "blue"):
        with Image.new("RGB", (16, 12), color) as image, BytesIO() as output:
            image.save(output, format="PNG")
            result.append(output.getvalue())
    return result


def admission(q, images, identifier="request-1", **changes):
    quota = q.VerifiedQuotaEvidence(
        source="dashboard", evidence_sha256="a" * 64, verified_by="trusted_qualification_caller", status="ok",
        api_access_verified=True, free_shared_service_confirmed=True, remaining_allowance=1.0,
        observed_at=NOW - timedelta(seconds=10), expires_at=NOW + timedelta(minutes=5),
        reset_at=NOW + timedelta(hours=1),
    )
    values = dict(admission_id=identifier, authorization="existing_mission_authorization", catalog_receipt_sha256="b" * 64,
                  input_sha256=tuple(hashlib.sha256(raw).hexdigest() for raw in images),
                  prompt_sha256=hashlib.sha256(PROMPT.encode()).hexdigest(),
                  schema_sha256=schema_digest(inspection_schema(len(images), allow_candidates=False)),
                  allow_candidates=False, quota=quota)
    return q.QualificationAdmission(**(values | changes))


def payload(images, prompt=PROMPT):
    return {"model": TOKENFACTORY_MIMO_MODEL, "stream": False, "temperature": 0, "max_tokens": 512,
            "reasoning_effort": "none", "messages": [{"role": "user", "content": [
                *[_image_content(raw) for raw in images], {"type": "text", "text": prompt}]}],
            "response_format": {"type": "json_schema", "json_schema": {"name": "rekit_inspection", "strict": True,
                "schema": inspection_schema(len(images), allow_candidates=False)}}}


def invoke(guard, body, **changes):
    args = dict(url=TOKENFACTORY_ENDPOINT, token=TOKEN, payload=json.dumps(body).encode(),
                timeout=5.0, max_response_bytes=128 * 1024)
    return guard(**(args | changes))


def test_committed_reservation_precedes_transport_without_holding_write_lock(qualification, tmp_path, images):
    q = qualification
    ledger = q.QualificationLedger.initialize(tmp_path)
    approved = admission(q, images)
    calls = []
    def transport(url, token, body, **bounds):
        assert token == TOKEN and url == TOKENFACTORY_ENDPOINT
        # Another connection can acquire a write lock while the network stand-in runs.
        connection = sqlite3.connect(ledger.path, timeout=0.1, isolation_level=None)
        try:
            connection.execute("BEGIN IMMEDIATE")
            assert connection.execute("SELECT COUNT(*) FROM attempts").fetchone()[0] == 1
            assert connection.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0] == 0
            connection.execute("ROLLBACK")
        finally:
            connection.close()
        calls.append(body)
        return HttpResponse(200, b'{"not":"a qualification result"}', "application/json")
    guard = q.GuardedQualificationTransport(ledger, approved, transport=transport)
    result = invoke(guard, payload(images))
    row, = ledger.records()
    assert row["kind"] == "http_response" and row["http_status"] == 200 and len(calls) == 1
    assert row["request_sha256"] == hashlib.sha256(calls[0]).hexdigest()
    assert row["response_sha256"] == hashlib.sha256(result.body).hexdigest()
    saved = ledger.path.read_bytes()
    assert TOKEN.encode() not in saved and PROMPT.encode() not in saved and result.body not in saved


def test_reopen_keeps_attempt_and_replay_or_changed_admission_never_calls_transport(qualification, tmp_path, images):
    q = qualification
    approved = admission(q, images)
    ledger = q.QualificationLedger.initialize(tmp_path)
    invoke(q.GuardedQualificationTransport(ledger, approved, transport=lambda *a, **k: HttpResponse(200, b"{}", "application/json")), payload(images))
    reopened = q.QualificationLedger(tmp_path)
    never = lambda *a, **k: pytest.fail("An existing admission must never retry")
    for item, message in ((approved, "already consumed"),
                          (approved.model_copy(update={"catalog_receipt_sha256": "c" * 64}), "different approval")):
        with pytest.raises(q.QualificationError, match=message):
            invoke(q.GuardedQualificationTransport(reopened, item, transport=never), payload(images))
    assert len(reopened.records()) == 1


def test_fixed_budget_across_admissions_and_concurrent_independent_connections(qualification, tmp_path, images):
    q = qualification
    ledger = q.QualificationLedger.initialize(tmp_path)
    calls = []
    def transport(*args, **kwargs):
        calls.append(1)
        return HttpResponse(200, b"{}", "application/json")
    for index in range(5):
        invoke(q.GuardedQualificationTransport(ledger, admission(q, images, f"first-{index}"), transport=transport), payload(images))
    barrier = threading.Barrier(5)
    def contender(index):
        independent = q.QualificationLedger(tmp_path)
        guard = q.GuardedQualificationTransport(independent, admission(q, images, f"race-{index}"), transport=transport)
        barrier.wait()
        try:
            invoke(guard, payload(images))
            return True
        except q.QualificationError:
            return False
    with ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(contender, range(5)))
    assert sum(results) == 1 and len(calls) == 6
    reopened = q.QualificationLedger(tmp_path)
    assert len(reopened.records()) == 6
    with pytest.raises(q.QualificationError, match="budget"):
        invoke(q.GuardedQualificationTransport(reopened, admission(q, images, "seventh"), transport=transport), payload(images))
    assert len(calls) == 6


def test_interrupted_pending_attempt_is_charged_blocks_until_manual_review(qualification, tmp_path, images):
    q = qualification
    ledger = q.QualificationLedger.initialize(tmp_path)
    first = admission(q, images)
    attempt = ledger.reserve(first, "c" * 64)  # Crash after durable reserve, before a terminal receipt.
    reopened = q.QualificationLedger(tmp_path)
    never = lambda *a, **k: pytest.fail("Uncertain attempt must stop later work")
    guard = q.GuardedQualificationTransport(reopened, admission(q, images, "later"), transport=never)
    with pytest.raises(q.QualificationError, match="uncertain"):
        invoke(guard, payload(images))
    reopened.review_uncertain(attempt, reviewed_by="authorized_operator")
    assert reopened.records()[0]["kind"] is None
    with pytest.raises(q.QualificationError, match="already consumed"):
        invoke(q.GuardedQualificationTransport(reopened, first, transport=never), payload(images))
    invoke(q.GuardedQualificationTransport(reopened, admission(q, images, "later"),
           transport=lambda *a, **k: HttpResponse(200, b"{}", "application/json")), payload(images))
    assert len(reopened.records()) == 2


@pytest.mark.parametrize("error", [RemoteTransportError("timeout"), RuntimeError(TOKEN), KeyboardInterrupt()])
def test_failed_unknown_and_cancelled_attempts_stay_charged_and_sanitized(qualification, tmp_path, images, error):
    q = qualification
    ledger = q.QualificationLedger.initialize(tmp_path)
    def fail(*a, **k):
        raise error
    guard = q.GuardedQualificationTransport(ledger, admission(q, images), transport=fail)
    expected = KeyboardInterrupt if isinstance(error, KeyboardInterrupt) else RemoteTransportError
    with pytest.raises(expected) as caught:
        invoke(guard, payload(images))
    assert TOKEN not in str(caught.value)
    assert len(ledger.records()) == 1 and ledger.records()[0]["http_status"] is None
    assert TOKEN.encode() not in ledger.path.read_bytes()
    with pytest.raises(q.QualificationError, match="uncertain"):
        invoke(q.GuardedQualificationTransport(ledger, admission(q, images, "next"), transport=fail), payload(images))


@pytest.mark.parametrize("status", [401, 403, 429])
@pytest.mark.parametrize("echo", [False, True])
def test_auth_and_rate_limit_halt_remaining_admissions_even_with_credential_echo(qualification, tmp_path, images, status, echo):
    q = qualification
    ledger = q.QualificationLedger.initialize(tmp_path)
    body = json.dumps({"discarded": TOKEN if echo else "controlled rejection"}).encode()
    guard = q.GuardedQualificationTransport(ledger, admission(q, images),
                                           transport=lambda *a, **k: HttpResponse(status, body, "application/json"))
    if echo:
        with pytest.raises(RemoteTransportError):
            invoke(guard, payload(images))
        ledger.review_uncertain(1, reviewed_by="authorized_operator")
    else:
        assert invoke(guard, payload(images)).status == status
    with pytest.raises(q.QualificationError, match="halted"):
        invoke(q.GuardedQualificationTransport(q.QualificationLedger(tmp_path), admission(q, images, "next"),
               transport=lambda *a, **k: pytest.fail("Halted ledger may not call transport")), payload(images))
    assert len(ledger.records()) == 1
    if echo:
        assert ledger.records()[0]["response_sha256"] is None
    assert TOKEN.encode() not in ledger.path.read_bytes()


@pytest.mark.parametrize("change", ["model", "url", "order", "schema", "json_object", "reasoning", "prompt", "extra", "tokens", "temperature"])
def test_request_mismatch_cannot_consume_budget_or_reach_transport(qualification, tmp_path, images, change):
    q = qualification
    ledger = q.QualificationLedger.initialize(tmp_path)
    body = payload(images)
    extra = {}
    if change == "model": body["model"] = "different-model"
    elif change == "url": extra["url"] = TOKENFACTORY_ENDPOINT + "?redirect=1"
    elif change == "order": body["messages"][0]["content"][:2] = list(reversed(body["messages"][0]["content"][:2]))
    elif change == "schema": body["response_format"]["json_schema"]["schema"]["additionalProperties"] = True
    elif change == "json_object": body["response_format"] = {"type": "json_object"}
    elif change == "reasoning": body["reasoning_effort"] = "high"
    elif change == "prompt": body["messages"][0]["content"][-1]["text"] = "A different prompt"
    elif change == "extra": body["tools"] = []
    elif change == "tokens": body["max_tokens"] = 1024
    elif change == "temperature": body["temperature"] = False
    guard = q.GuardedQualificationTransport(ledger, admission(q, images), transport=lambda *a, **k: pytest.fail("No unapproved request"))
    with pytest.raises(q.QualificationError, match="immutable"):
        invoke(guard, body, **extra)
    assert ledger.records() == ()


@pytest.mark.parametrize("changes", [
    {"status": "not_available"}, {"remaining_allowance": 0.0}, {"remaining_allowance": float("nan")},
    {"api_access_verified": False}, {"free_shared_service_confirmed": False},
    {"observed_at": NOW.replace(tzinfo=None)}, {"expires_at": NOW + timedelta(hours=1)},
    {"reset_at": NOW + timedelta(minutes=5)}, {"reviewed_by": "person@example.test"},
])
def test_missing_unverified_unbounded_quota_evidence_rejected(qualification, images, changes):
    q = qualification
    values = admission(q, images).quota.model_dump() | changes
    with pytest.raises(ValidationError):
        q.VerifiedQuotaEvidence(**values)


@pytest.mark.parametrize("shift", [timedelta(minutes=-10), timedelta(minutes=10)])
def test_quota_expired_or_from_future_stops_before_reserve(qualification, tmp_path, images, shift):
    q = qualification
    approved = admission(q, images)
    values = approved.quota.model_dump()
    for name in ("observed_at", "expires_at", "reset_at"):
        values[name] += shift
    approved = admission(q, images, quota=q.VerifiedQuotaEvidence(**values))
    ledger = q.QualificationLedger.initialize(tmp_path)
    with pytest.raises(q.QualificationError, match="Current verified quota"):
        invoke(q.GuardedQualificationTransport(ledger, approved, transport=lambda *a, **k: pytest.fail("No stale quota")), payload(images))
    assert ledger.records() == ()


def test_model_copy_bypass_and_duplicate_image_admission_are_revalidated(qualification, tmp_path, images):
    q = qualification
    approved = admission(q, images)
    bad = approved.model_copy(update={"quota": approved.quota.model_copy(update={"api_access_verified": False})})
    with pytest.raises(q.QualificationError, match="Invalid qualification"):
        q.GuardedQualificationTransport(q.QualificationLedger.initialize(tmp_path), bad, transport=lambda *a, **k: None)
    with pytest.raises(ValidationError):
        admission(q, [images[0], images[0]])


def test_reserve_failure_rolls_back_admission_and_never_calls_network(qualification, tmp_path, images):
    q = qualification
    ledger = q.QualificationLedger.initialize(tmp_path)
    with sqlite3.connect(ledger.path) as connection:
        connection.execute("CREATE TRIGGER reject_attempt AFTER INSERT ON attempts BEGIN SELECT RAISE(FAIL, 'injected'); END")
    with pytest.raises(q.QualificationError, match="transaction"):
        invoke(q.GuardedQualificationTransport(ledger, admission(q, images),
               transport=lambda *a, **k: pytest.fail("No durable reserve, no network")), payload(images))
    with sqlite3.connect(ledger.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM admissions").fetchone()[0] == 0
    assert ledger.records() == ()


def test_outcome_failure_retains_charged_pending_attempt_and_blocks_restart(qualification, tmp_path, images):
    q = qualification
    ledger = q.QualificationLedger.initialize(tmp_path)
    with sqlite3.connect(ledger.path) as connection:
        connection.execute("CREATE TRIGGER reject_outcome AFTER INSERT ON outcomes BEGIN SELECT RAISE(FAIL, 'injected'); END")
    calls = []
    def transport(*a, **k):
        calls.append(1)
        return HttpResponse(200, b"{}", "application/json")
    with pytest.raises(q.QualificationError, match="transaction"):
        invoke(q.GuardedQualificationTransport(ledger, admission(q, images), transport=transport), payload(images))
    assert len(calls) == 1 and len(ledger.records()) == 1 and ledger.records()[0]["kind"] is None
    with pytest.raises(q.QualificationError, match="uncertain"):
        invoke(q.GuardedQualificationTransport(q.QualificationLedger(tmp_path), admission(q, images, "later"), transport=transport), payload(images))
    assert len(calls) == 1


def test_audit_tables_are_append_only(qualification, tmp_path, images):
    q = qualification
    ledger = q.QualificationLedger.initialize(tmp_path)
    attempt = ledger.reserve(admission(q, images), "d" * 64)
    ledger._finish(attempt, error_code="timeout")
    ledger.review_uncertain(attempt, reviewed_by="authorized_operator")
    with sqlite3.connect(ledger.path) as connection:
        for table, key in (("admissions", "id"), ("attempts", "id"), ("outcomes", "attempt_id"), ("reviews", "attempt_id")):
            for statement in (f"DELETE FROM {table}", f"UPDATE {table} SET {key}={key}"):
                with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                    connection.execute(statement)
    assert len(ledger.records()) == 1


def test_real_provider_can_use_guard_without_contract_or_authority_changes(qualification, tmp_path, images):
    q = qualification
    settings = RemoteVisionSettings(provider="amd-tokenfactory", base_url=TOKENFACTORY_BASE,
        allowed_endpoints=(TOKENFACTORY_ENDPOINT,), api_key=SecretStr(TOKEN), model_id=TOKENFACTORY_MIMO_MODEL,
        model_revision=None, processor_revision=None)
    output = {"observations": [], "candidates": [], "uncertainties": ["Controlled test output, not AI evidence."], "additional_views": []}
    response = HttpResponse(200, json.dumps({"model": TOKENFACTORY_MIMO_MODEL, "choices": [{"index": 0,
        "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(output)}}]}).encode(), "application/json")
    # Obtain only the real provider's configuration; no call or credential lookup.
    configuration = OpenAICompatibleVision(settings, transport=lambda *a, **k: pytest.fail("No unguarded call")).configuration
    approved = admission(q, images, prompt_sha256=configuration.preprocessing["prompt_sha256"])
    ledger = q.QualificationLedger.initialize(tmp_path)
    guard = q.GuardedQualificationTransport(ledger, approved, transport=lambda *a, **k: response)
    result = OpenAICompatibleVision(settings, transport=guard).inspect(images)
    assert result["provider"] == "amd-tokenfactory" and result["device"] == "remote"
    assert result["model_revision"] is None and result["metrics"]["input_sha256"] == list(approved.input_sha256)
    assert json.loads(result["text"]) == output and len(ledger.records()) == 1


def test_no_default_transport_and_no_cli(qualification, tmp_path, images):
    q = qualification
    with pytest.raises(TypeError):
        q.GuardedQualificationTransport(q.QualificationLedger.initialize(tmp_path), admission(q, images))
    assert not hasattr(q, "main")


def test_initialization_is_exclusive_and_default_open_never_creates_or_resets(qualification, tmp_path, images):
    q = qualification
    path = tmp_path / q.LEDGER_NAME
    with pytest.raises(q.QualificationError, match="already exist"):
        q.QualificationLedger(tmp_path)
    assert not path.exists()
    ledger = q.QualificationLedger.initialize(tmp_path)
    ledger.reserve(admission(q, images), "e" * 64)
    original = path.read_bytes()
    with pytest.raises(q.QualificationError, match="new file"):
        q.QualificationLedger.initialize(tmp_path)
    assert path.read_bytes() == original
    path.rename(tmp_path / "preserved-ledger.sqlite3")
    for operation in (lambda: q.QualificationLedger(tmp_path), ledger.records):
        with pytest.raises(q.QualificationError, match="already exist"):
            operation()
    assert not path.exists()


@pytest.mark.parametrize("damage", ["table", "trigger", "corrupt"])
def test_existing_damaged_ledger_fails_closed_without_schema_healing(qualification, tmp_path, damage):
    q = qualification
    ledger = q.QualificationLedger.initialize(tmp_path)
    if damage == "corrupt":
        ledger.path.write_bytes(b"not a SQLite database")
    else:
        with sqlite3.connect(ledger.path) as connection:
            connection.execute("DROP TABLE outcomes" if damage == "table" else "DROP TRIGGER attempts_limit")
    original = ledger.path.read_bytes()
    with pytest.raises(q.QualificationError, match="corrupt or incompatible"):
        q.QualificationLedger(tmp_path)
    assert ledger.path.read_bytes() == original


@pytest.mark.parametrize("status", [401, 403, 429])
@pytest.mark.parametrize("body", ["invalid-body-type", b"x" * (128 * 1024 + 1)], ids=["wrong-type", "oversized"])
def test_known_halt_status_survives_invalid_or_oversized_body(qualification, tmp_path, images, status, body):
    q = qualification
    ledger = q.QualificationLedger.initialize(tmp_path)
    guard = q.GuardedQualificationTransport(ledger, admission(q, images),
                                           transport=lambda *a, **k: HttpResponse(status, body, "application/json"))
    with pytest.raises(RemoteTransportError):
        invoke(guard, payload(images))
    ledger.review_uncertain(1, reviewed_by="authorized_operator")
    assert ledger.records()[0]["http_status"] == status and ledger.records()[0]["response_sha256"] is None
    with pytest.raises(q.QualificationError, match="halted"):
        invoke(q.GuardedQualificationTransport(ledger, admission(q, images, "later"),
               transport=lambda *a, **k: pytest.fail("Known halt may not be lost")), payload(images))


@pytest.mark.parametrize("escaped", [False, True])
def test_credential_echo_is_rejected_before_even_response_hash_is_persisted(qualification, tmp_path, images, escaped):
    q = qualification
    ledger = q.QualificationLedger.initialize(tmp_path)
    body = (''.join(f"\\u{ord(char):04x}" for char in TOKEN) if escaped else TOKEN).encode()
    with pytest.raises(RemoteTransportError) as caught:
        invoke(q.GuardedQualificationTransport(ledger, admission(q, images),
               transport=lambda *a, **k: HttpResponse(200, body, "application/json")), payload(images))
    assert TOKEN not in str(caught.value) and ledger.records()[0]["response_sha256"] is None
    assert TOKEN.encode() not in ledger.path.read_bytes() and body not in ledger.path.read_bytes()


@pytest.mark.parametrize("timeout", [0, True, float("nan")])
def test_invalid_transport_bounds_never_reserve_or_send(qualification, tmp_path, images, timeout):
    q = qualification
    ledger = q.QualificationLedger.initialize(tmp_path)
    with pytest.raises(q.QualificationError):
        invoke(q.GuardedQualificationTransport(ledger, admission(q, images),
               transport=lambda *a, **k: pytest.fail("Invalid bounds")), payload(images), timeout=timeout)
    assert ledger.records() == ()


def initial_probe_quota(q, images, **changes):
    values = admission(q, images).quota.model_dump() | {
        "api_access_verified": None, "initial_probe_authorized": True,
        "key_issued_reported": True, "allowance_unit": "pt",
    }
    return q.VerifiedQuotaEvidence(**(values | changes))


def test_authorized_dashboard_initial_probe_preserves_unknown_status_points_and_single_attempt(qualification, tmp_path, images):
    q = qualification
    images = images[:1]
    quota = initial_probe_quota(q, images)
    assert quota.api_access_verified is None and quota.allowance_unit == "pt" and quota.remaining_allowance == 1.0
    ledger = q.QualificationLedger.initialize(tmp_path)
    calls = []
    def transport(*a, **k):
        calls.append(1)
        return HttpResponse(200, b"{}", "application/json")
    invoke(q.GuardedQualificationTransport(ledger, admission(q, images, quota=quota), transport=transport), payload(images))
    with sqlite3.connect(ledger.path) as connection:
        stored = json.loads(connection.execute("SELECT payload FROM admissions").fetchone()[0])
    assert stored["quota"]["api_access_verified"] is None and stored["quota"]["allowance_unit"] == "pt"
    with pytest.raises(q.QualificationError, match="only the first ledger attempt"):
        invoke(q.GuardedQualificationTransport(q.QualificationLedger(tmp_path),
               admission(q, images, "second-probe", quota=quota), transport=transport), payload(images))
    assert calls == [1] and len(ledger.records()) == 1


@pytest.mark.parametrize("changes", [
    {"initial_probe_authorized": False}, {"key_issued_reported": False},
    {"source": "official_usage"}, {"api_access_verified": False},
    {"free_shared_service_confirmed": False}, {"allowance_unit": "USD"},
])
def test_unknown_api_status_requires_specific_dashboard_authorization(qualification, images, changes):
    with pytest.raises(ValidationError):
        initial_probe_quota(qualification, images, **changes)


def test_unknown_initial_probe_cannot_admit_joint_images_or_bypass_with_model_copy(qualification, tmp_path, images):
    q = qualification
    quota = initial_probe_quota(q, images)
    with pytest.raises(ValidationError, match="exactly one"):
        admission(q, images, quota=quota)
    forged = admission(q, images).model_copy(update={"quota": quota})
    with pytest.raises(q.QualificationError, match="Invalid qualification"):
        q.GuardedQualificationTransport(q.QualificationLedger.initialize(tmp_path), forged,
                                         transport=lambda *a, **k: pytest.fail("No joint initial probe"))


def test_reviewed_failed_initial_probe_stays_charged_and_cannot_be_repeated(qualification, tmp_path, images):
    q = qualification
    images = images[:1]
    quota = initial_probe_quota(q, images)
    ledger = q.QualificationLedger.initialize(tmp_path)
    attempt = ledger.reserve(admission(q, images, quota=quota), "f" * 64)
    ledger.review_uncertain(attempt, reviewed_by="authorized_operator")
    with pytest.raises(q.QualificationError, match="only the first ledger attempt"):
        invoke(q.GuardedQualificationTransport(ledger, admission(q, images, "retry-with-new-id", quota=quota),
               transport=lambda *a, **k: pytest.fail("No uncertain repeated initial probe")), payload(images))
    assert len(ledger.records()) == 1


def diagnostic_admission(q, images, prior_digest, identifier="diagnostic", **quota_changes):
    quota = initial_probe_quota(q, images, source="response_headers", initial_probe_authorized=False,
                                diagnostic_replay_authorized=True, allowance_unit="provider_capacity", **quota_changes)
    return admission(q, images, identifier, quota=quota, diagnostic_prior_request_sha256=prior_digest)


def test_exact_diagnostic_replay_consumes_only_attempt_two_and_preserves_first_receipt(qualification, tmp_path, images):
    q = qualification
    images = images[:1]
    body = payload(images)
    digest = hashlib.sha256(json.dumps(body).encode()).hexdigest()
    ledger = q.QualificationLedger.initialize(tmp_path)
    invoke(q.GuardedQualificationTransport(ledger, admission(q, images, quota=initial_probe_quota(q, images)),
           transport=lambda *a, **k: HttpResponse(400, b'{}', "application/json")), body)
    first = ledger.records()[0].copy()
    calls = []
    def diagnostic(*a, **k):
        calls.append(1)
        return HttpResponse(400, b'{"error":"controlled diagnostic"}', "application/json")
    invoke(q.GuardedQualificationTransport(ledger, diagnostic_admission(q, images, digest), transport=diagnostic), body)
    assert ledger.records()[0] == first and len(ledger.records()) == 2 and calls == [1]
    with pytest.raises(q.QualificationError, match="sole prior HTTP 400"):
        invoke(q.GuardedQualificationTransport(q.QualificationLedger(tmp_path),
               diagnostic_admission(q, images, digest, "another-diagnostic"), transport=diagnostic), body)
    assert calls == [1]


@pytest.mark.parametrize("prior_status", [None, 200, 404, 500])
def test_diagnostic_requires_one_terminal_http_400(qualification, tmp_path, images, prior_status):
    q = qualification
    images = images[:1]
    body = payload(images)
    digest = hashlib.sha256(json.dumps(body).encode()).hexdigest()
    ledger = q.QualificationLedger.initialize(tmp_path)
    if prior_status is not None:
        invoke(q.GuardedQualificationTransport(ledger, admission(q, images),
               transport=lambda *a, **k: HttpResponse(prior_status, b"{}", "application/json")), body)
    with pytest.raises(q.QualificationError, match="sole prior HTTP 400"):
        invoke(q.GuardedQualificationTransport(ledger, diagnostic_admission(q, images, digest),
               transport=lambda *a, **k: pytest.fail("No diagnostic without exact prior 400")), body)
    assert len(ledger.records()) == (0 if prior_status is None else 1)


@pytest.mark.parametrize("change", ["admitted-prior-hash", "outgoing-bytes", "prior-kind"])
def test_diagnostic_rejects_mismatched_binding_or_protocol_failure(qualification, tmp_path, images, change):
    q = qualification
    images = images[:1]
    body = payload(images)
    digest = hashlib.sha256(json.dumps(body).encode()).hexdigest()
    ledger = q.QualificationLedger.initialize(tmp_path)
    attempt = ledger.reserve(admission(q, images), digest)
    if change == "prior-kind":
        ledger._finish(attempt, error_code="protocol", http_status=400)
        ledger.review_uncertain(attempt, reviewed_by="authorized_operator")
    else:
        ledger._finish(attempt, response=HttpResponse(400, b"{}", "application/json"))
    approved = diagnostic_admission(q, images, "0" * 64 if change == "admitted-prior-hash" else digest)
    extra = {"payload": json.dumps(body, separators=(",", ":")).encode()} if change == "outgoing-bytes" else {}
    with pytest.raises(q.QualificationError, match="identical request bytes"):
        invoke(q.GuardedQualificationTransport(ledger, approved,
               transport=lambda *a, **k: pytest.fail("No changed diagnostic request")), body, **extra)
    assert len(ledger.records()) == 1


def test_diagnostic_marker_source_joint_images_and_missing_prior_hash_rejected(qualification, images):
    q = qualification
    quota = initial_probe_quota(q, images, source="response_headers", initial_probe_authorized=False,
                                diagnostic_replay_authorized=True)
    for changed in ({"diagnostic_replay_authorized": False}, {"source": "dashboard"}, {"api_access_verified": True}):
        with pytest.raises(ValidationError):
            q.VerifiedQuotaEvidence(**(quota.model_dump() | changed))
    with pytest.raises(ValidationError, match="exactly one"):
        admission(q, images, quota=quota, diagnostic_prior_request_sha256="d" * 64)
    with pytest.raises(ValidationError, match="prior request digest"):
        admission(q, images[:1], quota=quota)
