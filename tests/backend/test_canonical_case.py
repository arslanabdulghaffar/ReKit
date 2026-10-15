"""Canonical evidence, same-input economics, and execution receipts are real checks."""

import asyncio
from collections import Counter
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys

from PIL import Image
import pytest

from rekit.recovery.models import RecoveryActionKind, RecoveryPlan, RecoveryProblem
from rekit.recovery.planner import generate_candidates


ROOT = Path(__file__).parents[2]


def _load(name: str, path: Path):
    specification = spec_from_file_location(name, path)
    module = module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


case = _load("canonical_case", ROOT / "evaluation" / "canonical_case.py")
sys.modules.setdefault("canonical_case", case)
runner = _load("rekit_canonical_runner", ROOT / "evaluation" / "run_canonical_case.py")


@pytest.fixture(scope="module")
def receipt() -> dict:
    return asyncio.run(runner.run_case())


def _independent_exact_cover_values(problem: RecoveryProblem) -> list[int]:
    """Enumerate tiny candidate covers, independent of CP-SAT and its validator."""
    candidates = generate_candidates(problem).actions
    required = {item.component.physical_component_id for item in problem.inventory}
    by_component = {component_id: [action for action in candidates if component_id in action.component_ids]
                    for component_id in required}
    limits = {entry.configuration_id: entry.demand_limit for entry in problem.scenario.kits}
    results = []

    def visit(assigned: set[str], selected: tuple) -> None:
        if assigned == required:
            minutes = sum(action.labor_minutes for action in selected)
            if problem.scenario.labor_capacity_minutes is not None and minutes > problem.scenario.labor_capacity_minutes:
                return
            counts = Counter(action.configuration_id for action in selected if action.kind == RecoveryActionKind.REBUILD)
            if any(limit is not None and counts[configuration_id] > limit for configuration_id, limit in limits.items()):
                return
            results.append(sum(action.cash_recovery_cents + action.retained_value_cents for action in selected))
            return
        next_id = min(required - assigned)
        for action in by_component[next_id]:
            members = set(action.component_ids)
            if not members & assigned and members <= required:
                visit(assigned | members, (*selected, action))

    visit(set(), ())
    return results


@pytest.mark.parametrize("name, optimum, values", [
    ("baseline", 17500, {"two_rebuilds": 17500, "liquidate_all_returns": 10250, "retain_all": 1600}),
    ("changed_labor", 8500, {"two_rebuilds": 7000, "liquidate_all_returns": 8500, "retain_all": 1600}),
])
def test_same_input_alternatives_and_solver_match_independent_exact_cover_oracle(receipt: dict, name: str, optimum: int, values: dict) -> None:
    plan = RecoveryPlan.model_validate(receipt[f"{name}_plan"]["plan"])
    comparison = receipt["economic_comparison"][name]
    assert plan.status == "OPTIMAL"
    oracle_values = _independent_exact_cover_values(plan.problem)
    assert max(oracle_values) == plan.modeled_value_cents == optimum
    assert comparison["best_bound_cents"] == optimum
    assert comparison["absolute_gap_cents"] == 0
    for key, expected in values.items():
        alternative = comparison["alternatives"][key]
        assert alternative["input_hash"] == plan.input_hash
        assert alternative["feasible"] is True and alternative["violations"] == []
        assert alternative["modeled_value_cents"] == expected
        assert expected in oracle_values
        assert alternative["cash_recovery_cents"] == alternative["gross_recovery_cents"] - alternative["labor_cost_cents"] - alternative["processing_cost_cents"]
        assert alternative["modeled_value_cents"] == alternative["cash_recovery_cents"] + alternative["retained_value_cents"]
        assert alternative["incremental_vs_retain_cents"] == expected - 1600
        allocated = [component_id for action in alternative["actions"] for component_id in action["component_ids"]]
        assert len(allocated) == len(set(allocated)) == 4


def test_one_labor_change_flips_decision_without_changing_other_inputs(receipt: dict) -> None:
    baseline = receipt["baseline_plan"]["plan"]["problem"]
    changed = receipt["changed_labor_plan"]["plan"]["problem"]
    assert baseline["scenario"]["labor_cost_per_minute_cents"] == 25
    assert changed["scenario"]["labor_cost_per_minute_cents"] == 200
    assert baseline | {"scenario": baseline["scenario"] | {"labor_cost_per_minute_cents": 200}} == changed
    comparisons = receipt["economic_comparison"]
    assert comparisons["baseline"]["selected"]["action_counts"] == {"rebuild": 2}
    assert comparisons["changed_labor"]["selected"]["action_counts"] == {"liquidate": 3}
    assert receipt["changed_labor_plan"]["state"] == "proposed"
    assert comparisons["baseline"]["input_hash"] != comparisons["changed_labor"]["input_hash"]


def test_revision_correction_preserves_original_assets_and_human_assertion(receipt: dict) -> None:
    correction = receipt["correction"]
    before, prior, after = correction["before"], correction["before_correction"], correction["after"]
    assert before["current"]["verification"]["identity"]["revision"] == "B"
    assert correction["prior_compatibility"]["compatible"] is False
    assert before["events"] == prior["events"][:-1]
    assert prior["events"] == after["events"][:-1]
    assert prior["current"]["state"] == "review_required"
    assert after["current"]["verification"]["supersedes_verification_id"] == before["current"]["verification"]["verification_id"]
    assert after["current"]["verification"]["identity"]["revision"] == "A"
    assert len(after["current"]["verification"]["evidence_observation_ids"]) == 3
    assert correction["corrected_compatibility"]["compatible"] is True
    assert receipt["original_image_count"] == 9
    sources = {source["filename"]: source for source in case.source_images()}
    assert len({source["sha256"] for source in sources.values()}) == 9
    for uploaded in receipt["image_provenance"]:
        source = sources[uploaded["source"]["filename"]]
        assert sha256(source["bytes"]).hexdigest() == uploaded["asset"]["sha256"]
        assert uploaded["asset"]["return_id"] == source["return_id"]
        assert uploaded["asset"]["physical_component_id"] == source["physical_component_id"]
        assert uploaded["observation"]["evidence_reference"] == f"asset:{uploaded['asset']['asset_id']}"


def test_reservation_confirmation_and_final_lineage_preserve_authority(receipt: dict) -> None:
    assert receipt["negative_checks"] == {
        "stale_correction_http": 409, "stale_plan_approval_http": 409,
        "double_allocation_http": 409, "unconfirmed_completion_http": 422,
        "prior_evidence_preserved": True, "rejected_operations_left_inventory_unchanged": True,
    }
    reserved = receipt["reserved_inventory"]
    assert not reserved["completed_kits"]
    assert len(reserved["items"]) == 4
    assert all(entry["availability"] == "reserved" for entry in reserved["items"])
    assert receipt["final_plan_state"] == "completed"
    assert all(entry["availability"] == "consumed" for entry in receipt["final_inventory"]["items"])
    lineage = receipt["completed_kit_lineage"]
    assert len(lineage) == 2
    components = [component for kit in lineage for component in kit["components"]]
    assert len({component["physical_component_id"] for component in components}) == 4
    assert len({component["source_return_id"] for component in components}) == 3
    assert all(component["verification"]["operator_id"] == "canonical-scripted-human" for component in components)
    assert all(component["evidence_version"] > 1 and component["source_images"] for component in components)
    assert [event["kind"] for event in receipt["plan_audit"]] == ["proposed", "approved", "action_completed", "action_completed"]
    assert receipt["temporary_state_removed"] is True
    assert receipt["credentials_persisted"] is False
    assert receipt["inference_enabled"] is False
    assert receipt["amd_generation_requests"] == 0


def test_comparison_rejects_incomplete_duplicate_and_tampered_allocations(receipt: dict) -> None:
    plan = RecoveryPlan.model_validate(receipt["baseline_plan"]["plan"])
    with pytest.raises(ValueError, match="complete feasible allocation"):
        case.summarize_selection(plan.problem, plan.selected_actions[:1])
    with pytest.raises(ValueError, match="complete feasible allocation"):
        case.summarize_selection(plan.problem, (plan.selected_actions[0], plan.selected_actions[0]))
    action = plan.selected_actions[0]
    tampered = action.model_copy(update={
        "modeled_value_cents": action.modeled_value_cents + 1,
        "cash_recovery_cents": action.cash_recovery_cents + 1,
        "incremental_vs_retain_cents": action.incremental_vs_retain_cents + 1,
    })
    with pytest.raises(ValueError, match="complete feasible allocation"):
        case.summarize_selection(plan.problem, (tampered, plan.selected_actions[1]))


def test_fixture_and_renderer_are_reproducible_without_mutating_original() -> None:
    original = ROOT / "tests" / "fixtures" / "synthetic_recovery.json"
    before = original.read_bytes()
    first = case.load_case()
    first["scenario"]["labor_cost_per_minute_cents"] = 999
    assert case.load_case()["scenario"]["labor_cost_per_minute_cents"] == 25
    assert original.read_bytes() == before
    for source in case.source_images():
        assert source["bytes"] == case.render_image(source["physical_component_id"], source["view"], clarified=source["view"] == 3)
        with Image.open(BytesIO(source["bytes"])) as image:
            assert image.format == "PNG" and image.size == (720, 440)
    with pytest.raises(ValueError):
        case.render_image("unknown", 1)
    with pytest.raises(ValueError):
        case.render_image("synthetic-body-001", 3, clarified=True)


def test_review_export_retains_originals_and_refuses_overwrite(receipt: dict, tmp_path: Path) -> None:
    output = tmp_path / "review"
    runner.write_review_artifacts(output, receipt)
    assert json.loads((output / "receipt.json").read_text(encoding="utf-8")) == receipt
    assert len(list((output / "original-images").glob("*.png"))) == 9
    for source in case.source_images():
        assert (output / "original-images" / source["filename"]).read_bytes() == source["bytes"]
    before = (output / "receipt.json").read_bytes()
    with pytest.raises(FileExistsError):
        runner.write_review_artifacts(output, receipt)
    assert (output / "receipt.json").read_bytes() == before


def test_cli_runs_offline_from_another_directory_and_cleans_temporary_state(tmp_path: Path) -> None:
    temporary = tmp_path / "temporary"
    temporary.mkdir()
    output = tmp_path / "review"
    environment = os.environ.copy()
    environment.update(TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary), PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, "-B", "-W", "error", str(ROOT / "evaluation" / "run_canonical_case.py"), "--output", str(output)],
                            cwd=tmp_path, env=environment, capture_output=True, text=True, check=True, timeout=60)
    assert result.stderr == ""
    assert json.loads(result.stdout)["status"] == "passed"
    assert list(temporary.iterdir()) == []
    report = json.loads((output / "receipt.json").read_text(encoding="utf-8"))
    assert report["inference_enabled"] is False and report["credentials_persisted"] is False
    assert not list(output.rglob("*.sqlite3"))
    retry = subprocess.run([sys.executable, "-B", str(ROOT / "evaluation" / "run_canonical_case.py"), "--output", str(output)],
                           cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=60)
    assert retry.returncode == 2
    assert "already exists" in retry.stderr
    assert list(temporary.iterdir()) == []
