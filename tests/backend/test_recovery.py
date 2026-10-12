"""Recovery feasibility and economics checked independently of CP-SAT search."""

from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

import pytest
from ortools.sat.python import cp_model

from rekit.catalog.models import Catalog, ComponentIdentity, VisibleCondition
from rekit.evidence.models import (
    CurrentEvidence,
    OperatorVerification,
    PhysicalComponent,
    VerificationState,
)
from rekit.inventory.models import InventoryEligibility, InventoryItem
from rekit.recovery.models import (
    ComponentEconomics,
    DispositionPolicy,
    EconomicScenario,
    KitEconomics,
    RecoveryAction,
    RecoveryActionKind,
    RecoveryPlan,
    RecoveryProblem,
    ReturnContents,
    ReturnEconomics,
    SolveStatus,
    SolverSettings,
)
from rekit.recovery.planner import (
    evaluate_selection,
    explain_alternative,
    generate_candidates,
    solve_recovery,
)


NOW = datetime(2026, 10, 13, 18, tzinfo=timezone.utc)


@pytest.fixture
def catalog() -> Catalog:
    path = Path(__file__).parents[1] / "fixtures" / "synthetic_catalog.json"
    return Catalog.model_validate_json(path.read_text(encoding="utf-8"))


def inventory_item(
    physical_id: str,
    component_type: str,
    source_return: str,
    *,
    revision: str = "A",
    condition: VisibleCondition = VisibleCondition.ACCEPTABLE,
    state: VerificationState = VerificationState.VERIFIED,
) -> InventoryItem:
    verification = OperatorVerification(
        verification_id=f"verification-{physical_id}",
        physical_component_id=physical_id,
        identity=ComponentIdentity(component_type_id=component_type, revision=revision),
        operator_id="synthetic-reviewer",
        verified_at=NOW,
        evidence_observation_ids=(f"observation-{physical_id}",),
        visible_condition=condition,
        reason="Synthetic fixture asserts only visible identity and condition.",
    )
    eligible = state is VerificationState.VERIFIED and condition is not VisibleCondition.UNKNOWN
    return InventoryItem(
        component=PhysicalComponent(
            physical_component_id=physical_id,
            source_return_id=source_return,
            registered_at=NOW,
        ),
        evidence=CurrentEvidence(
            physical_component_id=physical_id,
            state=state,
            verification=verification if state is not VerificationState.UNRESOLVED else None,
            unresolved_reasons=("Revision needs further review.",)
            if state is VerificationState.REVIEW_REQUIRED else (),
        ),
        eligibility=InventoryEligibility.ELIGIBLE if eligible else InventoryEligibility.HELD,
    )


def problem_for(
    catalog: Catalog,
    items: tuple[InventoryItem, ...],
    *,
    kit_price: int = 1000,
    kit_labor: int = 10,
    labor_rate: int = 10,
    labor_capacity: int | None = None,
    demand: int | None = None,
    donor_values: dict[str, int] | None = None,
    liquidation_values: dict[str, int] | None = None,
    salvage_values: dict[str, int] | None = None,
    return_contents: tuple[ReturnContents, ...] | None = None,
) -> RecoveryProblem:
    donors = donor_values or {}
    liquidations = liquidation_values or {}
    salvage = salvage_values or {}
    if return_contents is None:
        return_ids = sorted({item.component.source_return_id for item in items})
        return_contents = tuple(
            ReturnContents(
                return_id=return_id,
                component_ids=tuple(
                    item.component.physical_component_id for item in items
                    if item.component.source_return_id == return_id
                ),
            )
            for return_id in return_ids
        )
    return RecoveryProblem(
        catalog=catalog,
        inventory=items,
        return_contents=return_contents,
        scenario=EconomicScenario(
            scenario_id="synthetic-economics",
            description="Invented scenario values for deterministic tests only.",
            currency="USD",
            valuation_date=NOW.date(),
            labor_cost_per_minute_cents=labor_rate,
            labor_capacity_minutes=labor_capacity,
            kits=(KitEconomics(
                configuration_id="standard-kit",
                selling_price_cents=kit_price,
                labor_minutes=kit_labor,
                demand_limit=demand,
            ),),
            components=tuple(
                ComponentEconomics(
                    physical_component_id=item.component.physical_component_id,
                    donor_value_cents=donors.get(item.component.physical_component_id, 0),
                    salvage_value_cents=salvage.get(item.component.physical_component_id, 0),
                )
                for item in items
            ),
            returns=tuple(
                ReturnEconomics(return_id=return_id, liquidation_value_cents=value)
                for return_id, value in liquidations.items()
            ),
        ),
        policy=DispositionPolicy(
            policy_id="synthetic-disposition-policy",
            version="1",
            approved_by="synthetic-reviewer",
            approved_at=NOW,
            liquidation_allowed_return_ids=tuple(liquidations),
            liquidation_allowed_conditions=(VisibleCondition.ACCEPTABLE, VisibleCondition.DAMAGED),
            salvage_allowed_component_types=tuple(
                item.component_type_id for item in catalog.component_types
            ) if salvage_values is not None else (),
            salvage_allowed_conditions=(VisibleCondition.ACCEPTABLE, VisibleCondition.DAMAGED),
        ),
    )


def kit_items() -> tuple[InventoryItem, ...]:
    return (
        inventory_item("body-001", "body", "return-body"),
        inventory_item("adapter-001", "adapter", "return-adapter"),
    )


def selected_kind(plan: RecoveryPlan, kind: RecoveryActionKind) -> tuple[RecoveryAction, ...]:
    return tuple(action for action in plan.selected_actions if action.kind is kind)


def independent_best_value(problem: RecoveryProblem, actions: tuple[RecoveryAction, ...]) -> int:
    """Brute-force feasible subsets without calling the planner's feasibility checker."""
    required_ids = {item.component.physical_component_id for item in problem.inventory}
    demand_limits = {kit.configuration_id: kit.demand_limit for kit in problem.scenario.kits}
    feasible_values = []
    for size in range(len(actions) + 1):
        for subset in combinations(actions, size):
            assigned = [component_id for action in subset for component_id in action.component_ids]
            if len(assigned) != len(set(assigned)) or set(assigned) != required_ids:
                continue
            if problem.scenario.labor_capacity_minutes is not None and (
                sum(action.labor_minutes for action in subset) > problem.scenario.labor_capacity_minutes
            ):
                continue
            if any(
                limit is not None
                and sum(action.kind is RecoveryActionKind.REBUILD and action.configuration_id == configuration_id
                        for action in subset) > limit
                for configuration_id, limit in demand_limits.items()
            ):
                continue
            feasible_values.append(sum(action.cash_recovery_cents + action.retained_value_cents for action in subset))
    assert feasible_values, "Generated holds should permit at least one complete disposition."
    return max(feasible_values)


def test_compatible_components_from_different_returns_form_one_complete_kit(catalog: Catalog) -> None:
    problem = problem_for(catalog, kit_items())
    plan = solve_recovery(problem)
    rebuilds = selected_kind(plan, RecoveryActionKind.REBUILD)
    assert plan.status is SolveStatus.OPTIMAL
    assert len(rebuilds) == 1
    assert set(rebuilds[0].component_ids) == {"body-001", "adapter-001"}
    assert plan.cash_recovery_cents == plan.modeled_value_cents == 900
    assert plan.retained_value_cents == 0
    assert evaluate_selection(problem, plan.selected_actions) == ()


def test_incomplete_bom_cannot_produce_a_rebuild(catalog: Catalog) -> None:
    problem = problem_for(catalog, (kit_items()[0],), donor_values={"body-001": 75})
    candidates = generate_candidates(problem)
    assert not any(action.kind is RecoveryActionKind.REBUILD for action in candidates.actions)
    plan = solve_recovery(problem)
    assert plan.status is SolveStatus.OPTIMAL
    assert selected_kind(plan, RecoveryActionKind.RETAIN)
    assert plan.modeled_value_cents == 75


@pytest.mark.parametrize(
    "adapter",
    [
        inventory_item("adapter-001", "adapter", "return-adapter", revision="B"),
        inventory_item("adapter-001", "adapter", "return-adapter", condition=VisibleCondition.DAMAGED),
        inventory_item("adapter-001", "adapter", "return-adapter", condition=VisibleCondition.UNKNOWN),
        inventory_item("adapter-001", "adapter", "return-adapter", state=VerificationState.REVIEW_REQUIRED),
        inventory_item("adapter-001", "adapter", "return-adapter", state=VerificationState.UNRESOLVED),
    ],
    ids=["wrong-revision", "damaged", "unknown-condition", "review-required", "unverified"],
)
def test_incompatible_or_unverified_component_cannot_enter_a_rebuild(
    catalog: Catalog, adapter: InventoryItem,
) -> None:
    problem = problem_for(catalog, (kit_items()[0], adapter))
    assert not any(action.kind is RecoveryActionKind.REBUILD for action in generate_candidates(problem).actions)
    plan = solve_recovery(problem)
    assert not selected_kind(plan, RecoveryActionKind.REBUILD)
    assert evaluate_selection(problem, plan.selected_actions) == ()


def test_a_scarce_component_cannot_be_allocated_to_two_rebuilds(catalog: Catalog) -> None:
    items = kit_items() + (inventory_item("body-002", "body", "return-second-body"),)
    problem = problem_for(catalog, items)
    candidates = generate_candidates(problem)
    rebuilds = tuple(action for action in candidates.actions if action.kind is RecoveryActionKind.REBUILD)
    assert len(rebuilds) == 2
    assert evaluate_selection(problem, rebuilds)
    plan = solve_recovery(problem)
    assert len(selected_kind(plan, RecoveryActionKind.REBUILD)) == 1
    assigned = [identifier for action in plan.selected_actions for identifier in action.component_ids]
    assert len(assigned) == len(set(assigned)) == len(items)


@pytest.mark.parametrize(("capacity", "demand", "expected_kits"), [(0, None, 0), (10, None, 1), (20, 1, 1), (20, 0, 0), (20, 2, 2)])
def test_labor_and_demand_are_hard_limits(
    catalog: Catalog, capacity: int, demand: int | None, expected_kits: int,
) -> None:
    items = kit_items() + (
        inventory_item("body-002", "body", "return-003"),
        inventory_item("adapter-002", "adapter", "return-004"),
    )
    problem = problem_for(catalog, items, labor_capacity=capacity, demand=demand)
    plan = solve_recovery(problem)
    assert len(selected_kind(plan, RecoveryActionKind.REBUILD)) == expected_kits
    assert plan.labor_minutes <= capacity
    assert evaluate_selection(problem, plan.selected_actions) == ()


def test_whole_return_liquidation_conflicts_with_rebuilding_any_member(catalog: Catalog) -> None:
    items = (
        inventory_item("body-001", "body", "return-whole"),
        inventory_item("adapter-001", "adapter", "return-whole"),
    )
    problem = problem_for(catalog, items, liquidation_values={"return-whole": 1200})
    candidates = generate_candidates(problem).actions
    liquidation = next(action for action in candidates if action.kind is RecoveryActionKind.LIQUIDATE)
    rebuild = next(action for action in candidates if action.kind is RecoveryActionKind.REBUILD)
    assert set(liquidation.component_ids) == {"body-001", "adapter-001"}
    assert evaluate_selection(problem, (liquidation, rebuild))
    reasons = explain_alternative(problem, (liquidation,), rebuild)
    assert reasons
    assert not any("globally infeasible" in reason.lower() for reason in reasons)
    plan = solve_recovery(problem)
    assert plan.selected_actions == (liquidation,)
    assert plan.modeled_value_cents == 1200


def test_partial_return_snapshot_cannot_be_liquidated_as_a_whole_return(catalog: Catalog) -> None:
    problem = problem_for(
        catalog,
        (inventory_item("body-001", "body", "return-whole"),),
        liquidation_values={"return-whole": 5000},
        return_contents=(ReturnContents(return_id="return-whole", component_ids=("body-001", "missing-member")),),
    )
    candidates = generate_candidates(problem)
    assert not any(action.kind is RecoveryActionKind.LIQUIDATE for action in candidates.actions)
    assert candidates.rejections
    assert not selected_kind(solve_recovery(problem), RecoveryActionKind.LIQUIDATE)


def test_rebuild_competes_with_retained_assets_without_double_subtracting_donors(catalog: Catalog) -> None:
    problem = problem_for(catalog, kit_items(), donor_values={"body-001": 400, "adapter-001": 400})
    plan = solve_recovery(problem)
    rebuild, = selected_kind(plan, RecoveryActionKind.REBUILD)
    assert rebuild.donor_opportunity_cost_cents == 800
    assert rebuild.incremental_vs_retain_cents == 100
    assert rebuild.modeled_value_cents == rebuild.cash_recovery_cents == 900
    assert plan.modeled_value_cents == 900
    assert plan.retained_value_cents == 0


def test_profitable_rebuild_can_be_inferior_to_retaining_donor_inventory(catalog: Catalog) -> None:
    problem = problem_for(catalog, kit_items(), donor_values={"body-001": 500, "adapter-001": 500})
    plan = solve_recovery(problem)
    assert not selected_kind(plan, RecoveryActionKind.REBUILD)
    assert len(selected_kind(plan, RecoveryActionKind.RETAIN)) == 2
    assert plan.retained_value_cents == plan.modeled_value_cents == 1000
    assert plan.cash_recovery_cents == 0


def test_price_and_labor_sensitivity_change_the_selected_disposition(catalog: Catalog) -> None:
    kwargs = {"donor_values": {"body-001": 400, "adapter-001": 400}}
    low_price = solve_recovery(problem_for(catalog, kit_items(), kit_price=700, **kwargs))
    high_price = solve_recovery(problem_for(catalog, kit_items(), kit_price=1000, **kwargs))
    expensive_labor = solve_recovery(problem_for(catalog, kit_items(), kit_price=1000, labor_rate=30, **kwargs))
    assert not selected_kind(low_price, RecoveryActionKind.REBUILD)
    assert selected_kind(high_price, RecoveryActionKind.REBUILD)
    assert not selected_kind(expensive_labor, RecoveryActionKind.REBUILD)
    assert low_price.modeled_value_cents == expensive_labor.modeled_value_cents == 800
    assert high_price.modeled_value_cents == 900


def test_all_five_dispositions_can_coexist_without_double_allocation(catalog: Catalog) -> None:
    items = kit_items() + (
        inventory_item("liquidation-body", "body", "liquidation-return"),
        inventory_item("retained-adapter", "adapter", "retained-return"),
        inventory_item("salvage-adapter", "adapter", "salvage-return", revision="B", condition=VisibleCondition.DAMAGED),
        inventory_item("held-adapter", "adapter", "held-return", state=VerificationState.UNRESOLVED),
    )
    problem = problem_for(
        catalog, items,
        donor_values={"retained-adapter": 500},
        liquidation_values={"liquidation-return": 2000},
        salvage_values={"salvage-adapter": 1000, "held-adapter": 9999},
    )
    plan = solve_recovery(problem)
    assert {action.kind for action in plan.selected_actions} == set(RecoveryActionKind)
    assert plan.cash_recovery_cents == 3900
    assert plan.retained_value_cents == 500
    assert plan.modeled_value_cents == 4400
    assert evaluate_selection(problem, plan.selected_actions) == ()


@pytest.mark.parametrize(
    ("price", "donor_value", "capacity", "demand", "liquidation", "salvage"),
    [
        (1000, 100, None, None, 0, 0),
        (1000, 500, None, None, 0, 0),
        (1000, 450, None, None, 0, 0),  # Equal-value plans: allocation identity is not asserted.
        (1000, 100, 0, None, 0, 0),
        (1000, 100, None, 0, 1200, 0),
        (50, 0, None, None, 0, 0),
        (1000, 100, None, None, 500, 700),
    ],
)
def test_solver_matches_independent_exhaustive_feasible_subset_oracle(
    catalog: Catalog,
    price: int,
    donor_value: int,
    capacity: int | None,
    demand: int | None,
    liquidation: int,
    salvage: int,
) -> None:
    items = (
        inventory_item("body-001", "body", "return-whole"),
        inventory_item("adapter-001", "adapter", "return-whole"),
    )
    problem = problem_for(
        catalog, items, kit_price=price,
        donor_values={"body-001": donor_value, "adapter-001": donor_value},
        labor_capacity=capacity, demand=demand,
        liquidation_values={"return-whole": liquidation} if liquidation else None,
        salvage_values={"body-001": salvage, "adapter-001": salvage} if salvage else None,
    )
    candidates = generate_candidates(problem).actions
    expected_value = independent_best_value(problem, candidates)
    plan = solve_recovery(problem)
    assert plan.status is SolveStatus.OPTIMAL
    assert plan.modeled_value_cents == expected_value
    assert plan.cash_recovery_cents + plan.retained_value_cents == expected_value
    assert plan.best_bound_cents == expected_value
    assert plan.absolute_gap_cents == 0
    assert evaluate_selection(problem, plan.selected_actions) == ()


def test_zero_time_limit_reports_unknown_without_an_invented_plan(catalog: Catalog) -> None:
    plan = solve_recovery(problem_for(catalog, kit_items()), SolverSettings(max_time_seconds=0.0))
    assert plan.status is SolveStatus.UNKNOWN
    assert plan.selected_actions == ()
    assert plan.modeled_value_cents is None
    assert plan.cash_recovery_cents is None
    assert plan.retained_value_cents is None
    assert plan.labor_minutes is None
    assert plan.absolute_gap_cents is None


def test_deterministic_checker_rejects_missing_coverage_and_coherent_forged_economics(catalog: Catalog) -> None:
    problem = problem_for(catalog, kit_items())
    assert evaluate_selection(problem, ())
    rebuild = next(action for action in generate_candidates(problem).actions if action.kind is RecoveryActionKind.REBUILD)
    inflated = RecoveryAction.model_validate(rebuild.model_dump() | {
        "cash_recovery_cents": rebuild.cash_recovery_cents + 100,
        "modeled_value_cents": rebuild.modeled_value_cents + 100,
        "incremental_vs_retain_cents": rebuild.incremental_vs_retain_cents + 100,
    })
    assert evaluate_selection(problem, (inflated,))


@pytest.mark.parametrize("simulated_status", [SolveStatus.FEASIBLE, SolveStatus.INFEASIBLE, SolveStatus.MODEL_INVALID])
def test_simulated_solver_status_is_reported_without_claiming_optimality(
    catalog: Catalog, monkeypatch: pytest.MonkeyPatch, simulated_status: SolveStatus,
) -> None:
    """Exercise status branches; injected statuses are not measured solver outcomes."""
    real_solve = cp_model.CpSolver.solve

    def solve_with_simulated_status(solver: cp_model.CpSolver, model: cp_model.CpModel):
        real_solve(solver, model)
        return getattr(cp_model, simulated_status.value)

    monkeypatch.setattr(cp_model.CpSolver, "solve", solve_with_simulated_status)
    plan = solve_recovery(problem_for(catalog, kit_items()))
    assert plan.status is simulated_status
    if simulated_status is SolveStatus.FEASIBLE:
        assert plan.selected_actions
        assert plan.modeled_value_cents == 900
        assert any("optimality is not proven" in explanation for explanation in plan.explanations)
    else:
        assert not plan.selected_actions
        assert plan.modeled_value_cents is None
        assert plan.cash_recovery_cents is None
        assert plan.retained_value_cents is None
        assert plan.labor_minutes is None
        assert plan.absolute_gap_cents is None


def test_economic_estimates_cannot_authorize_unapproved_dispositions(catalog: Catalog) -> None:
    problem = problem_for(
        catalog, kit_items(),
        liquidation_values={"return-body": 10000},
        salvage_values={"body-001": 10000, "adapter-001": 10000},
    )
    denied_policy = DispositionPolicy.model_validate(problem.policy.model_dump() | {
        "liquidation_allowed_return_ids": (), "salvage_allowed_component_types": (),
    })
    problem = RecoveryProblem.model_validate(problem.model_dump() | {"policy": denied_policy})
    prohibited = {RecoveryActionKind.LIQUIDATE, RecoveryActionKind.SALVAGE}
    assert not any(action.kind in prohibited for action in generate_candidates(problem).actions)
    assert not any(action.kind in prohibited for action in solve_recovery(problem).selected_actions)


@pytest.mark.parametrize("invalid_money", [True, 1.5])
def test_money_rejects_boolean_and_fractional_cents(invalid_money: object) -> None:
    with pytest.raises(ValueError):
        KitEconomics(configuration_id="standard-kit", selling_price_cents=invalid_money, labor_minutes=0)
    with pytest.raises(ValueError):
        ComponentEconomics(physical_component_id="body-001", donor_value_cents=invalid_money)


def test_consuming_an_asset_cannot_also_claim_its_retained_value(catalog: Catalog) -> None:
    problem = problem_for(catalog, kit_items())
    rebuild = next(action for action in generate_candidates(problem).actions if action.kind is RecoveryActionKind.REBUILD)
    with pytest.raises(ValueError):
        RecoveryAction.model_validate(rebuild.model_dump() | {
            "retained_value_cents": 50,
            "modeled_value_cents": rebuild.modeled_value_cents + 50,
            "incremental_vs_retain_cents": rebuild.incremental_vs_retain_cents + 50,
        })


@pytest.mark.parametrize(("capacity", "expected_value", "expected_rebuilds"), [(10, 1400, 1), (20, 2200, 2)])
def test_multiple_configurations_respect_bom_quantity_and_shared_capacity(
    catalog: Catalog, capacity: int, expected_value: int, expected_rebuilds: int,
) -> None:
    catalog_payload = catalog.model_dump(mode="json")
    catalog_payload["configurations"].append({
        "configuration_id": "double-adapter-kit", "family_id": "demo-kit", "version": "1",
        "bom": [{"component_type_id": "body", "quantity": 1}, {"component_type_id": "adapter", "quantity": 2}],
    })
    catalog_payload["policies"].append(catalog_payload["policies"][0] | {
        "policy_id": "double-adapter-policy", "configuration_id": "double-adapter-kit",
    })
    extended_catalog = Catalog.model_validate(catalog_payload)
    items = kit_items() + (
        inventory_item("body-002", "body", "return-003"),
        inventory_item("adapter-002", "adapter", "return-004"),
        inventory_item("adapter-003", "adapter", "return-005"),
    )
    problem = problem_for(extended_catalog, items, kit_price=900, labor_capacity=capacity, demand=1)
    scenario = EconomicScenario.model_validate(problem.scenario.model_dump() | {"kits": (
        *problem.scenario.kits,
        KitEconomics(configuration_id="double-adapter-kit", selling_price_cents=1500, labor_minutes=10, demand_limit=1),
    )})
    problem = RecoveryProblem.model_validate(problem.model_dump() | {"scenario": scenario})
    plan = solve_recovery(problem)
    rebuilds = selected_kind(plan, RecoveryActionKind.REBUILD)
    assert len(rebuilds) == expected_rebuilds
    double_kit, = (action for action in rebuilds if action.configuration_id == "double-adapter-kit")
    assert len(double_kit.component_ids) == 3
    assert sum(identifier.startswith("adapter-") for identifier in double_kit.component_ids) == 2
    assert plan.modeled_value_cents == expected_value
    assert plan.labor_minutes <= capacity
    assigned = [identifier for action in plan.selected_actions for identifier in action.component_ids]
    assert len(assigned) == len(set(assigned)) == len(items)
    assert evaluate_selection(problem, plan.selected_actions) == ()
