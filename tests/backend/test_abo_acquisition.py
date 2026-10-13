"""Bounded ABO acquisition using synthetic metadata and controlled HTTP bodies."""

from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
import gzip
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from urllib.request import Request

import pytest


SCRIPT = Path(__file__).parents[2] / "evaluation" / "prepare_abo.py"
specification = spec_from_file_location("rekit_abo_acquisition", SCRIPT)
acquisition = module_from_spec(specification)
specification.loader.exec_module(acquisition)


class Response:
    def __init__(self, raw, *, length=None, status=200):
        self.body = BytesIO(raw)
        self.status = status
        self.headers = {} if length is None else {"Content-Length": str(length)}
        self.read_sizes = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *arguments):
        self.closed = True

    def read(self, size):
        self.read_sizes.append(size)
        return self.body.read(size)


class Opener:
    def __init__(self, responses=()):
        self.responses = list(responses)
        self.requests = []

    def open(self, request, *, timeout):
        self.requests.append(request)
        assert timeout > 0
        if not self.responses:
            pytest.fail("Unexpected network access; this test has no real HTTP transport")
        return self.responses.pop(0)


@pytest.fixture
def storage(tmp_path, monkeypatch):
    monkeypatch.setattr(acquisition, "ROOT", tmp_path)
    monkeypatch.setattr(acquisition, "timestamp", lambda: "2026-10-14T01:00:00+09:00")
    monkeypatch.setattr(acquisition.urllib.request, "build_opener", lambda *handlers: Opener())
    root = tmp_path / "var" / "evaluation" / "abo"
    downloader = acquisition.Downloader(root)
    return SimpleNamespace(root=root, downloader=downloader)


def test_verified_download_is_reused_after_reopen_without_http(storage):
    raw = b"tiny synthetic official-object response"
    response = Response(raw, length=len(raw))
    storage.downloader.opener = Opener([response])
    receipt = storage.downloader.fetch("README.md", "metadata/readme.md", kind="metadata", maximum=100)
    assert receipt["url"] == acquisition.BASE + "README.md"
    assert receipt["bytes"] == len(raw)
    assert receipt["sha256"] == sha256(raw).hexdigest()
    assert (storage.root / receipt["local"]).read_bytes() == raw
    assert response.closed
    request = storage.downloader.opener.requests[0]
    assert request.get_header("Accept-encoding") == "identity"
    reopened = acquisition.Downloader(storage.root)
    assert reopened.fetch("README.md", "metadata/readme.md", kind="metadata", maximum=100) == receipt
    assert reopened.opener.requests == []


@pytest.mark.parametrize("length", [None, 1])
def test_actual_stream_is_bounded_even_with_missing_or_understated_length(storage, length):
    response = Response(b"abcdef", length=length)
    storage.downloader.opener = Opener([response])
    with pytest.raises(ValueError):
        storage.downloader.fetch("images/original/ab/abcdef.jpg", "images/example.jpg", kind="image", maximum=4)
    assert response.closed
    assert 0 < response.body.tell() <= 4
    assert not (storage.root / "images/example.jpg").exists()
    assert acquisition.BASE + "images/original/ab/abcdef.jpg" not in storage.downloader.receipts


@pytest.mark.parametrize("status,length", [(200, 20), (206, 3), (404, 3)])
def test_header_or_status_rejection_reads_no_body(storage, status, length):
    response = Response(b"abc", length=length, status=status)
    storage.downloader.opener = Opener([response])
    with pytest.raises(ValueError):
        storage.downloader.fetch("README.md", "metadata/readme", kind="metadata", maximum=4)
    assert response.read_sizes == []
    assert response.closed
    assert not (storage.root / "metadata/readme").exists()


def test_short_response_cannot_be_committed_as_a_complete_download(storage):
    response = Response(b"abc", length=4)
    storage.downloader.opener = Opener([response])
    with pytest.raises(ValueError, match="length"):
        storage.downloader.fetch("README.md", "metadata/readme", kind="metadata", maximum=8)
    assert not (storage.root / "metadata/readme").exists()
    assert acquisition.BASE + "README.md" not in storage.downloader.receipts


@pytest.mark.parametrize("destination", ["https://unrelated.example/file", acquisition.BASE + "other-object"])
def test_redirect_handler_rejects_redirects_including_same_host(destination):
    handler = acquisition.NoRedirect()
    with pytest.raises(ValueError, match="redirect"):
        handler.redirect_request(Request(acquisition.BASE + "README.md"), None, 302, "Found", {}, destination)


def test_same_size_cache_tampering_is_rejected_without_redownload(storage):
    storage.downloader.opener = Opener([Response(b"original", length=8)])
    storage.downloader.fetch("README.md", "metadata/readme", kind="metadata", maximum=10)
    target = storage.root / "metadata/readme"
    target.write_bytes(b"tampered")
    reopened = acquisition.Downloader(storage.root)
    with pytest.raises(ValueError):
        reopened.fetch("README.md", "metadata/readme", kind="metadata", maximum=10)
    assert target.read_bytes() == b"tampered"
    assert reopened.opener.requests == []


def test_oversized_cache_is_rejected_before_reading_its_bytes(storage, monkeypatch):
    storage.downloader.opener = Opener([Response(b"good", length=4)])
    storage.downloader.fetch("README.md", "metadata/readme", kind="metadata", maximum=8)
    target = storage.root / "metadata/readme"
    target.write_bytes(b"too large now")
    original_read = Path.read_bytes

    def guarded_read(path):
        if path == target:
            pytest.fail("A cache with a changed size must be rejected before loading its body")
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", guarded_read)
    with pytest.raises(ValueError):
        storage.downloader.fetch("README.md", "metadata/readme", kind="metadata", maximum=8)


def test_unreceipted_file_is_preserved_and_never_overwritten(storage):
    target = storage.root / "existing.txt"
    target.write_bytes(b"preserve me")
    with pytest.raises(ValueError, match="overwrite"):
        storage.downloader.fetch("README.md", "existing.txt", kind="metadata", maximum=100)
    assert target.read_bytes() == b"preserve me"
    assert storage.downloader.opener.requests == []


@pytest.mark.parametrize("relative", ["../README.md", "images/../README.md", "https://other.example/x", "image?x=1", "image#fragment"])
def test_remote_paths_cannot_override_the_official_destination(storage, relative):
    with pytest.raises(ValueError):
        storage.downloader.fetch(relative, "images/example.jpg", kind="image", maximum=10)
    assert storage.downloader.opener.requests == []


def test_local_path_and_collection_root_must_remain_inside_ignored_storage(storage, tmp_path):
    with pytest.raises(ValueError, match="escaped"):
        storage.downloader.fetch("README.md", "../outside.txt", kind="metadata", maximum=10)
    with pytest.raises(ValueError, match="ignored"):
        acquisition.Downloader(tmp_path / "not-ignored")
    assert not (storage.root.parent / "outside.txt").exists()
    assert not (tmp_path / "not-ignored").exists()
    assert storage.downloader.opener.requests == []


def test_metadata_and_image_budgets_are_separate_and_persist_across_runs(storage, monkeypatch):
    monkeypatch.setattr(acquisition, "METADATA_LIMIT", 5)
    monkeypatch.setattr(acquisition, "IMAGE_LIMIT", 5)
    storage.downloader.opener = Opener([Response(b"meta", length=4), Response(b"image", length=5)])
    storage.downloader.fetch("README.md", "metadata/readme", kind="metadata", maximum=10)
    storage.downloader.fetch("images/original/ab/abcdef.jpg", "images/a.jpg", kind="image", maximum=10)
    reopened = acquisition.Downloader(storage.root)
    rejected = Response(b"xx", length=2)
    reopened.opener = Opener([rejected])
    with pytest.raises(ValueError):
        reopened.fetch("images/README.md", "metadata/other", kind="metadata", maximum=10)
    assert rejected.read_sizes == []
    with pytest.raises(ValueError, match="budget"):
        reopened.fetch("images/original/cd/cdefab.jpg", "images/b.jpg", kind="image", maximum=10)
    assert len(reopened.opener.requests) == 1


def test_failed_stream_bytes_remain_charged_after_reopen(storage, monkeypatch):
    monkeypatch.setattr(acquisition, "IMAGE_LIMIT", 5)
    first = Response(b"abcd")
    storage.downloader.opener = Opener([first])
    with pytest.raises(ValueError):
        storage.downloader.fetch("images/original/ab/abcdef.jpg", "images/a.jpg", kind="image", maximum=3)
    assert first.body.tell() == 3
    reopened = acquisition.Downloader(storage.root)
    second = Response(b"xyz", length=3)
    reopened.opener = Opener([second])
    with pytest.raises(ValueError):
        reopened.fetch("images/original/cd/cdefab.jpg", "images/b.jpg", kind="image", maximum=3)
    assert second.read_sizes == []
    assert not (storage.root / "images/a.jpg").exists()
    assert not (storage.root / "images/b.jpg").exists()


def test_existing_manifest_is_rejected_before_acquisition(storage, tmp_path, monkeypatch):
    manifest = tmp_path / "existing-manifest.json"
    manifest.write_text('{"preserve":true}', encoding="utf-8")
    monkeypatch.setattr(acquisition, "metadata", lambda *_: pytest.fail("Existing selection must be checked before network work"))
    with pytest.raises(ValueError, match="overwrite"):
        acquisition.prepare(storage.root, manifest)
    assert manifest.read_text(encoding="utf-8") == '{"preserve":true}'


def test_metadata_categories_and_marketplaces_do_not_create_visual_ground_truth(storage):
    metadata = storage.root / "metadata"
    metadata.mkdir()
    first = {"item_id": "B000TEST01", "domain_name": "amazon.com",
             "item_name": [{"language_tag": "en_US", "value": "USB adapter model REV A"}],
             "model_number": [{"value": "REV A"}], "main_image_id": "51TESTimage"}
    second = {**first, "domain_name": "amazon.co.uk"}
    unrelated = {"item_id": "B000OTHER1", "item_name": [{"language_tag": "en_US", "value": "Cotton pillow"}]}
    for digit in "0123456789abcdef":
        with gzip.open(metadata / f"listings_{digit}.json.gz", "wt", encoding="utf-8") as stream:
            if digit == "0":
                stream.write("\n".join(json.dumps(record) for record in (first, second, unrelated)) + "\n")
    with gzip.open(metadata / "images.csv.gz", "wt", encoding="utf-8") as stream:
        stream.write("image_id,height,width,path\n51TESTimage,1000,1000,ab/abcdef.jpg\nunused,500,500,cd/cdefab.jpg\n")
    buckets, images = acquisition.candidates(storage.root)
    assert list(buckets["computer_interfaces"]) == ["B000TEST01"]
    source = buckets["computer_interfaces"]["B000TEST01"]
    assert source["model_number"] == "REV A"
    assert source["domain_name"] == "amazon.com"
    assert source["metadata_shard"] == "listings_0.json.gz" and source["metadata_line"] == 1
    assert "revision_supported" not in source and "review_status" not in source
    assert images["51TESTimage"]["path"] == "ab/abcdef.jpg"
    assert "unused" not in images
    assert all("B000OTHER1" not in values for values in buckets.values())
    assert storage.downloader.opener.requests == []


def test_offline_selection_preserves_pending_truth_and_same_listing_groups(storage, tmp_path, monkeypatch):
    """Exercise real selection, manifest validation and JPEG integrity without HTTP."""
    from PIL import Image

    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    buckets = {category: {} for category in acquisition.CATEGORIES}
    index, bodies = {}, {}
    for category_number, (category, items) in enumerate(buckets.items()):
        for number in range(8):
            listing = f"listing-{category_number}-{number}"
            image_ids = []
            for view in range(2):
                serial = (category_number * 8 + number) * 2 + view + 1
                image_id = f"image+{serial}"
                image_ids.append(image_id)
                buffer = BytesIO()
                Image.new("RGB", (256, 256), (serial * 2, serial, 255 - serial)).save(buffer, format="JPEG")
                relative = f"images/original/ab/{serial:08x}.jpg"
                bodies[acquisition.BASE + relative] = buffer.getvalue()
                index[image_id] = {"width": "256", "height": "256", "path": relative.removeprefix("images/original/")}
            items[listing] = {"item_id": listing, "main_image_id": image_ids[0], "other_image_id": image_ids[1:],
                              "item_name": [{"language_tag": "en_US", "value": "Source claims model REV A"}],
                              "model_number": [{"value": "REV A"}], "domain_name": "amazon.com"}

    class ImageOpener:
        def open(self, request, *, timeout):
            raw = bodies[request.full_url]
            return Response(raw, length=len(raw))

    receipts = [{"url": acquisition.BASE + f"metadata-{number}", "bytes": 1, "sha256": sha256(str(number).encode()).hexdigest()}
                for number in range(21)]
    monkeypatch.setattr(acquisition.urllib.request, "build_opener", lambda *handlers: ImageOpener())
    monkeypatch.setattr(acquisition, "metadata", lambda _: receipts)
    monkeypatch.setattr(acquisition, "candidates", lambda _: (buckets, index))
    destination = tmp_path / "selection.json"
    summary = acquisition.prepare(storage.root, destination)
    manifest = json.loads(destination.read_text(encoding="utf-8"))
    assert summary["status"] == "verified"
    assert summary["images"] == 52 and summary["groups"] == 48
    assert summary["reviewed"] == 0 and summary["pending"] == 52
    assert len(manifest["metadata_receipts"]) == 21
    assert len({image["sha256"] for image in manifest["images"]}) == 52
    groups = {}
    for image in manifest["images"]:
        assert image["review_status"] == "pending"
        assert all(image[field] is None for field in ("marking_visible", "exact_identity_visually_established", "revision_supported"))
        assert image["source_labels"]["model_number"] == "REV A"
        groups.setdefault(image["group_id"], set()).add(image["split"])
    assert all(len(splits) == 1 for splits in groups.values())
    assert sum(image["source_labels"]["view_selection"] == "additional_same_listing" for image in manifest["images"]) == 4


@pytest.fixture
def small_shard(tmp_path):
    records = [
        {"item_id": "unrelated", "item_name": "Cotton pillow"},
        {"item_id": "adapter-1", "item_name": [{"language_tag": "en_US", "value": "USB adapter REV A"}],
         "model_number": [{"value": "REV A"}], "domain_name": "amazon.com",
         "main_image_id": "main+image", "other_image_id": ["other-image"]},
    ]
    decoded = ("\n".join(json.dumps(record) for record in records) + "\n").encode()
    path = tmp_path / "listings_a.json.gz"
    path.write_bytes(gzip.compress(decoded, mtime=0))
    return SimpleNamespace(path=path, decoded=decoded)


def test_real_isolated_worker_preserves_source_hash_line_and_plain_metadata(small_shard, monkeypatch):
    real_run = subprocess.run
    calls = []

    def observed_run(command, **options):
        calls.append((command, options))
        return real_run(command, **options)

    monkeypatch.setattr(acquisition.subprocess, "run", observed_run)
    result = acquisition.isolated_shard(small_shard.path)
    command, options = calls[0]
    assert command[0] == sys.executable and "-I" in command and "-S" in command
    assert command[-2:] == ["--parse-shard", str(small_shard.path.resolve())]
    assert options["timeout"] == 30 and options["check"] is False
    assert result["sha256"] == sha256(small_shard.path.read_bytes()).hexdigest()
    assert result["records"] == 2 and result["decoded_bytes"] == len(small_shard.decoded)
    assert len(result["selected"]) == 1
    row = result["selected"][0]
    assert row["category"] == "computer_interfaces"
    assert row["item"]["metadata_shard"] == small_shard.path.name
    assert row["item"]["metadata_line"] == 2
    assert row["item"]["model_number"] == "REV A"
    assert row["item"]["other_image_id"] == ["other-image"]
    assert "revision_supported" not in row["item"]


def test_worker_loads_no_application_or_native_dependencies(small_shard):
    probe = """
import json, runpy, sys
from pathlib import Path
worker = runpy.run_path(sys.argv[1])
result = worker['parse_shard'](Path(sys.argv[2]))
forbidden = [name for name in sys.modules if name.split('.')[0] in
             {'PIL', 'pydantic', 'pydantic_core', 'torch', 'product_data', 'site'}]
print(json.dumps({'records': result['records'], 'forbidden': forbidden}))
"""
    result = subprocess.run([sys.executable, "-I", "-S", "-c", probe, str(SCRIPT), str(small_shard.path)],
                            capture_output=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert json.loads(result.stdout) == {"records": 2, "forbidden": []}


@pytest.mark.parametrize("invalid", [b'{"broken":\n', b'[]\n', b'\xff\n'])
def test_worker_invalid_record_names_exact_source_and_line(tmp_path, invalid):
    path = tmp_path / "listings_c.json.gz"
    path.write_bytes(gzip.compress(b'{}\n' + invalid, mtime=0))
    with pytest.raises(ValueError, match=r"listings_c\.json\.gz:2"):
        acquisition.parse_shard(path)


@pytest.mark.parametrize("limit", ["MAX_RECORD_BYTES", "MAX_DECODED_BYTES", "MAX_PROJECTION_BYTES"])
def test_worker_line_decompression_and_projection_bounds(small_shard, monkeypatch, limit):
    monkeypatch.setattr(acquisition, limit, 16)
    with pytest.raises(ValueError, match="bound"):
        acquisition.parse_shard(small_shard.path)


def test_worker_compressed_size_is_checked_before_loading(small_shard, monkeypatch):
    original_stat = Path.stat

    def oversized_stat(path, **options):
        if path == small_shard.path:
            return SimpleNamespace(st_size=15 * 1024**2 + 1)
        return original_stat(path, **options)

    monkeypatch.setattr(Path, "stat", oversized_stat)
    monkeypatch.setattr(Path, "read_bytes", lambda _: pytest.fail("Oversized shard body must not load"))
    with pytest.raises(ValueError, match="Compressed shard"):
        acquisition.parse_shard(small_shard.path)


@pytest.mark.parametrize("changes", [
    {"sha256": "0" * 64}, {"shard": "wrong-shard.json.gz"},
    {"records": True}, {"records": 0}, {"decoded_bytes": True},
    {"decoded_bytes": acquisition.MAX_DECODED_BYTES + 1},
])
def test_parent_rejects_changed_source_or_invalid_child_counts(small_shard, monkeypatch, changes):
    result = acquisition.parse_shard(small_shard.path)
    result.update(changes)
    monkeypatch.setattr(acquisition.subprocess, "run", lambda *args, **kwargs:
                        SimpleNamespace(returncode=0, stdout=json.dumps(result).encode(), stderr=b""))
    with pytest.raises(ValueError, match="child receipt"):
        acquisition.isolated_shard(small_shard.path)


def test_parent_rejects_oversized_child_output_before_decoding(small_shard, monkeypatch):
    monkeypatch.setattr(acquisition, "MAX_PROJECTION_BYTES", 32)
    monkeypatch.setattr(acquisition.subprocess, "run", lambda *args, **kwargs:
                        SimpleNamespace(returncode=0, stdout=b"x" * 33, stderr=b""))
    with pytest.raises(ValueError, match="output exceeds"):
        acquisition.isolated_shard(small_shard.path)


@pytest.mark.parametrize("failure", ["native_exit", "timeout", "invalid_json"])
def test_child_failure_cannot_write_parent_ledgers_or_publish_manifest(storage, tmp_path, monkeypatch, failure):
    storage.downloader.opener = Opener([Response(b"known cached object", length=19)])
    storage.downloader.fetch("README.md", "metadata/readme", kind="metadata", maximum=100)
    before = {path.relative_to(storage.root): path.read_bytes() for path in storage.root.rglob("*") if path.is_file()}

    def failed_child(command, **options):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, options["timeout"])
        return SimpleNamespace(returncode=-1073741819 if failure == "native_exit" else 0,
                               stdout=b'{"incomplete":', stderr=b"Controlled synthetic child failure")

    monkeypatch.setattr(acquisition, "metadata", lambda _: [])
    monkeypatch.setattr(acquisition.subprocess, "run", failed_child)
    manifest = tmp_path / "must-not-exist.json"
    with pytest.raises(ValueError):
        acquisition.prepare(storage.root, manifest, cached_only=True)
    assert not manifest.exists()
    assert {path.relative_to(storage.root): path.read_bytes() for path in storage.root.rglob("*") if path.is_file()} == before


def test_prepare_defers_native_imports_until_metadata_succeeds(storage, tmp_path, monkeypatch):
    import builtins

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"PIL", "pydantic", "product_data"}:
            pytest.fail("Application dependencies imported before metadata succeeded")
        return original_import(name, *args, **kwargs)

    def metadata_failure(_):
        raise ValueError("Synthetic isolated metadata failure")

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(acquisition, "metadata", lambda _: [])
    monkeypatch.setattr(acquisition, "candidates", metadata_failure)
    with pytest.raises(ValueError, match="Synthetic isolated metadata failure"):
        acquisition.prepare(storage.root, tmp_path / "never-published.json", cached_only=True)


def test_cached_only_missing_object_never_opens_http_or_writes_ledgers(storage):
    cached = acquisition.Downloader(storage.root, cached_only=True)
    with pytest.raises(ValueError, match="Cached-only"):
        cached.fetch("README.md", "metadata/readme", kind="metadata", maximum=100)
    assert cached.opener.requests == []
    assert not cached.ledger_path.exists() and not cached.transfer_path.exists()
