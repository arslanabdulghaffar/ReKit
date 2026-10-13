"""CPU-only evaluation accounting with generated images and a controlled provider."""

from copy import deepcopy
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

from PIL import Image
import pytest

from rekit.inference.constrained import SCHEMA_VERSION, inspection_schema, schema_digest
from rekit.inference.models import InferenceConfiguration
from rekit.inference.provider import VisionError, VisionTimeout, VisionUnavailable


SCRIPT = Path(__file__).parents[2] / "evaluation/run_product_evaluation.py"
specification = spec_from_file_location("rekit_product_evaluation", SCRIPT)
evaluation = module_from_spec(specification)
specification.loader.exec_module(evaluation)


def configuration(*, allow_candidates=False):
    return InferenceConfiguration(
        provider="local-transformers", model_repository="controlled-test/model",
        model_revision=evaluation.MODEL_REVISION, processor_revision=evaluation.MODEL_REVISION,
        runtime={"fixture": "CPU test double; no GPU execution"}, device="cuda:1",
        prompt_version="controlled-test", preprocessing={"prompt_sha256": "1" * 64},
        generation={"decoding": "lm-format-enforcer", "schema_version": SCHEMA_VERSION,
                    "schema_sha256_1": schema_digest(inspection_schema(1, allow_candidates=allow_candidates)),
                    "schema_sha256_2": schema_digest(inspection_schema(2, allow_candidates=allow_candidates)),
                    "identity_candidates_allowed": allow_candidates},
    )


def valid_output():
    return {"observations": [{"kind": "appearance", "text": "A gray connector.", "image_indices": [1]}],
            "candidates": [], "uncertainties": ["Identity is unknown."],
            "additional_views": [{"view": "Label close-up", "reason": "Need readable markings.", "image_indices": [1]}]}


class ControlledProvider:
    """All execution measurements here are synthetic assertions, never benchmarks."""

    def __init__(self, response=None, *, allow_candidates=False):
        self.configuration = configuration(allow_candidates=allow_candidates)
        self.calls = []
        self.response = response

    def inspect(self, images):
        index = len(self.calls)
        self.calls.append(images)
        result = {key: getattr(self.configuration, key) for key in
                  ("provider", "model_repository", "model_revision", "device")}
        result.update(status="succeeded", text=json.dumps(valid_output()), runtime={"fixture": "controlled"},
                      metrics={"input_sha256": [sha256(raw).hexdigest() for raw in images],
                               "vision_forward_calls": 1, "decoding": "lm-format-enforcer",
                               "schema_version": SCHEMA_VERSION,
                               "schema_sha256": schema_digest(inspection_schema(len(images), allow_candidates=self.configuration.generation["identity_candidates_allowed"])),
                               "inference_seconds": float(index + 1), "model_loaded_this_request": index == 0,
                               "load_peak_allocated_bytes": 50, "peak_allocated_bytes": 100 + index,
                               "peak_reserved_bytes": 200 + index})
        return self.response(index, result) if self.response else result


@pytest.fixture
def collection(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPT.parent))
    monkeypatch.setattr(evaluation, "ROOT", tmp_path)
    from product_data import DatasetManifest, split_for_group

    root = tmp_path / "var/images"
    (root / "images").mkdir(parents=True)
    images = []

    def image(group, category):
        number = len(images) + 1
        buffer = BytesIO()
        Image.new("RGB", (32, 32), ((number * 11) % 256, (number * 17) % 256, (number * 23) % 256)).save(buffer, format="JPEG")
        raw = buffer.getvalue()
        image_id = f"image-{number}"
        local = f"images/{image_id}.jpg"
        (root / local).write_bytes(raw)
        return {"image_id": image_id, "listing_id": group, "group_id": group, "split": split_for_group(group),
                "source_url": f"https://example.test/{image_id}.jpg", "local_path": local,
                "sha256": sha256(raw).hexdigest(), "byte_size": len(raw), "width": 32, "height": 32,
                "category": category, "source_labels": {"model_number": "UNVERIFIED REV A"},
                "downloaded_at": "2026-10-14T00:00:00+00:00"}

    pair_group = None
    for category in range(6):
        candidates = [f"category-{category}-group-{number}" for number in range(50)]
        holdout = next(group for group in candidates if split_for_group(group) == "holdout")
        development = [group for group in candidates if split_for_group(group) == "development"][:2]
        for group in [holdout, *development]:
            images.append(image(group, f"category-{category}"))
        if category == 0:
            pair_group = development[0]
    images.append(image(pair_group, "category-0"))
    manifest = DatasetManifest.model_validate({
        "source_url": "https://example.test/", "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "attribution": "Generated test images only; not an ABO result.", "downloaded_at": "2026-10-14T00:00:00+00:00",
        "metadata_receipts": [], "images": images,
    })
    path = tmp_path / "manifest.json"
    path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    output = tmp_path / "var/results.json"
    return SimpleNamespace(root=root, manifest=manifest, manifest_path=path, output=output, model_dir=tmp_path / "model")


def run(collection, monkeypatch, provider):
    monkeypatch.setattr(evaluation, "_make_provider", lambda model_dir, device: provider)
    code = evaluation.run(manifest_path=collection.manifest_path, image_root=collection.root,
                          model_dir=collection.model_dir, device=1, output=collection.output)
    return code, json.loads(collection.output.read_text(encoding="utf-8"))


def test_selection_is_fixed_development_only_and_joint_uses_one_listing(collection):
    cases = evaluation.select_cases(collection.manifest)
    assert len(cases) == 13 and [case["kind"] for case in cases] == ["single"] * 12 + ["joint"]
    assert [case["case_id"] for case in cases] == [f"case-{number:02d}" for number in range(1, 14)]
    singles = [case["inputs"][0] for case in cases[:12]]
    assert len({image["group_id"] for image in singles}) == 12
    assert all(image["split"] == "development" for case in cases for image in case["inputs"])
    assert [image["image_id"] for image in singles[:2]] == ["image-2", "image-3"]
    assert [image["image_id"] for image in cases[-1]["inputs"]] == ["image-2", "image-19"]
    assert len({image["group_id"] for image in cases[-1]["inputs"]}) == 1
    changed_metadata = collection.manifest.model_copy(deep=True)
    for image in changed_metadata.images:
        image.source_labels["model_number"] = "ANOTHER UNSUPPORTED ID"
    assert evaluation.select_cases(changed_metadata) == cases


@pytest.mark.parametrize("failure", ["missing_category", "missing_development_group", "missing_pair"])
def test_incomplete_sample_never_fills_from_holdout(collection, failure):
    manifest = collection.manifest.model_copy(deep=True)
    if failure == "missing_category":
        manifest.images = [image for image in manifest.images if image.category != "category-5"]
    elif failure == "missing_development_group":
        excluded = manifest.images[2].group_id
        manifest.images = [image for image in manifest.images if image.group_id != excluded]
    else:
        manifest.images = manifest.images[:-1]
    with pytest.raises(ValueError):
        evaluation.select_cases(manifest)


def test_complete_run_preserves_plan_raw_configuration_and_unreviewed_denominators(collection, monkeypatch):
    observed = []

    def response(index, result):
        saved = json.loads(collection.output.read_text(encoding="utf-8"))
        assert len(saved["case_plan"]) == 13 and len(saved["cases"]) == 13
        assert saved["cases"][index]["status"] == "running"
        if index:
            assert saved["cases"][index - 1]["status"] == "succeeded"
        observed.append(result["text"])
        return result

    provider = ControlledProvider(response)
    code, record = run(collection, monkeypatch, provider)
    assert code == 0 and record["status"] == "completed"
    assert len(provider.calls) == 13 and sum(map(len, provider.calls)) == 14
    assert record["manifest_sha256"] == sha256(collection.manifest_path.read_bytes()).hexdigest()
    assert record["configuration"] == provider.configuration.model_dump(mode="json")
    assert record["catalog_supplied"] is False and record["independent_human_review"] is False
    assert [case["execution"]["text"] for case in record["cases"]] == observed
    assert all(case["output"] == valid_output() for case in record["cases"])
    summary = record["summary"]
    assert summary["attempted_cases"] == 13 and summary["input_presentations"] == 14
    assert summary["unique_images"] == 13 and summary["unique_groups"] == 12
    assert summary["schema_valid_responses"]["numerator"] == summary["schema_valid_responses"]["denominator"] == 13
    assert summary["instructed_abstention"]["numerator"] == summary["instructed_abstention"]["denominator"] == 13
    assert summary["latency_seconds"]["inference_measured"] == {"n": 13, "min": 1.0, "p50": 7.0, "p95": 13.0, "max": 13.0}
    assert summary["latency_seconds"]["inference_cold"]["n"] == 1
    assert summary["latency_seconds"]["inference_warm"]["n"] == 12
    assert summary["gpu_memory_bytes"]["peak_allocated_bytes"] == {"n": 13, "max": 112}
    assert summary["gpu_memory_bytes"]["peak_reserved_bytes"] == {"n": 13, "max": 212}
    assert all(metric["rate"] is None and metric["numerator"] is None and metric["denominator"] == 0
               for metric in summary["semantic_metrics"].values())


def test_raw_unicode_output_is_saved_before_strict_parser_runs(collection, monkeypatch):
    import rekit.inference.parsing as parsing

    original_parse = parsing.parse_output

    def observed_parse(raw, image_count, *, allow_candidates):
        saved = json.loads(collection.output.read_text(encoding="utf-8"))
        current = next(case for case in saved["cases"] if case["status"] == "running")
        assert current["execution"]["text"] == raw and current["output"] is None
        assert allow_candidates is False
        return original_parse(raw, image_count, allow_candidates=allow_candidates)

    def response(index, result):
        payload = valid_output()
        payload["observations"][0]["text"] = "표시 α visible."
        result["text"] = json.dumps(payload, ensure_ascii=False)
        return result

    monkeypatch.setattr(parsing, "parse_output", observed_parse)
    code, record = run(collection, monkeypatch, ControlledProvider(response))
    assert code == 0 and "표시 α" in record["cases"][0]["execution"]["text"]


def test_failures_stay_in_denominators_and_do_not_erase_raw_responses(collection, monkeypatch):
    def response(index, result):
        if index == 0:
            result["text"] = "Actual controlled malformed response"
        if index == 1:
            raise VisionTimeout("Controlled timeout")
        if index == 2:
            raise VisionError("Controlled runtime error")
        if index == 3:
            result["metrics"]["schema_sha256"] = "0" * 64
        return result

    provider = ControlledProvider(response)
    code, record = run(collection, monkeypatch, provider)
    assert code == 1 and len(provider.calls) == 13
    assert record["status"] == "completed_with_failures"
    assert [case["status"] for case in record["cases"][:4]] == ["invalid_output", "timed_out", "failed", "failed"]
    assert record["cases"][0]["execution"]["text"] == "Actual controlled malformed response"
    assert all(case["output"] is None for case in record["cases"][:4])
    summary = record["summary"]
    assert summary["schema_valid_responses"]["numerator"] == 9
    assert summary["schema_valid_responses"]["denominator"] == 13
    assert summary["latency_seconds"]["wall_all_attempts"]["n"] == 13
    assert summary["gpu_memory_bytes"]["peak_allocated_bytes"]["n"] == 11


def test_unavailable_provider_stops_without_inventing_remaining_attempts(collection, monkeypatch):
    def unavailable(index, result):
        raise VisionUnavailable("Controlled missing runtime")

    provider = ControlledProvider(unavailable)
    code, record = run(collection, monkeypatch, provider)
    assert code == 1 and len(provider.calls) == 1
    assert record["summary"]["attempted_cases"] == 1 and record["summary"]["not_attempted_cases"] == 12
    assert record["summary"]["schema_valid_responses"]["denominator"] == 1
    assert record["summary"]["gpu_memory_bytes"]["peak_allocated_bytes"] == {"n": 0, "max": None}
    assert all(case["status"] == "not_attempted" for case in record["cases"][1:])


@pytest.mark.parametrize("field,value", [
    ("provider", "wrong-provider"), ("model_repository", "wrong/model"),
    ("model_revision", "0" * 40), ("device", "cuda:0"),
    ("input_sha256", ["0" * 64]), ("vision_forward_calls", 0), ("vision_forward_calls", True),
    ("schema_version", "wrong-version"), ("schema_sha256", "0" * 64), ("decoding", "unconstrained"),
])
def test_execution_provenance_and_image_encoder_claims_are_checked(field, value):
    provider = ControlledProvider()
    raw = b"controlled input"
    result = provider.inspect([raw])
    target = result if field in {"provider", "model_repository", "model_revision", "device"} else result["metrics"]
    target[field] = value
    with pytest.raises(ValueError):
        evaluation._check_execution(result, provider.configuration.model_dump(mode="json"), [{"sha256": sha256(raw).hexdigest()}])


def test_joint_hash_order_is_not_treated_as_an_unordered_set(collection, monkeypatch):
    def reversed_hashes(index, result):
        if index == 12:
            result["metrics"]["input_sha256"].reverse()
        return result

    code, record = run(collection, monkeypatch, ControlledProvider(reversed_hashes))
    assert code == 1 and record["cases"][-1]["status"] == "failed"
    assert record["cases"][-1]["output"] is None
    assert record["cases"][-1]["execution"]["text"]


def test_out_of_range_source_reference_is_not_repaired(collection, monkeypatch):
    def invalid_source(index, result):
        if index == 0:
            payload = valid_output()
            payload["observations"][0]["image_indices"] = [2]
            result["text"] = json.dumps(payload)
        return result

    code, record = run(collection, monkeypatch, ControlledProvider(invalid_source))
    assert code == 1 and record["cases"][0]["status"] == "invalid_output"
    assert record["cases"][0]["output"] is None
    assert json.loads(record["cases"][0]["execution"]["text"])["observations"][0]["image_indices"] == [2]


def test_historical_candidate_and_marking_counts_do_not_become_semantic_accuracy(collection, monkeypatch):
    def claimed_identity(index, result):
        if index == 0:
            payload = valid_output()
            payload["observations"][0] = {"kind": "marking", "text": "REV A", "image_indices": [1]}
            payload["candidates"] = [{"component_type_id": "claimed-identity", "revision": "A",
                                      "revision_marking": "REV A", "reason": "Unverified claim.", "image_indices": [1]}]
            result["text"] = json.dumps(payload)
        return result

    code, record = run(collection, monkeypatch, ControlledProvider(claimed_identity, allow_candidates=True))
    assert code == 0
    counts = record["summary"]["output_counts"]
    assert counts["identity_candidates"] == counts["revision_candidates"] == counts["revision_marking_quotes"] == counts["marking_observations"] == 1
    assert counts["responses_with_candidates_despite_no_catalog"] == 1
    assert record["summary"]["instructed_abstention"]["numerator"] == 12
    assert record["summary"]["semantic_metrics"]["unsupported_identity_claims"]["rate"] is None


def test_no_catalog_candidate_is_invalid_output_and_raw_claim_remains_reviewable(collection, monkeypatch):
    def forbidden_candidate(index, result):
        if index == 0:
            payload = valid_output()
            payload["candidates"] = [{"component_type_id": "invented-part", "revision": "A",
                                      "revision_marking": "REV A", "reason": "Controlled unsupported claim.",
                                      "image_indices": [1]}]
            result["text"] = json.dumps(payload)
        return result

    code, record = run(collection, monkeypatch, ControlledProvider(forbidden_candidate))
    rejected = record["cases"][0]
    assert code == 1 and rejected["status"] == "invalid_output" and rejected["output"] is None
    assert json.loads(rejected["execution"]["text"])["candidates"][0]["component_type_id"] == "invented-part"
    assert record["configuration"]["generation"]["identity_candidates_allowed"] is False
    assert record["summary"]["schema_valid_responses"]["numerator"] == 12
    assert record["summary"]["schema_valid_responses"]["denominator"] == 13


def test_corrupt_input_fails_integrity_before_provider_creation(collection, monkeypatch):
    first = collection.manifest.images[0]
    (collection.root / first.local_path).write_bytes(b"corrupt")
    monkeypatch.setattr(evaluation, "_make_provider", lambda *args: pytest.fail("Model construction preceded integrity checks"))
    code = evaluation.run(manifest_path=collection.manifest_path, image_root=collection.root,
                          model_dir=collection.model_dir, device=1, output=collection.output)
    record = json.loads(collection.output.read_text(encoding="utf-8"))
    assert code == 1 and record["status"] == "failed"
    assert record["summary"]["attempted_cases"] == 0 and "configuration" not in record


def test_changed_input_after_preflight_is_rejected_before_inference(collection, monkeypatch):
    provider = ControlledProvider()

    def factory(model_dir, device):
        selected = evaluation.select_cases(collection.manifest)[0]["inputs"][0]
        (collection.root / selected["local_path"]).write_bytes(b"changed after preflight")
        return provider

    monkeypatch.setattr(evaluation, "_make_provider", factory)
    code = evaluation.run(manifest_path=collection.manifest_path, image_root=collection.root,
                          model_dir=collection.model_dir, device=1, output=collection.output)
    record = json.loads(collection.output.read_text(encoding="utf-8"))
    assert code == 1 and record["cases"][0]["status"] == "failed"
    assert record["cases"][0]["execution"] is None and record["cases"][0]["output"] is None
    assert len(provider.calls) == 11  # The changed image also participates in the joint case.


@pytest.mark.parametrize("destination", ["outside", "existing"])
def test_output_never_overwrites_prior_results_or_leaves_ignored_storage(collection, monkeypatch, destination):
    output = collection.output if destination == "existing" else collection.output.parent.parent / "outside.json"
    if destination == "existing":
        output.write_text("preserve prior result", encoding="utf-8")
    monkeypatch.setattr(evaluation, "_make_provider", lambda *args: pytest.fail("Output validation must precede model initialization"))
    with pytest.raises((ValueError, FileExistsError)):
        evaluation.run(manifest_path=collection.manifest_path, image_root=collection.root,
                       model_dir=collection.model_dir, device=1, output=output)
    if destination == "existing":
        assert output.read_text(encoding="utf-8") == "preserve prior result"
    else:
        assert not output.exists()


def test_provider_factory_supplies_no_catalog(monkeypatch, tmp_path):
    import rekit.inference.provider as providers

    calls = []
    monkeypatch.setattr(providers, "LocalVisionProvider", lambda **kwargs: calls.append(kwargs))
    evaluation._make_provider(tmp_path, 1)
    assert calls == [{"model_dir": tmp_path, "device": 1, "catalog": None}]


def test_module_import_does_not_import_application_or_gpu_dependencies():
    probe = """
import runpy, sys
runpy.run_path(sys.argv[1])
assert not any(name.split('.')[0] in {'rekit','torch','transformers','PIL','pydantic','product_data'} for name in sys.modules)
print('stdlib-only import')
"""
    result = subprocess.run([sys.executable, "-I", "-S", "-c", probe, str(SCRIPT)], capture_output=True, timeout=10, check=False)
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    assert result.stdout.strip() == b"stdlib-only import"
