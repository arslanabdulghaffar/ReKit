"""A single bounded HTTPS call, isolated so DNS/TLS/slow I/O can be stopped."""

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import sys
import threading
import time

from rekit.inference.adapters.https_worker import (
    MAX_HEADER_BYTES, MAX_PROTOCOL_BYTES, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES,
    WorkerError, validate_request,
)


_WORKER_PATH = Path(__file__).with_name("https_worker.py")
_ERRORS = {
    "timeout": "Remote inference exceeded its network deadline",
    "unavailable": "Remote inference transport is unavailable",
    "oversized": "Remote inference transport exceeded a size limit",
    "protocol": "Remote inference transport rejected an invalid protocol message",
}


class RemoteTransportError(RuntimeError):
    def __init__(self, code: str):
        self.code = code if code in _ERRORS else "protocol"
        super().__init__(_ERRORS[self.code])


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes
    content_type: str


def _decode_response(raw: bytes, maximum: int) -> HttpResponse:
    if len(raw) > MAX_PROTOCOL_BYTES + maximum:
        raise RemoteTransportError("oversized")
    line, separator, body = raw.partition(b"\n")
    if not separator or len(line) > MAX_PROTOCOL_BYTES:
        raise RemoteTransportError("protocol")
    try:
        metadata = json.loads(line)
    except (ValueError, UnicodeError):
        raise RemoteTransportError("protocol") from None
    if not isinstance(metadata, dict):
        raise RemoteTransportError("protocol")
    if set(metadata) == {"error"} and not body:
        raise RemoteTransportError(metadata["error"] if isinstance(metadata["error"], str) else "protocol")
    if set(metadata) != {"status", "body_size", "content_type"}:
        raise RemoteTransportError("protocol")
    status, size, content_type = metadata["status"], metadata["body_size"], metadata["content_type"]
    if (type(status) is not int or not 200 <= status <= 599 or 300 <= status <= 399
            or type(size) is not int or size != len(body) or size > maximum
            or not isinstance(content_type, str) or len(content_type) > 128
            or any(ord(char) < 32 or ord(char) >= 127 for char in content_type)):
        raise RemoteTransportError("protocol")
    return HttpResponse(status=status, body=body, content_type=content_type)


def post_https(url: str, token: str, payload: bytes, *, timeout: float,
               max_response_bytes: int) -> HttpResponse:
    """Never put credentials in argv or logs. Kill and reap on absolute deadline.

    The deadline also bounds blocked stdin on Windows, where communicate's own
    timeout does not interrupt its synchronous pipe write. OS process creation
    and final process cleanup can add overhead; no network work survives timeout.
    """
    if not isinstance(payload, bytes):
        raise RemoteTransportError("protocol")
    try:
        validate_request(url, token, len(payload), timeout, max_response_bytes)
    except WorkerError as error:
        raise RemoteTransportError(error.code) from None
    header = json.dumps({
        "url": url, "token": token, "payload_size": len(payload),
        "timeout": timeout, "max_response_bytes": max_response_bytes,
    }, separators=(",", ":")).encode("ascii") + b"\n"
    if len(header) > MAX_HEADER_BYTES:
        raise RemoteTransportError("oversized")
    expired = threading.Event()
    deadline = time.monotonic() + timeout
    try:
        process = subprocess.Popen(
            [sys.executable, "-I", "-S", str(_WORKER_PATH)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            close_fds=True,
        )
    except OSError:
        raise RemoteTransportError("unavailable") from None
    def expire():
        expired.set()
        try:
            process.kill()
        except OSError:
            pass  # It may have exited between the timer and kill call.

    timer = None
    timer_started = False
    try:
        try:
            timer = threading.Timer(max(0, deadline - time.monotonic()), expire)
            timer.daemon = True
            timer.start()
            timer_started = True
        except (RuntimeError, OSError):
            raise RemoteTransportError("unavailable") from None
        try:
            raw, _ = process.communicate(header + payload, timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            expire()
            process.communicate()  # The worker creates no descendants; drain and reap.
            raise RemoteTransportError("timeout") from None
        except OSError:
            timed_out = expired.is_set() or time.monotonic() >= deadline
            expire()
            process.communicate()
            raise RemoteTransportError("timeout" if timed_out else "unavailable") from None
        if expired.is_set() or time.monotonic() >= deadline:
            raise RemoteTransportError("timeout")
        if process.returncode != 0:
            raise RemoteTransportError("unavailable")
        return _decode_response(raw, max_response_bytes)
    finally:
        if timer is not None:
            timer.cancel()
            if timer_started:
                timer.join()
        if process.poll() is None:
            process.kill()
            process.communicate()
        elif not timer_started:
            process.communicate()  # Close pipes even if startup failed after the child exited.
