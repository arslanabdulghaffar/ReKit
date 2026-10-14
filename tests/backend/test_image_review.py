"""CPU-only image-review contracts; every annotation here is synthetic test data."""

import base64
from copy import deepcopy
import hashlib
from html.parser import HTMLParser
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
SCRIPT = ROOT / "evaluation" / "image_review.py"
NOW = "2026-10-14T03:00:00+00:00"


@pytest.fixture
def review(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "evaluation"))
    spec = spec_from_file_location("rekit_image_review_tests", SCRIPT)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def collection(tmp_path, review, monkeypatch):
    from product_data import DatasetManifest, split_for_group

    monkeypatch.setattr(review, "ROOT", tmp_path)
    root = tmp_path / "var" / "source"
    (root / "images").mkdir(parents=True)
    development = [f"group-{i}" for i in range(200) if split_for_group(f"group-{i}") == "development"]
    heldout = next(f"heldout-{i}" for i in range(100) if split_for_group(f"heldout-{i}") == "holdout")
    records = []
    groups = [(development[index], f"category-{index // 4}") for index in range(24)]
    groups.extend([(development[0], "category-0"), (heldout, "category-0")])
    for index, (group, category) in enumerate(groups):
        with Image.new("RGB", (24, 16), (index * 9, 255 - index * 9, index * 5)) as image, BytesIO() as stream:
            image.save(stream, format="JPEG", quality=95)
            raw = stream.getvalue()
        image_id = f"image-{index:02}"
        (root / "images" / f"{image_id}.jpg").write_bytes(raw)
        records.append({"image_id": image_id, "listing_id": group, "group_id": group,
                        "split": split_for_group(group), "source_url": f"https://example.org/{image_id}.jpg",
                        "local_path": f"images/{image_id}.jpg", "sha256": hashlib.sha256(raw).hexdigest(),
                        "byte_size": len(raw), "width": 24, "height": 16, "category": category,
                        "source_labels": {"title": "Never use this listing title as visual truth"},
                        "downloaded_at": NOW})
    manifest = DatasetManifest.model_validate({"source_url": "https://example.org/data",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "Controlled fixture images, not independently reviewed dataset photographs.",
        "downloaded_at": NOW, "metadata_receipts": [], "images": records})
    path = root / "manifest.json"
    path.write_text(manifest.model_dump_json(), encoding="utf-8")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"root": root, "manifest": manifest, "path": path, "sha": sha,
            "selection": review.build_selection(manifest, sha),
            "output": tmp_path / "var" / "gallery"}


def create(review, collection):
    return review.create_gallery(collection["path"], collection["root"], collection["output"])


def check_reviews(review, collection, ledger):
    return review.validate_selected_reviews(collection["manifest"], collection["sha"],
                                            collection["selection"], ledger)


def draft(review, collection):
    return review.ReviewDraft(manifest_sha256=collection["sha"],
        selection_sha256=review.digest(collection["selection"]),
        forms=[review.DraftRow(image_id=item["image_id"], sha256=item["sha256"])
               for item in collection["selection"]["images"]])


def declared(review, collection, **changes):
    raw = review.pending_ledger(collection["selection"]).model_dump(mode="json")
    raw["reviews"][0].update(review_status="reviewed", reviewer="synthetic-test-reviewer", reviewed_at=NOW,
        independent_human_review=True, marking_visible=False, exact_identity_visually_established=False,
        revision_supported=False, support_notes="Synthetic test declaration only; no source image was labeled.")
    raw["reviews"][0].update(changes)
    return review.ReviewLedger.model_validate(raw)


def test_selection_three_distinct_development_groups_each_category_then_first_pair(review, collection):
    selected = review.select_images(collection["manifest"])
    assert [item.image_id for item in selected] == [f"image-{i:02}" for i in range(24) if i % 4 < 3] + ["image-24"]
    assert len(selected) == 19 and len({item.group_id for item in selected}) == 18
    assert all(item.split == "development" for item in selected)
    assert selected[0].group_id == selected[-1].group_id
    assert review.build_selection(collection["manifest"], collection["sha"]) == collection["selection"]
    assert all(item.review_status == "pending" and item.marking_visible is None for item in collection["manifest"].images)


def test_actual_manifest_selection_metadata_only_has_nineteen_and_covers_existing_thirteen(review):
    # Read small committed metadata only; no acquired image files or model/runtime required.
    manifest, sha = review._manifest(ROOT / "evaluation" / "fixtures" / "abo-manifest.json")
    selected = review.build_selection(manifest, sha)["images"]
    assert len(selected) == 19 and len({row["group_id"] for row in selected}) == 18
    assert {row["split"] for row in selected} == {"development"}
    assert {"71rr7OjqWqL", "812Xgtrv0EL", "715hP9Tq6OL", "81UaZP1cm5L"} <= {row["image_id"] for row in selected}


def test_empty_development_selection_rejected(review, collection):
    manifest = collection["manifest"].model_copy(update={"images": [collection["manifest"].images[-1]]})
    with pytest.raises(ValueError, match="no development"):
        review.select_images(manifest)


@pytest.mark.parametrize("change", ["manifest", "policy", "hash", "order", "omit", "extra", "holdout"])
def test_selection_tampering_rejected(review, collection, change):
    selection = deepcopy(collection["selection"])
    if change == "manifest":
        selection["manifest_sha256"] = "f" * 64
    elif change == "policy":
        selection["policy"] = "manually-changed"
    elif change == "hash":
        selection["images"][0]["sha256"] = "f" * 64
    elif change == "order":
        selection["images"].reverse()
    elif change == "omit":
        selection["images"].pop()
    elif change == "extra":
        selection["new_field"] = True
    else:
        selection["images"][0]["image_id"] = collection["manifest"].images[-1].image_id
    with pytest.raises(ValueError, match="exact manifest"):
        review.validate_selection(collection["manifest"], collection["sha"], selection)


def test_pending_and_declared_counts_keep_selected_and_full_source_separate(review, collection):
    pending = review.pending_ledger(collection["selection"])
    result = check_reviews(review, collection, pending)
    assert (result["selected_images"], result["selected_groups"], result["selected_reviewed"], result["selected_pending"]) == (19, 18, 0, 19)
    assert (result["full_images"], result["full_pending"], result["not_selected"]) == (26, 26, 7)
    assert result["semantic_accuracy"] is None
    assert all(not row.independent_human_review and row.reviewer is None and row.marking_visible is None for row in pending.reviews)
    result = check_reviews(review, collection, declared(review, collection))
    assert result["selected_reviewed"] == 1 and result["selected_pending"] == 18 and result["full_pending"] == 25
    assert result["semantic_accuracy"] is None


@pytest.mark.parametrize("change", ["missing", "extra", "order", "hash", "pending_notes"])
def test_ledger_requires_exact_selected_subset_and_empty_pending_facts(review, collection, change):
    raw = review.pending_ledger(collection["selection"]).model_dump(mode="json")
    if change == "missing":
        raw["reviews"].pop()
    elif change == "extra":
        image = collection["manifest"].images[-1]
        raw["reviews"].append(review.ReviewEntry(image_id=image.image_id, sha256=image.sha256).model_dump(mode="json"))
    elif change == "order":
        raw["reviews"].reverse()
    elif change == "hash":
        raw["reviews"][0]["sha256"] = "f" * 64
    else:
        raw["reviews"][0]["ambiguity_notes"] = "Unchecked factual statement"
    with pytest.raises(ValueError):
        check_reviews(review, collection, review.ReviewLedger.model_validate(raw))


@pytest.mark.parametrize("changes", [
    {"independent_human_review": False}, {"reviewer": " "}, {"reviewed_at": None},
    {"reviewed_at": "2026-10-14T03:00:00"}, {"support_notes": " "}, {"marking_visible": None},
    {"exact_identity_visually_established": True}, {"revision_supported": True, "revision_label": "A"},
    {"marking_visible": False, "visible_markings": ["LABEL"]},
])
def test_reviewed_contract_never_invents_missing_declaration_or_support(review, collection, changes):
    with pytest.raises(ValidationError):
        declared(review, collection, **changes)


def test_existing_contract_represents_unreadable_marking_without_invented_text(review, collection):
    ledger = declared(review, collection, marking_visible=True, visible_markings=[],
                      ambiguity_notes="Visible synthetic test marking cannot be read; request a close-up.")
    assert check_reviews(review, collection, ledger)["selected_reviewed"] == 1
    assert ledger.reviews[0].identity_label is ledger.reviews[0].revision_label is None


def test_draft_stores_form_strings_but_is_not_an_annotation(review, collection):
    value = draft(review, collection)
    value.reviewer = "Synthetic test draft author"
    value.forms[0].marking_visible = "yes"
    value.forms[0].visible_markings = "Unconfirmed draft text"
    value.forms[0].support_notes = "Work in progress"
    assert review.validate_draft(collection["manifest"], collection["sha"], collection["selection"], value) == value
    with pytest.raises(ValidationError):
        review.ReviewLedger.model_validate_json(value.model_dump_json())
    assert "independent_human_review" not in value.model_dump_json()


@pytest.mark.parametrize("text", ["x" * 64032, "\U0001f600" * 16000], ids=["ascii", "unicode"])
def test_individually_valid_draft_fields_cannot_exceed_total_utf8_export_bound(review, collection, text):
    value = draft(review, collection)
    for row in value.forms:
        row.visible_markings = text
    # Each form is valid. The complete file would be impossible to re-import.
    review.ReviewDraft.model_validate_json(value.model_dump_json())
    with pytest.raises(ValueError, match="1 MiB byte limit"):
        review.validate_draft(collection["manifest"], collection["sha"], collection["selection"], value)


@pytest.mark.parametrize("change", ["manifest", "selection", "order", "hash", "omit", "declaration", "status", "bool_choice", "oversize"])
def test_draft_validates_binding_fields_and_refuses_review_metadata(review, collection, change):
    raw = draft(review, collection).model_dump(mode="json")
    if change == "manifest":
        raw["manifest_sha256"] = "f" * 64
    elif change == "selection":
        raw["selection_sha256"] = "f" * 64
    elif change == "order":
        raw["forms"].reverse()
    elif change == "hash":
        raw["forms"][0]["sha256"] = "f" * 64
    elif change == "omit":
        raw["forms"].pop()
    elif change == "declaration":
        raw["forms"][0]["independent_human_review"] = True
    elif change == "status":
        raw["forms"][0]["review_status"] = "reviewed"
    elif change == "bool_choice":
        raw["forms"][0]["marking_visible"] = True
    else:
        raw["forms"][0]["support_notes"] = "x" * 4001
    with pytest.raises(ValueError):
        review.validate_draft(collection["manifest"], collection["sha"], collection["selection"], review.ReviewDraft.model_validate(raw))


@pytest.mark.parametrize("change", ["missing", "changed"])
def test_missing_or_tampered_original_prevents_any_gallery_output(review, collection, change):
    path = collection["root"] / collection["manifest"].images[0].local_path
    if change == "missing":
        path.unlink()
    else:
        raw = bytearray(path.read_bytes())
        raw[-1] ^= 1
        path.write_bytes(raw)
    with pytest.raises(ValueError):
        create(review, collection)
    assert not collection["output"].exists()


def test_gallery_new_only_ignored_output_and_original_images_unchanged(review, collection, tmp_path):
    originals = {path.name: path.read_bytes() for path in (collection["root"] / "images").iterdir()}
    result = create(review, collection)
    assert result["selected_pending"] == 19 and result["selected_reviewed"] == 0
    assert {path.name for path in collection["output"].iterdir()} == {"index.html", "selection.json", "image-reviews.json"}
    assert {path.name: path.read_bytes() for path in (collection["root"] / "images").iterdir()} == originals
    with pytest.raises(ValueError, match="new directory"):
        create(review, collection)
    with pytest.raises(ValueError, match="ignored var"):
        review.create_gallery(collection["path"], collection["root"], tmp_path / "outside")


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.scripts, self.images, self.checkboxes, self.csp = [], [], [], None
        self.inside_script = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script":
            self.inside_script = True
            self.scripts.append("")
        if tag == "img":
            self.images.append(attrs)
        if tag == "input" and attrs.get("type") == "checkbox":
            self.checkboxes.append(attrs)
        if tag == "meta" and attrs.get("http-equiv") == "Content-Security-Policy":
            self.csp = attrs["content"]

    def handle_endtag(self, tag):
        if tag == "script":
            self.inside_script = False

    def handle_data(self, data):
        if self.inside_script:
            self.scripts[-1] += data


def test_gallery_escapes_data_binds_csp_and_has_no_predictions_or_default_declarations(review, collection):
    data = collection["manifest"].model_dump(mode="json")
    hostile = '</script><script>window.unwanted=true</script>'
    data["attribution"] = hostile
    data["images"][0]["category"] = hostile
    data["images"][0]["source_labels"] = {"title": "SOURCE LABEL MUST NOT BE PREFILLED"}
    collection["path"].write_text(json.dumps(data), encoding="utf-8")
    create(review, collection)
    source = (collection["output"] / "index.html").read_text(encoding="utf-8")
    parsed = Document()
    parsed.feed(source)
    assert len(parsed.scripts) == 1
    assert hostile not in source and "SOURCE LABEL MUST NOT BE PREFILLED" not in source
    expected = base64.b64encode(hashlib.sha256(parsed.scripts[0].encode()).digest()).decode()
    assert f"'sha256-{expected}'" in parsed.csp
    assert "connect-src 'none'" in parsed.csp and "default-src 'none'" in parsed.csp
    assert all(not image["src"].startswith(("http", "data:")) for image in parsed.images)
    assert all("checked" not in field for field in parsed.checkboxes)
    assert "Missing images block affected reviewed entries" in source
    assert "beforeunload" in parsed.scripts[0] and "checked=false" in parsed.scripts[0]
    assert "No independent reviews have been recorded" in source


def test_cli_checks_pending_ledger_draft_and_changed_sources_without_creating_labels(review, collection):
    create(review, collection)
    common = [sys.executable, "-B", str(SCRIPT), "check", "--manifest", str(collection["path"]),
              "--root", str(collection["root"]), "--selection", str(collection["output"] / "selection.json")]
    reviews_path = collection["output"] / "image-reviews.json"
    original = reviews_path.read_bytes()
    result = subprocess.run([*common, "--reviews", str(reviews_path)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads(result.stdout)
    assert summary["selected_pending"] == 19 and summary["full_pending"] == 26 and summary["semantic_accuracy"] is None
    draft_path = collection["output"] / "draft.json"
    draft_path.write_text(draft(review, collection).model_dump_json(), encoding="utf-8")
    result = subprocess.run([*common, "--draft", str(draft_path)], capture_output=True, text=True, check=False)
    assert result.returncode == 0 and json.loads(result.stdout)["independent_reviews_created"] == 0
    result = subprocess.run([*common, "--reviews", str(draft_path)], capture_output=True, text=True, check=False)
    assert result.returncode == 1 and json.loads(result.stdout)["status"] == "failed"
    (collection["root"] / collection["manifest"].images[0].local_path).unlink()
    result = subprocess.run([*common, "--reviews", str(reviews_path)], capture_output=True, text=True, check=False)
    assert result.returncode == 1 and "Missing" in json.loads(result.stdout)["error"]
    assert reviews_path.read_bytes() == original


def test_file_byte_bounds(review, tmp_path):
    path = tmp_path / "too-large.json"
    path.write_bytes(b" " * (review.MAX_REVIEW_BYTES + 1))
    with pytest.raises(ValueError, match="byte limit"):
        review._read(path)
