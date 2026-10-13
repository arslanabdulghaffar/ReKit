"""CPU-only collection integrity and human-review boundaries; no downloads."""

from copy import deepcopy
import hashlib
from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys

from PIL import Image
from pydantic import ValidationError
import pytest


ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "evaluation" / "product_data.py"
specification = spec_from_file_location("rekit_product_data_tests", SCRIPT)
data = module_from_spec(specification)
specification.loader.exec_module(data)
NOW = "2026-10-14T01:00:00+00:00"


def image_bytes(color="red", format="JPEG"):
    with Image.new("RGB", (32, 24), color) as image, BytesIO() as buffer:
        image.save(buffer, format=format)
        return buffer.getvalue()


def image_record(image_id="image-one", listing_id="listing-one", raw=None):
    raw = image_bytes() if raw is None else raw
    return {"image_id": image_id, "listing_id": listing_id, "group_id": listing_id,
            "split": data.split_for_group(listing_id), "source_url": f"https://example.org/{image_id}.jpg",
            "local_path": f"images/{image_id}.jpg", "sha256": hashlib.sha256(raw).hexdigest(),
            "byte_size": len(raw), "width": 32, "height": 24, "category": "connector",
            "source_labels": {"title": "Metadata claims Product X revision A", "domain_name": "example.org"},
            "downloaded_at": NOW, "ambiguity_notes": "Source labels are not human visual review."}


def manifest_payload(images=None):
    return {"source_url": "https://example.org/distribution", "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "attribution": "Controlled test metadata; not an acquired product dataset.", "downloaded_at": NOW,
            "metadata_receipts": [{"url": "https://example.org/metadata", "bytes": 123, "sha256": "a" * 64}],
            "images": [image_record()] if images is None else images}


@pytest.fixture
def collection(tmp_path):
    manifest = data.DatasetManifest.model_validate(manifest_payload())
    images = tmp_path / "images"
    images.mkdir()
    (images / "image-one.jpg").write_bytes(image_bytes())
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(), encoding="utf-8")
    return manifest, tmp_path, manifest_path


def reviewed_entry(**changes):
    row = {"image_id": "image-one", "sha256": hashlib.sha256(image_bytes()).hexdigest(),
           "review_status": "reviewed", "reviewer": "controlled-human-review-fixture",
           "reviewed_at": NOW, "independent_human_review": True, "visible_markings": [],
           "marking_visible": False, "exact_identity_visually_established": False,
           "identity_label": None, "revision_supported": False, "revision_label": None,
           "support_notes": "Synthetic test assertion only; no actual human dataset review.", "ambiguity_notes": "Unknown identity."}
    row.update(changes)
    return row


def test_manifest_metadata_never_becomes_visual_ground_truth(collection):
    manifest, root, manifest_path = collection
    loaded = data.load_manifest(manifest_path)
    assert loaded == manifest
    image = loaded.images[0]
    assert "revision A" in image.source_labels["title"]
    assert image.marking_visible is image.exact_identity_visually_established is image.revision_supported is None
    assert image.review_status == "pending"
    result = data.verify_images(loaded, root)
    assert result["status"] == "verified"
    assert result["images"] == result["groups"] == result["pending"] == 1
    assert result["reviewed"] == 0


@pytest.mark.parametrize("field,value", [
    ("marking_visible", True), ("exact_identity_visually_established", False),
    ("revision_supported", False), ("review_status", "reviewed"),
    ("width", True), ("byte_size", 1.0), ("downloaded_at", "2026-10-14T01:00:00"),
    ("source_url", "http://example.org/image.jpg"), ("source_url", "https://secret@example.org/image.jpg"),
    ("local_path", "../escape.jpg"), ("local_path", "images/../escape.jpg"),
    ("local_path", "C:/private/image.jpg"), ("group_id", "other-listing"),
    ("unexpected", "field"),
])
def test_source_manifest_rejects_unreviewed_truth_invalid_paths_types_and_timestamps(field, value):
    record = image_record()
    record[field] = value
    with pytest.raises(ValidationError):
        data.DatasetManifest.model_validate(manifest_payload([record]))


def test_multiple_views_stay_in_one_group_and_cannot_cross_splits():
    first = image_record()
    second = image_record("image-two", raw=image_bytes("blue"))
    manifest = data.DatasetManifest.model_validate(manifest_payload([first, second]))
    assert manifest.images[0].group_id == manifest.images[1].group_id
    assert manifest.images[0].split == manifest.images[1].split
    second["split"] = "holdout" if first["split"] == "development" else "development"
    with pytest.raises(ValidationError, match="deterministic group split"):
        data.DatasetManifest.model_validate(manifest_payload([first, second]))


def test_official_plus_image_ids_and_twenty_one_metadata_receipts_are_supported():
    payload = manifest_payload([image_record("11Y+Xpt1lfL")])
    payload["metadata_receipts"] = [{"url": f"https://example.org/metadata-{index}", "bytes": 123,
                                      "sha256": f"{index:064x}"} for index in range(21)]
    manifest = data.DatasetManifest.model_validate(payload)
    assert manifest.images[0].local_path == "images/11Y+Xpt1lfL.jpg"
    assert data.review_template(manifest).reviews[0].image_id == "11Y+Xpt1lfL"


@pytest.mark.parametrize("duplicate", ["image_id", "sha256"])
def test_repeated_images_do_not_count_as_distinct_products(duplicate):
    first = image_record()
    second = image_record("image-two", "other-listing", image_bytes("blue"))
    second[duplicate] = first[duplicate]
    if duplicate == "image_id":
        second["local_path"] = first["local_path"]
    with pytest.raises(ValidationError, match="Duplicate image"):
        data.DatasetManifest.model_validate(manifest_payload([first, second]))


def test_manifest_download_and_pixel_budgets_are_enforced():
    too_large = image_record()
    too_large.update(width=8192, height=8192)
    with pytest.raises(ValidationError, match="pixel limit"):
        data.DatasetManifest.model_validate(manifest_payload([too_large]))
    payload = manifest_payload([])
    payload["metadata_receipts"].append(deepcopy(payload["metadata_receipts"][0]))
    payload["metadata_receipts"][1]["url"] += "-second"
    for receipt in payload["metadata_receipts"]:
        receipt["bytes"] = data.MAX_METADATA_BYTES
    with pytest.raises(ValidationError, match="150 MiB"):
        data.DatasetManifest.model_validate(payload)
    records = [image_record(f"image-{i}", f"listing-{i}") for i in range(21)]
    for i, record in enumerate(records):
        record.update(sha256=f"{i:064x}", byte_size=data.MAX_IMAGE_BYTES)
    with pytest.raises(ValidationError, match="200 MiB"):
        data.DatasetManifest.model_validate(manifest_payload(records))


@pytest.mark.parametrize("mutation", ["missing", "size", "same-size-tamper", "dimensions", "wrong-mime", "decode"])
def test_local_integrity_rejects_missing_changed_or_misrepresented_bytes(collection, mutation):
    manifest, root, _ = collection
    path = root / manifest.images[0].local_path
    payload = manifest.model_dump(mode="json")
    if mutation == "missing":
        path.unlink()
    elif mutation == "size":
        path.write_bytes(path.read_bytes() + b"extra")
    elif mutation == "same-size-tamper":
        raw = bytearray(path.read_bytes())
        raw[-1] ^= 1
        path.write_bytes(raw)
    elif mutation == "dimensions":
        payload["images"][0]["width"] = 31
    else:
        raw = image_bytes(format="PNG") if mutation == "wrong-mime" else b"not an image"
        path.write_bytes(raw)
        payload["images"][0].update(sha256=hashlib.sha256(raw).hexdigest(), byte_size=len(raw))
    with pytest.raises(ValueError):
        data.verify_images(data.DatasetManifest.model_validate(payload), root)


def test_integrity_revalidates_forged_nested_model_instances(collection):
    manifest, root, _ = collection
    forged = manifest.model_copy(update={"images": [manifest.images[0].model_copy(update={"local_path": "../escape.jpg"})]})
    with pytest.raises(ValidationError):
        data.verify_images(forged, root)


def test_integrity_rejects_symlink_before_reading_image(collection, monkeypatch):
    manifest, root, _ = collection
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path.name == "images" or original(path))
    with pytest.raises(ValueError, match="links or junctions"):
        data.verify_images(manifest, root)


def test_missing_dataset_is_explicit_not_successful_accuracy(tmp_path):
    manifest = data.DatasetManifest.model_validate(manifest_payload([]))
    assert data.verify_images(manifest, tmp_path)["status"] == "missing_data"
    assert data.validate_reviews(data.review_template(manifest), manifest) == {
        "reviewed": 0, "pending": 0, "accuracy_denominator_images": 0,
    }


def test_pending_and_absent_reviews_are_excluded_from_denominators(collection):
    manifest, _, _ = collection
    template = data.review_template(manifest)
    assert template.reviews[0].independent_human_review is False
    assert template.reviews[0].reviewer is None
    assert template.reviews[0].marking_visible is None
    for ledger in (template, data.ReviewLedger(reviews=[])):
        assert data.validate_reviews(ledger, manifest) == {"reviewed": 0, "pending": 1, "accuracy_denominator_images": 0}
    ledger = data.ReviewLedger.model_validate({"reviews": [reviewed_entry()]})
    assert data.validate_reviews(ledger, manifest) == {"reviewed": 1, "pending": 0, "accuracy_denominator_images": 1}


@pytest.mark.parametrize("changes", [
    {"review_status": "pending"}, {"independent_human_review": False},
    {"independent_human_review": 1}, {"reviewer": None}, {"reviewed_at": None},
    {"reviewed_at": "2026-10-14"}, {"support_notes": " "}, {"marking_visible": None},
    {"identity_label": "Title-derived identity"}, {"exact_identity_visually_established": True},
    {"revision_label": "A"}, {"revision_supported": True, "revision_label": "A"},
    {"visible_markings": ["REV A"]},
])
def test_unreviewed_or_unsupported_labels_cannot_enter_reviewed_truth(changes):
    with pytest.raises(ValidationError):
        data.ReviewEntry.model_validate(reviewed_entry(**changes))


def test_reviewed_transcription_and_revision_require_human_support(collection, tmp_path):
    manifest, _, _ = collection
    entry = reviewed_entry(marking_visible=True, visible_markings=["REV A"], revision_supported=True,
                           revision_label="A", exact_identity_visually_established=True, identity_label="Product X")
    ledger = data.ReviewLedger.model_validate({"reviews": [entry]})
    path = tmp_path / "reviewed.json"
    path.write_text(ledger.model_dump_json(), encoding="utf-8")
    assert data.load_reviews(path, manifest) == ledger
    assert manifest.images[0].revision_supported is None


@pytest.mark.parametrize("change", ["duplicate", "unknown-image", "wrong-hash"])
def test_reviews_link_exactly_once_to_original_bytes(collection, change):
    manifest, _, _ = collection
    entries = [reviewed_entry()]
    if change == "duplicate":
        entries.append(deepcopy(entries[0]))
    elif change == "unknown-image":
        entries[0]["image_id"] = "not-in-dataset"
    else:
        entries[0]["sha256"] = "b" * 64
    with pytest.raises(ValueError):
        data.validate_reviews(data.ReviewLedger.model_validate({"reviews": entries}), manifest)


def test_cli_creates_only_pending_template_and_never_overwrites_reviews(collection):
    _, root, manifest_path = collection
    path = root / "reviews.json"
    base = [sys.executable, str(SCRIPT)]
    template = [*base, "review-template", "--manifest", str(manifest_path), "--output", str(path)]
    result = subprocess.run(template, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    original = path.read_bytes()
    result = subprocess.run(template, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 1
    assert path.read_bytes() == original
    result = subprocess.run([*base, "check", "--manifest", str(manifest_path), "--root", str(root), "--reviews", str(path)],
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["accuracy_denominator_images"] == 0


def test_data_contracts_import_without_pillow_or_model_runtime():
    script = f"""
import importlib.abc, runpy, sys
class BlockRuntime(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {{'PIL', 'torch', 'transformers', 'lmformatenforcer'}}:
            raise AssertionError('Unexpected image/model import ' + fullname)
sys.meta_path.insert(0, BlockRuntime())
runpy.run_path({str(SCRIPT)!r}, run_name='import_only')
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
