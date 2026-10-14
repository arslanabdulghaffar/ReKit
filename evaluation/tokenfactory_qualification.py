"""Offline-tested admission/attempt guard, deliberately without a CLI or live default.

The trusted caller must verify quota independently, approve the exact input hashes,
keep one mission directory with private ACLs, and inject the existing HTTPS
transport. This module cannot verify a dashboard statement, predict request cost,
or make a failed discovery receipt usable. Transport receipts do not certify
schema conformance, visual correctness, or AMD hardware. The normal provider and
inference service still perform their independent validation and provenance work.
"""

import base64
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from rekit.inference.adapters.openai_remote import (
    MAX_IMAGE_BYTES, MAX_REQUEST_BYTES, TOKENFACTORY_ENDPOINT, TOKENFACTORY_MIMO_MODEL,
    TOKENFACTORY_PROVIDER, _contains_secret, _image_content,
)
from rekit.inference.adapters.remote_transport import HttpResponse, RemoteTransportError
from rekit.inference.constrained import SCHEMA_VERSION, inspection_schema, schema_digest
from rekit.inference.parsing import _invalid_constant, _unique_object


MAX_ATTEMPTS = 6
LEDGER_NAME = "generation-attempts.sqlite3"
Digest = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")]


class QualificationError(RuntimeError):
    """Controlled admission failure; never include credentials or response text."""


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)


class VerifiedQuotaEvidence(_Frozen):
    """Trusted quota evidence; an authorized initial probe may retain unknown API status."""

    source: Literal["official_usage", "dashboard", "response_headers"]
    evidence_sha256: Digest
    verified_by: Literal["trusted_qualification_caller"]
    status: Literal["ok"]
    api_access_verified: bool | None
    initial_probe_authorized: bool = False
    diagnostic_replay_authorized: bool = False
    key_issued_reported: bool = False
    free_shared_service_confirmed: bool
    remaining_allowance: float = Field(gt=0, le=2**53 - 1, allow_inf_nan=False)
    allowance_unit: Literal["pt", "provider_capacity"] = "provider_capacity"
    observed_at: datetime
    expires_at: datetime
    reset_at: datetime

    @model_validator(mode="after")
    def verified_window(self):
        initial_probe = (self.api_access_verified is None and self.source == "dashboard"
                         and self.initial_probe_authorized and self.key_issued_reported
                         and not self.diagnostic_replay_authorized)
        diagnostic = (self.api_access_verified is None and self.source == "response_headers"
                      and self.diagnostic_replay_authorized and self.key_issued_reported
                      and not self.initial_probe_authorized)
        if self.diagnostic_replay_authorized and not diagnostic:
            raise ValueError("Diagnostic replay requires unknown API status and fresh response-header evidence")
        if not self.free_shared_service_confirmed or (self.api_access_verified is not True and not initial_probe and not diagnostic):
            raise ValueError("Verified API access or an explicitly authorized bounded probe is required")
        dates = (self.observed_at, self.expires_at, self.reset_at)
        if any(value.tzinfo is None or value.utcoffset() is None for value in dates):
            raise ValueError("Quota timestamps must include a timezone")
        if not (self.observed_at < self.expires_at < self.reset_at
                and self.expires_at <= self.observed_at + timedelta(minutes=15)):
            raise ValueError("Quota evidence must expire before reset and within fifteen minutes")
        return self


class QualificationAdmission(_Frozen):
    """One explicit request admission under the existing bounded mission authority."""

    admission_id: Identifier
    authorization: Literal["existing_mission_authorization"]
    provider: Literal["amd-tokenfactory"] = TOKENFACTORY_PROVIDER
    endpoint: Literal["https://developer.amd.com.cn/radeon/api/v1/chat/completions"] = TOKENFACTORY_ENDPOINT
    model_id: Literal["MiMo-V2.6-Flash"] = TOKENFACTORY_MIMO_MODEL
    catalog_receipt_sha256: Digest
    input_sha256: tuple[Digest, ...] = Field(min_length=1, max_length=2)
    prompt_sha256: Digest
    schema_version: Literal["rekit-inspection-schema-v2"] = SCHEMA_VERSION
    schema_sha256: Digest
    allow_candidates: bool
    quota: VerifiedQuotaEvidence
    diagnostic_prior_request_sha256: Digest | None = None

    @model_validator(mode="after")
    def exact_schema(self):
        if self.quota.api_access_verified is None and len(self.input_sha256) != 1:
            raise ValueError("An unverified probe requires exactly one approved image")
        if self.quota.diagnostic_replay_authorized != (self.diagnostic_prior_request_sha256 is not None):
            raise ValueError("Only a diagnostic admission must bind the prior request digest")
        if len(set(self.input_sha256)) != len(self.input_sha256):
            raise ValueError("Distinct approved image bytes are required")
        expected = schema_digest(inspection_schema(len(self.input_sha256), allow_candidates=self.allow_candidates))
        if self.schema_sha256 != expected:
            raise ValueError("Admission requires the current exact ReKit schema")
        return self


def _now():
    return datetime.now(UTC)


def _validated(admission):
    try:
        # Roundtrip even constructed/copied models; nested input is not trusted.
        return QualificationAdmission.model_validate_json(admission.model_dump_json(warnings=False))
    except (AttributeError, TypeError, ValueError):
        raise QualificationError("Invalid qualification admission") from None


def _current(admission):
    now = _now()
    if not admission.quota.observed_at <= now < admission.quota.expires_at:
        raise QualificationError("Current verified quota evidence is required")
    return now.isoformat()


def _canonical(model):
    return json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), allow_nan=False)


class QualificationLedger:
    """One fixed six-attempt mission ledger; no reset, refund or cap override API.

    Directory ownership/ACL enforcement belongs to the private launcher. Keep
    this directory across runs; deleting/replacing it defeats any local budget.
    OS administrators and arbitrary SQL writers are outside this boundary.
    """

    def __init__(self, directory: Path):
        self.path = Path(directory).absolute() / LEDGER_NAME
        connection = self._connect()
        connection.close()

    @classmethod
    def initialize(cls, directory: Path):
        """Explicit one-time setup; never overwrite or silently replace a ledger."""
        ledger = cls.__new__(cls)
        ledger.path = Path(directory).absolute() / LEDGER_NAME
        ledger._check_path(existing=False)
        try:
            with ledger.path.open("xb"):
                pass
        except OSError:
            raise QualificationError("Qualification ledger initialization requires a new file") from None
        # A failed initialization remains on disk for inspection, never auto-reset.
        with ledger._write(initializing=True) as connection:
            connection.execute("CREATE TABLE mission (id INTEGER PRIMARY KEY CHECK(id=1), version INTEGER NOT NULL, maximum INTEGER NOT NULL)")
            connection.execute("INSERT INTO mission VALUES (1,1,6)")
            connection.execute("CREATE TABLE admissions (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
            connection.execute("""CREATE TABLE attempts (
                id INTEGER PRIMARY KEY, admission_id TEXT NOT NULL UNIQUE REFERENCES admissions(id),
                request_sha256 TEXT NOT NULL, started_at TEXT NOT NULL)""")
            connection.execute("""CREATE TABLE outcomes (
                attempt_id INTEGER PRIMARY KEY REFERENCES attempts(id),
                kind TEXT NOT NULL CHECK(kind IN ('http_response', 'transport_error', 'unknown')),
                finished_at TEXT NOT NULL, http_status INTEGER, response_sha256 TEXT,
                response_bytes INTEGER, error_code TEXT)""")
            connection.execute("""CREATE TABLE reviews (
                attempt_id INTEGER PRIMARY KEY REFERENCES attempts(id),
                reviewed_by TEXT NOT NULL, reviewed_at TEXT NOT NULL)""")
            for table in ("mission", "admissions", "attempts", "outcomes", "reviews"):
                for operation in ("UPDATE", "DELETE"):
                    connection.execute(f"CREATE TRIGGER {table}_no_{operation.lower()} "
                                       f"BEFORE {operation} ON {table} BEGIN "
                                       "SELECT RAISE(ABORT, 'Qualification audit is immutable'); END")
            connection.execute("""CREATE TRIGGER attempts_limit BEFORE INSERT ON attempts
                WHEN (SELECT COUNT(*) FROM attempts) >= 6
                BEGIN SELECT RAISE(ABORT, 'Six-attempt mission limit reached'); END""")
        return cls(directory)

    def _check_path(self, *, existing=True):
        if not self.path.parent.is_dir():
            raise QualificationError("An existing private ledger directory is required")
        for path in (self.path, *self.path.parents):
            if path.is_symlink() or path.is_junction():
                raise QualificationError("Ledger paths must not contain links or junctions")
        if existing and (not self.path.is_file() or self.path.stat().st_size == 0):
            raise QualificationError("An initialized qualification ledger must already exist")
        if self.path.exists() and not self.path.is_file():
            raise QualificationError("Invalid qualification ledger file")

    def _connect(self, *, initializing=False):
        self._check_path(existing=not initializing)
        connection = None
        try:
            connection = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=5, isolation_level=None)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA synchronous = FULL")
            if not initializing:
                expected = {
                    "mission": ("id", "version", "maximum"), "admissions": ("id", "payload"),
                    "attempts": ("id", "admission_id", "request_sha256", "started_at"),
                    "outcomes": ("attempt_id", "kind", "finished_at", "http_status", "response_sha256", "response_bytes", "error_code"),
                    "reviews": ("attempt_id", "reviewed_by", "reviewed_at"),
                }
                for table, columns in expected.items():
                    if tuple(row["name"] for row in connection.execute(f"PRAGMA table_info({table})")) != columns:
                        raise QualificationError("Qualification ledger schema is missing or incompatible")
                triggers = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
                required = {f"{table}_no_{action}" for table in expected for action in ("update", "delete")} | {"attempts_limit"}
                if not required <= triggers or [tuple(row) for row in connection.execute("SELECT * FROM mission")] != [(1, 1, 6)]:
                    raise QualificationError("Qualification ledger safeguards are missing or incompatible")
            return connection
        except (sqlite3.Error, QualificationError):
            if connection is not None:
                connection.close()
            raise QualificationError("Qualification ledger is missing, corrupt or incompatible") from None

    @contextmanager
    def _write(self, *, initializing=False):
        connection = None
        try:
            connection = self._connect(initializing=initializing)
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.execute("COMMIT")
        except sqlite3.Error:
            if connection is not None and connection.in_transaction:
                connection.execute("ROLLBACK")
            raise QualificationError("Qualification ledger transaction failed") from None
        except BaseException:
            if connection is not None and connection.in_transaction:
                connection.execute("ROLLBACK")
            raise
        finally:
            if connection is not None:
                connection.close()

    def reserve(self, admission: QualificationAdmission, request_sha256: str) -> int:
        admission = _validated(admission)
        if not isinstance(request_sha256, str) or len(request_sha256) != 64 or any(c not in "0123456789abcdef" for c in request_sha256):
            raise QualificationError("Invalid request digest")
        with self._write() as connection:
            started = _current(admission)  # Recheck after acquiring the write lock.
            prior = connection.execute("SELECT payload FROM admissions WHERE id=?", (admission.admission_id,)).fetchone()
            if prior and prior["payload"] != _canonical(admission):
                raise QualificationError("Admission ID is bound to different approval evidence")
            if connection.execute("SELECT 1 FROM attempts WHERE admission_id=?", (admission.admission_id,)).fetchone():
                raise QualificationError("This admission already consumed its single attempt; no retry")
            if connection.execute("SELECT 1 FROM outcomes WHERE http_status IN (401,403,429)").fetchone():
                raise QualificationError("Authentication or rate limiting halted this mission ledger")
            if connection.execute("""SELECT 1 FROM attempts a LEFT JOIN outcomes o ON o.attempt_id=a.id
                LEFT JOIN reviews r ON r.attempt_id=a.id
                WHERE r.attempt_id IS NULL AND (o.attempt_id IS NULL OR o.kind != 'http_response')""").fetchone():
                raise QualificationError("An uncertain prior attempt requires explicit review")
            count = connection.execute("SELECT COUNT(*) FROM attempts").fetchone()[0]
            if admission.quota.diagnostic_replay_authorized:
                first = connection.execute("""SELECT a.request_sha256, o.kind, o.http_status FROM attempts a
                    JOIN outcomes o ON o.attempt_id=a.id WHERE a.id=1""").fetchone()
                if (count != 1 or first is None or first["kind"] != "http_response" or first["http_status"] != 400
                        or request_sha256 != first["request_sha256"]
                        or request_sha256 != admission.diagnostic_prior_request_sha256):
                    raise QualificationError("Diagnostic replay requires the sole prior HTTP 400 and identical request bytes")
            elif admission.quota.api_access_verified is None and count != 0:
                raise QualificationError("Unverified dashboard evidence authorizes only the first ledger attempt")
            if count >= MAX_ATTEMPTS:
                raise QualificationError("The six-generation mission budget is exhausted")
            connection.execute("INSERT OR IGNORE INTO admissions VALUES (?,?)", (admission.admission_id, _canonical(admission)))
            cursor = connection.execute("INSERT INTO attempts(admission_id,request_sha256,started_at) VALUES (?,?,?)",
                                        (admission.admission_id, request_sha256, started))
            return cursor.lastrowid

    def _finish(self, attempt_id, *, response=None, error_code=None, http_status=None):
        kind = "http_response" if response is not None else ("unknown" if error_code == "interrupted" else "transport_error")
        with self._write() as connection:
            connection.execute("INSERT INTO outcomes VALUES (?,?,?,?,?,?,?)", (
                attempt_id, kind, _now().isoformat(), response.status if response is not None else http_status,
                hashlib.sha256(response.body).hexdigest() if response is not None else None,
                len(response.body) if response is not None else None, error_code,
            ))

    def review_uncertain(self, attempt_id: int, *, reviewed_by: str):
        """Trusted manual review AFTER the owned transport has stopped; never refund.

        This cannot override 401/403/429 or re-use the attempted admission. It
        does not assert whether a timed-out/interrupted request ran remotely.
        """
        if type(attempt_id) is not int or attempt_id < 1 or reviewed_by != "authorized_operator":
            raise QualificationError("An explicit authorized-operator review is required")
        with self._write() as connection:
            row = connection.execute("""SELECT a.id, o.kind FROM attempts a
                LEFT JOIN outcomes o ON o.attempt_id=a.id WHERE a.id=?""", (attempt_id,)).fetchone()
            if row is None or row["kind"] == "http_response":
                raise QualificationError("Only an uncertain recorded attempt can be reviewed")
            connection.execute("INSERT INTO reviews VALUES (?,?,?)", (attempt_id, reviewed_by, _now().isoformat()))

    def records(self) -> tuple[dict, ...]:
        connection = self._connect()
        try:
            return tuple(dict(row) for row in connection.execute("""SELECT a.*, o.kind, o.http_status,
                o.response_sha256, o.response_bytes, o.error_code, o.finished_at AS finished_at, r.reviewed_by
                FROM attempts a LEFT JOIN outcomes o ON o.attempt_id=a.id
                LEFT JOIN reviews r ON r.attempt_id=a.id ORDER BY a.id"""))
        finally:
            connection.close()


def _check_payload(admission, url, token, payload, timeout, max_response_bytes):
    try:
        if (url != TOKENFACTORY_ENDPOINT or not isinstance(token, str) or not 1 <= len(token) <= 4096
                or any(not 33 <= ord(c) <= 126 for c in token)
                or type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 120
                or type(max_response_bytes) is not int or not 1024 <= max_response_bytes <= 128 * 1024
                or not isinstance(payload, bytes) or not 0 < len(payload) <= MAX_REQUEST_BYTES):
            raise ValueError
        body = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        if _contains_secret(body, token) or _contains_secret(_canonical(admission), token):
            raise ValueError
        if (set(body) != {"model", "stream", "temperature", "max_tokens", "reasoning_effort", "messages", "response_format"}
                or body["model"] != TOKENFACTORY_MIMO_MODEL or body["stream"] is not False
                or type(body["temperature"]) is not int or body["temperature"] != 0
                or type(body["max_tokens"]) is not int or body["max_tokens"] != 512 or body["reasoning_effort"] != "none"):
            raise ValueError
        messages = body["messages"]
        if (not isinstance(messages, list) or len(messages) != 1 or set(messages[0]) != {"role", "content"}
                or messages[0]["role"] != "user"):
            raise ValueError
        content = messages[0]["content"]
        if not isinstance(content, list) or len(content) != len(admission.input_sha256) + 1:
            raise ValueError
        prompt = content[-1]
        if (set(prompt) != {"type", "text"} or prompt["type"] != "text" or not isinstance(prompt["text"], str)
                or not 1 <= len(prompt["text"]) <= 12000
                or hashlib.sha256(prompt["text"].encode()).hexdigest() != admission.prompt_sha256):
            raise ValueError
        for part, expected in zip(content[:-1], admission.input_sha256, strict=True):
            if set(part) != {"type", "image_url"} or part["type"] != "image_url" or set(part["image_url"]) != {"url"}:
                raise ValueError
            data_url = part["image_url"]["url"]
            if not isinstance(data_url, str) or ";base64," not in data_url:
                raise ValueError
            _, encoded = data_url.split(";base64,", 1)
            raw = base64.b64decode(encoded, validate=True)
            if not 0 < len(raw) <= MAX_IMAGE_BYTES or hashlib.sha256(raw).hexdigest() != expected or _image_content(raw) != part:
                raise ValueError
        schema = inspection_schema(len(admission.input_sha256), allow_candidates=admission.allow_candidates)
        expected_format = {"type": "json_schema", "json_schema": {"name": "rekit_inspection", "strict": True, "schema": schema}}
        # Canonical JSON distinguishes booleans from integers, unlike dict equality.
        if json.dumps(body["response_format"], sort_keys=True) != json.dumps(expected_format, sort_keys=True):
            raise ValueError
    except Exception:
        raise QualificationError("Request does not match the immutable strict qualification admission") from None


class GuardedQualificationTransport:
    """One injected transport call per admission, after durable budget reservation.

    No default transport, credential lookup, executable entry point or automatic
    retry. HTTP receipts alone are not successful visual/schema qualification.
    """

    def __init__(self, ledger: QualificationLedger, admission: QualificationAdmission, *, transport):
        self._ledger, self._admission = ledger, _validated(admission)
        if not callable(transport):
            raise QualificationError("An explicit transport is required")
        self._transport = transport

    def __call__(self, url, token, payload, *, timeout, max_response_bytes):
        _check_payload(self._admission, url, token, payload, timeout, max_response_bytes)
        attempt = self._ledger.reserve(self._admission, hashlib.sha256(payload).hexdigest())
        response = None
        try:
            response = self._transport(url, token, payload, timeout=timeout, max_response_bytes=max_response_bytes)
            if (not isinstance(response, HttpResponse) or type(response.status) is not int
                    or not 200 <= response.status <= 599 or 300 <= response.status <= 399
                    or not isinstance(response.body, bytes) or len(response.body) > max_response_bytes):
                raise RemoteTransportError("protocol")
            if _contains_secret(response.body.decode("utf-8", errors="replace"), token):
                raise RemoteTransportError("protocol")
        except BaseException as error:
            code = error.code if isinstance(error, RemoteTransportError) else "unavailable"
            if code not in {"timeout", "unavailable", "oversized", "protocol"}:
                code = "protocol"
            if not isinstance(error, Exception):
                code = "interrupted"
            halted_status = (response.status if isinstance(response, HttpResponse)
                             and type(response.status) is int and response.status in (401, 403, 429) else None)
            self._ledger._finish(attempt, error_code=code, http_status=halted_status)
            if not isinstance(error, Exception):
                raise
            raise RemoteTransportError(code) from None
        self._ledger._finish(attempt, response=response)
        return response
