"""Offline transport tests; no AMD connection, credentials, or GPU required."""

from io import BytesIO
from datetime import datetime, timezone
import json
from pathlib import Path
import ssl
import subprocess
import sys
import time

import pytest

from rekit.inference.adapters import https_worker as worker
from rekit.inference.adapters import remote_transport as transport


URL = "https://inference.example.test:8443/v1/chat/completions"
TOKEN = "test-only-private-token"
PAYLOAD = b'{"test":"private-input"}'


def request_header(**changes):
    data = {"url": URL, "token": TOKEN, "payload_size": len(PAYLOAD),
            "timeout": 1.0, "max_response_bytes": 1024}
    data.update(changes)
    return json.dumps(data).encode() + b"\n"


def wire_response(body=b'{"ok":true}', status=200, headers=None):
    fields = headers if headers is not None else [
        ("Content-Type", "application/json"), ("Content-Length", str(len(body)))
    ]
    return (f"HTTP/1.1 {status} Response\r\n".encode()
            + b"".join(f"{key}: {value}\r\n".encode() for key, value in fields)
            + b"\r\n" + body)


def install_connection(monkeypatch, raw):
    instances = []

    class Socket:
        def makefile(self, mode):
            assert mode == "rb"
            return BytesIO(raw)

    class Connection:
        def __init__(self, host, port, *, timeout, context):
            self.host, self.port, self.timeout, self.context = host, port, timeout, context
            self.calls = []
            self.closed = False
            instances.append(self)

        def request(self, method, path, **kwargs):
            self.calls.append((method, path, kwargs))

        def getresponse(self):
            result = self.response_class(Socket())
            result.begin()
            return result

        def close(self):
            self.closed = True

    monkeypatch.setattr(worker.http.client, "HTTPSConnection", Connection)
    return instances


def worker_result(monkeypatch, raw, **changes):
    instances = install_connection(monkeypatch, raw)
    output = BytesIO()
    assert worker.main(BytesIO(request_header(**changes) + PAYLOAD), output) == 0
    metadata, _, body = output.getvalue().partition(b"\n")
    return json.loads(metadata), body, instances


def test_worker_uses_verified_tls_exact_destination_and_one_post_without_proxy(monkeypatch):
    monkeypatch.setenv("HTTPS_PROXY", "http://must-not-be-used.invalid:8080")
    metadata, body, instances = worker_result(monkeypatch, wire_response())
    assert metadata == {"status": 200, "content_type": "application/json", "body_size": len(body)}
    assert body == b'{"ok":true}'
    assert len(instances) == 1
    connection = instances[0]
    assert (connection.host, connection.port, connection.timeout) == ("inference.example.test", 8443, 1.0)
    assert connection.context.check_hostname is True
    assert connection.context.verify_mode == ssl.CERT_REQUIRED
    assert connection.calls == [("POST", "/v1/chat/completions", {
        "body": PAYLOAD,
        "headers": {"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json",
                    "Accept": "application/json", "Accept-Encoding": "identity", "Connection": "close"},
    })]
    assert connection.closed


@pytest.mark.parametrize("url", [
    "http://example.test/infer", "https://name:password@example.test/infer",
    "https://example.test/infer#fragment", "https://example.test/infer#",
    "https://example.test:0/infer", "https://example.test:65536/infer",
    "https://example.test\r\nHost: other", "https://example.test\\other/infer",
    "https:///no-host", "https://%65xample.test/infer",
])
def test_invalid_https_destination_is_rejected_before_process_creation(monkeypatch, url):
    monkeypatch.setattr(transport.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("worker started"))
    with pytest.raises(transport.RemoteTransportError) as error:
        transport.post_https(url, TOKEN, PAYLOAD, timeout=1, max_response_bytes=1024)
    assert error.value.code == "protocol"
    assert url not in str(error.value)


@pytest.mark.parametrize("field,value", [
    ("token", "bad\r\nX: header"), ("token", ""), ("token", "space token"),
    ("timeout", True), ("timeout", 0), ("timeout", float("nan")), ("timeout", 181),
    ("max_response_bytes", True), ("max_response_bytes", 0),
    ("max_response_bytes", worker.MAX_RESPONSE_BYTES + 1),
])
def test_invalid_limits_and_credentials_fail_closed(monkeypatch, field, value):
    monkeypatch.setattr(transport.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("worker started"))
    options = {"url": URL, "token": TOKEN, "payload": PAYLOAD, "timeout": 1, "max_response_bytes": 1024}
    options[field] = value
    with pytest.raises(transport.RemoteTransportError) as error:
        transport.post_https(**options)
    assert error.value.code == "protocol"
    assert TOKEN not in str(error.value)


def test_request_size_ceiling_rejects_before_worker(monkeypatch):
    monkeypatch.setattr(transport.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("worker started"))
    with pytest.raises(transport.RemoteTransportError) as error:
        transport.post_https(URL, TOKEN, b"x" * (worker.MAX_REQUEST_BYTES + 1),
                             timeout=1, max_response_bytes=1024)
    assert error.value.code == "oversized"


@pytest.mark.parametrize("raw,code", [
    (wire_response(status=302, headers=[("Location", "https://other.invalid")]), "protocol"),
    (wire_response(headers=[("Content-Encoding", "gzip")]), "protocol"),
    (wire_response(headers=[("Content-Length", "4"), ("Content-Length", "4")]), "protocol"),
    (wire_response(headers=[("Transfer-Encoding", "gzip")]), "protocol"),
    (wire_response(headers=[("Transfer-Encoding", "chunked"), ("Content-Length", "4")]), "protocol"),
    (wire_response(headers=[("Content-Length", "-1")]), "protocol"),
    (wire_response(headers=[("Content-Length", "1, 1")]), "protocol"),
    (wire_response(headers=[("Content-Length", "1025")]), "oversized"),
    (wire_response(body=b"x" * 1025, headers=[]), "oversized"),
    (wire_response(body=b"x", headers=[("Content-Length", "8")]), "protocol"),
    (wire_response(headers=[("Content-Type", "application/json"), ("Content-Type", "text/plain")]), "protocol"),
    (wire_response(headers=[("Content-Type", "x" * 129)]), "protocol"),
    (b"not-an-http-status\r\n\r\n", "protocol"),
])
def test_worker_rejects_redirect_encoding_ambiguous_framing_and_bad_bounds(monkeypatch, raw, code):
    metadata, body, connections = worker_result(monkeypatch, raw)
    assert metadata == {"error": code}
    assert body == b""
    assert len(connections) == 1 and len(connections[0].calls) == 1 and connections[0].closed


def test_declared_and_actual_response_at_limit_is_accepted(monkeypatch):
    body = b"x" * 1024
    metadata, returned, _ = worker_result(monkeypatch, wire_response(body))
    assert metadata["body_size"] == 1024 and returned == body


def test_chunked_body_and_trailers_have_bounded_metadata(monkeypatch):
    raw = wire_response(body=b"2\r\n{}\r\n0\r\nX-Trailer: value\r\n\r\n",
                        headers=[("Transfer-Encoding", "chunked"), ("Content-Type", "application/json")])
    metadata, body, _ = worker_result(monkeypatch, raw)
    assert metadata["body_size"] == 2 and body == b"{}"
    oversized = wire_response(body=b"2\r\n{}\r\n0\r\nX-Trailer: " + b"x" * worker.MAX_HEADER_BYTES + b"\r\n\r\n",
                              headers=[("Transfer-Encoding", "chunked")])
    assert worker_result(monkeypatch, oversized)[0] == {"error": "oversized"}


@pytest.mark.parametrize("raw", [
    wire_response(headers=[("X-Large", "x" * worker.MAX_HEADER_BYTES)]),
    b"HTTP/1.1 100 Continue\r\nX-Info: " + b"x" * 9000 + b"\r\n\r\n"
    + wire_response(headers=[("X-Info", "x" * 9000)]),
    wire_response(body=(b"1;" + b"x" * worker.MAX_HEADER_BYTES + b"\r\nx\r\n0\r\n\r\n"),
                  headers=[("Transfer-Encoding", "chunked")]),
])
def test_cumulative_status_headers_and_chunk_lines_cannot_exceed_16k(monkeypatch, raw):
    assert worker_result(monkeypatch, raw)[0] == {"error": "oversized"}


@pytest.mark.parametrize("error,code", [
    (TimeoutError("secret-timeout-message"), "timeout"),
    (ssl.SSLError("private-cert-or-path"), "unavailable"),
    (OSError("private-DNS-host"), "unavailable"),
])
def test_worker_errors_never_emit_exception_text_credentials_or_payload(monkeypatch, capsys, error, code):
    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(worker, "request", fail)
    output = BytesIO()
    worker.main(BytesIO(request_header() + PAYLOAD), output)
    assert json.loads(output.getvalue()) == {"error": code}
    assert capsys.readouterr() == ("", "")
    assert TOKEN.encode() not in output.getvalue() and PAYLOAD not in output.getvalue()


@pytest.mark.parametrize("raw", [
    b"bad-json\n", request_header(payload_size=len(PAYLOAD) + 1) + PAYLOAD,
    request_header() + PAYLOAD + b"unexpected", b"x" * (worker.MAX_HEADER_BYTES + 1),
    request_header(payload_size=worker.MAX_REQUEST_BYTES + 1),
])
def test_private_worker_input_is_bounded_and_validated_without_network(monkeypatch, raw):
    monkeypatch.setattr(worker, "request", lambda *args, **kwargs: pytest.fail("network invoked"))
    output = BytesIO()
    worker.main(BytesIO(raw), output)
    assert json.loads(output.getvalue())["error"] in {"protocol", "oversized"}


@pytest.mark.parametrize("resource", [None, "models", "usage"])
def test_parent_passes_token_and_payload_only_in_stdin(monkeypatch, resource):
    captured = {}

    class Process:
        returncode = 0

        def __init__(self, command, **kwargs):
            captured.update(command=command, options=kwargs)
            self.stdin, self.stdout, self.stderr = BytesIO(), BytesIO(), None
            captured["pipes"] = (self.stdin, self.stdout)

        def communicate(self, data=None, timeout=None):
            captured.update(data=data, timeout=timeout)
            return b'{"status":200,"body_size":2,"content_type":"application/json"}\n{}', None

        def poll(self):
            return self.returncode

        def kill(self):
            pytest.fail("completed worker killed")

    monkeypatch.setattr(transport.subprocess, "Popen", Process)
    if resource is None:
        result = transport.post_https(URL, TOKEN, PAYLOAD, timeout=1.0, max_response_bytes=1024)
    else:
        result = transport.get_tokenfactory(resource, TOKEN, timeout=1.0, max_response_bytes=1024)
    assert result == transport.HttpResponse(200, b"{}", "application/json")
    assert captured["command"] == [sys.executable, "-I", "-S", str(transport._WORKER_PATH)]
    assert TOKEN not in repr(captured["command"]) and URL not in repr(captured["command"])
    assert captured["options"]["stderr"] == subprocess.DEVNULL
    assert captured["options"]["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)
    assert captured["options"]["close_fds"] is True
    header, _, body = captured["data"].partition(b"\n")
    fields = json.loads(header)
    assert fields["token"] == TOKEN
    if resource is None:
        assert body == PAYLOAD and "method" not in fields
    else:
        assert body == b"" and fields["payload_size"] == 0 and fields["method"] == "GET"
        assert fields["url"] == worker.TOKENFACTORY_RESOURCES[resource]
    assert 0 < captured["timeout"] <= 1.0
    assert all(pipe.closed for pipe in captured["pipes"])


@pytest.mark.parametrize("raw,code", [
    (b'{"error":"timeout"}\n', "timeout"),
    (b'{"error":"private-secret"}\n', "protocol"),
    (b'{"status":200,"body_size":3,"content_type":"application/json"}\n{}', "protocol"),
    (b'{"status":302,"body_size":0,"content_type":""}\n', "protocol"),
    (b'{"status":true,"body_size":0,"content_type":""}\n', "protocol"),
    (b'{"status":200,"body_size":0,"content_type":"","extra":1}\n', "protocol"),
    (b"not-json\n", "protocol"),
    (b"x" * (worker.MAX_PROTOCOL_BYTES + 1025), "oversized"),
])
def test_parent_validates_child_protocol_without_echoing_untrusted_output(raw, code):
    with pytest.raises(transport.RemoteTransportError) as error:
        transport._decode_response(raw, 1024)
    assert error.value.code == code
    assert "private-secret" not in str(error.value)


@pytest.mark.parametrize("read_only", [False, True])
def test_absolute_deadline_kills_and_reaps_worker_even_if_it_never_reads_stdin(monkeypatch, tmp_path, read_only):
    blocked = tmp_path / "blocked_worker.py"
    blocked.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    monkeypatch.setattr(transport, "_WORKER_PATH", blocked)
    real_popen = subprocess.Popen
    children = []

    def launch(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(transport.subprocess, "Popen", launch)
    started = time.monotonic()
    with pytest.raises(transport.RemoteTransportError) as error:
        if read_only:
            transport.get_tokenfactory("models", TOKEN, timeout=0.3, max_response_bytes=1024)
        else:
            transport.post_https(URL, TOKEN, b"x" * (2 * 1024 * 1024), timeout=0.3, max_response_bytes=1024)
    elapsed = time.monotonic() - started
    assert error.value.code == "timeout"
    assert 0.2 <= elapsed < 5
    assert len(children) == 1 and children[0].poll() is not None
    assert children[0].stdin.closed and children[0].stdout.closed


@pytest.mark.parametrize("already_expired", [False, True])
def test_pipe_oserror_after_deadline_retains_timeout_classification(monkeypatch, already_expired):
    class Timer:
        def __init__(self, interval, callback):
            self.callback = callback

        def start(self):
            if already_expired:
                self.callback()

        def cancel(self):
            pass

        def join(self):
            pass

    class Process:
        returncode = None
        calls = 0

        def __init__(self, *args, **kwargs):
            self.stdin, self.stdout, self.stderr = BytesIO(), BytesIO(), None

        def communicate(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise OSError("private pipe failure")
            return b"", None

        def kill(self):
            self.returncode = -9

        def poll(self):
            return self.returncode

    monkeypatch.setattr(transport.threading, "Timer", Timer)
    monkeypatch.setattr(transport.subprocess, "Popen", Process)
    with pytest.raises(transport.RemoteTransportError) as error:
        transport.post_https(URL, TOKEN, PAYLOAD, timeout=1, max_response_bytes=1024)
    assert error.value.code == ("timeout" if already_expired else "unavailable")
    assert "private pipe failure" not in str(error.value)


@pytest.mark.parametrize("failure_stage", ["construct", "start"])
def test_timer_startup_failure_kills_reaps_and_closes_worker_without_leaking_error(
    monkeypatch, tmp_path, capsys, failure_stage,
):
    blocked = tmp_path / "blocked_worker.py"
    blocked.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    monkeypatch.setattr(transport, "_WORKER_PATH", blocked)
    real_popen = subprocess.Popen
    children = []

    def launch(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        children.append(process)
        return process

    class BrokenTimer:
        def __init__(self, *args):
            if failure_stage == "construct":
                raise RuntimeError("private construction detail " + TOKEN)

        def start(self):
            raise RuntimeError("private thread-start detail " + TOKEN)

        def cancel(self):
            pass

        def join(self):
            pytest.fail("unstarted timer must not be joined")

    monkeypatch.setattr(transport.subprocess, "Popen", launch)
    monkeypatch.setattr(transport.threading, "Timer", BrokenTimer)
    with pytest.raises(transport.RemoteTransportError) as error:
        transport.post_https(URL, TOKEN, PAYLOAD, timeout=1, max_response_bytes=1024)
    assert error.value.code == "unavailable"
    assert TOKEN not in str(error.value) and "private" not in str(error.value)
    assert error.value.__suppress_context__ is True
    assert capsys.readouterr() == ("", "")
    assert len(children) == 1 and children[0].poll() is not None
    assert children[0].stdin.closed and children[0].stdout.closed


def test_worker_runs_isolated_without_site_packages_and_rejects_input_offline():
    result = subprocess.run([sys.executable, "-I", "-S", str(transport._WORKER_PATH)],
                            input=b"{}\n", capture_output=True, timeout=10, check=False,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert result.returncode == 0
    assert result.stdout == b'{"error":"protocol"}\n'
    assert result.stderr == b""


def test_importing_transport_does_not_load_gpu_or_application_packages():
    script = """
import importlib.abc
import sys
class Guard(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'torch', 'transformers', 'PIL', 'pydantic', 'fastapi'}:
            raise AssertionError('heavy import: ' + fullname)
sys.meta_path.insert(0, Guard())
from rekit.inference.adapters.remote_transport import post_https
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True,
                            timeout=10, cwd=Path(__file__).parents[2], check=False,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("resource,path", [
    ("models", "/radeon/api/v1/models"),
    ("usage", "/radeon/api/v1/usage?include_recent=true"),
])
def test_get_discovery_uses_only_exact_same_host_with_no_body_or_proxy(monkeypatch, resource, path):
    monkeypatch.setenv("HTTPS_PROXY", "http://must-not-be-used.invalid:8080")
    connections = install_connection(monkeypatch, wire_response())
    output = BytesIO()
    worker.main(BytesIO(request_header(url=worker.TOKENFACTORY_RESOURCES[resource],
                                      payload_size=0, method="GET")), output)
    metadata, _, body = output.getvalue().partition(b"\n")
    assert json.loads(metadata) == {"status": 200, "content_type": "application/json", "body_size": len(body)}
    assert len(connections) == 1
    connection = connections[0]
    assert (connection.host, connection.port) == ("developer.amd.com.cn", 443)
    assert connection.context.check_hostname is True
    assert connection.context.verify_mode == ssl.CERT_REQUIRED
    assert connection.calls == [("GET", path, {
        "body": None,
        "headers": {"Authorization": "Bearer " + TOKEN, "Accept": "application/json",
                    "Accept-Encoding": "identity", "Connection": "close"},
    })]
    assert connection.closed


@pytest.mark.parametrize("resource", ["", "Models", "../models", "chat/completions", "usage?include_recent=true",
                                      "https://radeon-global.anruicloud.com/api/profile/model-usage?include_recent=true",
                                      None, [], True])
def test_get_resource_cannot_be_an_arbitrary_url_or_path(monkeypatch, resource):
    monkeypatch.setattr(transport.subprocess, "Popen", lambda *args, **kwargs: pytest.fail("worker started"))
    with pytest.raises(transport.RemoteTransportError) as error:
        transport.get_tokenfactory(resource, TOKEN, timeout=1, max_response_bytes=1024)
    assert error.value.code == "protocol"
    assert TOKEN not in str(error.value)


@pytest.mark.parametrize("url", [
    "https://developer.amd.com.cn/radeon/api/v1/models/",
    "https://developer.amd.com.cn:443/radeon/api/v1/models",
    "https://DEVELOPER.amd.com.cn/radeon/api/v1/models",
    "https://developer.amd.com.cn/radeon/api/v1/%6dodels",
    "https://developer.amd.com.cn/radeon/api/v1/x/../models",
    "https://developer.amd.com.cn/radeon/api/v1/models?extra=true",
    "https://developer.amd.com.cn/radeon/api/v1/usage",
    "https://developer.amd.com.cn/radeon/api/v1/usage?include_recent=false",
    "https://developer.amd.com.cn/radeon/api/v1/usage?include_recent=true&extra=1",
    "https://developer.amd.com.cn.evil.invalid/radeon/api/v1/models",
    "https://radeon-global.anruicloud.com/api/profile/model-usage?include_recent=true",
    URL,
])
def test_worker_get_revalidates_exact_destinations_before_network(monkeypatch, url):
    monkeypatch.setattr(worker, "request", lambda *args, **kwargs: pytest.fail("network invoked"))
    output = BytesIO()
    worker.main(BytesIO(request_header(url=url, payload_size=0, method="GET")), output)
    assert output.getvalue() == b'{"error":"protocol"}\n'


@pytest.mark.parametrize("method,payload_size,body", [
    ("HEAD", 0, b""), ("DELETE", 0, b""), ("get", 0, b""), (True, 0, b""),
    ("GET", 1, b"x"), ("GET", True, b"x"), ("GET", 0, b"unexpected"), ("POST", 0, b""),
])
def test_worker_rejects_other_methods_get_bodies_and_empty_post(monkeypatch, method, payload_size, body):
    monkeypatch.setattr(worker, "request", lambda *args, **kwargs: pytest.fail("network invoked"))
    output = BytesIO()
    worker.main(BytesIO(request_header(url=worker.TOKENFACTORY_RESOURCES["models"],
                                      method=method, payload_size=payload_size) + body), output)
    assert output.getvalue() == b'{"error":"protocol"}\n'


def test_get_redirect_never_forwards_credentials_to_official_other_host(monkeypatch):
    connections = install_connection(monkeypatch, wire_response(status=302, headers=[
        ("Location", "https://radeon-global.anruicloud.com/api/profile/model-usage?include_recent=true"),
    ]))
    output = BytesIO()
    worker.main(BytesIO(request_header(url=worker.TOKENFACTORY_RESOURCES["usage"],
                                      method="GET", payload_size=0)), output)
    assert output.getvalue() == b'{"error":"protocol"}\n'
    assert len(connections) == 1 and len(connections[0].calls) == 1 and connections[0].closed
    assert connections[0].host == "developer.amd.com.cn"


def test_numeric_quota_and_retry_metadata_survive_parent_boundary_without_other_headers(monkeypatch):
    headers = [("Content-Type", "application/json"), ("Retry-After", "60"),
               ("X-RateLimit-Limit-User-RPM", "30"), ("X-RateLimit-Remaining-User-RPM", "0"),
               ("X-RateLimit-Reset", "1792018800"), ("X-RateLimit-Limit-User-Daily-USD", "10.50"),
               ("X-RateLimit-Used-User-Daily-USD", "1.8412"),
               ("X-RateLimit-Remaining-User-Daily-USD", "8.6588"),
               ("X-RateLimit-Reset-User-Daily-USD", "1792105200"),
               ("X-Private-Account", "private-account-must-not-leak"),
               ("Set-Cookie", "private-session-must-not-leak")]
    metadata, body, connections = worker_result(monkeypatch, wire_response(status=429, headers=headers))
    response = transport._decode_response(json.dumps(metadata).encode() + b"\n" + body, 1024)
    assert response.status == 429 and response.retry_after_seconds == 60
    assert response.quota_headers == {
        "user_rpm_limit": 30, "user_rpm_remaining": 0, "rpm_reset_unix": 1792018800,
        "daily_usd_limit": 10.5, "daily_usd_used": 1.8412, "daily_usd_remaining": 8.6588,
        "daily_reset_unix": 1792105200,
    }
    assert "private-" not in json.dumps(metadata)
    assert len(connections) == 1 and len(connections[0].calls) == 1
    assert len(json.dumps(metadata).encode()) < worker.MAX_PROTOCOL_BYTES


@pytest.mark.parametrize("value,expected", [
    (None, None), ("0", 0), ("60", 60), ("86400", 86400), ("86401", None),
    ("999999999999999999999999999", None), ("-1", None), ("1.5", None),
    ("NaN", None), ("Inf", None), ("1e2", None), ("６０", None), ("60\r\nX: secret", None),
    ("Thu, 15 Oct 2026 00:00:01 GMT", 1), ("Wed, 14 Oct 2026 23:59:59 GMT", 0),
    ("Fri, 16 Oct 2026 00:00:01 GMT", None), ("Thu, 15 Oct 2026 00:00:01 -0000", None),
])
def test_retry_after_parses_bounded_delta_or_aware_date_without_early_retry(value, expected):
    now = datetime(2026, 10, 15, 0, 0, 0, 100000, tzinfo=timezone.utc)
    assert worker._retry_after(value, now=now) == expected


@pytest.mark.parametrize("header", ["Retry-After"] + [field[0] for field in worker.QUOTA_FIELDS])
def test_duplicate_optional_headers_reject_ambiguous_response(monkeypatch, header):
    metadata, body, connections = worker_result(monkeypatch, wire_response(headers=[(header, "1"), (header, "2")]))
    assert metadata == {"error": "protocol"} and body == b""
    assert len(connections) == 1 and connections[0].closed


@pytest.mark.parametrize("header,value", [
    ("Retry-After", "999999"), ("X-RateLimit-Limit-User-RPM", "1.5"),
    ("X-RateLimit-Limit-User-RPM", "1000001"), ("X-RateLimit-Remaining-User-RPM", "-1"),
    ("X-RateLimit-Reset", "253402300800"), ("X-RateLimit-Reset-User-Daily-USD", "1e9"),
    ("X-RateLimit-Limit-User-Daily-USD", "NaN"), ("X-RateLimit-Used-User-Daily-USD", "Infinity"),
    ("X-RateLimit-Remaining-User-Daily-USD", "-0.1"),
    ("X-RateLimit-Limit-User-Daily-USD", "1000000001"),
    ("X-RateLimit-Used-User-Daily-USD", "9" * 65),
])
def test_invalid_optional_numeric_header_is_unknown_not_zero(monkeypatch, header, value):
    metadata, body, _ = worker_result(monkeypatch, wire_response(headers=[(header, value)]))
    response = transport._decode_response(json.dumps(metadata).encode() + b"\n" + body, 1024)
    assert response.status == 200 and response.retry_after_seconds is None and response.quota_headers is None


@pytest.mark.parametrize("extra", [
    {"retry_after_seconds": True}, {"retry_after_seconds": -1}, {"retry_after_seconds": 1.5},
    {"retry_after_seconds": 86401}, {"retry_after_seconds": None},
    {"quota_headers": None}, {"quota_headers": []}, {"quota_headers": {"secret": 1}},
    {"quota_headers": {"user_rpm_limit": True}}, {"quota_headers": {"user_rpm_remaining": 1.0}},
    {"quota_headers": {"rpm_reset_unix": 253402300800}},
    {"quota_headers": {"daily_usd_used": float("nan")}},
    {"quota_headers": {"daily_usd_limit": float("inf")}},
    {"quota_headers": {"daily_usd_remaining": -0.1}},
    {"quota_headers": {"daily_usd_limit": 10 ** 400}},
    {"quota_headers": {"daily_reset_unix": "1792105200"}},
])
def test_parent_revalidates_optional_metadata_strict_types_and_finite_bounds(extra):
    metadata = {"status": 200, "body_size": 2, "content_type": "application/json", **extra}
    with pytest.raises(transport.RemoteTransportError) as error:
        transport._decode_response(json.dumps(metadata).encode() + b"\n{}", 1024)
    assert error.value.code == "protocol"
