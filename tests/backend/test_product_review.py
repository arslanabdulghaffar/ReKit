"""CPU-only review provenance and human-owned metrics; no model execution."""

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
SCRIPT = ROOT / "evaluation" / "product_review.py"
NOW = "2026-10-14T03:00:00+00:00"


@pytest.fixture
def review(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "evaluation"))
    specification = spec_from_file_location("rekit_product_review_tests", SCRIPT)
    module = module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def case(case_id="case-01", *, raw='{"observations":[]}', hashes=None):
    hashes = ["a" * 64, "b" * 64] if hashes is None else hashes
    return {"case_id": case_id, "status": "succeeded" if raw is not None else "unavailable",
            "inputs": [{"image_id": f"image-{index}", "sha256": sha, "group_id": "listing-one"}
                       for index, sha in enumerate(hashes, 1)],
            "execution": {"text": raw} if raw is not None else None,
            "output": None, "error": None}


def result(cases=None):
    return {"schema_version": "rekit-product-evaluation-v1", "manifest_sha256": "c" * 64,
            "configuration": {"prompt_version": "test-only", "generation": {"schema_sha256_2": "d" * 64}},
            "cases": [case()] if cases is None else cases}


def assessed(review, source, **changes):
    value = review.template(source).model_dump(mode="json")
    for row in value["reviews"]:
        row.update(status="reviewed", reviewer="controlled-test-human", reviewed_at=NOW,
                   independent_human_review=True,
                   notes="Synthetic test assessment only; no real dataset labels were reviewed.")
    value["reviews"][0].update(changes)
    return review.Assessments.model_validate(value)


@pytest.fixture
def collection(tmp_path, review, monkeypatch):
    from product_data import DatasetManifest, split_for_group

    monkeypatch.setattr(review, "ROOT", tmp_path)
    root = tmp_path / "var" / "source"
    (root / "images").mkdir(parents=True)
    records = []
    for index, color in enumerate(("red", "blue"), 1):
        with Image.new("RGB", (32, 24), color) as image, BytesIO() as stream:
            image.save(stream, format="JPEG")
            raw = stream.getvalue()
        image_id = f"image-{index}"
        path = root / "images" / f"{image_id}.jpg"
        path.write_bytes(raw)
        records.append({"image_id": image_id, "listing_id": "listing-one", "group_id": "listing-one",
                        "split": split_for_group("listing-one"), "source_url": f"https://example.org/{image_id}.jpg",
                        "local_path": f"images/{image_id}.jpg", "sha256": hashlib.sha256(raw).hexdigest(),
                        "byte_size": len(raw), "width": 32, "height": 24, "category": "test-category",
                        "source_labels": {"title": "Metadata only; not visually established"}, "downloaded_at": NOW})
    manifest = DatasetManifest.model_validate({
        "source_url": "https://example.org/data", "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "Controlled test images, not the acquired dataset.", "downloaded_at": NOW,
        "metadata_receipts": [], "images": records,
    })
    manifest_path = root / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(), encoding="utf-8")
    record = result([case(hashes=[image.sha256 for image in manifest.images]), case("case-02", raw=None)])
    record["cases"][1]["inputs"] = deepcopy(record["cases"][0]["inputs"])
    record["manifest_sha256"] = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    result_path = root / "result.json"
    result_path.write_text(json.dumps(record), encoding="utf-8")
    return {"root": root, "manifest": manifest_path, "result": result_path, "record": record,
            "destination": tmp_path / "var" / "review-queue"}


def save_result(collection):
    collection["result"].write_text(json.dumps(collection["record"]), encoding="utf-8")


def queue(review, collection):
    return review.create_queue(collection["manifest"], collection["root"], collection["result"],
                               collection["destination"])


def test_template_keeps_raw_invalid_outputs_pending_and_handles_execution_absence(review):
    source = result([case(), case("case-02", raw="malformed model text"), case("case-03", raw=None)])
    source["cases"][1]["status"] = "invalid_output"
    original = deepcopy(source)
    template = review.template(source)
    assert source == original
    assert [row.case_id for row in template.reviews] == ["case-01", "case-02"]
    for row in template.reviews:
        assert row.status == "pending" and not row.independent_human_review
        assert row.reviewer is row.reviewed_at is None
        assert row.expected_marking_text is row.model_marking_text is None
        assert all(getattr(row, field) == "undetermined" for field in review.FIELDS)
    summary = review.summarize(source, template)
    assert summary["reviewed_cases"] == 0 and summary["pending_cases"] == 3
    assert all(metric == {"numerator": None, "denominator": 0, "rate": None, "excluded_cases": 3}
               for metric in summary["metrics"].values())


@pytest.mark.parametrize("changes", [
    {"identity": "supported"}, {"revision": "unsupported"}, {"marking": "not_present"},
    {"reviewer": "someone"}, {"reviewed_at": NOW}, {"independent_human_review": True},
    {"expected_marking_text": "LABEL", "model_marking_text": "LABEL"},
    {"correction": "A different identity"}, {"notes": "Automatic judgment"},
])
def test_pending_cannot_assert_human_judgment(review, changes):
    row = review.template(result()).reviews[0].model_dump(mode="json")
    with pytest.raises(ValidationError):
        review.CaseReview.model_validate({**row, **changes})


@pytest.mark.parametrize("changes", [
    {"independent_human_review": False}, {"reviewer": " "}, {"reviewed_at": None},
    {"reviewed_at": "2026-10-14T03:00:00"}, {"notes": " "},
    {"expected_marking_text": "LABEL"}, {"model_marking_text": "LABEL"},
])
def test_reviewed_requires_explicit_human_time_notes_and_paired_transcriptions(review, changes):
    with pytest.raises(ValidationError):
        assessed(review, result(), **changes)


@pytest.mark.parametrize("change", ["configuration", "raw", "order", "source_hash", "image_id"])
def test_whole_record_digest_binds_configuration_raw_output_and_ordered_sources(review, change):
    source = result()
    template = review.template(source)
    changed = deepcopy(source)
    if change == "configuration":
        changed["configuration"]["prompt_version"] = "different-prompt"
    elif change == "raw":
        changed["cases"][0]["execution"]["text"] += " "
    elif change == "order":
        changed["cases"][0]["inputs"].reverse()
    elif change == "source_hash":
        changed["cases"][0]["inputs"][0]["sha256"] = "e" * 64
    else:
        changed["cases"][0]["inputs"][0]["image_id"] = "different-image"
    with pytest.raises(ValueError, match="different execution/configuration"):
        review.summarize(changed, template)
    assert review.digest(dict(reversed(list(source.items())))) == review.digest(source)


@pytest.mark.parametrize("field,value", [
    ("case_id", "unknown-case"), ("output_sha256", "f" * 64),
    ("input_sha256", ["b" * 64, "a" * 64]),
])
def test_individual_review_bindings_reject_mismatch_even_with_correct_result_digest(review, field, value):
    source = result()
    payload = review.template(source).model_dump(mode="json")
    payload["reviews"][0][field] = value
    with pytest.raises(ValueError, match="ordered source hashes changed"):
        review.summarize(source, review.Assessments.model_validate(payload))


def test_duplicate_result_cases_including_no_output_and_duplicate_assessments_rejected(review):
    for raw in ("actual raw", None):
        with pytest.raises(ValueError, match="unique"):
            review.template(result([case(raw=raw), case(raw=raw)]))
    source = result()
    payload = review.template(source).model_dump(mode="json")
    payload["reviews"].append(deepcopy(payload["reviews"][0]))
    with pytest.raises(ValueError, match="Duplicate"):
        review.summarize(source, review.Assessments.model_validate(payload))


def test_semantic_denominators_exclude_pending_absent_and_undetermined_cases(review):
    source = result([case(f"case-{index}") for index in range(5)])
    payload = review.template(source).model_dump(mode="json")
    for row, judgment in zip(payload["reviews"][:4], ("supported", "unsupported", "not_present", "undetermined")):
        row.update(status="reviewed", reviewer="test-human", reviewed_at=NOW,
                   independent_human_review=True, notes="Controlled test only.")
        row.update({field: judgment for field in review.FIELDS})
    summary = review.summarize(source, review.Assessments.model_validate(payload))
    assert summary["reviewed_cases"] == 4 and summary["pending_cases"] == 1
    for field in review.FIELDS:
        assert summary["metrics"][field] == {"numerator": 1, "denominator": 2, "rate": 0.5, "excluded_cases": 3}
    assert "not individual claims or product accuracy" in summary["unit"]


def test_transcription_match_is_human_assessed_exact_text_and_corrections_are_not_automatic(review):
    source = result([case("case-1"), case("case-2"), case("case-3")])
    payload = assessed(review, source).model_dump(mode="json")
    payload["reviews"][0].update(marking="supported", expected_marking_text="REV A",
                                  model_marking_text="REV A", correction="Human correction")
    payload["reviews"][1].update(marking="unsupported", expected_marking_text="REV A", model_marking_text="rev a")
    summary = review.summarize(source, review.Assessments.model_validate(payload))
    assert summary["metrics"]["transcription_exact_match"] == {
        "numerator": 1, "denominator": 2, "rate": 0.5, "excluded_cases": 1}
    assert summary["metrics"]["human_corrections"]["numerator"] == 1
    assert summary["metrics"]["human_corrections"]["denominator"] == 3


@pytest.mark.parametrize("judgment", ["not_present", "undetermined"])
def test_transcription_cannot_bypass_a_missing_or_undetermined_marking_judgment(review, judgment):
    with pytest.raises(ValidationError, match="marking"):
        assessed(review, result(), marking=judgment, expected_marking_text="REV A", model_marking_text="REV A")


def test_mutated_pending_model_is_revalidated_before_metrics(review):
    source = result()
    template = review.template(source)
    template.reviews[0].identity = "supported"
    with pytest.raises(ValidationError):
        review.summarize(source, template)


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.template = ""
        self.in_template = False

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        self.in_template = tag == "script" and dict(attrs).get("id") == "template"

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_template = False

    def handle_data(self, value):
        if self.in_template:
            self.template += value


def test_queue_escapes_hostile_model_source_and_case_text_without_creating_reviews(review, collection):
    hostile = '</script><script>alert("model")</script><img src=x onerror=alert(1)>'
    manifest = json.loads(collection["manifest"].read_text(encoding="utf-8"))
    manifest["images"][0]["source_labels"]["title"] = hostile
    manifest["attribution"] = hostile
    collection["manifest"].write_text(json.dumps(manifest), encoding="utf-8")
    collection["record"]["manifest_sha256"] = hashlib.sha256(collection["manifest"].read_bytes()).hexdigest()
    collection["record"]["cases"][0]["execution"]["text"] = hostile
    collection["record"]["cases"][0]["case_id"] = 'case"><img src=x onerror=alert(2)>'
    save_result(collection)
    outcome = queue(review, collection)
    assert outcome["cases"] == 2 and outcome["reviewed"] == 0
    page = (collection["destination"] / "index.html").read_text(encoding="utf-8")
    parsed = Page()
    parsed.feed(page)
    assert hostile not in page and "&lt;/script&gt;" in page
    assert all(not any(name.startswith("on") for name in attrs) for _, attrs in parsed.tags)
    assert all(attrs.get("src") != "x" for tag, attrs in parsed.tags if tag == "img")
    assert len([tag for tag, _ in parsed.tags if tag == "script"]) == 2
    assert "connect-src 'none'" in page and "form-action 'none'" in page
    template = review.Assessments.model_validate_json(parsed.template)
    assert template.reviews[0].status == "pending" and not template.reviews[0].independent_human_review
    assert template.reviews[0].case_id == collection["record"]["cases"][0]["case_id"]
    saved = review.Assessments.model_validate_json(
        (collection["destination"] / "case-assessments.json").read_text(encoding="utf-8"))
    assert saved == template
    assert review.summarize(collection["record"], saved)["reviewed_cases"] == 0


@pytest.mark.parametrize("change", ["manifest", "image_hash", "group", "bytes"])
def test_queue_rejects_changed_manifest_or_image_provenance_before_writing(review, collection, change):
    if change == "manifest":
        collection["record"]["manifest_sha256"] = "f" * 64
    elif change == "image_hash":
        collection["record"]["cases"][0]["inputs"][0]["sha256"] = "f" * 64
    elif change == "group":
        collection["record"]["cases"][0]["inputs"][0]["group_id"] = "other-listing"
    else:
        (collection["root"] / "images/image-1.jpg").write_bytes(b"tampered")
    save_result(collection)
    with pytest.raises(ValueError):
        queue(review, collection)
    assert not collection["destination"].exists()


def test_queue_refuses_overwrite_or_export_outside_ignored_storage(review, collection):
    queue(review, collection)
    before = {path.name: path.read_bytes() for path in collection["destination"].iterdir()}
    with pytest.raises(ValueError):
        queue(review, collection)
    assert before == {path.name: path.read_bytes() for path in collection["destination"].iterdir()}
    outside = collection["destination"].parents[1] / "published"
    with pytest.raises(ValueError):
        review.create_queue(collection["manifest"], collection["root"], collection["result"], outside)
    assert not outside.exists()


def test_result_reader_rejects_unbounded_or_invalid_case_collections(review, tmp_path):
    path = tmp_path / "result.json"
    for value in ([], {}, {"cases": "wrong"}, {"cases": [{}] * 61}):
        path.write_text(json.dumps(value), encoding="utf-8")
        with pytest.raises(ValueError):
            review.read_result(path)
    with path.open("wb") as stream:
        stream.truncate(8 * 1024**2 + 1)
    with pytest.raises(ValueError, match="bound"):
        review.read_result(path)


def test_check_cli_reports_null_metrics_for_pending_assessments(review, collection):
    path = collection["root"] / "pending-assessments.json"
    path.write_text(review.template(collection["record"]).model_dump_json(), encoding="utf-8")
    completed = subprocess.run([sys.executable, str(SCRIPT), "check", "--result", str(collection["result"]),
                                "--assessments", str(path)], capture_output=True, text=True, timeout=30, check=False)
    assert completed.returncode == 0, completed.stderr
    output = json.loads(completed.stdout)
    assert output["reviewed_cases"] == 0 and output["pending_cases"] == 2
    assert output["metrics"]["identity"]["rate"] is None
