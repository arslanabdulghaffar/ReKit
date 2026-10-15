"""A reproducible synthetic case using existing evidence and planner contracts.

This module renders local fixture diagrams and compares complete feasible
selections. It is not an inference adapter, an alternate planner, or business
ground truth. Mutable inventory remains exclusively behind the existing API.
"""

from collections import Counter
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
from itertools import combinations
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from rekit.recovery.models import RecoveryAction, RecoveryActionKind, RecoveryPlan, RecoveryProblem
from rekit.recovery.planner import evaluate_selection, generate_candidates


ROOT = Path(__file__).resolve().parents[1]
CASE_PATH = ROOT / "evaluation" / "fixtures" / "canonical_case.json"
CORRECTION_COMPONENT_ID = "synthetic-adapter-002"


def load_case() -> dict:
    """Resolve explicit fixture amendments without mutating the original case."""
    specification = json.loads(CASE_PATH.read_text(encoding="utf-8"))
    if specification.get("synthetic") is not True or specification.get("scenario_estimate") is not True:
        raise ValueError("Canonical case must be explicitly synthetic scenario evidence")
    # This reviewed source is fixed rather than accepting arbitrary fixture paths.
    if specification["base_fixture"] != "tests/fixtures/synthetic_recovery.json":
        raise ValueError("Canonical case names an unexpected base fixture")
    fixture = json.loads((ROOT / specification["base_fixture"]).read_text(encoding="utf-8"))
    if fixture.get("synthetic") is not True or fixture["scenario"].get("scenario_estimate") is not True:
        raise ValueError("Canonical source must be explicitly synthetic scenario evidence")
    fixture["fixture_id"] = specification["case_id"]
    fixture["description"] = specification["description"]
    fixture["scenario"]["scenario_id"] = specification["case_id"]
    fixture["scenario"]["description"] = "Canonical synthetic economics: complete alternative allocations; invented USD estimates, not realized savings."
    fixture["scenario"]["returns"] = deepcopy(specification["returns"])
    fixture["canonical"] = specification
    return fixture


def render_image(component_id: str, view: int, *, clarified: bool = False) -> bytes:
    """Create a deterministic PNG diagram; no image generation or model is used.

    The correction subject's first two views intentionally carry no legible
    revision. Its third view is the additional original evidence for correction.
    """
    fixture = load_case()
    records = {record["component"]["physical_component_id"]: record for record in fixture["components"]}
    if component_id not in records or type(view) is not int or type(clarified) is not bool:
        raise ValueError("Unknown canonical component or invalid view")
    if (clarified and (component_id != CORRECTION_COMPONENT_ID or view != 3)) or (not clarified and view not in (1, 2)):
        raise ValueError("Canonical views are two intake images and one explicit correction close-up")
    identity = records[component_id]["verification"]["identity"]
    with Image.new("RGB", (720, 440), "#eef1e9") as image:
        draw = ImageDraw.Draw(image)
        title = ImageFont.load_default(size=19)
        body = ImageFont.load_default(size=22)
        small = ImageFont.load_default(size=17)
        draw.text((24, 24), "SYNTHETIC DIAGRAM - NOT A PRODUCT PHOTOGRAPH", fill="#171c17", font=title)
        draw.text((24, 62), f"{component_id} / ORIGINAL VIEW {view}", fill="#171c17", font=small)
        draw.rounded_rectangle((80 + view * 6, 110, 640, 280), radius=20,
                               fill="#344939" if identity["component_type_id"] == "body" else "#8b662c")
        draw.text((115, 145), f"INVENTED {identity['component_type_id'].upper()}", fill="white", font=body)
        marking = "REVISION UNCLEAR" if component_id == CORRECTION_COMPONENT_ID and not clarified else "REV A"
        draw.text((115, 192), marking, fill="white", font=body)
        if clarified:
            draw.text((24, 310), "Additional original close-up for scripted B-to-A correction.", fill="#171c17", font=small)
        elif component_id == CORRECTION_COMPONENT_ID:
            draw.text((24, 310), "Initial B assertion is deliberately wrong, not model output.", fill="#171c17", font=small)
        else:
            draw.text((24, 310), "Invented original intake evidence for this physical ID only.", fill="#171c17", font=small)
        draw.text((24, 355), "Scripted human workflow; no inference or safety claim.", fill="#171c17", font=small)
        draw.text((24, 387), fixture["fixture_id"], fill="#171c17", font=small)
        buffer = BytesIO()
        image.save(buffer, format="PNG")
    return buffer.getvalue()


def source_images() -> list[dict]:
    """Return all nine original diagrams with component/return provenance."""
    fixture = load_case()
    images = []
    for record in fixture["components"]:
        component = record["component"]
        component_id = component["physical_component_id"]
        for view in ((1, 2, 3) if component_id == CORRECTION_COMPONENT_ID else (1, 2)):
            raw = render_image(component_id, view, clarified=view == 3)
            images.append({
                "physical_component_id": component_id, "return_id": component["source_return_id"],
                "view": view, "filename": f"{component_id}-view-{view}.png",
                "sha256": sha256(raw).hexdigest(), "byte_size": len(raw), "bytes": raw,
            })
    return images


def summarize_selection(problem: RecoveryProblem, actions: tuple[RecoveryAction, ...]) -> dict:
    """Validate a full alternative before exposing any comparison arithmetic."""
    violations = evaluate_selection(problem, actions)
    if violations:
        raise ValueError("Alternative is not a complete feasible allocation: " + "; ".join(violations))
    kits = {entry.configuration_id: entry for entry in problem.scenario.kits}
    returns = {entry.return_id: entry for entry in problem.scenario.returns}
    components = {entry.physical_component_id: entry for entry in problem.scenario.components}
    gross = processing = 0
    for action in actions:
        if action.kind == RecoveryActionKind.REBUILD:
            estimate = kits[action.configuration_id]
            gross += estimate.selling_price_cents
            processing += estimate.other_cost_cents
        elif action.kind == RecoveryActionKind.LIQUIDATE:
            gross += returns[action.source_return_id].liquidation_value_cents
        elif action.kind == RecoveryActionKind.SALVAGE:
            gross += components[action.component_ids[0]].salvage_value_cents
    labor_minutes = sum(action.labor_minutes for action in actions)
    labor_cost = labor_minutes * problem.scenario.labor_cost_per_minute_cents
    cash = sum(action.cash_recovery_cents for action in actions)
    retained = sum(action.retained_value_cents for action in actions)
    modeled = sum(action.modeled_value_cents for action in actions)
    if cash != gross - labor_cost - processing or modeled != cash + retained:
        raise AssertionError("Existing candidate arithmetic disagrees with the complete alternative breakdown")
    return {
        "feasible": True, "violations": [],
        "action_counts": dict(sorted(Counter(action.kind.value for action in actions).items())),
        "gross_recovery_cents": gross, "labor_minutes": labor_minutes, "labor_cost_cents": labor_cost,
        "processing_cost_cents": processing, "cash_recovery_cents": cash,
        "retained_value_cents": retained, "modeled_value_cents": modeled,
        "retention_baseline_cents": sum(estimate.donor_value_cents for estimate in problem.scenario.components),
        "incremental_vs_retain_cents": sum(action.incremental_vs_retain_cents for action in actions),
        "actions": [action.model_dump(mode="json") for action in actions],
    }


def compare_plan(plan: RecoveryPlan) -> dict:
    """Compare complete alternatives under the plan's identical frozen inputs.

    Candidate generation and feasibility remain the existing planner's job. This
    display deliberately makes no claim to enumerate all feasible alternatives.
    The solver's selected allocation and proof status are reported separately.
    """
    problem = plan.problem
    candidates = generate_candidates(problem).actions
    rebuilds = tuple(action for action in candidates if action.kind == RecoveryActionKind.REBUILD)
    rebuild_options = [pair for pair in combinations(rebuilds, 2) if not evaluate_selection(problem, pair)]
    if not rebuild_options:
        raise ValueError("Canonical comparison requires a complete two-kit feasible selection")
    # Stable presentation of one pairing; this does not assert a unique optimum.
    alternatives = {
        "two_rebuilds": rebuild_options[0],
        "liquidate_all_returns": tuple(action for action in candidates if action.kind == RecoveryActionKind.LIQUIDATE),
        "retain_all": tuple(action for action in candidates if action.kind == RecoveryActionKind.RETAIN),
    }
    return {
        "input_hash": plan.input_hash, "currency": problem.scenario.currency,
        "labor_cost_per_minute_cents": problem.scenario.labor_cost_per_minute_cents,
        "solver_status": plan.status.value, "solver_version": plan.solver_version,
        "best_bound_cents": plan.best_bound_cents, "absolute_gap_cents": plan.absolute_gap_cents,
        "selected": summarize_selection(problem, plan.selected_actions),
        "alternatives": {name: {"input_hash": plan.input_hash, **summarize_selection(problem, actions)}
                         for name, actions in alternatives.items()},
        "explanations": list(plan.explanations),
        "limitations": "Complete feasible examples, not exhaustive alternatives. Equal-value physical pairings can exist. All values are invented scenario estimates.",
    }
