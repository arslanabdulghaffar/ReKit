"""Unverified model JSON has bounded content, explicit provenance, and no authority."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
import json

from pydantic import ValidationError
import pytest

from rekit.inference.models import (
    AdditionalView, IdentityCandidate, InferenceConfiguration, InferenceOutcome,
    InferenceRun, InferenceStart, InputAsset, InspectionOutput, InspectionRequest,
)
from rekit.inference.parsing import parse_output


NOW = datetime(2026, 10, 13, tzinfo=UTC)
ASSET = "asset-" + "a" * 32
SECOND_ASSET = "asset-" + "b" * 32


def configuration() -> dict:
    return {
        "provider": "local-transformers", "model_repository": "Qwen/Qwen3-VL-2B-Instruct",
        "model_revision": "a" * 40, "processor_revision": "a" * 40,
        "runtime": {"torch": "2.9.0+cu128", "transformers": "4.57.6"},
        "device": "cuda:1", "prompt_version": "inspection-v1",
        "preprocessing": {"max_side": 768, "exif_transpose": True},
        "generation": {"do_sample": False, "temperature": None, "max_new_tokens": 256},
    }


def output() -> dict:
    return {
        "observations": [{"kind": "marking", "text": "Visible text: REV A.", "image_indices": [1]}],
        "candidates": [{"component_type_id": "adapter", "revision": "A", "revision_marking": "REV A",
                        "reason": "The visible label names the proposed revision.", "image_indices": [1]}],
        "uncertainties": [],
        "additional_views": [{"view": "Underside", "reason": "The connector is not visible.", "image_indices": [1]}],
    }


def start() -> InferenceStart:
    return InferenceStart(
        run_id="run-1", request_id="request-1", actor_id="operator-1", physical_component_id="physical-1",
        source_return_id="return-1", inputs=(InputAsset(asset_id=ASSET, sha256="c" * 64, observation_id="observation-1"),),
        evidence_version=3, configuration=InferenceConfiguration.model_validate(configuration()), started_at=NOW,
    )


def outcome(**changes) -> InferenceOutcome:
    values = {
        "run_id": "run-1", "status": "succeeded", "completed_at": NOW + timedelta(seconds=1),
        "output": InspectionOutput.model_validate(output()), "evidence_version_after": 3,
    }
    values.update(changes)
    return InferenceOutcome.model_validate(values)


@pytest.mark.parametrize("fenced", [False, True])
def test_valid_output_preserves_actual_observations_candidates_and_sources(fenced):
    raw = json.dumps(output())
    if fenced:
        raw = f"```json\n{raw}\n```"
    parsed = parse_output(raw, 1)
    assert parsed.observations[0].text == "Visible text: REV A."
    assert parsed.candidates[0].revision_marking == "REV A"
    assert parsed.candidates[0].image_indices == (1,)
    assert parsed.additional_views[0].reason == "The connector is not visible."
    assert parsed.model_dump(mode="json") == output()
    with pytest.raises(ValidationError, match="frozen"):
        parsed.candidates = ()


def test_unknown_and_conflicting_identities_require_explicit_uncertainty():
    unknown = parse_output('{"uncertainties":["No readable identifying marking."]}', 1)
    assert unknown.candidates == ()
    with pytest.raises(ValidationError, match="uncertainty"):
        parse_output("{}", 1)
    data = output()
    data["candidates"].append({"component_type_id": "body", "reason": "Shape is ambiguous.", "image_indices": [1]})
    with pytest.raises(ValidationError, match="uncertainty"):
        parse_output(json.dumps(data), 1)
    data["uncertainties"] = ["Two different identities remain possible."]
    assert len(parse_output(json.dumps(data), 1).candidates) == 2


def test_out_of_catalog_label_stays_a_hypothesis_without_inventing_a_revision():
    data = {"candidates": [{"component_type_id": "not-in-catalog", "reason": "Unverified visual hypothesis.", "image_indices": [1]}]}
    candidate = parse_output(json.dumps(data), 1).candidates[0]
    assert candidate.component_type_id == "not-in-catalog"
    assert candidate.revision is candidate.revision_marking is None


@pytest.mark.parametrize("raw", [
    "", "   ", "[]", "null", "true", "123", '"text"',
    '{"uncertainties":["unknown"]} {"uncertainties":["other"]}',
    'Here is the answer: {"uncertainties":["unknown"]}',
    '```json\n{"uncertainties":["unknown"]}\n```\nExplanation follows.',
    '```\n{"uncertainties":["unknown"]}\n```',
    '{"uncertainties":["unknown"],}',
    '{"uncertainties":["unknown"],"uncertainties":["overridden"]}',
    '{"observations":[{"kind":"marking","text":"first","text":"second","image_indices":[1]}],"uncertainties":["unknown"]}',
    '{"uncertainties":[NaN]}', '{"uncertainties":[Infinity]}',
])
def test_parser_rejects_malformed_prose_duplicate_keys_and_non_json_values(raw):
    with pytest.raises(ValueError):
        parse_output(raw, 1)


@pytest.mark.parametrize("field", ["confidence", "compatible", "functional", "electrically_safe", "approved", "operator_id"])
def test_model_cannot_supply_authority_or_confidence_fields(field):
    data = output()
    data[field] = True
    with pytest.raises(ValidationError, match="Extra inputs"):
        parse_output(json.dumps(data), 1)
    data = output()
    data["candidates"][0][field] = True
    with pytest.raises(ValidationError, match="Extra inputs"):
        parse_output(json.dumps(data), 1)


@pytest.mark.parametrize("indices", [[], [0], [3], [1, 1], [1, 2, 1], [True], ["1"], [1.0]])
def test_source_indices_are_strict_unique_and_bounded(indices):
    data = output()
    data["observations"][0]["image_indices"] = indices
    with pytest.raises(ValidationError):
        parse_output(json.dumps(data), 2)


@pytest.mark.parametrize("section", ["observations", "candidates", "additional_views"])
def test_every_output_kind_must_reference_an_actual_supplied_image(section):
    data = output()
    data[section][0]["image_indices"] = [2]
    with pytest.raises(ValueError, match="not supplied"):
        parse_output(json.dumps(data), 1)
    assert parse_output(json.dumps(data), 2)


@pytest.mark.parametrize("image_count", [0, 3, True, 1.0, "1"])
def test_parser_does_not_coerce_actual_input_count(image_count):
    with pytest.raises(ValueError):
        parse_output(json.dumps(output()), image_count)


def test_revision_requires_visible_marking_and_candidates_cannot_repeat():
    data = output()
    del data["candidates"][0]["revision_marking"]
    with pytest.raises(ValidationError, match="visible revision marking"):
        parse_output(json.dumps(data), 1)
    data = output()
    data["candidates"][0]["revision"] = None
    with pytest.raises(ValidationError, match="explicit proposed revision"):
        parse_output(json.dumps(data), 1)
    data = output()
    data["candidates"].append(deepcopy(data["candidates"][0]))
    data["uncertainties"] = ["A duplicate is not an alternative identity."]
    with pytest.raises(ValidationError, match="distinct"):
        parse_output(json.dumps(data), 1)


@pytest.mark.parametrize("section,limit", [("observations", 6), ("candidates", 3), ("uncertainties", 5), ("additional_views", 3)])
def test_output_collection_sizes_are_bounded(section, limit):
    data = output()
    item = "Uncertainty." if section == "uncertainties" else data[section][0]
    data[section] = [deepcopy(item) for _ in range(limit + 1)]
    with pytest.raises(ValidationError):
        parse_output(json.dumps(data), 1)


@pytest.mark.parametrize("text", ["", " \n ", "x" * 601, 42])
def test_observation_text_is_nonblank_bounded_and_not_coerced(text):
    data = output()
    data["observations"][0]["text"] = text
    with pytest.raises(ValidationError):
        parse_output(json.dumps(data), 1)


def test_raw_output_length_and_other_text_bounds():
    raw = '{"uncertainties":["unknown"]}'
    assert parse_output(raw + " " * (32_000 - len(raw)), 1)
    with pytest.raises(ValueError, match="32000"):
        parse_output(raw + " " * 32_000, 1)
    with pytest.raises(ValidationError):
        AdditionalView(view="x" * 201, reason="Unknown connector.", image_indices=(1,))
    with pytest.raises(ValidationError):
        IdentityCandidate(component_type_id="body", reason="x" * 601, image_indices=(1,))


def test_request_and_input_provenance_are_strict_and_distinct():
    request = InspectionRequest(request_id="request-1", physical_component_id="physical-1", asset_ids=(ASSET, SECOND_ASSET), expected_version=3)
    assert request.asset_ids == (ASSET, SECOND_ASSET)
    values = request.model_dump()
    for invalid in (True, 3.0, "3", 0):
        with pytest.raises(ValidationError):
            InspectionRequest.model_validate({**values, "expected_version": invalid})
    for invalid in ((), (ASSET, ASSET), (ASSET, SECOND_ASSET, "asset-" + "c" * 32), ("https://example.invalid/image.png",)):
        with pytest.raises(ValidationError):
            InspectionRequest.model_validate({**values, "asset_ids": invalid})
    with pytest.raises(ValidationError):
        InputAsset(asset_id=ASSET, sha256="C" * 64, observation_id="observation-1")
    with pytest.raises(ValidationError, match="unique"):
        InferenceStart.model_validate({**start().model_dump(), "inputs": (start().inputs[0], start().inputs[0])})


@pytest.mark.parametrize("field,value", [
    ("model_revision", "main"), ("processor_revision", "A" * 40),
    ("runtime", {}), ("preprocessing", {}), ("generation", {}),
    ("runtime", {"torch": 2.9}), ("runtime", {"torch": " "}),
    ("runtime", {str(index): "version" for index in range(33)}),
    ("generation", {"nested": {"value": True}}), ("generation", {"list": [1, 2]}),
    ("generation", {"number": float("nan")}), ("generation", {"number": float("inf")}),
    ("preprocessing", {"x" * 129: True}), ("preprocessing", {"value": "x" * 2001}),
    ("generation", {str(index): True for index in range(33)}),
])
def test_configuration_requires_pinned_revisions_and_bounded_scalar_metadata(field, value):
    with pytest.raises(ValidationError):
        InferenceConfiguration.model_validate({**configuration(), field: value})


@pytest.mark.parametrize("status", ["failed", "unavailable", "timed_out", "invalid_output"])
def test_non_success_outcomes_require_reason_without_validated_output_or_applied_events(status):
    assert outcome(status=status, output=None, failure_reason="Explicit execution failure.").status == status
    for changes in ({"failure_reason": None}, {"output": InspectionOutput.model_validate(output())}, {"applied_event_ids": ("event-1",)}):
        values = {"status": status, "output": None, "failure_reason": "Explicit failure."}
        values.update(changes)
        with pytest.raises(ValidationError):
            outcome(**values)


def test_success_and_staleness_are_separate_from_applicability():
    stale = outcome(stale=True, stale_reason="An input image is no longer available.")
    assert stale.status == "succeeded" and stale.output is not None and stale.applied_event_ids == ()
    assert outcome(status="failed", output=None, failure_reason="GPU unavailable.", stale=True, stale_reason="Evidence changed.")
    for changes in (
        {"output": None}, {"failure_reason": "Contradictory success."},
        {"stale": True}, {"stale_reason": "But not stale."},
        {"stale": "true", "stale_reason": "Must be a boolean."},
        {"stale": True, "stale_reason": "Changed.", "applied_event_ids": ("event-1",)},
        {"applied_event_ids": ("event-1", "event-1")},
        {"raw_output": "x" * 32_001}, {"failure_reason": "x" * 2001},
    ):
        with pytest.raises(ValidationError):
            outcome(**changes)


def test_run_linkage_chronology_and_actual_image_provenance():
    pending = InferenceRun(start=start())
    assert pending.outcome is None
    assert InferenceRun(start=start(), outcome=outcome())
    for changes in (
        {"run_id": "different-run"}, {"completed_at": NOW - timedelta(seconds=1)},
        {"evidence_version_after": 2},
    ):
        with pytest.raises(ValidationError):
            InferenceRun(start=start(), outcome=outcome(**changes))
    data = output()
    data["observations"][0]["image_indices"] = [2]
    with pytest.raises(ValidationError, match="not supplied"):
        InferenceRun(start=start(), outcome=outcome(output=InspectionOutput.model_validate(data)))
    with pytest.raises(ValidationError):
        InferenceStart.model_validate({**start().model_dump(), "started_at": NOW.replace(tzinfo=None)})
    with pytest.raises(ValidationError):
        outcome(completed_at=NOW.replace(tzinfo=None))
