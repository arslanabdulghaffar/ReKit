"""Recorded decision evidence fails closed and cannot acquire operational authority."""

import asyncio
from copy import deepcopy
from hashlib import sha256
from importlib.util import module_from_spec, spec_from_file_location
import os
from pathlib import Path
import socket
import subprocess
import sys

import pytest

from rekit.recovery.models import RecoveryPlan
from rekit.recovery import planner


ROOT = Path(__file__).parents[2]


def load(name: str, filename: str):
    specification = spec_from_file_location(name, ROOT / "evaluation" / filename)
    module = module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


case = load("canonical_case", "canonical_case.py")
sys.modules.setdefault("canonical_case", case)
runner = load("decision_demo_canonical_runner", "run_canonical_case.py")
sensitivity = load("decision_demo_sensitivity", "run_canonical_sensitivity.py")
demo = load("decision_demo", "build_decision_evidence_demo.py")


@pytest.fixture(scope="module")
def recorded():
    # Portable CI source: no dependency on ignored owner evidence or cloud access.
    canonical = asyncio.run(runner.run_case())
    problem = RecoveryPlan.model_validate(canonical["baseline_plan"]["plan"]).problem
    report = sensitivity.analyze(problem)
    report["conditional_evidence_research"] = sensitivity.compare_evidence_branches(problem, canonical)
    return report, canonical


def test_all_six_recorded_results_preserve_cash_noncash_and_authority(recorded):
    report, canonical = recorded
    before = deepcopy(recorded)
    data = demo.validate_receipts(report, canonical)
    rows = {(r["rate_cents"], r["branch"]): r for r in data["rows"]}
    assert len(rows) == 6
    assert [rows[(25, b)]["modeled_total_cents"] for b in demo.BRANCHES] == [10775, 9350, 17500]
    assert [rows[(200, b)]["modeled_total_cents"] for b in demo.BRANCHES] == [8500, 7600, 8500]
    assert rows[(25, "historical_scripted_B")]["cash_cents"] == 10175
    assert rows[(25, "historical_scripted_B")]["retained_cents"] == 600
    assert rows[(25, "review_required_held")]["evidence_state"] == "review_required"
    assert rows[(200, "corrected_scripted_A")]["action_counts"] == rows[(200, "historical_scripted_B")]["action_counts"]
    assert recorded == before


def test_supporting_visual_retains_all_three_physical_allocations_at_tie(recorded):
    points = demo.validate_receipts(*recorded)["sensitivity"]
    assert [(p["rate_cents"], p["rebuild_cents"], p["liquidate_cents"], p["optimal_physical_allocations"]) for p in points] == [
        (169, 8860, 8810, 2), (170, 8800, 8800, 3), (171, 8740, 8790, 1),
    ]
    assert all(p["status"] == "OPTIMAL" and p["absolute_gap_cents"] == 0 for p in points)


@pytest.mark.parametrize("change,match", [
    (lambda r, c: r["runs"][169]["plan"].update(input_hash="0" * 64), "fingerprint"),
    (lambda r, c: r["runs"][170]["plan"].update(status="FEASIBLE"), "proven optimal"),
    (lambda r, c: r["runs"][170]["plan"].update(best_bound_cents=8801), "bound disagree"),
    (lambda r, c: r["runs"][170].update(oracle_optimal_cover_indexes=r["runs"][170]["oracle_optimal_cover_indexes"][:1]), "tie evidence"),
    (lambda r, c: r["runs"].pop(), "Incomplete sensitivity"),
    (lambda r, c: r["conditional_evidence_research"]["runs"][1].update(source_json_pointer="/correction/after/current"), "source pointer"),
    (lambda r, c: r["conditional_evidence_research"]["runs"].__setitem__(1, deepcopy(r["conditional_evidence_research"]["runs"][0])), "duplicated conditional"),
    (lambda r, c: c["correction"]["before_correction"]["current"].update(state="verified"), "not the saved state"),
])
def test_modified_or_incomplete_evidence_cannot_be_labeled_verified(recorded, change, match):
    report, canonical = deepcopy(recorded)
    change(report, canonical)
    with pytest.raises(ValueError, match=match):
        demo.validate_receipts(report, canonical)


def test_builder_validation_uses_no_solver_or_network(recorded, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Offline artifact attempted a solver or network operation")
    monkeypatch.setattr(planner, "solve_recovery", forbidden)
    monkeypatch.setattr(socket, "socket", forbidden)
    data = demo.validate_receipts(*recorded)
    assert data["read_only"] is True


def test_frozen_loader_authenticates_before_parsing_and_never_accepts_arbitrary_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "ROOT", tmp_path)
    source = tmp_path / demo.SENSITIVITY
    source.parent.mkdir(parents=True)
    source.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="Frozen source hash mismatch"):
        demo.frozen_inputs()


def test_frozen_loader_binds_analysis_fixture_and_original_image_bytes(recorded, tmp_path, monkeypatch):
    report, canonical = deepcopy(recorded)
    report["analysis_source_sha256"] = demo.ANALYSIS_SHA256
    report["source"] = {
        "receipt": demo.CANONICAL, "baseline_problem_fingerprint": canonical["baseline_plan"]["plan"]["input_hash"],
        "fixtures": dict(zip(demo.FIXTURES, (canonical["fixture_sha256"], canonical["original_fixture_sha256"]), strict=True)),
    }
    canonical_raw = demo.json_bytes(canonical)
    report["source"]["receipt_sha256"] = sha256(canonical_raw).hexdigest()
    report_raw = demo.json_bytes(report)
    # Pin the disposable fixture's hashes; the production CLI exposes no override.
    monkeypatch.setattr(demo, "ROOT", tmp_path)
    monkeypatch.setattr(demo, "CANONICAL_SHA256", sha256(canonical_raw).hexdigest())
    monkeypatch.setattr(demo, "SENSITIVITY_SHA256", sha256(report_raw).hexdigest())
    files = {demo.CANONICAL: canonical_raw, demo.SENSITIVITY: report_raw,
             demo.ANALYSIS_SOURCE: (ROOT / demo.ANALYSIS_SOURCE).read_bytes(),
             "backend/src/rekit/recovery/models.py": (ROOT / "backend/src/rekit/recovery/models.py").read_bytes()}
    files.update({name: (ROOT / name).read_bytes() for name in demo.FIXTURES})
    for image in case.source_images():
        filename = str(Path(demo.CANONICAL).parent / "original-images" / image["filename"])
        files[filename] = image["bytes"]
    for relative, raw in files.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    data, copied = demo.frozen_inputs()
    assert len(data["original_images"]) == 3
    image_name = f"original-images/{demo.SUBJECT}-view-3.png"
    original = tmp_path / Path(demo.CANONICAL).parent / image_name
    assert copied[image_name] == original.read_bytes()
    original.write_bytes(original.read_bytes() + b"tampered")
    with pytest.raises(ValueError, match="Frozen source hash mismatch"):
        demo.frozen_inputs()


def test_render_is_offline_and_separates_history_compatibility_eligibility_and_allocation(recorded):
    data = demo.validate_receipts(*recorded)
    data["sources"] = {"sensitivity_sha256": demo.SENSITIVITY_SHA256, "canonical_sha256": demo.CANONICAL_SHA256, "analysis_sha256": demo.ANALYSIS_SHA256}
    files = demo.render_files(data)
    html = files["index.html"].decode()
    assert "deliberately wrong, scripted B assertion" in html
    assert "The old B assertion remains in history. No fresh identity has been verified." in html
    assert "The unchanged economic choice never waives review." in html
    assert html.count('class="state-card ') == 6
    assert 'id="labor-25"' in html and 'id="labor-200"' in html
    assert 'connect-src &#x27;none&#x27;' not in html  # CSP is real markup, not escaped display text.
    assert "connect-src 'none'" in html
    assert "fetch(" not in html and "localStorage" not in html and "http://" not in html and "https://" not in html
    assert "170" in files["sensitivity.html"].decode()
    assert "2 rebuilds" in html and "Liquidate all 3 returns" in html


def test_output_rejects_overwrite_outside_root_tampering_and_added_files(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "ROOT", tmp_path)
    output = tmp_path / "var/mission06-offline/block-e-decision-demo-test"
    files = {"index.html": b"recorded evidence", "sources/receipt.json": b"{}"}
    demo.write_package(output, files)
    demo.check_package(output, files)
    with pytest.raises(FileExistsError):
        demo.write_package(output, files)
    with pytest.raises(ValueError, match="under var/mission06-offline"):
        demo.write_package(tmp_path / "public/block-e-decision-demo-test", files)
    (output / "index.html").write_bytes(b"changed evidence")
    with pytest.raises(ValueError, match="Package file changed"):
        demo.check_package(output, files)
    (output / "index.html").write_bytes(files["index.html"])
    (output / "unexpected.html").write_bytes(b"extra")
    with pytest.raises(ValueError, match="Package file changed"):
        demo.check_package(output, files)


def test_linked_output_or_package_member_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "ROOT", tmp_path)
    target = tmp_path / "elsewhere"
    target.mkdir()
    link = tmp_path / "var/mission06-offline/block-e-decision-demo-link"
    link.parent.mkdir(parents=True)
    if os.name == "nt":
        # NTFS junctions do not require the symbolic-link privilege on Windows.
        subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(target)], check=True, capture_output=True)
    else:
        link.symlink_to(target, target_is_directory=True)
    try:
        with pytest.raises(ValueError, match="links or reparse"):
            demo.write_package(link, {"index.html": b"must not be written"})
        assert not list(target.iterdir())
    finally:
        # Remove only our link, never its target directory or any target contents.
        if os.name == "nt":
            link.rmdir()
        else:
            link.unlink()
