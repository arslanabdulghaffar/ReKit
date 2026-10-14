"""Private stdlib-only HTTPS worker, executable with Python -I -S.

One request, no redirects/retries/proxies. Only a bounded protocol response is
written to stdout; exception text and request credentials are never emitted.
"""

import http.client
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import json
import math
import re
import ssl
import sys
from urllib.parse import urlsplit


MAX_HEADER_BYTES = 16 * 1024
MAX_REQUEST_BYTES = 30 * 1024 * 1024
MAX_RESPONSE_BYTES = 128 * 1024
MAX_PROTOCOL_BYTES = 1024
MAX_RETRY_AFTER_SECONDS = 86400
TOKENFACTORY_RESOURCES = {
    "models": "https://developer.amd.com.cn/radeon/api/v1/models",
    # This mission-supplied alias is unverified; never fall back to another host.
    "usage": "https://developer.amd.com.cn/radeon/api/v1/usage?include_recent=true",
}
# A separately authorized, deliberate call. Never use this as alias fallback.
TOKENFACTORY_QUOTA_URL = "https://radeon-global.anruicloud.com/api/profile/model-usage?include_recent=true"
# Only documented numeric headers cross the worker boundary. These ceilings are
# parsing limits, not assumed account entitlements or permission to generate.
QUOTA_FIELDS = (
    ("X-RateLimit-Limit-User-RPM", "user_rpm_limit", int, 1_000_000),
    ("X-RateLimit-Remaining-User-RPM", "user_rpm_remaining", int, 1_000_000),
    ("X-RateLimit-Reset", "rpm_reset_unix", int, 253402300799),
    ("X-RateLimit-Limit-User-Daily-USD", "daily_usd_limit", float, 1_000_000_000),
    ("X-RateLimit-Used-User-Daily-USD", "daily_usd_used", float, 1_000_000_000),
    ("X-RateLimit-Remaining-User-Daily-USD", "daily_usd_remaining", float, 1_000_000_000),
    ("X-RateLimit-Reset-User-Daily-USD", "daily_reset_unix", int, 253402300799),
)


class WorkerError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def validate_request(url, token, payload_size, timeout, max_response_bytes, method="POST"):
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
    if method not in ("POST", "GET"):
        raise WorkerError("protocol")
    if method == "GET" and url not in (*TOKENFACTORY_RESOURCES.values(), TOKENFACTORY_QUOTA_URL):
        raise WorkerError("protocol")
    if (type(payload_size) is not int or payload_size < 0
            or (method == "POST" and payload_size == 0)
            or (method == "GET" and payload_size != 0)):
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


def _retry_after(value, *, now=None):
    """Return bounded seconds, never shorten an excessive wait into a retry."""
    if (not isinstance(value, str) or not 1 <= len(value) <= 128
            or any(ord(char) < 32 or ord(char) >= 127 for char in value)):
        return None
    if value.isdecimal():
        if len(value) > 10:
            return None
        seconds = int(value)
    else:
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                return None
            current = now if now is not None else datetime.now(timezone.utc)
            seconds = max(0, math.ceil((date - current).total_seconds()))
        except (ValueError, TypeError, OverflowError):
            return None
    return seconds if 0 <= seconds <= MAX_RETRY_AFTER_SECONDS else None


def _quota_value(value, kind, maximum):
    if not isinstance(value, str) or not 1 <= len(value) <= 64:
        return None
    pattern = r"[0-9]+" if kind is int else r"[0-9]+(?:\.[0-9]+)?"
    if re.fullmatch(pattern, value) is None:
        return None
    number = kind(value)
    return number if math.isfinite(number) and 0 <= number <= maximum else None


def validate_response_metadata(metadata):
    """Validate optional parsed fields again in the parent; no raw headers."""
    if "retry_after_seconds" in metadata:
        value = metadata["retry_after_seconds"]
        if type(value) is not int or not 0 <= value <= MAX_RETRY_AFTER_SECONDS:
            raise WorkerError("protocol")
    if "quota_headers" in metadata:
        quota = metadata["quota_headers"]
        allowed = {key: (kind, maximum) for _, key, kind, maximum in QUOTA_FIELDS}
        if not isinstance(quota, dict) or not set(quota) <= set(allowed):
            raise WorkerError("protocol")
        for key, value in quota.items():
            kind, maximum = allowed[key]
            types = (int,) if kind is int else (int, float)
            if (type(value) not in types or not 0 <= value <= maximum
                    or not math.isfinite(value)):
                raise WorkerError("protocol")


def request(url, token, payload, *, timeout, max_response_bytes, method="POST"):
    """Return status/type/body/parsed metadata; TLS verifies cert and hostname."""
    if not isinstance(payload, bytes):
        raise WorkerError("protocol")
    parsed = validate_request(url, token, len(payload), timeout, max_response_bytes, method)
    path = parsed.path or "/"
    if parsed.query:
        path += "?" + parsed.query
    connection = http.client.HTTPSConnection(
        parsed.hostname, parsed.port or 443, timeout=timeout,
        context=ssl.create_default_context(),
    )
    connection.response_class = _BoundedResponse
    try:
        headers = {
            "Authorization": "Bearer " + token,
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "Connection": "close",
        }
        if method == "POST":
            headers["Content-Type"] = "application/json"
        connection.request(method, path, body=payload if method == "POST" else None, headers=headers)
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
        parsed_metadata = {}
        retry = _retry_after(_one_header(response, "Retry-After"))
        if retry is not None:
            parsed_metadata["retry_after_seconds"] = retry
        quota = {}
        for header, key, kind, maximum in QUOTA_FIELDS:
            value = _quota_value(_one_header(response, header), kind, maximum)
            if value is not None:
                quota[key] = value
        if quota:
            parsed_metadata["quota_headers"] = quota
        body = response.read(max_response_bytes + 1)
        if len(body) > max_response_bytes:
            raise WorkerError("oversized")
        if declared is not None and len(body) != declared:
            raise WorkerError("protocol")
        return response.status, content_type, body, parsed_metadata
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
        required = {"url", "token", "payload_size", "timeout", "max_response_bytes"}
        if not isinstance(data, dict) or set(data) not in (required, required | {"method"}):
            raise WorkerError("protocol")
        validate_request(**data)
        payload = stdin.read(data["payload_size"] + 1)
        if len(payload) != data["payload_size"]:
            raise WorkerError("protocol")
        status, content_type, body, parsed_metadata = request(
            data["url"], data["token"], payload, timeout=data["timeout"],
            max_response_bytes=data["max_response_bytes"], method=data.get("method", "POST"),
        )
        metadata = {"status": status, "content_type": content_type, "body_size": len(body)}
        metadata.update(parsed_metadata)
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
