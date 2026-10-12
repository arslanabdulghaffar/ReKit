"""CPU CP-SAT recovery planning over explicit, fully enumerated candidate actions."""

from collections import Counter
import hashlib
from itertools import combinations, product
import json
from math import ceil, comb, prod
from uuid import uuid4

import ortools
from ortools.sat.python import cp_model

from rekit.catalog.compatibility import check_compatibility
from rekit.inventory.models import InventoryEligibility
from rekit.recovery.models import (
    AlternativeRejection,
    CandidateSet,
    RecoveryAction,
    RecoveryActionKind,
    RecoveryPlan,
    RecoveryProblem,
    SolveStatus,
    SolverSettings,
)


MAX_CANDIDATES = 10_000
_EXACT_INTEGER_LIMIT = 2**50


def _validated_problem(problem: RecoveryProblem) -> RecoveryProblem:
    return RecoveryProblem.model_validate(problem.model_dump(mode="json", warnings=False))


def _input_hash(problem: RecoveryProblem) -> str:
    # Collections in this snapshot represent sets, not chronological event logs.
    # Sorting them makes equivalent input ordering produce the same fingerprint.
    def ordered(value):
        if isinstance(value, dict):
            return {key: ordered(item) for key, item in value.items()}
        if isinstance(value, list):
            return sorted((ordered(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True))
        return value

    encoded = json.dumps(ordered(problem.model_dump(mode="json")), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _action(
    kind: RecoveryActionKind,
    component_ids: tuple[str, ...],
    donor_values: dict[str, int],
    *,
    labor: int = 0,
    cash: int = 0,
    retained: int = 0,
    configuration_id: str | None = None,
    source_return_id: str | None = None,
    explanation: tuple[str, ...],
) -> RecoveryAction:
    component_ids = tuple(sorted(component_ids))
    donor_cost = sum(donor_values.get(component_id, 0) for component_id in component_ids)
    value = cash + retained
    if max(abs(value), abs(cash), retained, donor_cost, abs(value - donor_cost), labor) >= _EXACT_INTEGER_LIMIT:
        raise ValueError("Scenario action arithmetic exceeds the supported exact integer range")
    signature = json.dumps((kind, component_ids, configuration_id, source_return_id), separators=(",", ":"))
    action_id = f"{kind}:{hashlib.sha256(signature.encode('utf-8')).hexdigest()[:24]}"
    return RecoveryAction(
        action_id=action_id, kind=kind, component_ids=component_ids,
        configuration_id=configuration_id, source_return_id=source_return_id,
        labor_minutes=labor, cash_recovery_cents=cash, retained_value_cents=retained,
        modeled_value_cents=value, donor_opportunity_cost_cents=donor_cost,
        incremental_vs_retain_cents=value - donor_cost, explanation=explanation,
    )


def _generate(problem: RecoveryProblem) -> CandidateSet:
    actions = []
    rejections = []
    inventory = {item.component.physical_component_id: item for item in problem.inventory}
    economics = {item.physical_component_id: item for item in problem.scenario.components}
    eligible = {
        component_id: item for component_id, item in inventory.items()
        if item.eligibility == InventoryEligibility.ELIGIBLE
    }
    donors = {component_id: economics[component_id].donor_value_cents for component_id in eligible}
    labor_rate = problem.scenario.labor_cost_per_minute_cents
    capacity = problem.scenario.labor_capacity_minutes

    def add(action: RecoveryAction) -> None:
        if len(actions) >= MAX_CANDIDATES:
            raise ValueError(f"Candidate count exceeds {MAX_CANDIDATES}; narrow the planning pool explicitly")
        actions.append(action)

    def reject(subject: str, *reasons: str) -> None:
        rejections.append(AlternativeRejection(subject=subject, reasons=reasons))

    for component_id in sorted(inventory):
        add(_action(
            RecoveryActionKind.HOLD, (component_id,), donors,
            explanation=("Hold has zero modeled value and zero realized cash; no approval is inferred.",),
        ))
        if component_id not in eligible:
            reject(f"use component {component_id}", "Component is held; current operator-verified eligible inventory is required")
            continue
        estimate = economics[component_id]
        verification = eligible[component_id].evidence.verification
        add(_action(
            RecoveryActionKind.RETAIN, (component_id,), donors, retained=estimate.donor_value_cents,
            explanation=(f"Scenario estimate: retain donor asset value {estimate.donor_value_cents} cents; cash recovery is zero.",),
        ))
        if verification.identity.component_type_id not in problem.policy.salvage_allowed_component_types:
            continue
        if verification.visible_condition not in problem.policy.salvage_allowed_conditions:
            reject(f"salvage component {component_id}", "Visible condition is not approved for salvage by the disposition policy")
            continue
        if capacity is not None and estimate.salvage_labor_minutes > capacity:
            reject(f"salvage component {component_id}", "Salvage labor exceeds the scenario labor capacity")
            continue
        labor_cost = estimate.salvage_labor_minutes * labor_rate
        add(_action(
            RecoveryActionKind.SALVAGE, (component_id,), donors,
            labor=estimate.salvage_labor_minutes, cash=estimate.salvage_value_cents - labor_cost,
            explanation=(f"Scenario estimate: salvage value {estimate.salvage_value_cents} minus labor cost {labor_cost} cents.",),
        ))

    for estimate in sorted(problem.scenario.kits, key=lambda item: item.configuration_id):
        configuration = problem.catalog.configuration(estimate.configuration_id)
        subject = f"rebuild configuration {configuration.configuration_id}"
        if estimate.demand_limit == 0:
            reject(subject, "Demand limit is zero")
            continue
        if capacity is not None and estimate.labor_minutes > capacity:
            reject(subject, "Rebuild labor exceeds the scenario labor capacity")
            continue
        compatible = {line.component_type_id: [] for line in configuration.bom}
        for component_id in sorted(eligible):
            verification = eligible[component_id].evidence.verification
            decision = check_compatibility(
                problem.catalog, configuration.configuration_id,
                verification.identity, verification.visible_condition,
            )
            if decision.compatible:
                compatible[verification.identity.component_type_id].append(component_id)
            else:
                reject(f"{subject} using {component_id}", *decision.reasons)
        missing = tuple(
            f"BOM requires {line.quantity} of {line.component_type_id}; only {len(compatible[line.component_type_id])} compatible eligible components are available"
            for line in configuration.bom if len(compatible[line.component_type_id]) < line.quantity
        )
        if missing:
            reject(subject, *missing)
            continue
        candidate_count = prod(comb(len(compatible[line.component_type_id]), line.quantity) for line in configuration.bom)
        if len(actions) + candidate_count > MAX_CANDIDATES:
            raise ValueError(f"Candidate count exceeds {MAX_CANDIDATES}; narrow the planning pool explicitly")
        # Count before materializing combinations, so large binomial pools cannot exhaust memory.
        pools = [tuple(combinations(compatible[line.component_type_id], line.quantity)) for line in configuration.bom]
        labor_cost = estimate.labor_minutes * labor_rate
        net = estimate.selling_price_cents - labor_cost - estimate.other_cost_cents
        for selected in product(*pools):
            component_ids = tuple(component_id for group in selected for component_id in group)
            add(_action(
                RecoveryActionKind.REBUILD, component_ids, donors,
                configuration_id=configuration.configuration_id, labor=estimate.labor_minutes, cash=net,
                explanation=(
                    f"Approved BOM and compatibility policy are satisfied for {configuration.configuration_id}.",
                    f"Scenario estimate: selling price {estimate.selling_price_cents} minus labor {labor_cost} and other costs {estimate.other_cost_cents} = {net} cents.",
                    "Retained donor value is a competing allocation, not a second deduction from the rebuild objective.",
                ),
            ))

    contents = {item.return_id: item for item in problem.return_contents}
    for estimate in sorted(problem.scenario.returns, key=lambda item: item.return_id):
        subject = f"liquidate return {estimate.return_id}"
        if estimate.return_id not in problem.policy.liquidation_allowed_return_ids:
            reject(subject, "Whole-return liquidation is not explicitly approved by the disposition policy")
            continue
        component_ids = contents[estimate.return_id].component_ids
        unavailable = sorted(set(component_ids) - set(eligible))
        if unavailable:
            reject(subject, *(f"Return component {component_id} is absent or held" for component_id in unavailable))
            continue
        invalid = [component_id for component_id in component_ids if eligible[component_id].evidence.verification.visible_condition not in problem.policy.liquidation_allowed_conditions]
        if invalid:
            reject(subject, *(f"Visible condition of {component_id} is not approved for liquidation" for component_id in sorted(invalid)))
            continue
        if capacity is not None and estimate.liquidation_labor_minutes > capacity:
            reject(subject, "Liquidation labor exceeds the scenario labor capacity")
            continue
        labor_cost = estimate.liquidation_labor_minutes * labor_rate
        add(_action(
            RecoveryActionKind.LIQUIDATE, component_ids, donors, source_return_id=estimate.return_id,
            labor=estimate.liquidation_labor_minutes, cash=estimate.liquidation_value_cents - labor_cost,
            explanation=(
                "Whole-return liquidation allocates every declared physical component and conflicts with separate use of any member.",
                f"Scenario estimate: liquidation value {estimate.liquidation_value_cents} minus labor cost {labor_cost} cents.",
            ),
        ))

    if sum(abs(action.modeled_value_cents) for action in actions) >= _EXACT_INTEGER_LIMIT:
        raise ValueError("Aggregate objective coefficients exceed the supported exact integer range")
    if sum(action.labor_minutes for action in actions) >= _EXACT_INTEGER_LIMIT:
        raise ValueError("Aggregate labor coefficients exceed the supported exact integer range")
    return CandidateSet(actions=tuple(sorted(actions, key=lambda action: action.action_id)), rejections=tuple(rejections))


def generate_candidates(problem: RecoveryProblem) -> CandidateSet:
    """Enumerate all approved action allocations within the explicit bounded pool."""
    return _generate(_validated_problem(problem))


def _invalid_action_reasons(problem: RecoveryProblem, action: RecoveryAction) -> tuple[str, ...]:
    inventory = {item.component.physical_component_id: item for item in problem.inventory}
    reasons = []
    for component_id in action.component_ids:
        item = inventory.get(component_id)
        if item is None:
            reasons.append(f"Unknown or unavailable physical component: {component_id}")
            continue
        if action.kind != RecoveryActionKind.HOLD and item.eligibility != InventoryEligibility.ELIGIBLE:
            reasons.append(f"Physical component {component_id} is held and cannot enter this disposition")
        if action.kind == RecoveryActionKind.REBUILD and item.evidence.verification is not None:
            try:
                decision = check_compatibility(problem.catalog, action.configuration_id, item.evidence.verification.identity, item.evidence.verification.visible_condition)
                reasons.extend(decision.reasons)
            except ValueError as error:
                reasons.append(str(error))
    if action.kind == RecoveryActionKind.REBUILD:
        estimate = next((item for item in problem.scenario.kits if item.configuration_id == action.configuration_id), None)
        if estimate is None:
            reasons.append("No explicit kit economics were supplied for this configuration")
        elif estimate.demand_limit == 0:
            reasons.append("Rebuild demand limit is zero for this configuration")
        try:
            configuration = problem.catalog.configuration(action.configuration_id)
            counts = Counter(
                inventory[component_id].evidence.verification.identity.component_type_id
                for component_id in action.component_ids
                if component_id in inventory and inventory[component_id].evidence.verification is not None
            )
            required = {line.component_type_id: line.quantity for line in configuration.bom}
            if dict(counts) != required:
                reasons.append("Selected components do not satisfy the complete approved BOM quantities")
        except ValueError as error:
            reasons.append(str(error))
    if action.kind == RecoveryActionKind.LIQUIDATE:
        contents = next((item for item in problem.return_contents if item.return_id == action.source_return_id), None)
        if contents is None or set(action.component_ids) != set(contents.component_ids):
            reasons.append("Whole-return liquidation must include every declared return component")
        if action.source_return_id not in problem.policy.liquidation_allowed_return_ids:
            reasons.append("Whole-return liquidation lacks explicit disposition approval")
        if not any(item.return_id == action.source_return_id for item in problem.scenario.returns):
            reasons.append("No explicit liquidation economics were supplied for this return")
        for component_id in action.component_ids:
            item = inventory.get(component_id)
            if item is not None and item.evidence.verification is not None:
                if item.evidence.verification.visible_condition not in problem.policy.liquidation_allowed_conditions:
                    reasons.append(f"Visible condition of {component_id} is not approved for liquidation")
    if action.kind == RecoveryActionKind.SALVAGE:
        for component_id in action.component_ids:
            item = inventory.get(component_id)
            if item is not None and item.evidence.verification is not None:
                verification = item.evidence.verification
                if verification.identity.component_type_id not in problem.policy.salvage_allowed_component_types:
                    reasons.append(f"Component type {verification.identity.component_type_id} is not approved for salvage")
                if verification.visible_condition not in problem.policy.salvage_allowed_conditions:
                    reasons.append(f"Visible condition of {component_id} is not approved for salvage")
    capacity = problem.scenario.labor_capacity_minutes
    if capacity is not None and action.labor_minutes > capacity:
        reasons.append(f"Action labor exceeds scenario capacity: {action.labor_minutes} > {capacity} minutes")
    reasons.append("Action allocation or economics does not match an approved candidate for this scenario")
    return tuple(dict.fromkeys(reasons))


def _evaluate(problem: RecoveryProblem, actions: tuple[RecoveryAction, ...], candidates: CandidateSet) -> tuple[str, ...]:
    reasons = []
    approved = {action.action_id: action for action in candidates.actions}
    action_ids = [action.action_id for action in actions]
    if len(set(action_ids)) != len(action_ids):
        reasons.append("Duplicate recovery action IDs in selection")
    for action in actions:
        if approved.get(action.action_id) != action:
            reasons.extend(_invalid_action_reasons(problem, action))
    counts = Counter(component_id for action in actions for component_id in action.component_ids)
    expected = {item.component.physical_component_id for item in problem.inventory}
    for component_id in sorted(expected | set(counts)):
        if component_id not in expected:
            reasons.append(f"Unknown physical component in allocation: {component_id}")
        elif counts[component_id] != 1:
            reasons.append(f"Physical component {component_id} requires exactly one disposition; selected {counts[component_id]}")
    labor = sum(action.labor_minutes for action in actions)
    capacity = problem.scenario.labor_capacity_minutes
    if capacity is not None and labor > capacity:
        reasons.append(f"Labor usage {labor} exceeds capacity {capacity} minutes")
    rebuild_counts = Counter(action.configuration_id for action in actions if action.kind == RecoveryActionKind.REBUILD)
    for estimate in problem.scenario.kits:
        if estimate.demand_limit is not None and rebuild_counts[estimate.configuration_id] > estimate.demand_limit:
            reasons.append(f"Demand limit {estimate.demand_limit} exceeded for {estimate.configuration_id}")
    return tuple(dict.fromkeys(reasons))


def evaluate_selection(problem: RecoveryProblem, candidate_actions: tuple[RecoveryAction, ...]) -> tuple[str, ...]:
    """Return deterministic violations; an empty tuple denotes a complete feasible allocation."""
    problem = _validated_problem(problem)
    actions = tuple(RecoveryAction.model_validate(action.model_dump(mode="json", warnings=False)) for action in candidate_actions)
    return _evaluate(problem, actions, _generate(problem))


def explain_alternative(
    problem: RecoveryProblem,
    selected_actions: tuple[RecoveryAction, ...],
    alternative_action: RecoveryAction,
) -> tuple[str, ...]:
    """Explain adding an alternative; conflicts do not prove a replacement is infeasible."""
    problem = _validated_problem(problem)
    selected = tuple(RecoveryAction.model_validate(action.model_dump(mode="json", warnings=False)) for action in selected_actions)
    alternative = RecoveryAction.model_validate(alternative_action.model_dump(mode="json", warnings=False))
    approved = {action.action_id: action for action in _generate(problem).actions}
    if any(approved.get(action.action_id) != action for action in selected):
        return ("The current selection contains an action outside the approved candidates or scenario economics.",)
    if approved.get(alternative.action_id) != alternative:
        return _invalid_action_reasons(problem, alternative)
    if alternative in selected:
        return ("This alternative is already in the current selection.",)
    reasons = []
    for action in selected:
        overlap = set(action.component_ids) & set(alternative.component_ids)
        for component_id in sorted(overlap):
            reasons.append(f"Alternative conflicts with current selection {action.action_id} on component {component_id}; replacing that action may be feasible.")
    capacity = problem.scenario.labor_capacity_minutes
    labor = sum(action.labor_minutes for action in selected) + alternative.labor_minutes
    if capacity is not None and labor > capacity:
        reasons.append(f"Adding the alternative to the current selection exceeds labor capacity: {labor} > {capacity} minutes; a replacement requires rechecking capacity.")
    for estimate in problem.scenario.kits:
        count = sum(action.kind == RecoveryActionKind.REBUILD and action.configuration_id == estimate.configuration_id for action in (*selected, alternative))
        if estimate.demand_limit is not None and count > estimate.demand_limit:
            reasons.append(f"Adding the alternative to the current selection exceeds demand limit {estimate.demand_limit} for {estimate.configuration_id}; a replacement may be feasible.")
    reasons.append(
        f"Alternative scenario value is {alternative.modeled_value_cents} cents, including {alternative.retained_value_cents} cents of noncash retained assets; "
        f"increment relative to retaining its donors is {alternative.incremental_vs_retain_cents} cents."
    )
    return tuple(reasons)


def solve_recovery(problem: RecoveryProblem, settings: SolverSettings = SolverSettings()) -> RecoveryPlan:
    """Solve the integer allocation model and report CP-SAT's actual completion status."""
    problem = _validated_problem(problem)
    settings = SolverSettings.model_validate(settings.model_dump(mode="json", warnings=False))
    candidates = _generate(problem)
    model = cp_model.CpModel()
    variables = [model.new_bool_var(action.action_id) for action in candidates.actions]
    for item in problem.inventory:
        component_id = item.component.physical_component_id
        model.add(sum(variable for action, variable in zip(candidates.actions, variables) if component_id in action.component_ids) == 1)
    if problem.scenario.labor_capacity_minutes is not None:
        model.add(sum(action.labor_minutes * variable for action, variable in zip(candidates.actions, variables)) <= problem.scenario.labor_capacity_minutes)
    for estimate in problem.scenario.kits:
        if estimate.demand_limit is not None:
            model.add(sum(variable for action, variable in zip(candidates.actions, variables) if action.configuration_id == estimate.configuration_id) <= estimate.demand_limit)
    model.maximize(sum(action.modeled_value_cents * variable for action, variable in zip(candidates.actions, variables)))
    metadata = dict(
        plan_id=str(uuid4()), input_hash=_input_hash(problem), problem=problem,
        solver_version=ortools.__version__, random_seed=settings.random_seed, worker_count=1,
        time_limit_seconds=settings.max_time_seconds, number_of_candidates=len(candidates.actions),
        rejections=candidates.rejections,
    )
    validation_error = model.validate()
    if validation_error:
        return RecoveryPlan(
            **metadata, status=SolveStatus.MODEL_INVALID, wall_time_seconds=0.0,
            explanations=(f"CP-SAT model validation rejected the model: {validation_error}",),
        )
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = settings.random_seed
    solver.parameters.max_time_in_seconds = settings.max_time_seconds
    status = SolveStatus(solver.status_name(solver.solve(model)))
    if status not in (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE):
        return RecoveryPlan(
            **metadata, status=status, wall_time_seconds=solver.wall_time,
            explanations=(f"CP-SAT returned {status}; no recovery allocation or scenario value is reported.",),
        )
    selected = tuple(action for action, variable in zip(candidates.actions, variables) if solver.value(variable))
    violations = _evaluate(problem, selected, candidates)
    if violations:
        raise RuntimeError(f"Solver allocation failed deterministic validation: {'; '.join(violations)}")
    value = sum(action.modeled_value_cents for action in selected)
    bound = ceil(solver.best_objective_bound)
    if bound < value or abs(solver.objective_value - value) > 0.5:
        raise RuntimeError("Solver objective or bound disagrees with integer scenario arithmetic")
    explanations = (
        f"CP-SAT returned {status} for the complete bounded candidate set; selected modeled value is {value} cents.",
        "Every supplied physical component has exactly one disposition; approved BOM, revision, condition, labor, and demand constraints were enforced.",
        "All values are scenario estimates. Retained donor assets are noncash; holds contribute zero value. Donor retention is an alternative allocation, so opportunity cost is not subtracted twice.",
        "Equal-value alternatives may exist; this result does not claim a unique optimum.",
    )
    if status == SolveStatus.FEASIBLE:
        explanations += ("The solution is feasible but optimality is not proven; inspect the reported bound and gap.",)
    return RecoveryPlan(
        **metadata, status=status, wall_time_seconds=solver.wall_time, selected_actions=selected,
        modeled_value_cents=value, cash_recovery_cents=sum(action.cash_recovery_cents for action in selected),
        retained_value_cents=sum(action.retained_value_cents for action in selected),
        labor_minutes=sum(action.labor_minutes for action in selected),
        best_bound_cents=bound, absolute_gap_cents=bound - value, explanations=explanations,
    )
