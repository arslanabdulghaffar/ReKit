"""Controlled fixture expectations, independent oracle, and clean runner execution."""

from collections import Counter
from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
from itertools import combinations
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from rekit.recovery.models import RecoveryActionKind, RecoveryProblem, SolveStatus
from rekit.recovery.planner import evaluate_selection, generate_candidates, solve_recovery


ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "evaluation" / "run_synthetic.py"
specification = spec_from_file_location("rekit_synthetic_evaluation", SCRIPT)
evaluation = module_from_spec(specification)
specification.loader.exec_module(evaluation)
CASES = json.loads((ROOT / "evaluation" / "fixtures" / "recovery_cases.json").read_text(encoding="utf-8"))["cases"]


def oracle(problem: RecoveryProblem) -> int:
    """Enumerate all tiny candidate subsets with independent allocation/resource checks."""
    candidates = generate_candidates(problem).actions
    required = {item.component.physical_component_id for item in problem.inventory}
    capacity = problem.scenario.labor_capacity_minutes
    limits = {kit.configuration_id: kit.demand_limit for kit in problem.scenario.kits}
    best = None
    for count in range(len(candidates) + 1):
        for subset in combinations(candidates, count):
            assigned = [component_id for action in subset for component_id in action.component_ids]
            if len(set(assigned)) != len(assigned) or set(assigned) != required:
                continue
            if capacity is not None and sum(action.labor_minutes for action in subset) > capacity:
                continue
            kit_counts = Counter(action.configuration_id for action in subset if action.kind == RecoveryActionKind.REBUILD)
            if any(limit is not None and kit_counts[configuration_id] > limit for configuration_id, limit in limits.items()):
                continue
            value = sum(action.cash_recovery_cents + action.retained_value_cents for action in subset)
            best = value if best is None else max(best, value)
    assert best is not None
    return best


@pytest.mark.parametrize("case", CASES, ids=[case["case_id"] for case in CASES])
def test_controlled_comparison_matches_independent_exhaustive_oracle(case: dict) -> None:
    problem = evaluation.build_comparison_problem(case)
    optimized = solve_recovery(problem)
    greedy = evaluation.greedy_selection(problem)
    assert optimized.status == SolveStatus.OPTIMAL
    assert optimized.modeled_value_cents == oracle(problem) == case["expected"]["cp_sat_modeled_value_cents"]
    assert sum(action.modeled_value_cents for action in greedy) == case["expected"]["greedy_modeled_value_cents"]
    assert evaluate_selection(problem, greedy) == ()
    comparison = evaluation.compare_case(case)
    assert comparison["modeled_difference_cents"] == case["expected"]["modeled_difference_cents"]
    if case["case_id"] == "synthetic-scarce-components":
        assert comparison["cp_sat_action_counts"] == {"rebuild": 2}
        assert comparison["greedy_action_counts"] == {"rebuild": 1, "retain": 1}
        assert comparison["greedy_retained_value_cents"] == 100
    else:
        assert comparison["cp_sat_cash_recovery_cents"] == comparison["greedy_cash_recovery_cents"] == 0
        assert comparison["cp_sat_retained_value_cents"] == comparison["greedy_retained_value_cents"] == 400


def test_greedy_enforces_shared_labor_demand_and_physical_uniqueness() -> None:
    case = deepcopy(CASES[0])
    case["labor_capacity_minutes"] = 10
    case["kits"][1]["demand_limit"] = 0
    problem = evaluation.build_comparison_problem(case)
    chosen = evaluation.greedy_selection(problem)
    rebuilds = [action for action in chosen if action.kind == RecoveryActionKind.REBUILD]
    assert len(rebuilds) == 1
    assert rebuilds[0].configuration_id == "standard-kit"
    assert sum(action.labor_minutes for action in chosen) == 10
    assigned = [component_id for action in chosen for component_id in action.component_ids]
    assert len(assigned) == len(set(assigned)) == 4
    assert evaluate_selection(problem, chosen) == ()


def test_expected_outputs_are_checks_not_hardcoded_plans() -> None:
    case = deepcopy(CASES[0])
    case["kits"][0]["selling_price_cents"] = 500
    with pytest.raises(AssertionError, match="expectation changed"):
        evaluation.compare_case(case)


def test_runner_prints_actual_json_and_leaves_no_database_or_generated_artifacts(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.update({"TEMP": str(tmp_path), "TMP": str(tmp_path), "TMPDIR": str(tmp_path), "PYTHONDONTWRITEBYTECODE": "1"})
    result = subprocess.run(
        [sys.executable, "-B", str(SCRIPT)], cwd=tmp_path,
        env=environment, capture_output=True, text=True, check=True, timeout=60,
    )
    assert result.stderr == ""
    report = json.loads(result.stdout)
    assert report["synthetic"] is True
    assert report["scenario_estimate"] is True
    assert report["solver_version"]
    end_to_end = report["end_to_end"]
    assert end_to_end["return_count"] == 3
    assert end_to_end["physical_component_count"] == end_to_end["consumed_component_count"] == 4
    assert end_to_end["completed_kit_count"] == 2
    assert end_to_end["modeled_value_cents"] == end_to_end["cash_recovery_cents"] == 17500
    assert end_to_end["final_plan_state"] == "completed"
    assert end_to_end["audit_event_count"] == 4
    assert [case["modeled_difference_cents"] for case in report["greedy_comparisons"]] == [1200, 0]
    assert list(tmp_path.iterdir()) == []
