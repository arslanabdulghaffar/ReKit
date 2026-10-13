"""Budget and integrity checks using tiny files, isolated storage, and no network."""

from copy import deepcopy
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).parents[2] / "evaluation" / "download_vision_model.py"
specification = spec_from_file_location("rekit_model_download", SCRIPT)
download = module_from_spec(specification)
specification.loader.exec_module(download)


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    destination = tmp_path / "models" / "fixture"
    manifest_path = tmp_path / "manifest.json"
    content = {name: f"Tiny synthetic file: {name}".encode("ascii") for name in download.EXPECTED_NAMES}
    files = []
    for name in sorted(content):
        raw = content[name]
        identity = {"name": name, "size": len(raw)}
        if name == "model.safetensors":
            identity["sha256"] = hashlib.sha256(raw).hexdigest()
        else:
            identity["git_blob_sha1"] = hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()
        files.append(identity)
    manifest = {
        "model_id": download.MODEL_ID, "revision": download.REVISION, "license": "Apache-2.0",
        "files": files, "expected_total_bytes": sum(file["size"] for file in files),
        "maximum_download_bytes": download.MAXIMUM_BYTES,
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(download, "ROOT", tmp_path)
    monkeypatch.setattr(download, "DESTINATION", destination)
    monkeypatch.setattr(download, "MANIFEST", manifest_path)
    monkeypatch.setattr(download, "urlopen", lambda *args, **kwargs: pytest.fail("Unexpected network request"))
    return SimpleNamespace(destination=destination, path=manifest_path, manifest=manifest, content=content)


@pytest.mark.parametrize("change", ["revision", "missing_file", "duplicate_file", "size_type", "hash", "total", "budget", "over_budget"])
def test_manifest_rejects_unapproved_identity_files_sizes_and_budget(isolated, change):
    assert download._manifest() == isolated.manifest
    manifest = deepcopy(isolated.manifest)
    if change == "revision":
        manifest["revision"] = "not-the-approved-revision"
    elif change == "missing_file":
        manifest["files"].pop()
    elif change == "duplicate_file":
        manifest["files"][0] = manifest["files"][1]
    elif change == "size_type":
        manifest["files"][0]["size"] = True
    elif change == "hash":
        manifest["files"][0]["git_blob_sha1"] = "not-an-official-hash"
    elif change == "total":
        manifest["expected_total_bytes"] += 1
    elif change == "budget":
        manifest["maximum_download_bytes"] += 1
    else:
        manifest["files"][0]["size"] = download.MAXIMUM_BYTES + 1
        manifest["expected_total_bytes"] = sum(file["size"] for file in manifest["files"])
    isolated.path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        download.run()
    assert not isolated.destination.exists()


def test_verified_files_and_receipt_are_reused_without_network(isolated):
    isolated.destination.mkdir(parents=True)
    for name, content in isolated.content.items():
        (isolated.destination / name).write_bytes(content)
    initial = download.run()
    receipt_path = isolated.destination / "rekit-download.json"
    receipt = receipt_path.read_bytes()
    repeated = download.run()
    assert initial["downloaded_bytes_this_run"] == repeated["downloaded_bytes_this_run"] == 0
    assert repeated["total_bytes"] == isolated.manifest["expected_total_bytes"]
    assert repeated["files"] == initial["files"]
    assert receipt_path.read_bytes() == receipt
    assert not (isolated.destination / ".rekit-download.lock").exists()
    assert all((isolated.destination / name).read_bytes() == content for name, content in isolated.content.items())


def test_existing_hash_mismatch_preserves_bytes_and_releases_lock(isolated):
    isolated.destination.mkdir(parents=True)
    for name, content in isolated.content.items():
        (isolated.destination / name).write_bytes(content)
    target = isolated.destination / "model.safetensors"
    altered = b"!" + target.read_bytes()[1:]
    target.write_bytes(altered)
    with pytest.raises(ValueError, match="Content hash mismatch"):
        download.run()
    assert target.read_bytes() == altered
    assert not target.with_name(target.name + ".part").exists()
    assert not (isolated.destination / "rekit-download.json").exists()
    assert not (isolated.destination / ".rekit-download.lock").exists()


@pytest.mark.parametrize("response_problem", ["status", "range", "length"])
def test_unconfirmed_resume_never_appends_or_replaces_partial(isolated, monkeypatch, response_problem):
    isolated.destination.mkdir(parents=True)
    expected = next(file for file in isolated.manifest["files"] if file["name"] == "model.safetensors")
    target = isolated.destination / expected["name"]
    partial = target.with_name(target.name + ".part")
    original = isolated.content[expected["name"]][:7]
    partial.write_bytes(original)
    required_range = f"bytes 7-{expected['size'] - 1}/{expected['size']}"

    class Response:
        status = 200 if response_problem == "status" else 206
        headers = {
            "Content-Range": "bytes 0-1/2" if response_problem == "range" else required_range,
            "Content-Length": str(expected["size"] - 7 + (1 if response_problem == "length" else 0)),
        }
        closed = False

        def __enter__(self):
            return self

        def __exit__(self, *arguments):
            self.closed = True

        def read(self, size):
            pytest.fail("An unconfirmed resume response was read")

    response = Response()

    def open_response(request, *, timeout):
        assert request.get_header("Range") == "bytes=7-"
        assert download.REVISION in request.full_url
        return response

    monkeypatch.setattr(download, "urlopen", open_response)
    with pytest.raises(RuntimeError):
        download._download(expected)
    assert response.closed
    assert partial.read_bytes() == original
    assert not target.exists()
