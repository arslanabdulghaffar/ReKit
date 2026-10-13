"""Private stdlib-only HTTPS worker, executable with Python -I -S.

One request, no redirects/retries/proxies. Only a bounded protocol response is
written to stdout; exception text and request credentials are never emitted.
"""

import http.client
import json
import math
import ssl
import sys
from urllib.parse import urlsplit


MAX_HEADER_BYTES = 16 * 1024
MAX_REQUEST_BYTES = 30 * 1024 * 1024
MAX_RESPONSE_BYTES = 128 * 1024
MAX_PROTOCOL_BYTES = 1024


class WorkerError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def validate_request(url, token, payload_size, timeout, max_response_bytes):
    """Validate both the parent boundary and the private worker input."""
    if (not isinstance(url, str) or not 1 <= len(url) <= 4096
            or any(ord(char) <= 32 or ord(char) >= 127 for char in url)
            or "\\" in url or "#" in url):
        raise WorkerError("protocol")
    try:
        parsed = urlsplit(url)
        port = parsed.port
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or "%" in parsed.hostname
                or (port is not None and not 1 <= port <= 65535)):
            raise ValueError
    except ValueError:
        raise WorkerError("protocol") from None
    if (not isinstance(token, str) or not 1 <= len(token) <= 4096
            or any(ord(char) <= 32 or ord(char) >= 127 for char in token)):
        raise WorkerError("protocol")
    if type(payload_size) is not int or payload_size < 1:
        raise WorkerError("protocol")
    if payload_size > MAX_REQUEST_BYTES:
        raise WorkerError("oversized")
    if (type(timeout) not in (int, float) or not math.isfinite(timeout)
            or not 0 < timeout <= 180):
        raise WorkerError("protocol")
    if type(max_response_bytes) is not int or not 1 <= max_response_bytes <= MAX_RESPONSE_BYTES:
        raise WorkerError("protocol")
    return parsed


class _BoundedMetadataReader:
    """Count status/headers and chunk framing/trailers, without counting body."""
    def __init__(self, stream):
        self.stream = stream
        self.used = 0

    def readline(self, size=-1):
        remaining = MAX_HEADER_BYTES - self.used
        size = min(size, remaining + 1) if size >= 0 else remaining + 1
        line = self.stream.readline(size)
        self.used += len(line)
        if self.used > MAX_HEADER_BYTES:
            raise WorkerError("oversized")
        return line

    def __getattr__(self, name):
        return getattr(self.stream, name)


class _BoundedResponse(http.client.HTTPResponse):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fp = _BoundedMetadataReader(self.fp)


def _one_header(response, name):
    values = response.headers.get_all(name, [])
    if len(values) > 1:
        raise WorkerError("protocol")
    return values[0].strip() if values else None


def request(url, token, payload, *, timeout, max_response_bytes):
    """Return (status, content_type, body); TLS verifies certificate and hostname."""
    if not isinstance(payload, bytes):
        raise WorkerError("protocol")
    parsed = validate_request(url, token, len(payload), timeout, max_response_bytes)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    connection = http.client.HTTPSConnection(
        parsed.hostname, parsed.port or 443, timeout=timeout,
        context=ssl.create_default_context(),
    )
    connection.response_class = _BoundedResponse
    try:
        connection.request("POST", path, body=payload, headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "Connection": "close",
        })
        response = connection.getresponse()
        if not 200 <= response.status <= 599 or 300 <= response.status <= 399:
            raise WorkerError("protocol")
        encoding = _one_header(response, "Content-Encoding")
        if encoding is not None and encoding.lower() != "identity":
            raise WorkerError("protocol")
        transfer = _one_header(response, "Transfer-Encoding")
        length = _one_header(response, "Content-Length")
        if transfer is not None and (transfer.lower() != "chunked" or length is not None):
            raise WorkerError("protocol")
        declared = None
        if length is not None:
            if not length.isascii() or not length.isdecimal():
                raise WorkerError("protocol")
            declared = int(length)
            if declared > max_response_bytes:
                raise WorkerError("oversized")
        content_type = _one_header(response, "Content-Type") or ""
        if len(content_type) > 128 or any(ord(char) < 32 or ord(char) >= 127 for char in content_type):
            raise WorkerError("protocol")
        body = response.read(max_response_bytes + 1)
        if len(body) > max_response_bytes:
            raise WorkerError("oversized")
        if declared is not None and len(body) != declared:
            raise WorkerError("protocol")
        return response.status, content_type, body
    finally:
        connection.close()


def main(stdin=None, stdout=None):
    stdin = stdin if stdin is not None else sys.stdin.buffer
    stdout = stdout if stdout is not None else sys.stdout.buffer
    try:
        line = stdin.readline(MAX_HEADER_BYTES + 1)
        if len(line) > MAX_HEADER_BYTES or not line.endswith(b"\n"):
            raise WorkerError("protocol")
        data = json.loads(line)
        if not isinstance(data, dict) or set(data) != {
            "url", "token", "payload_size", "timeout", "max_response_bytes"
        }:
            raise WorkerError("protocol")
        validate_request(**data)
        payload = stdin.read(data["payload_size"] + 1)
        if len(payload) != data["payload_size"]:
            raise WorkerError("protocol")
        status, content_type, body = request(
            data["url"], data["token"], payload, timeout=data["timeout"],
            max_response_bytes=data["max_response_bytes"],
        )
        metadata = {"status": status, "content_type": content_type, "body_size": len(body)}
    except WorkerError as error:
        metadata, body = {"error": error.code}, b""
    except TimeoutError:
        metadata, body = {"error": "timeout"}, b""
    except (ValueError, TypeError, http.client.HTTPException):
        metadata, body = {"error": "protocol"}, b""
    except Exception:
        metadata, body = {"error": "unavailable"}, b""
    stdout.write(json.dumps(metadata, separators=(",", ":")).encode("ascii") + b"\n" + body)
    stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
