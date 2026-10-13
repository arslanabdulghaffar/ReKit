"""Offline transport tests; no AMD connection, credentials, or GPU required."""

from io import BytesIO
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


def test_parent_passes_token_and_payload_only_in_stdin(monkeypatch):
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
    result = transport.post_https(URL, TOKEN, PAYLOAD, timeout=1.0, max_response_bytes=1024)
    assert result == transport.HttpResponse(200, b"{}", "application/json")
    assert captured["command"] == [sys.executable, "-I", "-S", str(transport._WORKER_PATH)]
    assert TOKEN not in repr(captured["command"]) and URL not in repr(captured["command"])
    assert captured["options"]["stderr"] == subprocess.DEVNULL
    assert captured["options"]["creationflags"] == getattr(subprocess, "CREATE_NO_WINDOW", 0)
    assert captured["options"]["close_fds"] is True
    header, _, body = captured["data"].partition(b"\n")
    assert json.loads(header)["token"] == TOKEN and body == PAYLOAD
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


def test_absolute_deadline_kills_and_reaps_worker_even_if_it_never_reads_stdin(monkeypatch, tmp_path):
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
