"""Package existing Block D results as an offline, read-only explanation.

This builder never solves, infers, opens a database or changes application state.
The accepted receipts and original diagrams must already exist locally. Tests
exercise the same semantic validation with disposable canonical-case receipts.
"""

import argparse
from collections import Counter
from copy import deepcopy
from hashlib import sha256
from html import escape
import json
from pathlib import Path

from rekit.recovery.models import RecoveryPlan
from rekit.recovery.planner import problem_fingerprint


ROOT = Path(__file__).resolve().parents[1]
SENSITIVITY = "var/mission06-offline/block-d-canonical-sensitivity-20261015-224735/receipt.json"
SENSITIVITY_SHA256 = "cb565d5cdf87a46aa68bc02f3fe4b34da619c9d45d54c8304c63faf787a4ee3f"
CANONICAL = "var/mission06-offline/canonical-case-b1-first/receipt.json"
CANONICAL_SHA256 = "c405c532543cfbba0d32632025e0272a1f79c0bcdc88cc402ed9e4138ab507e7"
ANALYSIS_SOURCE = "evaluation/run_canonical_sensitivity.py"
ANALYSIS_SHA256 = "efca1bce8f8cf7561a4f85bfe0997ab9eb84fe2eb4840ba30ae0dfbe80ddd697"
SUBJECT = "synthetic-adapter-002"
BRANCHES = {
    "historical_scripted_B": ("before", "eligible", 4, "verified", "B"),
    "review_required_held": ("before_correction", "held", 5, "review_required", "B"),
    "corrected_scripted_A": ("after", "eligible", 6, "verified", "A"),
}
EXPECTED = {
    (25, "historical_scripted_B"): (10175, 600, {"rebuild": 1, "liquidate": 1, "retain": 1}),
    (25, "review_required_held"): (8750, 600, {"rebuild": 1, "retain": 1, "hold": 1}),
    (25, "corrected_scripted_A"): (17500, 0, {"rebuild": 2}),
    (200, "historical_scripted_B"): (8500, 0, {"liquidate": 3}),
    (200, "review_required_held"): (7600, 0, {"liquidate": 2, "hold": 1}),
    (200, "corrected_scripted_A"): (8500, 0, {"liquidate": 3}),
}
FIXTURES = ("evaluation/fixtures/canonical_case.json", "tests/fixtures/synthetic_recovery.json")
ASSETS = Path(__file__).parent / "assets"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def checked_plan(row: dict) -> RecoveryPlan:
    plan = RecoveryPlan.model_validate(row["plan"])
    require(plan.input_hash == problem_fingerprint(plan.problem), "Recorded input fingerprint changed")
    require(plan.status == "OPTIMAL" and plan.absolute_gap_cents == 0, "A recorded solve is not proven optimal")
    require(plan.modeled_value_cents == plan.best_bound_cents == row["oracle_optimum_cents"], "Recorded optimum and bound disagree")
    require(row["cp_sat_matches_exact_cover"] is True, "Missing exact-cover agreement")
    require(plan.problem.scenario.labor_cost_per_minute_cents == row["labor_cost_per_minute_cents"], "Labor assumption disagrees")
    return plan


def validate_receipts(report: dict, canonical: dict) -> dict:
    """Validate all saved results without invoking the solver or an oracle.

    File authentication is a separate, mandatory production-loader boundary.
    This function also accepts fresh disposable receipts for portable CI tests.
    """
    require(report["status"] == "passed" and report["synthetic"] is True, "Expected passed synthetic research")
    require(report["inference_enabled"] is False and report["application_state_modified"] is False, "Research boundaries changed")
    require(report["amd_generation_requests"] == 0 and report["scenario_estimate"] is True, "Unexpected inference or non-scenario result")
    require(canonical["synthetic"] is True and canonical["inference_enabled"] is False, "Canonical source is not inference-free synthetic evidence")
    baseline_plan = RecoveryPlan.model_validate(canonical["baseline_plan"]["plan"])
    require(baseline_plan.input_hash == problem_fingerprint(baseline_plan.problem), "Canonical fingerprint changed")
    baseline = baseline_plan.problem.model_dump(mode="json")
    require(len(baseline["inventory"]) == 4 and len(baseline["return_contents"]) == 3, "Unexpected physical pool")
    require(baseline["scenario"]["currency"] == "USD" and baseline["scenario"]["labor_capacity_minutes"] == 60, "Unexpected economic scope")
    require(len(baseline["scenario"]["kits"]) == 1 and baseline["scenario"]["kits"][0]["demand_limit"] == 2, "Unexpected kit demand")
    require(report["domain"] == {
        "field": "scenario.labor_cost_per_minute_cents", "minimum": 0, "maximum": 200, "step": 1,
        "currency": "USD", "input_unit": "integer cents per minute", "all_other_problem_fields_identical": True,
    }, "Unexpected sensitivity domain")
    require(report["candidate_count"] == 19 and report["distinct_value_labor_lines"] == 73, "Unexpected sensitivity candidates")
    covers = report["all_feasible_covers"]
    require(report["feasible_complete_cover_count"] == len(covers) == 210, "Incomplete allocation evidence")
    require(len({tuple(c["action_ids"]) for c in covers}) == 210, "Duplicate allocation evidence")
    require(report["cp_sat_solve_count"] == len(report["runs"]) == 201, "Incomplete sensitivity sweep")
    require(report["all_solves_optimal_and_match_oracle"] is True, "Unverified sensitivity sweep")
    selected_sensitivity = []
    for rate, row in enumerate(report["runs"]):
        require(row["labor_cost_per_minute_cents"] == rate, "Missing or duplicated labor rate")
        require(row["only_labor_rate_changed"] is True and row["candidate_set_unchanged"] is True and row["candidate_economics_match_affine_model"] is True, "Unverified sensitivity input scope")
        plan = checked_plan(row)
        restored = plan.problem.model_dump(mode="json")
        restored["scenario"]["labor_cost_per_minute_cents"] = 25
        require(restored == baseline, "Sensitivity changed unrelated inputs")
        values = [cover["value_intercept_cents"] - rate * cover["labor_minutes"] for cover in covers]
        winners = [index for index, value in enumerate(values) if value == max(values)]
        require(row["oracle_optimal_cover_indexes"] == winners and plan.modeled_value_cents == max(values), "Incomplete or incorrect tie evidence")
        require(sorted(a.action_id for a in plan.selected_actions) in [covers[i]["action_ids"] for i in winners], "Selected allocation is not a recorded optimum")
        if rate in (169, 170, 171):
            rebuild_values = {values[i] for i, cover in enumerate(covers) if cover["action_counts"] == {"rebuild": 2}}
            liquidation_values = {values[i] for i, cover in enumerate(covers) if cover["action_counts"] == {"liquidate": 3}}
            require(rebuild_values == {19000 - 60 * rate} and liquidation_values == {10500 - 10 * rate}, "Supporting comparison differs from recorded complete covers")
            selected_sensitivity.append({
                "rate_cents": rate, "rebuild_cents": next(iter(rebuild_values)),
                "liquidate_cents": next(iter(liquidation_values)), "optimum_cents": plan.modeled_value_cents,
                "optimal_physical_allocations": len(winners), "input_hash": plan.input_hash,
                "status": plan.status.value, "best_bound_cents": plan.best_bound_cents,
                "absolute_gap_cents": plan.absolute_gap_cents,
                "receipt_pointer": f"/runs/{rate}",
            })
    require([r["optimal_physical_allocations"] for r in selected_sensitivity] == [2, 3, 1], "Expected physical ties not retained")
    research = report["conditional_evidence_research"]
    require(research["status"] == "passed" and research["new_human_assertions"] == research["store_writes"] == 0, "Conditional authority boundary changed")
    require(research["probabilities_used"] is False and len(research["runs"]) == 6, "Expected six nonprobabilistic recorded states")
    require(canonical["correction"]["physical_component_id"] == SUBJECT, "Unexpected correction subject")
    require(canonical["correction"]["prior_compatibility"]["compatible"] is False, "Historical B compatibility changed")
    require(canonical["correction"]["corrected_compatibility"]["compatible"] is True, "Corrected A compatibility changed")
    subject_index = next(i for i, item in enumerate(baseline["inventory"]) if item["component"]["physical_component_id"] == SUBJECT)
    rows = []
    seen = set()
    for index, row in enumerate(research["runs"]):
        key = (row["labor_cost_per_minute_cents"], row["branch"])
        require(key in EXPECTED and key not in seen, "Unexpected or duplicated conditional branch")
        seen.add(key)
        rate, branch = key
        snapshot, eligibility, version, state, revision = BRANCHES[branch]
        pointer = f"/correction/{snapshot}/current"
        require(row["source_json_pointer"] == pointer and row["physical_component_id"] == SUBJECT, "Conditional source pointer changed")
        require(row["hypothetical_planning_snapshot"] is True and row["only_subject_evidence_eligibility_and_rate_changed"] is True, "Conditional input boundary changed")
        require(row["feasible_complete_cover_count"] == {"historical_scripted_B": 184, "review_required_held": 46, "corrected_scripted_A": 210}[branch], "Conditional allocation evidence changed")
        plan = checked_plan(row)
        payload = plan.problem.model_dump(mode="json")
        item = payload["inventory"][subject_index]
        require(item["evidence"] == canonical["correction"][snapshot]["current"], "Conditional evidence is not the saved state")
        require(item["eligibility"] == eligibility and item["evidence"]["state"] == state, "Conditional eligibility changed")
        require(item["evidence"]["version"] == version and item["evidence"]["verification"]["identity"]["revision"] == revision, "Conditional identity or evidence version changed")
        payload["inventory"][subject_index] = deepcopy(baseline["inventory"][subject_index])
        payload["scenario"]["labor_cost_per_minute_cents"] = 25
        require(payload == baseline, "Conditional comparison changed unrelated fields")
        cash, retained, counts = EXPECTED[key]
        require(plan.cash_recovery_cents == cash and plan.retained_value_cents == retained, "Conditional cash/noncash values changed")
        require(dict(Counter(a.kind.value for a in plan.selected_actions)) == counts, "Conditional allocation changed")
        if eligibility == "held":
            require(all(a.kind == "hold" for a in plan.selected_actions if SUBJECT in a.component_ids), "Held subject was consumed")
        rows.append({
            "branch": branch, "rate_cents": rate, "version": version, "evidence_state": state,
            "revision_assertion": revision, "eligibility": eligibility, "cash_cents": cash,
            "retained_cents": retained, "modeled_total_cents": plan.modeled_value_cents,
            "action_counts": counts, "selected_actions": [a.model_dump(mode="json") for a in plan.selected_actions],
            "input_hash": plan.input_hash, "source_json_pointer": pointer,
            "receipt_pointer": f"/conditional_evidence_research/runs/{index}",
            "status": plan.status.value, "best_bound_cents": plan.best_bound_cents,
            "absolute_gap_cents": plan.absolute_gap_cents, "solver_version": plan.solver_version,
            "labor_minutes": plan.labor_minutes, "feasible_complete_cover_count": row["feasible_complete_cover_count"],
        })
    return {"subject": SUBJECT, "synthetic": True, "read_only": True, "rows": rows, "sensitivity": selected_sensitivity}


def unlinked(path: Path) -> None:
    require(not any(p.is_symlink() or (p.exists() and getattr(p.lstat(), "st_file_attributes", 0) & 1024)
                    for p in (path, *path.parents) if p != p.parent), "Path must not traverse links or reparse points")


def authenticated_file(relative: str, digest: str) -> bytes:
    path = ROOT / relative
    unlinked(path)
    raw = path.read_bytes()
    require(sha256(raw).hexdigest() == digest, f"Frozen source hash mismatch: {relative}")
    return raw


def frozen_inputs() -> tuple[dict, dict[str, bytes]]:
    sensitivity_bytes = authenticated_file(SENSITIVITY, SENSITIVITY_SHA256)
    canonical_bytes = authenticated_file(CANONICAL, CANONICAL_SHA256)
    analysis = authenticated_file(ANALYSIS_SOURCE, ANALYSIS_SHA256)
    report, canonical = json.loads(sensitivity_bytes), json.loads(canonical_bytes)
    require(report["analysis_source_sha256"] == ANALYSIS_SHA256, "Analysis-source identity mismatch")
    require(report["source"]["receipt"] == CANONICAL and report["source"]["receipt_sha256"] == CANONICAL_SHA256, "Canonical source binding changed")
    require(report["source"]["baseline_problem_fingerprint"] == canonical["baseline_plan"]["plan"]["input_hash"], "Baseline source binding changed")
    data = validate_receipts(report, canonical)
    files = {
        "sources/block-d-receipt.json": sensitivity_bytes, "sources/canonical-receipt.json": canonical_bytes,
        "sources/run_canonical_sensitivity.py": analysis,
        "sources/recovery-plan.schema.json": json_bytes(RecoveryPlan.model_json_schema()),
        "sources/recovery-models.py": (ROOT / "backend/src/rekit/recovery/models.py").read_bytes(),
    }
    for fixture, key in zip(FIXTURES, ("fixture_sha256", "original_fixture_sha256"), strict=True):
        require(report["source"]["fixtures"][fixture] == canonical[key], "Fixture source binding changed")
        files["sources/" + Path(fixture).name] = authenticated_file(fixture, canonical[key])
    originals = []
    for view in (1, 2, 3):
        filename = f"{SUBJECT}-view-{view}.png"
        records = [r for r in canonical["image_provenance"] if r["source"]["filename"] == filename]
        require(len(records) == 1, "Original diagram provenance is ambiguous")
        record = records[0]
        require(record["source"]["sha256"] == record["asset"]["sha256"] and record["source"]["physical_component_id"] == SUBJECT, "Original diagram provenance changed")
        raw = authenticated_file(str(Path(CANONICAL).parent / "original-images" / filename), record["source"]["sha256"])
        require(len(raw) == record["asset"]["byte_size"], "Original diagram size changed")
        files[f"original-images/{filename}"] = raw
        originals.append(record)
    data["original_images"] = originals
    data["sources"] = {"sensitivity_sha256": SENSITIVITY_SHA256, "canonical_sha256": CANONICAL_SHA256, "analysis_sha256": ANALYSIS_SHA256}
    return data, files


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def usd(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def state_card(row: dict) -> str:
    branch = row["branch"]
    title, badge, policy, eligibility = {
        "historical_scripted_B": ("Historical B", "Scripted assertion · version 4", "B fails the approved A-only rebuild rule.", "Eligible for other permitted dispositions; not this rebuild."),
        "review_required_held": ("Review required", "Added close-up · version 5", "The old B assertion remains in history. No fresh identity has been verified.", "Held. Adapter 002 cannot be rebuilt, liquidated, salvaged or retained as an eligible donor."),
        "corrected_scripted_A": ("Corrected A", "Scripted correction · version 6", "A satisfies the approved revision rule.", "Eligible for permitted choices after scripted human verification; this does not select a plan."),
    }[branch]
    patterns = {
        (25, "historical_scripted_B"): "1 rebuild · liquidate adapter 002 · retain 1 body",
        (25, "review_required_held"): "1 rebuild · retain 1 body · hold adapter 002",
        (25, "corrected_scripted_A"): "2 rebuilds",
        (200, "historical_scripted_B"): "Liquidate all 3 returns",
        (200, "review_required_held"): "Liquidate 2 returns · hold adapter 002",
        (200, "corrected_scripted_A"): "Liquidate all 3 returns",
    }
    alternatives = "Equal-value body/adapter pairings can exist; the solver's selected physical pairing is not uniquely preferable." if row["rate_cents"] == 25 else "The displayed optimum is conditional on this saved state and the fixed assumptions."
    return f'''<article class="state-card {branch}" data-state="{branch}" data-rate="{row['rate_cents']}">
      <p class="eyebrow">{badge}</p><h3>{title}</h3>
      <div class="rule"><h4>Rebuild compatibility</h4><p>{policy}</p><h4>Permission to use the component</h4><p>{eligibility}</p></div>
      <div class="allocation"><span class="eyebrow">Globally optimal allocation</span><p class="pattern">{patterns[(row['rate_cents'], branch)]}</p>
      <p class="value" data-total-cents="{row['modeled_total_cents']}">{usd(row['modeled_total_cents'])}</p><p class="value-label">Modeled total · USD</p>
      <dl class="values"><div><dt>Estimated cash</dt><dd data-cash-cents="{row['cash_cents']}">{usd(row['cash_cents'])}</dd></div><div><dt>Retained noncash value</dt><dd data-retained-cents="{row['retained_cents']}">{usd(row['retained_cents'])}</dd></div></dl></div>
      <p class="small">{alternatives}</p>
      <details><summary>Recorded solve and physical allocation</summary><p>CP-SAT {escape(row['solver_version'])} · {row['status']} · bound {usd(row['best_bound_cents'])} · gap {usd(row['absolute_gap_cents'])}. {row['feasible_complete_cover_count']} feasible allocations checked in Block D. Selected labor: {row['labor_minutes']} minutes.</p><p>Input fingerprint <code>{row['input_hash']}</code></p><p>Canonical source <code>{row['source_json_pointer']}</code></p><p>Block D result <code>{row['receipt_pointer']}</code></p><pre>{escape(json.dumps(row['selected_actions'], indent=2))}</pre></details>
    </article>'''


def render_files(data: dict) -> dict[str, bytes]:
    css = (ASSETS / "decision-evidence-demo.css").read_text(encoding="utf-8")
    script = (ASSETS / "decision-evidence-demo.js").read_text(encoding="utf-8")
    panels = []
    for rate in (25, 200):
        conclusion = ("At low labor cost, the A correction changes the best allocation: two rebuilds become possible and optimal."
                      if rate == 25 else "At high labor cost, A changes rebuild compatibility, but B and A have the same best decision: liquidate all three returns.")
        cards = "".join(state_card(next(r for r in data["rows"] if r["rate_cents"] == rate and r["branch"] == b)) for b in BRANCHES)
        panels.append(f'<section id="rate-panel-{rate}" class="rate-panel" aria-labelledby="labor-{rate}"{(" hidden" if rate == 200 else "")}><p class="conclusion">{conclusion}</p><div class="cards">{cards}</div></section>')
    sources = data["sources"]
    proof = f'''<details id="source-proof"><summary>Inspect the saved evidence and integrity checks</summary><p>All six conditional results and all 201 sweep runs were saved in Block D. This page selects recorded results; it does not run CP-SAT. The exact-cover cross-check shares candidate generation and assumptions with the planner, so it is not independent verification of policy or business truth.</p><ul><li><a href="sources/block-d-receipt.json">Full Block D receipt: 201 sweep + 6 conditional solves</a><br><code>{sources['sensitivity_sha256']}</code></li><li><a href="sources/canonical-receipt.json">Original canonical receipt: evidence history and scripted correction</a><br><code>{sources['canonical_sha256']}</code></li><li><a href="sources/run_canonical_sensitivity.py">Exact analysis source</a><br><code>{sources['analysis_sha256']}</code></li><li><a href="sources/recovery-plan.schema.json">RecoveryPlan schema</a> · <a href="sources/recovery-models.py">Schema source</a> · <a href="data.json">Compact presentation data and image provenance</a> · <a href="manifest.json">Package hashes</a> · <a href="validation.json">Build checks</a></li></ul><p>Trust boundary: frozen source hashes and current schemas are checked by the local builder. Run the documented <code>--check</code> command before review to detect modified files. Opening this HTML does not reauthenticate the package or establish current inventory availability.</p></details>'''
    template = (ASSETS / "decision-evidence-demo.html").read_text(encoding="utf-8")
    main = template.replace("@@STYLE@@", css).replace("@@PANELS@@", "".join(panels)).replace("@@PROOF@@", proof).replace("@@SCRIPT@@", script)
    rows = []
    for row in data["sensitivity"]:
        rate = row["rate_cents"]
        outcome = {169: "Two rebuilds", 170: "Tie: rebuild or liquidate", 171: "Liquidate all 3 returns"}[rate]
        rows.append(f'''<article class="frontier-card" data-rate="{rate}"><p class="eyebrow">Labor per minute</p><h2>{usd(rate)}</h2><dl class="frontier-values"><div><dt>Two rebuilds</dt><dd>{usd(row['rebuild_cents'])}</dd></div><div><dt>All-return liquidation</dt><dd>{usd(row['liquidate_cents'])}</dd></div></dl><p class="frontier-outcome">{outcome}</p><p>{row['optimal_physical_allocations']} optimal physical allocation{'s' if row['optimal_physical_allocations'] != 1 else ''}</p><details><summary>Saved solve proof</summary><p>{row['status']} · bound {usd(row['best_bound_cents'])} · gap {usd(row['absolute_gap_cents'])}</p><code>{row['receipt_pointer']}<br>{row['input_hash']}</code></details></article>''')
    supplement = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'; connect-src 'none'"><title>ReKit · three tested labor rates</title><style>{css}</style></head><body><main class="shell"><a class="back" href="index.html">← Return to the evidence comparison</a><header><p class="eyebrow">Optional supporting evidence · synthetic estimates</p><h1>Three tested points around the tie</h1><p class="lead">The same corrected A inventory. Only labor cost changes.</p></header><div id="sensitivity-visual" class="frontier">{''.join(rows)}</div><aside class="boundary"><h2>A global comparison, not just two intersecting lines</h2><p>Block D checked all <strong>210 feasible allocations</strong>, including mixed dispositions, at all <strong>201 integer rates from $0.00 to $2.00/minute</strong>. These three cards are actual saved runs.</p><p>At $1.70, both possible two-kit pairings and one all-return liquidation allocation tie at $88.00. No single physical pairing is uniquely best.</p></aside><section><h2>Keep the economic claim bounded</h2><p>Two rebuilds use 60 labor minutes; all-return liquidation uses 10. Their modeled totals in cents are <code>19000 − 60r</code> and <code>10500 − 10r</code>, where <code>r</code> is cents per minute. The all-allocation cross-check establishes the optimum only within the tested integer domain.</p><p>Invented scenario inputs. This is not a measured market threshold, revenue increase or value of an additional photograph. The seven-slide deck is unchanged; this supplemental page is for optional deeper explanation.</p></section>{proof}<footer>Offline supporting artifact · no inference, approvals or inventory writes · AMD execution pending</footer></main></body></html>'''
    return {"index.html": main.encode("utf-8"), "sensitivity.html": supplement.encode("utf-8"), "data.json": json_bytes(data)}


def package_files() -> dict[str, bytes]:
    data, files = frozen_inputs()
    files.update(render_files(data))
    files["validation.json"] = json_bytes({
        "status": "passed", "frozen_sources_authenticated": True, "conditional_rows": 6,
        "saved_sweep_runs_validated": 201, "saved_complete_allocations": 210,
        "original_diagrams_copied_byte_for_byte": 3, "new_solver_calls": 0,
        "inference_requests": 0, "application_writes": 0, "browser_storage": False,
        "human_usability_review": "pending", "production_integration": False,
    })
    files["README.txt"] = (
        "ReKit Block E: offline recorded decision evidence\n\n"
        "Open index.html directly in Chrome or Edge. No server, installation or sign-in is required.\n"
        "Choose $0.25/min and $2.00/min, compare all three states, then inspect the original views and source proof.\n"
        "sensitivity.html is a separate optional supporting visual; it is not inserted in the seven-slide deck.\n"
        "Tab to either labor button and press Enter or Space. Buttons preserve focus and expose aria-pressed.\n"
        "Before review, from the repository root run:\n"
        "  .venv\\Scripts\\python.exe -B evaluation/build_decision_evidence_demo.py --check <this-directory>\n\n"
        "The check authenticates the fixed original sources and regenerates expected package bytes in memory.\n"
        "A changed or incomplete package fails closed in that CLI. Opening HTML alone does not verify hashes.\n"
        "No network, browser storage, database connection, model inference, solver call or operational action occurs.\n"
        "The only interactions select already recorded assumptions and expand evidence.\n"
        "This package contains synthetic nonsecret evidence in an ignored local directory. The builder does not set private ACLs.\n"
        "All identities are scripted assertions. Historical B was deliberately wrong. These are not independent judgments.\n"
        "Do not infer probabilities, expected information value, actual revenue increases, capture recommendations,\n"
        "hidden functional or safety properties, or current availability. Human verification and approvals remain separate.\n"
    ).encode("utf-8")
    manifest = {
        "format_version": 1, "kind": "offline-read-only-synthetic-decision-evidence",
        "builder_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
        "template_sha256": {p.name: sha256(p.read_bytes()).hexdigest() for p in sorted(ASSETS.glob("decision-evidence-demo.*"))},
        "files": {name: {"sha256": sha256(raw).hexdigest(), "bytes": len(raw)} for name, raw in sorted(files.items())},
    }
    files["manifest.json"] = json_bytes(manifest)
    return files


def allowed_directory(output: Path) -> Path:
    unlinked(output)
    resolved = output.resolve()
    allowed = (ROOT / "var/mission06-offline").resolve()
    require(resolved != allowed and resolved.is_relative_to(allowed), "Output must be under var/mission06-offline")
    require(resolved.name.startswith("block-e-decision-demo-"), "Output must use the block-e-decision-demo- prefix")
    return resolved


def write_package(output: Path, files: dict[str, bytes]) -> None:
    output = allowed_directory(output)
    output.mkdir(parents=True, exist_ok=False)
    for relative, raw in sorted(files.items()):
        target = output / relative
        require(not Path(relative).is_absolute() and target.resolve().is_relative_to(output), "Unsafe package filename")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)


def check_package(output: Path, expected: dict[str, bytes]) -> None:
    output = allowed_directory(output)
    require(output.is_dir(), "Package directory is missing")
    actual = set()
    for path in output.rglob("*"):
        unlinked(path)
        if path.is_file():
            relative = path.relative_to(output).as_posix()
            actual.add(relative)
            require(relative in expected and path.read_bytes() == expected[relative], f"Package file changed: {relative}")
    require(actual == set(expected), "Package is incomplete")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--output", type=Path, help="New block-e-decision-demo-* directory under var/mission06-offline")
    mode.add_argument("--check", type=Path, help="Verify the complete package without writing")
    args = parser.parse_args()
    output = args.output or args.check
    allowed_directory(output)
    if args.output and output.exists():
        parser.error("Output exists; preserve the previous artifact")
    files = package_files()
    if args.output:
        write_package(output, files)
    check_package(output, files)
    print(json.dumps({"status": "passed", "mode": "check" if args.check else "build", "directory": str(output), "files": len(files), "conditional_results": 6, "new_solver_calls": 0, "inference_requests": 0}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
