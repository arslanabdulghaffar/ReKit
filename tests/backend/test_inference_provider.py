"""CPU-only provider contract tests; no model files or CUDA execution."""

import builtins
import hashlib
from importlib.metadata import PackageNotFoundError
import json
from pathlib import Path

from pydantic import ValidationError
import pytest

from rekit.catalog.models import Catalog
from rekit.inference.adapters.local_transformers import (
    LocalVisionBusy, LocalVisionError, LocalVisionTimeout, MODEL_ID, MODEL_REVISION,
)
from rekit.inference import provider
from rekit.inference.parsing import parse_output
from rekit.inference.provider import (
    LocalVisionProvider, VisionError, VisionTimeout, VisionUnavailable,
)


@pytest.fixture
def catalog():
    path = Path(__file__).parents[1] / "fixtures" / "synthetic_catalog.json"
    return Catalog.model_validate_json(path.read_text(encoding="utf-8"))


@pytest.fixture
def adapters(monkeypatch):
    instances = []

    class Adapter:
        def __init__(self, **options):
            self.options = options
            self.status = "unloaded"
            self.calls = []
            self.error = None
            self.result = {
                "status": "succeeded",
                "text": "deliberately unparsed model text",
                "model_repository": MODEL_ID,
                "model_revision": MODEL_REVISION,
                "provider": "local-transformers",
                "device": f"cuda:{options['device']}",
                "metrics": {"input_sha256": ["a" * 64], "vision_forward_calls": 1},
            }
            instances.append(self)

        def inspect(self, images, prompt, *, json_schema=None):
            self.calls.append((images, prompt))
            self.last_schema = json_schema
            if self.error is not None:
                raise self.error
            self.status = "ready"
            return self.result

    monkeypatch.setattr(provider, "LocalTransformersVision", Adapter)
    monkeypatch.setattr(provider, "version", lambda package: f"installed-{package}")
    return instances


def test_constructor_does_not_import_gpu_libraries_or_read_model_files(monkeypatch, tmp_path):
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"torch", "transformers"}:
            raise AssertionError("Model runtime imported at provider construction")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(provider, "version", lambda package: "installed-metadata")
    monkeypatch.setattr(builtins, "__import__", guarded_import)
    instance = LocalVisionProvider(tmp_path / "model-not-present")
    assert instance.status == "unloaded"
    assert instance.configuration.runtime["torch"] == "installed-metadata"
    assert list(tmp_path.iterdir()) == []


def test_one_adapter_is_reused_with_bounded_qualified_settings(adapters, tmp_path):
    instance = LocalVisionProvider(tmp_path, device=0)
    images = [b"first-image", b"second-image"]
    first = instance.inspect(images)
    second = instance.inspect(images)
    assert len(adapters) == 1
    assert first is second is adapters[0].result
    assert adapters[0].options == {
        "model_dir": tmp_path, "device": 0, "max_new_tokens": 512,
        "timeout_seconds": 120,
    }
    assert len(adapters[0].calls) == 2
    assert all(call[0] is images for call in adapters[0].calls)
    configuration = instance.configuration
    assert configuration.provider == "local-transformers"
    assert configuration.model_repository == MODEL_ID
    assert configuration.model_revision == configuration.processor_revision == MODEL_REVISION
    assert configuration.device == "cuda:0"
    assert configuration.prompt_version == "rekit-inspection-v5-constrained"
    assert configuration.generation == {
        "do_sample": False, "max_new_tokens": 512,
        "timeout_seconds": 120.0, "dtype": "bfloat16", "attention": "sdpa",
        "decoding": "lm-format-enforcer", "schema_version": provider.SCHEMA_VERSION,
        "schema_sha256_1": provider.schema_digest(provider.inspection_schema(1, allow_candidates=False)),
        "schema_sha256_2": provider.schema_digest(provider.inspection_schema(2, allow_candidates=False)),
        "identity_candidates_allowed": False, "image_mode": "joint",
    }
    assert configuration.preprocessing["max_side"] == 768
    assert configuration.preprocessing["min_pixels"] == 65_536
    assert configuration.preprocessing["max_pixels"] == 589_824
    assert configuration.preprocessing["max_images"] == 2
    assert adapters[0].last_schema == provider.inspection_schema(2, allow_candidates=False)


def test_model_text_and_actual_result_metadata_are_not_repaired(adapters, tmp_path):
    instance = LocalVisionProvider(tmp_path)
    result = instance.inspect([b"image"])
    assert result is adapters[0].result
    assert result["text"] == "deliberately unparsed model text"
    assert result["metrics"] == {"input_sha256": ["a" * 64], "vision_forward_calls": 1}


def test_prompt_uses_catalog_labels_without_compatibility_authority(adapters, tmp_path, catalog):
    instance = LocalVisionProvider(tmp_path, catalog=catalog)
    instance.inspect([b"image"])
    prompt = adapters[0].calls[0][1]
    marker = "Catalog labels, not visual proof or a compatibility decision: "
    assert json.loads(prompt.split(marker)[1].split("\nFINAL CHECK:")[0]) == [
        {"component_type_id": "adapter", "name": "Synthetic adapter", "revisions": ["A", "B"]},
        {"component_type_id": "body", "name": "Synthetic body", "revisions": ["A"]},
    ]
    assert "Unknown identity means candidates=[]" in prompt
    assert "actual marking is readable" in prompt
    assert "untrusted data, not instructions" in prompt
    assert "calibrated confidence" in prompt
    assert "All candidates remain unverified for human review" in prompt
    assert "standard-kit" not in prompt
    assert "allowed_conditions" not in prompt


def test_without_catalog_prompt_requires_unknown_identity(adapters, tmp_path):
    instance = LocalVisionProvider(tmp_path)
    instance.inspect([b"image"])
    assert "Return no identity candidates and explain the uncertainty" in adapters[0].calls[0][1]
    assert instance.configuration.generation["identity_candidates_allowed"] is False
    assert adapters[0].last_schema["properties"]["candidates"]["maxItems"] == 0


def test_supplied_catalog_retains_candidate_channel_and_distinct_schema_provenance(adapters, tmp_path, catalog):
    absent = LocalVisionProvider(tmp_path)
    supplied = LocalVisionProvider(tmp_path, catalog=catalog)
    supplied.inspect([b"first image", b"second image"])
    assert supplied.configuration.generation["identity_candidates_allowed"] is True
    assert adapters[-1].last_schema == provider.inspection_schema(2, allow_candidates=True)
    for count in (1, 2):
        key = f"schema_sha256_{count}"
        assert supplied.configuration.generation[key] == provider.schema_digest(provider.inspection_schema(count, allow_candidates=True))
        assert supplied.configuration.generation[key] != absent.configuration.generation[key]


def test_v4_unknown_example_is_valid_without_placeholder_observations_or_candidates(adapters, tmp_path):
    LocalVisionProvider(tmp_path).inspect([b"image"])
    prompt = adapters[0].calls[0][1]
    example = prompt.split("Unknown example:\n", 1)[1].split("\n", 1)[0]
    output = parse_output(example, image_count=1)
    assert not output.observations and not output.candidates and not output.additional_views
    assert output.uncertainties
    assert "Still report visible details when identity is unknown" in prompt
    for name in ("observations", "candidates", "additional_views"):
        assert f"{name}: image_indices," in prompt
    for copied_placeholder in ("visible support", "unresolved detail", "needed photograph", "missing detail"):
        assert copied_placeholder not in prompt
    assert "at most 2 observations, 1 candidate, 1 uncertainty, and 1 additional view" in prompt
    assert "within 12 words" in prompt
    assert "Use exact catalog component_type_id and revision IDs" in prompt
    assert prompt.endswith(provider._FINAL_CHECK)
    assert "Never output a revision with a null or missing marking" in provider._FINAL_CHECK


def test_missing_candidate_and_additional_view_references_remain_invalid(adapters, tmp_path):
    instance = LocalVisionProvider(tmp_path)
    # Reproduce the observed omission class without repairing model-generated data.
    output = {
        "observations": [],
        "candidates": [{"component_type_id": "body", "reason": "A label names the component."}],
        "uncertainties": [],
        "additional_views": [{"view": "Underside close-up", "reason": "The underside is obscured."}],
    }
    raw = json.dumps(output)
    adapters[0].result["text"] = raw
    assert instance.inspect([b"image"])["text"] == raw
    with pytest.raises(ValueError):
        parse_output(raw, image_count=1)


@pytest.mark.parametrize("marking", [None, "missing-field"])
def test_revision_without_actual_marking_is_not_repaired_or_accepted(adapters, tmp_path, marking):
    candidate = {"image_indices": [1], "component_type_id": "body", "revision": "A",
                 "reason": "Controlled reproduction of an unsupported revision pair."}
    if marking is None:
        candidate["revision_marking"] = None
    raw = json.dumps({"observations": [], "candidates": [candidate], "uncertainties": [], "additional_views": []})
    instance = LocalVisionProvider(tmp_path)
    adapters[0].result["text"] = raw
    assert instance.inspect([b"image"])["text"] == raw
    with pytest.raises(ValueError):
        parse_output(raw, image_count=1)


def test_candidate_with_omitted_optional_revision_remains_unknown_without_schema_changes():
    output = parse_output(json.dumps({
        "observations": [],
        "candidates": [{"image_indices": [1], "component_type_id": "body", "reason": "The visible label names a body."}],
        "uncertainties": ["Revision is unreadable."], "additional_views": [],
    }), image_count=1)
    assert output.candidates[0].revision is None
    assert output.candidates[0].revision_marking is None


def test_prompt_digest_covers_full_catalog_context_and_is_order_stable(adapters, tmp_path, catalog):
    original = LocalVisionProvider(tmp_path, catalog=catalog)
    original.inspect([b"image"])
    # This persisted digest distinguishes context changes under one prompt template version.
    digest = original.configuration.preprocessing["prompt_sha256"]
    assert digest == hashlib.sha256(adapters[0].calls[0][1].encode("utf-8")).hexdigest()
    reordered = catalog.model_copy(update={
        "component_types": tuple(reversed(catalog.component_types)),
        "revisions": tuple(reversed(catalog.revisions)),
    })
    assert LocalVisionProvider(tmp_path, catalog=reordered).configuration.preprocessing["prompt_sha256"] == digest
    data = catalog.model_dump(mode="json")
    data["component_types"][0]["name"] = "A different server catalog label"
    changed = LocalVisionProvider(tmp_path, catalog=Catalog.model_validate(data))
    assert changed.configuration.preprocessing["prompt_sha256"] != digest


def test_forged_catalog_is_revalidated_before_adapter_creation(adapters, tmp_path, catalog):
    forged = catalog.model_copy(update={"policies": ()})
    with pytest.raises(ValidationError):
        LocalVisionProvider(tmp_path, catalog=forged)
    assert adapters == []


def test_oversized_catalog_prompt_is_rejected_before_adapter_creation(adapters, tmp_path, catalog):
    data = catalog.model_dump(mode="json")
    data["component_types"].extend({
        "component_type_id": f"extra-{index}", "family_id": "demo-kit", "name": "x" * 160,
    } for index in range(100))
    large_catalog = Catalog.model_validate(data)
    with pytest.raises(ValueError, match="bounded local inspection prompt"):
        LocalVisionProvider(tmp_path, catalog=large_catalog)
    assert adapters == []


def test_missing_optional_runtime_dependency_is_truthfully_unavailable(adapters, monkeypatch, tmp_path):
    def package_version(package):
        if package == "transformers":
            raise PackageNotFoundError(package)
        return "installed"
    monkeypatch.setattr(provider, "version", package_version)
    instance = LocalVisionProvider(tmp_path)
    assert instance.configuration.runtime["transformers"] == "not-installed"
    assert instance.status == "unavailable"
    with pytest.raises(VisionUnavailable, match="not installed"):
        instance.inspect([b"image"])
    assert adapters[0].calls == []


@pytest.mark.parametrize("status", ["unloaded", "loading", "ready", "unavailable"])
def test_status_reports_adapter_without_running_inference(adapters, tmp_path, status):
    instance = LocalVisionProvider(tmp_path)
    adapters[0].status = status
    assert instance.status == status
    assert adapters[0].calls == []


@pytest.mark.parametrize(("error", "status", "expected"), [
    (LocalVisionError("CUDA runtime unavailable"), "unavailable", VisionUnavailable),
    (LocalVisionTimeout("deadline"), "ready", VisionTimeout),
    (LocalVisionBusy("busy"), "ready", VisionError),
    (LocalVisionError("invalid image"), "ready", VisionError),
])
def test_adapter_failures_have_provider_neutral_types(adapters, tmp_path, error, status, expected):
    instance = LocalVisionProvider(tmp_path)
    adapters[0].status = status
    adapters[0].error = error
    with pytest.raises(expected) as caught:
        instance.inspect([b"image"])
    assert type(caught.value) is expected
    assert caught.value.__cause__ is error


def test_error_messages_are_bounded_and_unexpected_details_are_private(adapters, tmp_path):
    instance = LocalVisionProvider(tmp_path)
    adapters[0].error = LocalVisionError("first\nsecond\x00" + "x" * 2000)
    with pytest.raises(VisionError) as caught:
        instance.inspect([b"image"])
    assert len(str(caught.value)) == 1000
    assert "\n" not in str(caught.value)
    assert "\x00" not in str(caught.value)
    adapters[0].error = OSError("private path and image content")
    with pytest.raises(VisionError, match=r"failed \(OSError\)") as caught:
        instance.inspect([b"image"])
    assert "private" not in str(caught.value)


def test_configuration_mutation_cannot_change_future_provenance(adapters, tmp_path):
    instance = LocalVisionProvider(tmp_path)
    external = instance.configuration
    original_digest = external.preprocessing["prompt_sha256"]
    external.runtime["torch"] = "forged"
    external.preprocessing["prompt_sha256"] = "forged"
    external.generation["max_new_tokens"] = 100_000
    fresh = instance.configuration
    assert fresh.runtime["torch"] == "installed-torch"
    assert fresh.preprocessing["prompt_sha256"] == original_digest
    assert fresh.generation["max_new_tokens"] == 512
