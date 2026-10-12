"""Integer-valued scenario estimates and explicit recovery planning contracts."""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, Field, StringConstraints, model_validator

from rekit.catalog.models import Catalog, CatalogModel, Identifier, VisibleCondition
from rekit.evidence.models import Text
from rekit.inventory.models import InventoryItem, validate_inventory

NonnegativeInt = Annotated[int, Field(strict=True, ge=0, le=10**9)]
SignedValue = Annotated[int, Field(strict=True, ge=-(2**50), le=2**50)]
NonnegativeValue = Annotated[int, Field(strict=True, ge=0, le=2**50)]


class KitEconomics(CatalogModel):
    configuration_id: Identifier
    selling_price_cents: NonnegativeInt
    labor_minutes: NonnegativeInt
    other_cost_cents: NonnegativeInt = 0
    demand_limit: NonnegativeInt | None = None


class ComponentEconomics(CatalogModel):
    physical_component_id: Identifier
    donor_value_cents: NonnegativeInt
    salvage_value_cents: NonnegativeInt = 0
    salvage_labor_minutes: NonnegativeInt = 0


class ReturnEconomics(CatalogModel):
    return_id: Identifier
    liquidation_value_cents: NonnegativeInt
    liquidation_labor_minutes: NonnegativeInt = 0


class EconomicScenario(CatalogModel):
    scenario_id: Identifier
    description: Text
    currency: Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Z]{3}$")]
    valuation_date: date
    labor_cost_per_minute_cents: NonnegativeInt
    labor_capacity_minutes: NonnegativeInt | None = None
    kits: tuple[KitEconomics, ...] = ()
    components: tuple[ComponentEconomics, ...] = ()
    returns: tuple[ReturnEconomics, ...] = ()
    scenario_estimate: Literal[True] = True

    @model_validator(mode="after")
    def unique_estimates(self) -> Self:
        for entries, field in (
            (self.kits, "configuration_id"),
            (self.components, "physical_component_id"),
            (self.returns, "return_id"),
        ):
            keys = [getattr(entry, field) for entry in entries]
            if len(keys) != len(set(keys)):
                raise ValueError(f"Duplicate economic estimate: {field}")
        return self


class ReturnContents(CatalogModel):
    """Full registered membership, including any items absent from the planning pool."""

    return_id: Identifier
    component_ids: tuple[Identifier, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_components(self) -> Self:
        if len(set(self.component_ids)) != len(self.component_ids):
            raise ValueError("Duplicate physical identifier in return contents")
        return self


class DispositionPolicy(CatalogModel):
    policy_id: Identifier
    version: Identifier
    approved_by: Identifier
    approved_at: AwareDatetime
    liquidation_allowed_return_ids: tuple[Identifier, ...] = ()
    liquidation_allowed_conditions: tuple[VisibleCondition, ...] = ()
    salvage_allowed_component_types: tuple[Identifier, ...] = ()
    salvage_allowed_conditions: tuple[VisibleCondition, ...] = ()

    @model_validator(mode="after")
    def explicit_approved_dispositions(self) -> Self:
        for entries in (
            self.liquidation_allowed_return_ids, self.liquidation_allowed_conditions,
            self.salvage_allowed_component_types, self.salvage_allowed_conditions,
        ):
            if len(entries) != len(set(entries)):
                raise ValueError("Duplicate disposition policy entry")
        if VisibleCondition.UNKNOWN in (*self.liquidation_allowed_conditions, *self.salvage_allowed_conditions):
            raise ValueError("Unknown condition cannot authorize liquidation or salvage")
        return self


class RecoveryProblem(CatalogModel):
    catalog: Catalog
    inventory: tuple[InventoryItem, ...] = Field(max_length=100)
    return_contents: tuple[ReturnContents, ...]
    scenario: EconomicScenario
    policy: DispositionPolicy

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        validate_inventory(self.catalog, self.inventory)
        item_ids = {item.component.physical_component_id for item in self.inventory}
        if {estimate.physical_component_id for estimate in self.scenario.components} != item_ids:
            raise ValueError("Explicit component economics must cover exactly the planning inventory")
        return_ids = [contents.return_id for contents in self.return_contents]
        if len(set(return_ids)) != len(return_ids):
            raise ValueError("Duplicate return in full return contents")
        membership = {}
        for contents in self.return_contents:
            for component_id in contents.component_ids:
                if component_id in membership:
                    raise ValueError("Physical component appears in more than one return")
                membership[component_id] = contents.return_id
        for item in self.inventory:
            if membership.get(item.component.physical_component_id) != item.component.source_return_id:
                raise ValueError("Planning inventory must match full registered return membership")
        for estimate in self.scenario.kits:
            self.catalog.configuration(estimate.configuration_id)
        known_returns = set(return_ids)
        if not {estimate.return_id for estimate in self.scenario.returns} <= known_returns:
            raise ValueError("Economic estimate names an unknown return")
        if not set(self.policy.liquidation_allowed_return_ids) <= known_returns:
            raise ValueError("Disposition policy names an unknown return")
        known_types = {item.component_type_id for item in self.catalog.component_types}
        if not set(self.policy.salvage_allowed_component_types) <= known_types:
            raise ValueError("Disposition policy names an unknown component type")
        return self


class RecoveryActionKind(StrEnum):
    REBUILD = "rebuild"
    LIQUIDATE = "liquidate"
    RETAIN = "retain"
    SALVAGE = "salvage"
    HOLD = "hold"


class RecoveryAction(CatalogModel):
    action_id: Identifier
    kind: RecoveryActionKind
    component_ids: tuple[Identifier, ...] = Field(min_length=1)
    configuration_id: Identifier | None = None
    source_return_id: Identifier | None = None
    labor_minutes: NonnegativeValue
    cash_recovery_cents: SignedValue
    retained_value_cents: NonnegativeValue
    modeled_value_cents: SignedValue
    donor_opportunity_cost_cents: NonnegativeValue
    incremental_vs_retain_cents: SignedValue
    explanation: tuple[Text, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def consistent_arithmetic(self) -> Self:
        if len(set(self.component_ids)) != len(self.component_ids):
            raise ValueError("A recovery action cannot use a physical component twice")
        if self.modeled_value_cents != self.cash_recovery_cents + self.retained_value_cents:
            raise ValueError("Action modeled value must equal cash estimate plus retained asset estimate")
        if self.incremental_vs_retain_cents != self.modeled_value_cents - self.donor_opportunity_cost_cents:
            raise ValueError("Incorrect incremental value relative to retained donors")
        if self.kind == RecoveryActionKind.HOLD and (
            self.modeled_value_cents or self.cash_recovery_cents or self.retained_value_cents or self.labor_minutes
        ):
            raise ValueError("A hold has zero modeled value, cash, retained value, and labor")
        if self.kind == RecoveryActionKind.RETAIN and self.cash_recovery_cents:
            raise ValueError("Retained donor inventory is not cash recovery")
        if self.kind in (RecoveryActionKind.HOLD, RecoveryActionKind.RETAIN, RecoveryActionKind.SALVAGE):
            if len(self.component_ids) != 1:
                raise ValueError("Hold, retain, and salvage each describe one physical component")
        if self.kind == RecoveryActionKind.RETAIN and (
            self.labor_minutes or self.incremental_vs_retain_cents
            or self.retained_value_cents != self.donor_opportunity_cost_cents
        ):
            raise ValueError("Retention carries donor asset value, zero labor, and no incremental recovery")
        if self.kind in (RecoveryActionKind.REBUILD, RecoveryActionKind.LIQUIDATE, RecoveryActionKind.SALVAGE):
            if self.retained_value_cents:
                raise ValueError("Consumed components cannot also contribute retained donor asset value")
        if (self.configuration_id is not None) != (self.kind == RecoveryActionKind.REBUILD):
            raise ValueError("Only a rebuild names a product configuration")
        if (self.source_return_id is not None) != (self.kind == RecoveryActionKind.LIQUIDATE):
            raise ValueError("Only whole-return liquidation names a source return")
        return self


class AlternativeRejection(CatalogModel):
    subject: Text
    reasons: tuple[Text, ...] = Field(min_length=1)


class CandidateSet(CatalogModel):
    actions: tuple[RecoveryAction, ...]
    rejections: tuple[AlternativeRejection, ...] = ()


class SolverSettings(CatalogModel):
    max_time_seconds: Annotated[float, Field(strict=True, ge=0, le=60, allow_inf_nan=False)] = 10.0
    random_seed: Annotated[int, Field(strict=True, ge=0, le=2**31 - 1)] = 0


class SolveStatus(StrEnum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    MODEL_INVALID = "MODEL_INVALID"
    UNKNOWN = "UNKNOWN"


class RecoveryPlan(CatalogModel):
    plan_id: Identifier
    input_hash: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    problem: RecoveryProblem
    status: SolveStatus
    selected_actions: tuple[RecoveryAction, ...] = ()
    modeled_value_cents: SignedValue | None = None
    cash_recovery_cents: SignedValue | None = None
    retained_value_cents: NonnegativeValue | None = None
    labor_minutes: NonnegativeValue | None = None
    best_bound_cents: SignedValue | None = None
    absolute_gap_cents: NonnegativeValue | None = None
    solver_version: Identifier
    random_seed: Annotated[int, Field(strict=True, ge=0)]
    worker_count: Literal[1] = 1
    time_limit_seconds: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    wall_time_seconds: Annotated[float, Field(ge=0, allow_inf_nan=False)]
    number_of_candidates: NonnegativeInt
    explanations: tuple[Text, ...] = Field(min_length=1)
    rejections: tuple[AlternativeRejection, ...] = ()
    scenario_estimate: Literal[True] = True

    @model_validator(mode="after")
    def solution_totals(self) -> Self:
        totals = (self.modeled_value_cents, self.cash_recovery_cents, self.retained_value_cents, self.labor_minutes)
        if self.status not in (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE):
            if self.selected_actions or any(total is not None for total in totals):
                raise ValueError("A solver without a solution cannot report actions or recovery value")
        else:
            if any(total is None for total in totals):
                raise ValueError("A feasible plan must report all scenario totals")
            for field in ("modeled_value_cents", "cash_recovery_cents", "retained_value_cents", "labor_minutes"):
                if getattr(self, field) != sum(getattr(action, field) for action in self.selected_actions):
                    raise ValueError(f"Plan total does not match selected actions: {field}")
            allocated = [component_id for action in self.selected_actions for component_id in action.component_ids]
            required = {item.component.physical_component_id for item in self.problem.inventory}
            if len(allocated) != len(set(allocated)) or set(allocated) != required:
                raise ValueError("A feasible plan must assign each supplied physical component exactly once")
            capacity = self.problem.scenario.labor_capacity_minutes
            if capacity is not None and self.labor_minutes > capacity:
                raise ValueError("Selected actions exceed scenario labor capacity")
            for estimate in self.problem.scenario.kits:
                count = sum(action.configuration_id == estimate.configuration_id for action in self.selected_actions)
                if estimate.demand_limit is not None and count > estimate.demand_limit:
                    raise ValueError("Selected rebuilds exceed scenario demand")
        return self
