"""Deterministic compatibility checks against an explicit approved catalog."""

from rekit.catalog.models import Catalog, CatalogModel, ComponentIdentity, VisibleCondition


class CompatibilityDecision(CatalogModel):
    compatible: bool
    reasons: tuple[str, ...]


def check_compatibility(
    catalog: Catalog,
    configuration_id: str,
    identity: ComponentIdentity,
    condition: VisibleCondition,
) -> CompatibilityDecision:
    """Check an identity and visible condition, without approving a physical item."""
    configuration = catalog.configuration(configuration_id)
    policy = catalog.policy_for(configuration_id)
    try:
        catalog.validate_identity(identity)
    except ValueError as error:
        return CompatibilityDecision(compatible=False, reasons=(str(error),))

    if identity.component_type_id not in {line.component_type_id for line in configuration.bom}:
        return CompatibilityDecision(
            compatible=False,
            reasons=(f"Component type {identity.component_type_id} is not required by {configuration_id}",),
        )
    rule = next(rule for rule in policy.rules if rule.component_type_id == identity.component_type_id)
    reasons = []
    if identity.revision not in rule.allowed_revisions:
        reasons.append(
            f"Revision {identity.component_type_id}/{identity.revision} is not approved by "
            f"policy {policy.policy_id} version {policy.version}; "
            f"allowed revisions: {', '.join(rule.allowed_revisions)}"
        )
    if condition == VisibleCondition.UNKNOWN:
        reasons.append("Visible condition is unknown and requires operator review")
    elif condition not in rule.allowed_conditions:
        reasons.append(
            f"Visible condition {condition} is not approved by policy {policy.policy_id} "
            f"version {policy.version}"
        )
    return CompatibilityDecision(compatible=not reasons, reasons=tuple(reasons))
