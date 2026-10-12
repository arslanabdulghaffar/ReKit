"""Approved catalog contracts; physical items and model guesses live elsewhere."""

from enum import StrEnum
from typing import Annotated, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator


Identifier = Annotated[
    str, StringConstraints(strict=True, min_length=1, max_length=128, pattern=r"^\S(?:.*\S)?$")
]
Label = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=160)
]


class CatalogModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class VisibleCondition(StrEnum):
    """Visible condition only; none of these values certifies function or safety."""

    UNKNOWN = "unknown"
    ACCEPTABLE = "acceptable"
    DAMAGED = "damaged"


class ComponentIdentity(CatalogModel):
    component_type_id: Identifier
    revision: Identifier


class ProductFamily(CatalogModel):
    family_id: Identifier
    name: Label
    required_component_types: tuple[Identifier, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_required_types(self) -> Self:
        if len(set(self.required_component_types)) != len(self.required_component_types):
            raise ValueError("Duplicate mandatory component type in product family")
        return self


class ComponentType(CatalogModel):
    component_type_id: Identifier
    family_id: Identifier
    name: Label


class ComponentRevision(ComponentIdentity):
    pass


class BOMLine(CatalogModel):
    component_type_id: Identifier
    quantity: Annotated[int, Field(strict=True, gt=0)]


class ProductConfiguration(CatalogModel):
    configuration_id: Identifier
    family_id: Identifier
    version: Identifier
    bom: tuple[BOMLine, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_bom_types(self) -> Self:
        type_ids = [line.component_type_id for line in self.bom]
        if len(set(type_ids)) != len(type_ids):
            raise ValueError("Duplicate component type in BOM; use quantity instead")
        return self


class CompatibilityRule(CatalogModel):
    component_type_id: Identifier
    allowed_revisions: tuple[Identifier, ...] = Field(min_length=1)
    allowed_conditions: tuple[VisibleCondition, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def explicit_unique_approvals(self) -> Self:
        if len(set(self.allowed_revisions)) != len(self.allowed_revisions):
            raise ValueError("Duplicate allowed revision in compatibility rule")
        if len(set(self.allowed_conditions)) != len(self.allowed_conditions):
            raise ValueError("Duplicate allowed condition in compatibility rule")
        if VisibleCondition.UNKNOWN in self.allowed_conditions:
            raise ValueError("Unknown visible condition cannot be approved by policy")
        return self


class CompatibilityPolicy(CatalogModel):
    policy_id: Identifier
    version: Identifier
    configuration_id: Identifier
    approved_by: Identifier
    approved_at: AwareDatetime
    rules: tuple[CompatibilityRule, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_rule_types(self) -> Self:
        type_ids = [rule.component_type_id for rule in self.rules]
        if len(set(type_ids)) != len(type_ids):
            raise ValueError("Duplicate component type in compatibility policy")
        return self


class Catalog(CatalogModel):
    catalog_id: Identifier
    version: Identifier
    synthetic: Annotated[bool, Field(strict=True)]
    description: Annotated[str, StringConstraints(strict=True, max_length=1000)] = ""
    families: tuple[ProductFamily, ...] = Field(min_length=1)
    component_types: tuple[ComponentType, ...] = Field(min_length=1)
    revisions: tuple[ComponentRevision, ...] = Field(min_length=1)
    configurations: tuple[ProductConfiguration, ...] = Field(min_length=1)
    policies: tuple[CompatibilityPolicy, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_catalog(self) -> Self:
        """Reject incomplete policy, cross-family references, and ambiguous keys."""
        for label, identifiers in (
            ("product family", [family.family_id for family in self.families]),
            ("component type", [item.component_type_id for item in self.component_types]),
            ("component revision", [(item.component_type_id, item.revision) for item in self.revisions]),
            ("product configuration", [item.configuration_id for item in self.configurations]),
            ("compatibility policy", [item.policy_id for item in self.policies]),
            ("configuration policy", [item.configuration_id for item in self.policies]),
        ):
            if len(set(identifiers)) != len(identifiers):
                raise ValueError(f"Duplicate {label}")

        families = {item.family_id: item for item in self.families}
        types = {item.component_type_id: item for item in self.component_types}
        revisions = {(item.component_type_id, item.revision) for item in self.revisions}
        configurations = {item.configuration_id: item for item in self.configurations}
        for item in self.component_types:
            if item.family_id not in families:
                raise ValueError(f"Unsupported product family: {item.family_id}")
        for family in self.families:
            for type_id in family.required_component_types:
                if type_id not in types:
                    raise ValueError(f"Unknown mandatory component type: {type_id}")
                if types[type_id].family_id != family.family_id:
                    raise ValueError(f"Mandatory component {type_id} belongs to a different family")
        for revision in self.revisions:
            if revision.component_type_id not in types:
                raise ValueError(f"Unknown component type in revision: {revision.component_type_id}")
        for configuration in self.configurations:
            if configuration.family_id not in families:
                raise ValueError(f"Unsupported product family: {configuration.family_id}")
            bom_types = {line.component_type_id for line in configuration.bom}
            missing = set(families[configuration.family_id].required_component_types) - bom_types
            if missing:
                raise ValueError(f"Missing mandatory BOM components: {', '.join(sorted(missing))}")
            for type_id in bom_types:
                if type_id not in types:
                    raise ValueError(f"Unknown component type in BOM: {type_id}")
                if types[type_id].family_id != configuration.family_id:
                    raise ValueError(f"BOM component {type_id} belongs to a different family")
        for policy in self.policies:
            if policy.configuration_id not in configurations:
                raise ValueError(f"Unknown policy configuration: {policy.configuration_id}")
            bom_types = {line.component_type_id for line in configurations[policy.configuration_id].bom}
            if {rule.component_type_id for rule in policy.rules} != bom_types:
                raise ValueError("Compatibility policy must cover exactly the BOM component types")
            for rule in policy.rules:
                for revision in rule.allowed_revisions:
                    if (rule.component_type_id, revision) not in revisions:
                        raise ValueError(f"Unknown allowed revision: {rule.component_type_id}/{revision}")
        if {item.configuration_id for item in self.policies} != set(configurations):
            raise ValueError("Every configuration requires one explicit approved compatibility policy")
        return self

    def configuration(self, configuration_id: str) -> ProductConfiguration:
        for configuration in self.configurations:
            if configuration.configuration_id == configuration_id:
                return configuration
        raise ValueError(f"Unknown product configuration: {configuration_id}")

    def policy_for(self, configuration_id: str) -> CompatibilityPolicy:
        for policy in self.policies:
            if policy.configuration_id == configuration_id:
                return policy
        raise ValueError(f"No approved policy for configuration: {configuration_id}")

    def validate_identity(self, identity: ComponentIdentity) -> None:
        if identity.component_type_id not in {item.component_type_id for item in self.component_types}:
            raise ValueError(f"Unknown component type: {identity.component_type_id}")
        if (identity.component_type_id, identity.revision) not in {
            (item.component_type_id, item.revision) for item in self.revisions
        }:
            raise ValueError(f"Unknown component revision: {identity.component_type_id}/{identity.revision}")
