"""Bounded synthetic sensitivity is exhaustive, auditable and never overclaimed."""

import asyncio
from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

import pytest

from rekit.recovery.models import RecoveryPlan, RecoveryProblem, SolverSettings
from rekit.recovery.planner import solve_recovery


ROOT = Path(__file__).parents[2]


def _load(name: str, filename: str):
    specification = spec_from_file_location(name, ROOT / "evaluation" / filename)
    module = module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


case = _load("canonical_case", "canonical_case.py")
sys.modules.setdefault("canonical_case", case)
runner = _load("sensitivity_case_runner", "run_canonical_case.py")
sensitivity = _load("canonical_sensitivity", "run_canonical_sensitivity.py")


@pytest.fixture(scope="module")
def receipt() -> dict:
    return asyncio.run(runner.run_case())


@pytest.fixture(scope="module")
def problem(receipt: dict) -> RecoveryProblem:
    return RecoveryPlan.model_validate(receipt["baseline_plan"]["plan"]).problem


@pytest.fixture(scope="module")
def result(problem: RecoveryProblem) -> dict:
    return sensitivity.analyze(problem)


def test_every_integer_rate_has_an_actual_optimal_cp_sat_plan_and_oracle_match(result: dict) -> None:
    assert result["status"] == "passed"
    assert result["cp_sat_solve_count"] == 201
    assert result["candidate_count"] == 19
    assert result["feasible_complete_cover_count"] == 210
    assert result["distinct_value_labor_lines"] == 73
    assert [row["labor_cost_per_minute_cents"] for row in result["runs"]] == list(range(201))
    for row in result["runs"]:
        plan = RecoveryPlan.model_validate(row["plan"])
        assert plan.status == "OPTIMAL"
        assert plan.best_bound_cents == plan.modeled_value_cents == row["oracle_optimum_cents"]
        assert plan.absolute_gap_cents == 0
        assert row["cp_sat_matches_exact_cover"] is True
    assert result["inference_enabled"] is False
    assert result["amd_generation_requests"] == 0
    assert result["application_state_modified"] is False


def test_tie_reports_all_three_physical_allocations_instead_of_one_solver_choice(result: dict) -> None:
    regimes = result["verified_integer_regimes"]
    assert [(r["first_integer_rate_cents"], r["last_integer_rate_cents"]) for r in regimes] == [(0, 169), (170, 170), (171, 200)]
    assert [len(r["optimal_cover_indexes"]) for r in regimes] == [2, 3, 1]
    tied = [result["all_feasible_covers"][index] for index in regimes[1]["optimal_cover_indexes"]]
    assert sum(cover["action_counts"] == {"rebuild": 2} for cover in tied) == 2
    assert sum(cover["action_counts"] == {"liquidate": 3} for cover in tied) == 1
    assert all(cover["value_intercept_cents"] - 170 * cover["labor_minutes"] == 8800 for cover in tied)


@pytest.mark.parametrize("rate,value", [(0, 19000), (25, 17500), (169, 8860), (170, 8800), (171, 8790), (200, 8500)])
def test_checkpoint_values(result: dict, rate: int, value: int) -> None:
    assert result["runs"][rate]["plan"]["modeled_value_cents"] == value


def test_oracle_includes_mixed_allocations_and_every_permitted_disposition(result: dict) -> None:
    covers = result["all_feasible_covers"]
    assert len({tuple(cover["action_ids"]) for cover in covers}) == 210
    assert any(len(cover["action_counts"]) >= 3 for cover in covers)
    assert {kind for cover in covers for kind in cover["action_counts"]} == {"hold", "retain", "salvage", "rebuild", "liquidate"}
    assert any(cover["action_counts"] == {"rebuild": 1, "retain": 1, "liquidate": 1} for cover in covers)


def test_all_other_inputs_preserved_and_source_problem_not_mutated(problem: RecoveryProblem, result: dict) -> None:
    original = problem.model_dump(mode="json")
    for row in result["runs"]:
        restored = deepcopy(row["plan"]["problem"])
        restored["scenario"]["labor_cost_per_minute_cents"] = 25
        assert restored == original
        assert row["only_labor_rate_changed"] is True
        assert row["candidate_set_unchanged"] is True
        assert row["candidate_economics_match_affine_model"] is True
    assert problem.scenario.labor_cost_per_minute_cents == 25


def test_zero_time_solver_status_cannot_be_presented_as_verified_frontier(problem: RecoveryProblem, monkeypatch: pytest.MonkeyPatch) -> None:
    def bounded_solve(candidate: RecoveryProblem) -> RecoveryPlan:
        if candidate.scenario.labor_cost_per_minute_cents == 170:
            return solve_recovery(candidate, SolverSettings(max_time_seconds=0.0))
        return solve_recovery(candidate)

    monkeypatch.setattr(sensitivity, "solve_recovery", bounded_solve)
    result = sensitivity.analyze(problem)
    assert result["status"] == "incomplete"
    assert result["all_solves_optimal_and_match_oracle"] is False
    assert result["verified_integer_regimes"] == []
    failed = result["runs"][170]
    assert failed["plan"]["status"] == "UNKNOWN"
    assert failed["plan"]["modeled_value_cents"] is None
    assert failed["plan"]["selected_actions"] == []
    assert failed["cp_sat_matches_exact_cover"] is False


def test_oracle_checks_combined_capacity_and_demand(problem: RecoveryProblem) -> None:
    payload = problem.model_dump(mode="json")
    payload["scenario"]["labor_capacity_minutes"] = 32
    payload["scenario"]["kits"][0]["demand_limit"] = 1
    limited = RecoveryProblem.model_validate(payload)
    covers = sensitivity.enumerate_covers(limited)
    assert all(cover["labor_minutes"] <= 32 for cover in covers)
    assert all(cover["action_counts"].get("rebuild", 0) <= 1 for cover in covers)
    assert any(cover["action_counts"].get("rebuild", 0) == 1 for cover in covers)
    plan = solve_recovery(limited)
    assert plan.modeled_value_cents == max(cover["value_intercept_cents"] - 25 * cover["labor_minutes"] for cover in covers)


def test_changed_frozen_source_is_rejected_before_parsing(tmp_path: Path) -> None:
    modified = tmp_path / "receipt.json"
    modified.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="not the frozen"):
        sensitivity.load_frozen_problem(modified)


def test_conditional_evidence_branches_use_saved_states_without_new_assertions(problem: RecoveryProblem, receipt: dict) -> None:
    before = deepcopy(receipt)
    branches = sensitivity.compare_evidence_branches(problem, receipt)
    assert branches["status"] == "passed"
    assert branches["new_human_assertions"] == branches["store_writes"] == 0
    assert branches["probabilities_used"] is False
    expected = {
        (25, "historical_scripted_B"): 10775,
        (25, "review_required_held"): 9350,
        (25, "corrected_scripted_A"): 17500,
        (200, "historical_scripted_B"): 8500,
        # Body return: 8000 - 5*200; adapter-001: 1000 - 2*200.
        (200, "review_required_held"): 7600,
        (200, "corrected_scripted_A"): 8500,
    }
    for row in branches["runs"]:
        assert row["oracle_optimum_cents"] == expected[(row["labor_cost_per_minute_cents"], row["branch"])]
        assert row["cp_sat_matches_exact_cover"] is True
        assert row["plan"]["best_bound_cents"] == row["plan"]["modeled_value_cents"]
        assert row["plan"]["absolute_gap_cents"] == 0
        assert row["only_subject_evidence_eligibility_and_rate_changed"] is True
        assert row["hypothetical_planning_snapshot"] is True
    assert receipt == before


def test_output_stays_under_ignored_root_and_cannot_replace_previous_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sensitivity, "ROOT", tmp_path)
    output = tmp_path / "var/mission06-offline/new-sensitivity"
    sensitivity.write_report(output, {"synthetic": True})
    before = (output / "receipt.json").read_bytes()
    with pytest.raises(FileExistsError):
        sensitivity.write_report(output, {"synthetic": False})
    assert (output / "receipt.json").read_bytes() == before
    with pytest.raises(ValueError, match="under var/mission06-offline"):
        sensitivity.write_report(tmp_path / "public", {})
