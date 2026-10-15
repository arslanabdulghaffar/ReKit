"""Offline labor sensitivity for the frozen, synthetic canonical case.

CP-SAT remains the planner. The tiny exact-cover enumeration is a verification
oracle, following test_canonical_case.py; it never writes application state.
No inference provider, external transport, or additional optimizer is used.
"""

import argparse
from collections import Counter
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path

from canonical_case import ROOT
from rekit.recovery.models import RecoveryActionKind, RecoveryPlan, RecoveryProblem, SolveStatus
from rekit.recovery.planner import generate_candidates, problem_fingerprint, solve_recovery


SOURCE_PATH = ROOT / "var/mission06-offline/canonical-case-b1-first/receipt.json"
SOURCE_SHA256 = "c405c532543cfbba0d32632025e0272a1f79c0bcdc88cc402ed9e4138ab507e7"
RATE_MIN = 0
RATE_MAX = 200


def load_frozen_problem(path: Path = SOURCE_PATH) -> tuple[RecoveryProblem, dict]:
    """Fail closed if the accepted receipt or its source fixtures have changed."""
    raw = path.read_bytes()
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Source is not the frozen canonical-case-b1-first receipt")
    receipt = json.loads(raw)
    if receipt["synthetic"] is not True or receipt["inference_enabled"] is not False:
        raise ValueError("Sensitivity requires the explicitly synthetic, inference-free receipt")
    sources = {
        "evaluation/fixtures/canonical_case.json": receipt["fixture_sha256"],
        "tests/fixtures/synthetic_recovery.json": receipt["original_fixture_sha256"],
    }
    for relative, digest in sources.items():
        if sha256((ROOT / relative).read_bytes()).hexdigest() != digest:
            raise ValueError("The frozen canonical source fixture has changed")
    plan = RecoveryPlan.model_validate(receipt["baseline_plan"]["plan"])
    if plan.input_hash != problem_fingerprint(plan.problem):
        raise ValueError("Frozen problem fingerprint disagrees with the recorded plan")
    return plan.problem, {
        "receipt": SOURCE_PATH.relative_to(ROOT).as_posix(),
        "receipt_sha256": SOURCE_SHA256,
        "baseline_problem_fingerprint": plan.input_hash,
        "fixtures": sources,
    }


def enumerate_covers(problem: RecoveryProblem) -> list[dict]:
    """Independently enforce coverage, exclusivity, capacity and demand.

    Uses the application's candidate generator but neither CP-SAT nor its
    selection validator. This verifies allocation, not independent correctness
    of candidate generation, compatibility policy, or the source assumptions.
    Deliberately bounded to the four-component demonstration.
    """
    candidates = generate_candidates(problem).actions
    if len(problem.inventory) != 4 or len(candidates) > 24:
        raise ValueError("Exact-cover verification is limited to the tiny canonical case")
    required = {item.component.physical_component_id for item in problem.inventory}
    by_component = {
        identifier: [action for action in candidates if identifier in action.component_ids]
        for identifier in required
    }
    limits = {entry.configuration_id: entry.demand_limit for entry in problem.scenario.kits}
    results = []

    def visit(assigned: set[str], selected: tuple) -> None:
        if assigned == required:
            labor = sum(action.labor_minutes for action in selected)
            capacity = problem.scenario.labor_capacity_minutes
            if capacity is not None and labor > capacity:
                return
            counts = Counter(action.configuration_id for action in selected if action.kind == RecoveryActionKind.REBUILD)
            if any(limit is not None and counts[key] > limit for key, limit in limits.items()):
                return
            cash = sum(action.cash_recovery_cents for action in selected)
            retained = sum(action.retained_value_cents for action in selected)
            results.append({
                "action_ids": sorted(action.action_id for action in selected),
                "action_counts": dict(sorted(Counter(action.kind.value for action in selected).items())),
                "labor_minutes": labor,
                "cash_at_zero_labor_rate_cents": cash + labor * problem.scenario.labor_cost_per_minute_cents,
                "retained_value_cents": retained,
                "value_intercept_cents": cash + retained + labor * problem.scenario.labor_cost_per_minute_cents,
            })
            return
        for action in by_component[min(required - assigned)]:
            members = set(action.component_ids)
            if not members & assigned and members <= required:
                visit(assigned | members, (*selected, action))

    visit(set(), ())
    return sorted(results, key=lambda item: item["action_ids"])


def analyze(problem: RecoveryProblem) -> dict:
    """Solve every representable integer rate in the declared 0..200 range."""
    baseline = problem.model_dump(mode="json")
    covers = enumerate_covers(problem)
    candidates = generate_candidates(problem).actions
    baseline_actions = {action.action_id: action for action in candidates}
    candidate_ids = set(baseline_actions)
    rows = []
    regimes = []
    for rate in range(RATE_MIN, RATE_MAX + 1):
        payload = deepcopy(baseline)
        payload["scenario"]["labor_cost_per_minute_cents"] = rate
        scenario = RecoveryProblem.model_validate(payload)
        # Explicitly prove that only the requested scalar changed.
        restored = scenario.model_dump(mode="json")
        restored["scenario"]["labor_cost_per_minute_cents"] = baseline["scenario"]["labor_cost_per_minute_cents"]
        if restored != baseline:
            raise AssertionError("Sensitivity changed another input")
        actions = generate_candidates(scenario).actions
        if {action.action_id for action in actions} != candidate_ids:
            raise AssertionError("Candidate membership changed with the labor rate")
        for action in actions:
            prior = baseline_actions[action.action_id]
            labor_delta = prior.labor_minutes * (rate - problem.scenario.labor_cost_per_minute_cents)
            if (
                action.labor_minutes != prior.labor_minutes
                or action.retained_value_cents != prior.retained_value_cents
                or action.cash_recovery_cents != prior.cash_recovery_cents - labor_delta
                or action.modeled_value_cents != prior.modeled_value_cents - labor_delta
            ):
                raise AssertionError("Candidate economics no longer match the fixed linear labor scenario")
        cover_values = [cover["value_intercept_cents"] - rate * cover["labor_minutes"] for cover in covers]
        optimum = max(cover_values)
        winning_indexes = [index for index, value in enumerate(cover_values) if value == optimum]
        winning_ids = {tuple(covers[index]["action_ids"]) for index in winning_indexes}
        plan = solve_recovery(scenario)
        selected_ids = tuple(sorted(action.action_id for action in plan.selected_actions))
        verified = (
            plan.status == SolveStatus.OPTIMAL
            and plan.modeled_value_cents == plan.best_bound_cents == optimum
            and plan.absolute_gap_cents == 0
            and selected_ids in winning_ids
        )
        rows.append({
            "labor_cost_per_minute_cents": rate,
            "only_labor_rate_changed": True,
            "candidate_set_unchanged": True,
            "candidate_economics_match_affine_model": True,
            "oracle_optimum_cents": optimum,
            "oracle_optimal_cover_indexes": winning_indexes,
            "cp_sat_matches_exact_cover": verified,
            "plan": plan.model_dump(mode="json"),
        })
        # Group by all winning physical allocations, not the solver's arbitrary
        # selection among equally valued pairings.
        if regimes and regimes[-1]["optimal_cover_indexes"] == winning_indexes:
            regimes[-1]["last_integer_rate_cents"] = rate
        else:
            regimes.append({
                "first_integer_rate_cents": rate,
                "last_integer_rate_cents": rate,
                "optimal_cover_indexes": winning_indexes,
            })
    verified = all(row["cp_sat_matches_exact_cover"] for row in rows)
    return {
        "status": "passed" if verified else "incomplete",
        "synthetic": True,
        "scenario_estimate": True,
        "inference_enabled": False,
        "amd_generation_requests": 0,
        "application_state_modified": False,
        "completed_at": datetime.now(UTC).isoformat(),
        "domain": {
            "field": "scenario.labor_cost_per_minute_cents",
            "minimum": RATE_MIN, "maximum": RATE_MAX, "step": 1,
            "currency": problem.scenario.currency,
            "input_unit": "integer cents per minute",
            "all_other_problem_fields_identical": True,
        },
        "candidate_count": len(candidates),
        "candidate_actions_at_baseline": [action.model_dump(mode="json") for action in candidates],
        "feasible_complete_cover_count": len(covers),
        "distinct_value_labor_lines": len({(cover["value_intercept_cents"], cover["labor_minutes"]) for cover in covers}),
        "all_feasible_covers": covers,
        "cp_sat_solve_count": len(rows),
        "all_solves_optimal_and_match_oracle": verified,
        "verified_integer_regimes": regimes if verified else [],
        "runs": rows,
        "limitations": [
            "Invented synthetic economics; not measured labor, realized cash, safety evidence or merchant savings.",
            "The verified domain is 0 through 200 integer cents per minute only; no extrapolated global threshold outside it.",
            "The exact-cover oracle shares existing candidate generation and inputs; it is independent of CP-SAT and its allocation validator, not independent policy validation.",
            "Equal-value physical pairings and different dispositions may tie; the chosen CP-SAT allocation is not a unique recommendation.",
            "Retained donor values are noncash scenario estimates. No probability, expected value of information, sale probability or capture cost is inferred.",
            "This is an offline proposal and changes no UI, presentation, authority, inventory or production optimization behavior.",
        ],
    }


def compare_evidence_branches(problem: RecoveryProblem, source_receipt: dict) -> dict:
    """Compare saved evidence states as hypothetical, read-only planning inputs.

    These are no new human assertions. The historical scripted B state, the
    review-required state after an added image, and the corrected A state come
    directly from the same receipt. Only that component's evidence/eligibility
    and the stated labor rate differ across these planning snapshots.
    """
    component_id = source_receipt["correction"]["physical_component_id"]
    snapshots = {
        "historical_scripted_B": ("before", "eligible"),
        "review_required_held": ("before_correction", "held"),
        "corrected_scripted_A": ("after", "eligible"),
    }
    baseline = problem.model_dump(mode="json")
    original = next(item for item in baseline["inventory"] if item["component"]["physical_component_id"] == component_id)
    if original["evidence"] != source_receipt["correction"]["after"]["current"]:
        raise ValueError("Baseline evidence does not match the saved corrected component")
    runs = []
    for rate in (25, 200):
        for branch, (snapshot, eligibility) in snapshots.items():
            payload = deepcopy(baseline)
            payload["scenario"]["labor_cost_per_minute_cents"] = rate
            item = next(item for item in payload["inventory"] if item["component"]["physical_component_id"] == component_id)
            item["evidence"] = deepcopy(source_receipt["correction"][snapshot]["current"])
            item["eligibility"] = eligibility
            scenario = RecoveryProblem.model_validate(payload)
            restored = scenario.model_dump(mode="json")
            restored["scenario"]["labor_cost_per_minute_cents"] = baseline["scenario"]["labor_cost_per_minute_cents"]
            index = next(i for i, entry in enumerate(restored["inventory"]) if entry["component"]["physical_component_id"] == component_id)
            restored["inventory"][index] = deepcopy(original)
            if restored != baseline:
                raise AssertionError("Conditional evidence comparison changed unrelated inputs")
            covers = enumerate_covers(scenario)
            oracle_value = max(cover["value_intercept_cents"] - rate * cover["labor_minutes"] for cover in covers)
            plan = solve_recovery(scenario)
            selected_ids = sorted(action.action_id for action in plan.selected_actions)
            matched = any(cover["action_ids"] == selected_ids and cover["value_intercept_cents"] - rate * cover["labor_minutes"] == oracle_value for cover in covers)
            verified = plan.status == SolveStatus.OPTIMAL and plan.modeled_value_cents == plan.best_bound_cents == oracle_value and plan.absolute_gap_cents == 0 and matched
            runs.append({
                "branch": branch, "hypothetical_planning_snapshot": True,
                "source_json_pointer": f"/correction/{snapshot}/current",
                "physical_component_id": component_id,
                "labor_cost_per_minute_cents": rate,
                "only_subject_evidence_eligibility_and_rate_changed": True,
                "feasible_complete_cover_count": len(covers),
                "oracle_optimum_cents": oracle_value,
                "cp_sat_matches_exact_cover": verified,
                "plan": plan.model_dump(mode="json"),
            })
    return {
        "status": "passed" if all(run["cp_sat_matches_exact_cover"] for run in runs) else "incomplete",
        "purpose": "Research-only conditional decision consequences, not evidence requests or expected value of information",
        "new_human_assertions": 0, "store_writes": 0, "probabilities_used": False,
        "runs": runs,
        "limitations": [
            "Historical B is a deliberately wrong scripted assertion; it is not a real product label or a prediction of what new evidence will show.",
            "The held branch retains the old B assertion in history but has review_required state and no disposition authority beyond hold for that component.",
            "Evidence state and eligibility are deliberately varied together; this is not a causal estimate of the value of one photograph.",
            "No branch is applied to application state; actual capture, human verification, policy checks and approval remain mandatory.",
            "No outcome probability, capture cost, risk utility, calibration or expected-value calculation is present.",
        ],
    }


def write_report(output: Path, report: dict) -> None:
    """Keep new, nonsecret receipts under the ignored offline evidence directory."""
    allowed = (ROOT / "var/mission06-offline").resolve()
    resolved = output.resolve()
    if resolved == allowed or not resolved.is_relative_to(allowed):
        raise ValueError("Output must be a new directory under var/mission06-offline")
    if any(part.is_symlink() or (part.exists() and getattr(part.stat(), "st_file_attributes", 0) & 1024)
           for part in (output, *output.parents) if part != part.parent):
        raise ValueError("Output must not traverse links or reparse points")
    resolved.mkdir(parents=True, exist_ok=False)
    with (resolved / "receipt.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New directory under var/mission06-offline; never overwrites")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output directory already exists; preserve the previous receipt")
    problem, source = load_frozen_problem()
    report = analyze(problem)
    source_bytes = SOURCE_PATH.read_bytes()
    if sha256(source_bytes).hexdigest() != SOURCE_SHA256:
        raise ValueError("Frozen receipt changed during analysis")
    report["conditional_evidence_research"] = compare_evidence_branches(problem, json.loads(source_bytes))
    if report["conditional_evidence_research"]["status"] != "passed":
        report["status"] = "incomplete"
    report["source"] = source
    report["analysis_source_sha256"] = sha256(Path(__file__).read_bytes()).hexdigest()
    write_report(args.output, report)
    print(json.dumps({
        "status": report["status"], "output": str(args.output),
        "cp_sat_solves": report["cp_sat_solve_count"],
        "complete_feasible_allocations": report["feasible_complete_cover_count"],
        "all_solves_optimal_and_match_oracle": report["all_solves_optimal_and_match_oracle"],
        "inference_enabled": False,
    }, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
