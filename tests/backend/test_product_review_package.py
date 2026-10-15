"""Frozen review provenance and denominators; synthetic test data only."""

from copy import deepcopy
import hashlib
import importlib
from io import BytesIO
import json
from pathlib import Path

from PIL import Image
import pytest


ROOT = Path(__file__).resolve().parents[2]
NOW = "2026-10-15T00:00:00+00:00"


@pytest.fixture
def package(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(ROOT / "evaluation"))
    module = importlib.import_module("package_product_review")
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.setattr(module.product_review, "ROOT", tmp_path)
    monkeypatch.setattr(module.image_review, "ROOT", tmp_path)
    return module


@pytest.fixture
def collection(package, tmp_path):
    from product_data import DatasetManifest, split_for_group

    source = tmp_path / "var/source"
    (source / "images").mkdir(parents=True)
    groups = [f"listing-{number}" for number in range(40) if split_for_group(f"listing-{number}") == "development"][:13]
    images = []
    for index, group in enumerate([*groups, groups[0]]):
        with Image.new("RGB", (32, 24), (index * 13, index * 7, index * 11)) as image, BytesIO() as stream:
            image.save(stream, format="JPEG")
            raw = stream.getvalue()
        image_id = f"image-{index}"
        relative = f"images/{image_id}.jpg"
        (source / relative).write_bytes(raw)
        images.append({"image_id": image_id, "listing_id": group, "group_id": group,
                       "split": "development", "source_url": f"https://example.org/{image_id}.jpg",
                       "local_path": relative, "sha256": hashlib.sha256(raw).hexdigest(), "byte_size": len(raw),
                       "width": 32, "height": 24, "category": f"category-{groups.index(group) // 2}",
                       "source_labels": {"title": "Metadata is not visual truth"}, "downloaded_at": NOW})
    manifest = DatasetManifest.model_validate({"source_url": "https://example.org/data",
        "license_url": "https://creativecommons.org/licenses/by/4.0/", "attribution": "Synthetic test images only.",
        "downloaded_at": NOW, "metadata_receipts": [], "images": images})
    manifest_path = source / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(), encoding="utf-8")
    sha = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    selection = package.image_review.build_selection(manifest, sha)
    selection_path = source / "selection.json"
    selection_path.write_text(json.dumps(selection), encoding="utf-8")
    cases = []
    for index, item in enumerate(images):
        inputs = [item] if index < 13 else [images[0], item]
        cases.append({"case_id": f"case-{index + 1:02d}", "status": "succeeded",
                      "inputs": [{key: image[key] for key in ("image_id", "sha256", "group_id")} for image in inputs],
                      "execution": {"text": 'Recorded text </script> \"quote\"\n' + str(index)}, "output": None})
    result = {"schema_version": "rekit-product-evaluation-v1", "manifest_sha256": sha,
              "configuration": {"provider": "controlled-test-only"}, "cases": cases}
    for name in ("baseline", "after"):
        (source / f"{name}.json").write_text(json.dumps(result), encoding="utf-8")
    return {"manifest": manifest, "manifest_path": manifest_path, "root": source, "selection": selection,
            "selection_path": selection_path, "baseline": source / "baseline.json", "after": source / "after.json",
            "result": result, "destination": tmp_path / "var/frozen-review"}


def create(package, collection):
    return package.create_package(collection["manifest_path"], collection["root"], collection["selection_path"],
                                  collection["baseline"], collection["after"], collection["destination"])


def test_package_is_portable_preserves_exact_inputs_outputs_and_pending_boundaries(package, collection):
    before = {path: path.read_bytes() for path in collection["root"].rglob("*") if path.is_file()}
    summary = create(package, collection)
    assert summary["listing_groups"] == 12 and summary["cases_per_variant"] == 13
    assert summary["original_images"] == 13 and summary["images"]["selected_pending"] == 13
    assert len(summary["selection_exclusions"]) == 1
    for run in summary["variants"].values():
        assert run["pending_cases"] == 13 and run["reviewed_cases"] == 0
        assert all(metric["denominator"] == 0 and metric["rate"] is None for metric in run["metrics"].values())
        assert run["disagreement"]["status"] == "not established"
    destination = collection["destination"]
    manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["selection"]["proposed_double_review_groups"]) == 4
    assert manifest["sources"]["baseline.json"]["sha256"] == hashlib.sha256(collection["baseline"].read_bytes()).hexdigest()
    for row in manifest["cases"]:
        original = next(case for case in collection["result"]["cases"] if case["case_id"] == row["case_id"])
        for run in ("baseline", "after"):
            assert (destination / row[run]["raw_output_path"]).read_bytes() == original["execution"]["text"].encode("utf-8")
            assert row[run]["source_case_sha256"] == package.product_review.digest(original)
    assert before == {path: path.read_bytes() for path in collection["root"].rglob("*") if path.is_file()}
    page = (destination / "output-after/index.html").read_text(encoding="utf-8")
    assert 'id="case-01" data-case="case-01"' in page and "&lt;/script&gt;" in page
    assert "connect-src 'none'" in page
    # Move the whole private package: relative original-image links and all hashes still work.
    moved = destination.with_name("moved-review")
    destination.rename(moved)
    assert package.check_package(moved)["original_images"] == 13


@pytest.mark.parametrize("relative", ["images/image-0.jpg", "source/baseline.json", "outputs/after/01.txt", "output-after/case-assessments.json"])
def test_integrity_check_rejects_mutated_frozen_files(package, collection, relative):
    create(package, collection)
    path = collection["destination"] / relative
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError, match="Frozen package file changed"):
        package.check_package(collection["destination"])


@pytest.mark.parametrize("field", ["configuration", "status", "review_package_source", "unexpected_field"])
def test_projection_cannot_change_source_metadata_even_if_its_file_hash_is_rewritten(package, collection, field):
    create(package, collection)
    destination = collection["destination"]
    path = destination / "results/after.json"
    projected = json.loads(path.read_text(encoding="utf-8"))
    if field == "configuration":
        projected[field]["provider"] = "fabricated-provider"
        projected[field]["runtime"] = {"device": "fabricated-device"}
    else:
        projected[field] = "fabricated-metadata"
    raw = json.dumps(projected).encode("utf-8")
    path.write_bytes(raw)
    manifest_path = destination / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"]["results/after.json"] = {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="exact allowed source projection"):
        package.check_package(destination)


@pytest.mark.parametrize("change", ["paired-input", "selection", "too-few", "missing-output", "manifest"])
def test_invalid_source_or_insufficient_groups_fail_before_creating_destination(package, collection, change):
    after = deepcopy(collection["result"])
    if change == "paired-input":
        after["cases"][0]["inputs"] = after["cases"][1]["inputs"]
    elif change == "too-few":
        after["cases"] = after["cases"][:11]
    elif change == "missing-output":
        for case in after["cases"][:3]:
            case["execution"] = None
    elif change == "manifest":
        after["manifest_sha256"] = "f" * 64
    else:
        collection["selection"]["images"].reverse()
        collection["selection_path"].write_text(json.dumps(collection["selection"]), encoding="utf-8")
    collection["after"].write_text(json.dumps(after), encoding="utf-8")
    with pytest.raises(ValueError):
        create(package, collection)
    assert not collection["destination"].exists()


def test_refuses_overwrite_and_outside_ignored_storage(package, collection):
    create(package, collection)
    before = (collection["destination"] / "manifest.json").read_bytes()
    with pytest.raises(ValueError, match="fresh"):
        create(package, collection)
    assert before == (collection["destination"] / "manifest.json").read_bytes()
    collection["destination"] = collection["root"].parents[1] / "public"
    with pytest.raises(ValueError, match="ignored var"):
        create(package, collection)


def _human_assessments(package, result, actor):
    value = package.product_review.template(result).model_dump(mode="json")
    value["reviews"][0].update(status="reviewed", reviewer=actor, reviewed_at=NOW,
        independent_human_review=True, notes="Synthetic test annotation, not an actual human review.", identity="supported")
    return value


def test_distinct_reviewers_and_field_denominators_preserve_disagreements_without_adjudication(package, collection):
    source = collection["result"]
    a = _human_assessments(package, source, "Test actor A")
    b = _human_assessments(package, source, "Test actor B")
    b["reviews"][0]["identity"] = "unsupported"
    b["reviews"][0]["revision"] = "not_present"
    model = package.product_review.Assessments
    summary = package.disagreements(source, model.model_validate(a), model.model_validate(b))
    assert summary["metrics"]["identity"]["eligible_paired_cases"] == 1
    assert summary["metrics"]["identity"]["rate"] == 1.0
    assert summary["metrics"]["identity"]["disagreeing_cases"] == ["case-01"]
    assert summary["metrics"]["revision"]["eligible_paired_cases"] == 0
    assert summary["metrics"]["revision"]["rate"] is None
    b["reviews"][0]["reviewer"] = " test ACTOR a "
    same = package.disagreements(source, model.model_validate(a), model.model_validate(b))
    assert same["status"] == "not established"
    assert same["metrics"]["identity"]["exclusions"][0]["reason"] == "same declared reviewer"
    assert a["reviews"][0]["identity"] == "supported" and b["reviews"][0]["identity"] == "unsupported"


@pytest.mark.parametrize("other,expected_rate", [("supported", 1.0), ("unsupported", 1.0), ("not_present", 0.0)])
def test_claim_presence_disagreement_is_distinct_from_semantic_accuracy_eligibility(package, collection, other, expected_rate):
    source = collection["result"]
    a = _human_assessments(package, source, "Test actor A")
    b = _human_assessments(package, source, "Test actor B")
    a["reviews"][0]["identity"] = "not_present"
    b["reviews"][0]["identity"] = other
    model = package.product_review.Assessments
    first, second = model.model_validate(a), model.model_validate(b)
    disagreement = package.disagreements(source, first, second)["metrics"]["identity"]
    assert disagreement["eligible_paired_cases"] == 1
    assert disagreement["rate"] == expected_rate
    assert package.product_review.summarize(source, first)["metrics"]["identity"]["denominator"] == 0
    assert package.product_review.summarize(source, first)["metrics"]["identity"]["rate"] is None
    assert package.product_review.summarize(source, second)["metrics"]["identity"]["denominator"] == int(other != "not_present")


def test_external_human_exports_are_validated_without_modifying_frozen_templates(package, collection):
    create(package, collection)
    destination = collection["destination"]
    result = package.product_review.read_result(destination / "results/after.json")
    exported = collection["root"] / "human-test-export.json"
    values = _human_assessments(package, result, "Test actor")
    exported.write_text(json.dumps(values), encoding="utf-8")
    summary = package.check_package(destination, after_path=exported)
    assert summary["variants"]["after"]["reviewed_cases"] == 1
    assert summary["variants"]["after"]["metrics"]["identity_supported"]["denominator"] == 1
    assert package.check_package(destination)["variants"]["after"]["reviewed_cases"] == 0
    values["reviews"][0]["output_sha256"] = "f" * 64
    exported.write_text(json.dumps(values), encoding="utf-8")
    with pytest.raises(ValueError, match="ordered source hashes"):
        package.check_package(destination, after_path=exported)
