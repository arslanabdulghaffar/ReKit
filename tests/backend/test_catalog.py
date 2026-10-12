"""Synthetic catalog validation and deterministic compatibility decisions."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from rekit.catalog.compatibility import check_compatibility
from rekit.catalog.models import BOMLine, Catalog, ComponentIdentity, VisibleCondition


@pytest.fixture
def catalog_data() -> dict:
    return json.loads((Path(__file__).parents[1] / "fixtures" / "synthetic_catalog.json").read_text())


@pytest.fixture
def catalog(catalog_data: dict) -> Catalog:
    return Catalog.model_validate(catalog_data)


def test_valid_synthetic_configuration_is_immutable(catalog: Catalog) -> None:
    assert catalog.synthetic is True
    assert catalog.configuration("standard-kit").bom == (
        BOMLine(component_type_id="body", quantity=1),
        BOMLine(component_type_id="adapter", quantity=1),
    )
    assert catalog.policy_for("standard-kit").approved_at.utcoffset() is not None
    assert isinstance(catalog.policies[0].rules, tuple)
    with pytest.raises(ValidationError, match="frozen"):
        catalog.version = "2"


def test_approved_identity_is_compatible(catalog: Catalog) -> None:
    identity = ComponentIdentity(component_type_id="adapter", revision="A")
    assert catalog.validate_identity(identity) is None
    decision = check_compatibility(catalog, "standard-kit", identity, VisibleCondition.ACCEPTABLE)
    assert decision.compatible is True
    assert decision.reasons == ()


@pytest.mark.parametrize("quantity", [0, -1, True, False, 1.0, 1.5, "1"])
def test_quantity_is_a_strict_positive_integer(quantity: object) -> None:
    with pytest.raises(ValidationError):
        BOMLine(component_type_id="body", quantity=quantity)


@pytest.mark.parametrize("value", ["", "   ", " body", "body ", "body\n", "x" * 129, None, 123])
def test_component_identifiers_are_bounded_nonblank_strings(value: object) -> None:
    with pytest.raises(ValidationError):
        ComponentIdentity(component_type_id=value, revision="A")


def test_missing_mandatory_bom_component_is_rejected(catalog_data: dict) -> None:
    catalog_data["configurations"][0]["bom"].pop()
    with pytest.raises(ValidationError, match="Missing mandatory BOM components: adapter"):
        Catalog.model_validate(catalog_data)


def test_unknown_bom_type_is_rejected(catalog_data: dict) -> None:
    catalog_data["configurations"][0]["bom"].append({"component_type_id": "unknown", "quantity": 1})
    with pytest.raises(ValidationError, match="Unknown component type in BOM: unknown"):
        Catalog.model_validate(catalog_data)


@pytest.mark.parametrize("collection", ["component_types", "configurations"])
def test_unsupported_product_family_is_rejected(catalog_data: dict, collection: str) -> None:
    catalog_data[collection][0]["family_id"] = "unsupported"
    with pytest.raises(ValidationError, match="Unsupported product family"):
        Catalog.model_validate(catalog_data)


@pytest.mark.parametrize("collection", ["families", "component_types", "revisions", "configurations", "policies"])
def test_duplicate_catalog_keys_are_rejected(catalog_data: dict, collection: str) -> None:
    catalog_data[collection].append(catalog_data[collection][0])
    with pytest.raises(ValidationError, match="Duplicate"):
        Catalog.model_validate(catalog_data)


def test_duplicate_mandatory_types_are_rejected(catalog_data: dict) -> None:
    catalog_data["families"][0]["required_component_types"].append("body")
    with pytest.raises(ValidationError, match="Duplicate mandatory"):
        Catalog.model_validate(catalog_data)


def test_unknown_mandatory_type_is_rejected(catalog_data: dict) -> None:
    catalog_data["families"][0]["required_component_types"].append("unknown")
    with pytest.raises(ValidationError, match="Unknown mandatory"):
        Catalog.model_validate(catalog_data)


def test_duplicate_bom_line_is_rejected(catalog_data: dict) -> None:
    catalog_data["configurations"][0]["bom"].append({"component_type_id": "body", "quantity": 1})
    with pytest.raises(ValidationError, match="Duplicate component type in BOM"):
        Catalog.model_validate(catalog_data)


def test_cross_family_bom_is_rejected(catalog_data: dict) -> None:
    catalog_data["families"].append({"family_id": "other", "name": "Other synthetic family", "required_component_types": ["foreign"]})
    catalog_data["component_types"].append({"component_type_id": "foreign", "family_id": "other", "name": "Foreign synthetic part"})
    catalog_data["configurations"][0]["bom"].append({"component_type_id": "foreign", "quantity": 1})
    with pytest.raises(ValidationError, match="BOM component foreign belongs to a different family"):
        Catalog.model_validate(catalog_data)


def test_unknown_type_revision_is_rejected(catalog_data: dict) -> None:
    catalog_data["revisions"].append({"component_type_id": "unknown", "revision": "A"})
    with pytest.raises(ValidationError, match="Unknown component type in revision"):
        Catalog.model_validate(catalog_data)


def test_unknown_approved_revision_is_rejected(catalog_data: dict) -> None:
    catalog_data["policies"][0]["rules"][0]["allowed_revisions"] = ["unknown"]
    with pytest.raises(ValidationError, match="Unknown allowed revision: body/unknown"):
        Catalog.model_validate(catalog_data)


@pytest.mark.parametrize("field,value", [("approved_by", " "), ("approved_at", "2026-10-13T00:00:00"), ("configuration_id", "unknown")])
def test_invalid_policy_approval_or_reference_is_rejected(catalog_data: dict, field: str, value: str) -> None:
    catalog_data["policies"][0][field] = value
    with pytest.raises(ValidationError):
        Catalog.model_validate(catalog_data)


def test_every_configuration_requires_an_explicit_policy(catalog_data: dict) -> None:
    duplicate = dict(catalog_data["configurations"][0], configuration_id="second-kit")
    catalog_data["configurations"].append(duplicate)
    with pytest.raises(ValidationError, match="Every configuration requires"):
        Catalog.model_validate(catalog_data)


def test_two_policies_for_one_configuration_are_rejected(catalog_data: dict) -> None:
    catalog_data["policies"].append(dict(catalog_data["policies"][0], policy_id="second-policy"))
    with pytest.raises(ValidationError, match="Duplicate configuration policy"):
        Catalog.model_validate(catalog_data)


def test_policy_must_cover_exactly_the_bom(catalog_data: dict) -> None:
    catalog_data["policies"][0]["rules"].pop()
    with pytest.raises(ValidationError, match="exactly the BOM"):
        Catalog.model_validate(catalog_data)


def test_duplicate_policy_rules_are_rejected(catalog_data: dict) -> None:
    catalog_data["policies"][0]["rules"].append(catalog_data["policies"][0]["rules"][0])
    with pytest.raises(ValidationError, match="Duplicate component type in compatibility policy"):
        Catalog.model_validate(catalog_data)


@pytest.mark.parametrize("field,values", [("allowed_revisions", ["A", "A"]), ("allowed_conditions", ["acceptable", "acceptable"]), ("allowed_conditions", ["unknown"])])
def test_policy_rejects_duplicates_and_unknown_condition(catalog_data: dict, field: str, values: list) -> None:
    catalog_data["policies"][0]["rules"][0][field] = values
    with pytest.raises(ValidationError):
        Catalog.model_validate(catalog_data)


@pytest.mark.parametrize("component_type_id,revision,condition,reason", [
    ("adapter", "B", VisibleCondition.ACCEPTABLE, "Revision adapter/B is not approved"),
    ("adapter", "Z", VisibleCondition.ACCEPTABLE, "Unknown component revision"),
    ("unknown", "A", VisibleCondition.ACCEPTABLE, "Unknown component type"),
    ("body", "A", VisibleCondition.UNKNOWN, "requires operator review"),
    ("body", "A", VisibleCondition.DAMAGED, "Visible condition damaged is not approved"),
])
def test_compatibility_rejects_unsupported_inputs_with_reasons(catalog: Catalog, component_type_id: str, revision: str, condition: VisibleCondition, reason: str) -> None:
    decision = check_compatibility(catalog, "standard-kit", ComponentIdentity(component_type_id=component_type_id, revision=revision), condition)
    assert decision.compatible is False
    assert any(reason in detail for detail in decision.reasons)


def test_identity_validation_distinguishes_known_incompatible_revision(catalog: Catalog) -> None:
    assert catalog.validate_identity(ComponentIdentity(component_type_id="adapter", revision="B")) is None
    with pytest.raises(ValueError, match="Unknown component type"):
        catalog.validate_identity(ComponentIdentity(component_type_id="unknown", revision="A"))
    with pytest.raises(ValueError, match="Unknown component revision"):
        catalog.validate_identity(ComponentIdentity(component_type_id="body", revision="Z"))


def test_unknown_lookups_fail_explicitly(catalog: Catalog) -> None:
    with pytest.raises(ValueError, match="Unknown product configuration"):
        catalog.configuration("unknown")
    with pytest.raises(ValueError, match="No approved policy"):
        catalog.policy_for("unknown")


def test_extra_fields_do_not_create_policy_authority() -> None:
    with pytest.raises(ValidationError, match="Extra inputs"):
        ComponentIdentity(component_type_id="body", revision="A", verified=True)
