"""Run invented recovery scenarios through real local backend logic; print JSON only."""

import asyncio
from collections import Counter
import json
from pathlib import Path
import secrets
from tempfile import TemporaryDirectory

import httpx
import ortools

from rekit.auth import Actor, ActorKind, AuthConfig, OperatorCredential, Role, token_digest
from rekit.catalog.models import Catalog
from rekit.evidence.models import Observation, OperatorVerification, PhysicalComponent, ReturnBatch, ReturnRecord
from rekit.evidence.store import EvidenceStore
from rekit.inventory.store import InventoryStore
from rekit.main import create_app
from rekit.recovery.models import (
    ComponentEconomics, DispositionPolicy, EconomicScenario, KitEconomics,
    RecoveryAction, RecoveryActionKind, RecoveryProblem, ReturnContents, SolveStatus,
)
from rekit.recovery.planner import evaluate_selection, generate_candidates, solve_recovery


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
CASES_PATH = ROOT / "evaluation" / "fixtures" / "recovery_cases.json"


def load_inputs() -> tuple[dict, dict]:
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    fixture = json.loads((ROOT / cases["inventory_fixture"]).read_text(encoding="utf-8"))
    if fixture.get("synthetic") is not True or cases.get("synthetic") is not True or cases.get("scenario_estimate") is not True:
        raise ValueError("The evaluation accepts explicitly labeled synthetic fixtures only")
    return fixture, cases


def _checked(response: httpx.Response, expected_status: int = 200):
    if response.status_code != expected_status:
        raise AssertionError(f"Unexpected HTTP {response.status_code}: {response.text}")
    return response.json()


async def run_end_to_end(fixture: dict) -> dict:
    """Exercise actual ASGI HTTP, SQLite evidence, optimization, and confirmation."""
    catalog = Catalog.model_validate_json((FIXTURES / fixture["catalog_file"]).read_text(encoding="utf-8"))
    policy = DispositionPolicy.model_validate_json((FIXTURES / fixture["disposition_policy_file"]).read_text(encoding="utf-8"))
    with TemporaryDirectory(prefix="rekit-evaluation-") as temporary:
        inventory = InventoryStore(EvidenceStore(Path(temporary) / "workflow.sqlite3", catalog), policy)
        token = secrets.token_urlsafe(32)
        auth = AuthConfig(operators=(OperatorCredential(
            actor=Actor(actor_id="synthetic-reviewer", kind=ActorKind.HUMAN, roles=tuple(Role)),
            token_sha256=token_digest(token),
        ),))
        app = create_app(inventory, auth=auth)
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://synthetic.local",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            _checked(await client.post("/batches", json=fixture["batch"]), 201)
            for returned in fixture["returns"]:
                _checked(await client.post("/returns", json=returned), 201)
            for record in fixture["components"]:
                component_id = record["component"]["physical_component_id"]
                _checked(await client.post("/components", json=record["component"]), 201)
                current = _checked(await client.post(f"/components/{component_id}/evidence", json={
                    "kind": "observation", "payload": record["observation"],
                }))
                before_review = _checked(await client.get(f"/components/{component_id}/compatibility?configuration_id=standard-kit"))
                if before_review["compatible"]:
                    raise AssertionError("An unverified observation became compatible inventory")
                _checked(await client.post(f"/components/{component_id}/verification", json={
                    "verification": {key: value for key, value in record["verification"].items() if key != "operator_id"}, "expected_version": current["version"],
                }))
                verified = _checked(await client.get(f"/components/{component_id}/compatibility?configuration_id=standard-kit"))
                if not verified["compatible"]:
                    raise AssertionError("The reviewed synthetic identity failed approved compatibility")
            stored = _checked(await client.post("/plans", json={"scenario": fixture["scenario"]}), 201)
            plan = stored["plan"]
            plan_id = plan["plan_id"]
            if plan["status"] != "OPTIMAL" or any(action["kind"] != "rebuild" for action in plan["selected_actions"]):
                raise AssertionError("The expected synthetic rebuilds were not found by the solver")
            stored = _checked(await client.post(f"/plans/{plan_id}/approve", json={
                "operation_id": "evaluation-approval",
                "expected_version": stored["version"], "reason": "Synthetic operator approves the computed recovery scenario.",
            }))
            reserved = _checked(await client.get("/inventory"))
            if reserved["completed_kits"] or any(entry["availability"] != "reserved" for entry in reserved["items"]):
                raise AssertionError("Approval did not exclusively reserve the intended inventory")
            for index, action in enumerate(plan["selected_actions"], start=1):
                command = {
                    "operation_id": f"evaluation-completion-{index}",
                    "expected_version": stored["version"], "reason": "Synthetic explicit confirmation of the actual reserved identities.",
                    "confirmed": True, "component_ids": action["component_ids"],
                    "evidence_references": [f"synthetic://evaluation/completed/{index}"],
                    "completed_kit_id": f"synthetic-evaluation-kit-{index}",
                }
                path = f"/plans/{plan_id}/actions/{action['action_id']}/complete"
                stored = _checked(await client.post(path, json=command))
                if _checked(await client.post(path, json=command)) != stored:
                    raise AssertionError("Exact completion retry was not idempotent")
            final = _checked(await client.get("/inventory"))
            audit = _checked(await client.get(f"/plans/{plan_id}/audit"))
            component_ids = [component_id for kit in final["completed_kits"] for component_id in kit["component_ids"]]
            expected_ids = {record["component"]["physical_component_id"] for record in fixture["components"]}
            if set(component_ids) != expected_ids or len(component_ids) != len(expected_ids):
                raise AssertionError("Final completed-kit lineage lost or reused a physical component")
            if stored["state"] != "completed" or any(entry["availability"] != "consumed" for entry in final["items"]):
                raise AssertionError("Explicit completion did not update final inventory")
            result = {
                "fixture_id": fixture["fixture_id"], "solver_status": plan["status"],
                "return_count": len(fixture["returns"]), "physical_component_count": len(final["items"]),
                "completed_kit_count": len(final["completed_kits"]), "consumed_component_count": len(component_ids),
                "modeled_value_cents": plan["modeled_value_cents"], "cash_recovery_cents": plan["cash_recovery_cents"],
                "retained_value_cents": plan["retained_value_cents"], "labor_minutes": plan["labor_minutes"],
                "audit_event_count": len(audit), "final_plan_state": stored["state"],
            }
            for field in ("return_count", "physical_component_count", "completed_kit_count", "modeled_value_cents", "cash_recovery_cents", "retained_value_cents", "labor_minutes"):
                if result[field] != fixture["expected"][field]:
                    raise AssertionError(f"Synthetic end-to-end expectation changed: {field}")
            if [record["kind"] for record in audit] != ["proposed", "approved", "action_completed", "action_completed"]:
                raise AssertionError("Unexpected execution audit sequence")
            return result


def build_comparison_problem(case: dict) -> RecoveryProblem:
    """Build actual verified store inventory from the synthetic operator assertions."""
    fixture, specifications = load_inputs()
    catalog_data = json.loads((FIXTURES / fixture["catalog_file"]).read_text(encoding="utf-8"))
    catalog_data["version"] = "synthetic-evaluation-1"
    catalog_data["description"] = "Synthetic evaluation catalog with an invented second kit size and explicit policies."
    catalog_data["configurations"].append(specifications["catalog_extension"]["configuration"])
    catalog_data["policies"].append(specifications["catalog_extension"]["policy"])
    catalog = Catalog.model_validate(catalog_data)
    with TemporaryDirectory(prefix="rekit-comparison-") as temporary:
        evidence = EvidenceStore(Path(temporary) / "evidence.sqlite3", catalog)
        evidence.register_batch(ReturnBatch.model_validate(fixture["batch"]))
        for returned in fixture["returns"]:
            evidence.register_return(ReturnRecord.model_validate(returned))
        for record in fixture["components"]:
            evidence.register_component(PhysicalComponent.model_validate(record["component"]))
            current = evidence.record_observation(Observation.model_validate(record["observation"]))
            evidence.verify(OperatorVerification.model_validate(record["verification"]), current.version)
        items = evidence.inventory_items()
    scenario = EconomicScenario(
        scenario_id=case["case_id"], description=case["description"], currency=case["currency"],
        valuation_date=case["valuation_date"], labor_cost_per_minute_cents=case["labor_cost_per_minute_cents"],
        labor_capacity_minutes=case["labor_capacity_minutes"],
        kits=tuple(KitEconomics.model_validate(kit) for kit in case["kits"]),
        components=tuple(ComponentEconomics(
            physical_component_id=item.component.physical_component_id,
            donor_value_cents=case["donor_value_per_component_cents"],
        ) for item in items),
    )
    policy = DispositionPolicy(
        policy_id="synthetic-evaluation-dispositions", version="1",
        approved_by="synthetic-policy-author", approved_at=fixture["batch"]["received_at"],
    )
    contents = tuple(ReturnContents(
        return_id=record["return_id"],
        component_ids=tuple(item.component.physical_component_id for item in items if item.component.source_return_id == record["return_id"]),
    ) for record in fixture["returns"])
    return RecoveryProblem(catalog=catalog, inventory=items, return_contents=contents, scenario=scenario, policy=policy)


def greedy_selection(problem: RecoveryProblem) -> tuple[RecoveryAction, ...]:
    """A feasible baseline ranking positive incremental value before allocating donors."""
    problem = RecoveryProblem.model_validate(problem.model_dump(mode="json", warnings=False))
    candidates = generate_candidates(problem).actions
    consuming = sorted(
        (action for action in candidates if action.kind in (RecoveryActionKind.REBUILD, RecoveryActionKind.LIQUIDATE, RecoveryActionKind.SALVAGE)),
        key=lambda action: (-action.incremental_vs_retain_cents, action.action_id),
    )
    selected = []
    allocated = set()
    labor = 0
    kit_counts = Counter()
    limits = {kit.configuration_id: kit.demand_limit for kit in problem.scenario.kits}
    capacity = problem.scenario.labor_capacity_minutes
    for action in consuming:
        if action.incremental_vs_retain_cents <= 0 or allocated.intersection(action.component_ids):
            continue
        if capacity is not None and labor + action.labor_minutes > capacity:
            continue
        limit = limits.get(action.configuration_id)
        if action.kind == RecoveryActionKind.REBUILD and limit is not None and kit_counts[action.configuration_id] >= limit:
            continue
        selected.append(action)
        allocated.update(action.component_ids)
        labor += action.labor_minutes
        if action.kind == RecoveryActionKind.REBUILD:
            kit_counts[action.configuration_id] += 1
    retain = {action.component_ids[0]: action for action in candidates if action.kind == RecoveryActionKind.RETAIN}
    hold = {action.component_ids[0]: action for action in candidates if action.kind == RecoveryActionKind.HOLD}
    for item in sorted(problem.inventory, key=lambda entry: entry.component.physical_component_id):
        component_id = item.component.physical_component_id
        if component_id not in allocated:
            selected.append(retain.get(component_id, hold[component_id]))
    result = tuple(sorted(selected, key=lambda action: action.action_id))
    violations = evaluate_selection(problem, result)
    if violations:
        raise AssertionError(f"Greedy baseline violated recovery constraints: {'; '.join(violations)}")
    return result


def compare_case(case: dict) -> dict:
    problem = build_comparison_problem(case)
    optimized = solve_recovery(problem)
    if optimized.status != SolveStatus.OPTIMAL:
        raise AssertionError(f"Controlled evaluation did not prove an optimum: {optimized.status}")
    greedy = greedy_selection(problem)
    greedy_value = sum(action.modeled_value_cents for action in greedy)
    result = {
        "case_id": case["case_id"], "currency": problem.scenario.currency,
        "solver_status": optimized.status.value, "input_hash": optimized.input_hash,
        "candidate_count": optimized.number_of_candidates,
        "cp_sat_modeled_value_cents": optimized.modeled_value_cents,
        "cp_sat_cash_recovery_cents": optimized.cash_recovery_cents,
        "cp_sat_retained_value_cents": optimized.retained_value_cents,
        "greedy_modeled_value_cents": greedy_value,
        "greedy_cash_recovery_cents": sum(action.cash_recovery_cents for action in greedy),
        "greedy_retained_value_cents": sum(action.retained_value_cents for action in greedy),
        "modeled_difference_cents": optimized.modeled_value_cents - greedy_value,
        "cp_sat_action_counts": dict(sorted(Counter(action.kind.value for action in optimized.selected_actions).items())),
        "greedy_action_counts": dict(sorted(Counter(action.kind.value for action in greedy).items())),
    }
    for field, value in case["expected"].items():
        if result[field] != value:
            raise AssertionError(f"Synthetic comparison expectation changed: {case['case_id']} / {field}")
    return result


async def run_evaluation() -> dict:
    fixture, cases = load_inputs()
    return {
        "synthetic": True, "scenario_estimate": True,
        "description": "Invented local backend scenarios; reported values are modeled estimates, not realized revenue or AI/AMD benchmarks.",
        "solver_version": ortools.__version__,
        "end_to_end": await run_end_to_end(fixture),
        "greedy_comparisons": [compare_case(case) for case in cases["cases"]],
    }


if __name__ == "__main__":
    print(json.dumps(asyncio.run(run_evaluation()), indent=2, sort_keys=True))
