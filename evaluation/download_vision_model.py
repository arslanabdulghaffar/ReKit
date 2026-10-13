"""Download only the approved immutable Qwen checkpoint into ignored local storage.

Uses the standard library. Existing complete files are verified and reused;
interrupted transfers resume only when the server confirms the requested range.
"""

from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "configs" / "inference" / "qwen3-vl-2b.json"
MODEL_ID = "Qwen/Qwen3-VL-2B-Instruct"
REVISION = "89644892e4d85e24eaac8bacfd4f463576704203"
DESTINATION = ROOT / "models" / "Qwen3-VL-2B-Instruct" / REVISION
MAXIMUM_BYTES = 6 * 1024**3
CHUNK_BYTES = 1024 * 1024
EXPECTED_NAMES = frozenset({
    "chat_template.json", "config.json", "generation_config.json", "merges.txt",
    "preprocessor_config.json", "tokenizer.json", "tokenizer_config.json",
    "video_preprocessor_config.json", "vocab.json", "model.safetensors",
})


def _contained(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT.resolve()) or resolved == ROOT.resolve():
        raise ValueError("Model storage must remain inside the repository's ignored models directory")
    cursor = path
    while cursor != ROOT:
        if cursor.is_symlink() or cursor.is_junction():
            raise ValueError("Model storage cannot traverse a symlink or junction")
        cursor = cursor.parent
    if not resolved.is_relative_to((ROOT / "models").resolve()):
        raise ValueError("Model storage must remain inside the ignored models directory")
    return resolved


def _manifest() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["model_id"] != MODEL_ID or manifest["revision"] != REVISION:
        raise ValueError("Only the qualified immutable model is authorized")
    files = manifest["files"]
    if len(files) != len(EXPECTED_NAMES) or {file["name"] for file in files} != EXPECTED_NAMES:
        raise ValueError("The model manifest must name exactly the ten approved files")
    for file in files:
        if type(file["size"]) is not int or file["size"] <= 0:
            raise ValueError("Every model file needs an exact positive byte count")
        algorithm = "sha256" if file["name"] == "model.safetensors" else "git_blob_sha1"
        length = 64 if algorithm == "sha256" else 40
        if not re.fullmatch(f"[0-9a-f]{{{length}}}", file.get(algorithm, "")):
            raise ValueError("Every model file needs its official content hash")
    total = sum(file["size"] for file in files)
    if total != manifest["expected_total_bytes"] or total > MAXIMUM_BYTES:
        raise ValueError("Model manifest exceeds its approved size or 6 GiB budget")
    if manifest["maximum_download_bytes"] != MAXIMUM_BYTES:
        raise ValueError("The model download budget cannot be enlarged")
    return manifest


def _verify(path: Path, expected: dict) -> dict:
    _contained(path)
    if not path.is_file() or path.stat().st_size != expected["size"]:
        raise ValueError(f"Unexpected size for {expected['name']}; existing bytes were preserved")
    sha256 = hashlib.sha256()
    git_blob = hashlib.sha1(f"blob {expected['size']}\0".encode("ascii"))
    with path.open("rb") as source:
        while block := source.read(CHUNK_BYTES):
            sha256.update(block)
            git_blob.update(block)
    actual = sha256.hexdigest() if "sha256" in expected else git_blob.hexdigest()
    required = expected.get("sha256", expected.get("git_blob_sha1"))
    if actual != required:
        raise ValueError(f"Content hash mismatch for {expected['name']}; existing bytes were preserved")
    return {"name": expected["name"], "size": expected["size"], "sha256": sha256.hexdigest()}


def _download(expected: dict) -> tuple[dict, int]:
    target = _contained(DESTINATION / expected["name"])
    partial = _contained(target.with_name(target.name + ".part"))
    if target.exists():
        print(f"Verify and reuse {target.name}", flush=True)
        return _verify(target, expected), 0
    offset = partial.stat().st_size if partial.exists() else 0
    if partial.exists() and not partial.is_file():
        raise ValueError("Partial model download must be a regular file")
    if offset > expected["size"]:
        raise ValueError(f"Partial {target.name} is oversized; existing bytes were preserved")
    downloaded = 0
    if offset < expected["size"]:
        headers = {"User-Agent": "ReKit-model-qualification/1", "Accept-Encoding": "identity"}
        if offset:
            headers["Range"] = f"bytes={offset}-"
        url = f"https://huggingface.co/{MODEL_ID}/resolve/{REVISION}/{target.name}"
        print(f"Download {target.name}: {offset}/{expected['size']} bytes", flush=True)
        try:
            response = urlopen(Request(url, headers=headers), timeout=20)
        except HTTPError as error:
            raise RuntimeError(f"Model download returned HTTP {error.code}; partial files remain resumable") from None
        except (URLError, TimeoutError) as error:
            raise RuntimeError(f"Model connection failed ({type(error).__name__}); partial files remain resumable") from None
        with response:
            if offset:
                required_range = f"bytes {offset}-{expected['size'] - 1}/{expected['size']}"
                if response.status != 206 or response.headers.get("Content-Range") != required_range:
                    raise RuntimeError("Server did not confirm the exact resume range; no duplicate bytes were saved")
            elif response.status != 200:
                raise RuntimeError("Server returned an unexpected status for the model file")
            length = response.headers.get("Content-Length")
            if length is not None and int(length) != expected["size"] - offset:
                raise RuntimeError("Server model size differs from the approved manifest")
            last_progress = time.monotonic()
            with partial.open("ab" if partial.exists() else "xb") as destination:
                while offset + downloaded < expected["size"]:
                    remaining = expected["size"] - offset - downloaded
                    block = response.read(min(CHUNK_BYTES, remaining))
                    if not block:
                        raise RuntimeError("Model transfer ended early; partial file remains resumable")
                    destination.write(block)
                    downloaded += len(block)
                    if time.monotonic() - last_progress >= 10:
                        print(f"Download {target.name}: {offset + downloaded}/{expected['size']} bytes", flush=True)
                        last_progress = time.monotonic()
                if response.read(1):
                    raise RuntimeError("Server sent excess model bytes; no excess bytes were saved")
                destination.flush()
                os.fsync(destination.fileno())
    print(f"Verify downloaded {target.name}", flush=True)
    record = _verify(partial, expected)
    if target.exists():
        raise RuntimeError("Model target appeared during download; neither file was overwritten")
    partial.rename(target)
    return record, downloaded


def run() -> dict:
    manifest = _manifest()
    _contained(DESTINATION)
    DESTINATION.mkdir(parents=True, exist_ok=True)
    lock = _contained(DESTINATION / ".rekit-download.lock")
    descriptor = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.close(descriptor)
    started = time.monotonic()
    try:
        verified = []
        downloaded = 0
        for expected in manifest["files"]:
            record, transferred = _download(expected)
            verified.append(record)
            downloaded += transferred
        record = {
            "model_id": MODEL_ID, "revision": REVISION, "license": manifest["license"],
            "verified_at": datetime.now(UTC).isoformat(),
            "total_bytes": sum(file["size"] for file in verified), "files": verified,
            "downloaded_bytes_this_run": downloaded,
            "elapsed_seconds_this_run": round(time.monotonic() - started, 3),
        }
        receipt = _contained(DESTINATION / "rekit-download.json")
        if receipt.exists():
            previous = json.loads(receipt.read_text(encoding="utf-8"))
            if previous["model_id"] != MODEL_ID or previous["revision"] != REVISION or previous["files"] != verified:
                raise ValueError("Existing verification receipt differs; it was preserved")
        else:
            with receipt.open("x", encoding="utf-8") as output:
                json.dump(record, output, indent=2)
                output.write("\n")
        print(json.dumps(record, indent=2), flush=True)
        return record
    finally:
        _contained(lock).unlink()


if __name__ == "__main__":
    try:
        run()
    except (OSError, RuntimeError, ValueError, KeyError) as failure:
        print(f"Model download stopped: {failure}", file=sys.stderr, flush=True)
        raise SystemExit(1) from None
