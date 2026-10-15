"""Bounded CPU-only investigation of the preserved Block D Windows native crash.

This diagnostic never repairs the environment, invokes inference, or writes
application state. Each workload runs in a fresh subprocess. Its output belongs
under the ignored offline evidence directory, not in a public submission.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from hashlib import sha256
from importlib import metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv/Scripts/python.exe"
SCRIPT = Path(__file__).resolve()
TARGET = "tests/backend/test_canonical_sensitivity.py::test_zero_time_solver_status_cannot_be_presented_as_verified_frontier"
PER_CHILD_SECONDS = 120
MATRIX_SECONDS = 480
VALIDATION_BATCHES = 1000
LOOP_SOLVES = 25
SOURCE_FILES = (
    "evaluation/investigate_native_crash.py",
    "evaluation/run_canonical_sensitivity.py",
    "tests/backend/test_canonical_sensitivity.py",
    "backend/src/rekit/recovery/planner.py",
    "backend/src/rekit/recovery/models.py",
    "pyproject.toml",
)
PRIOR_FILES = (
    "var/mission06-offline/canonical-case-b1-first/receipt.json",
    "var/mission06-offline/block-d-validation-20261015-224752-f4e5f3/backend-pytest.log",
    "var/mission06-offline/block-d-validation-20261015-224752-f4e5f3/validation.json",
    "var/mission06-offline/block-d-validation-20261015-224752-f4e5f3/validation-fresh.json",
)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def hashes(names: tuple[str, ...]) -> dict[str, str]:
    return {name: digest(ROOT / name) for name in names}


def new_output(path: Path) -> Path:
    """Create a new directory inside the ignored root; refuse replacement/escape."""
    output = path.resolve()
    allowed = (ROOT / "var/mission06-offline").resolve()
    if output == allowed or not output.is_relative_to(allowed):
        raise ValueError("Output must be a new directory under var/mission06-offline")
    output.mkdir(parents=True, exist_ok=False)
    return output


def emit(value: dict) -> None:
    print(json.dumps(value, sort_keys=True), flush=True)


def environment() -> dict:
    packages = {}
    native_files = []
    for name in ("pydantic", "pydantic-core", "ortools", "protobuf", "numpy", "pandas", "pytest"):
        dist = metadata.distribution(name)
        packages[name] = dist.version
        if name in {"pydantic-core", "ortools"}:
            for relative in sorted(dist.files or [], key=str):
                if Path(relative).suffix.lower() in {".pyd", ".dll"}:
                    actual = Path(dist.locate_file(relative)).resolve()
                    native_files.append({"distribution": name, "distribution_path": str(relative), "sha256": digest(actual)})
    return {
        "python": platform.python_version(), "implementation": platform.python_implementation(),
        "system": platform.system(), "release": platform.release(), "version": platform.version(),
        "machine": platform.machine(), "pointer_bits": 64 if sys.maxsize > 2**32 else 32,
        "python_executable_sha256": digest(Path(sys.executable)),
        "packages": packages, "native_files": native_files,
        "diagnostic_flags": {"dont_write_bytecode": sys.dont_write_bytecode, "xoptions": sys._xoptions},
        "solver_settings": {"num_search_workers": 1, "random_seed": 0, "normal_time_limit_seconds": 10.0, "zero_time_limit_seconds": 0.0},
        "environment_variables_collected": False, "torch_imported": False,
    }


def worker(mode: str) -> dict:
    if mode == "environment":
        return environment()

    import run_canonical_sensitivity as sensitivity
    from rekit.recovery.models import RecoveryAction, RecoveryProblem, SolverSettings
    from rekit.recovery.planner import generate_candidates, problem_fingerprint, solve_recovery

    problem, provenance = sensitivity.load_frozen_problem()
    original = problem_fingerprint(problem)
    payload = problem.model_dump(mode="json")
    result = {"mode": mode, "source": provenance}
    if mode == "model-validation":
        actions = [a.model_dump(mode="python") for a in generate_candidates(problem).actions]
        for batch in range(VALIDATION_BATCHES):
            for value in actions:
                item = RecoveryAction(**value) if batch % 2 == 0 else RecoveryAction.model_validate(value)
                if item.model_dump(mode="python") != value:
                    raise AssertionError("Action validation changed the frozen candidate")
            if (batch + 1) % 100 == 0:
                emit({"progress": "validation", "batches_completed": batch + 1})
        result.update(batches=VALIDATION_BATCHES, actions_per_batch=len(actions), validations=VALIDATION_BATCHES * len(actions), cp_sat_solves=0)
    elif mode == "lifecycle":
        normal_solve = sensitivity.solve_recovery
        pass_summaries = []
        try:
            for pass_number in range(1, 4):
                def observed_solve(candidate):
                    rate = candidate.scenario.labor_cost_per_minute_cents
                    emit({"progress": "before_solve", "pass": pass_number, "rate": rate})
                    if pass_number == 3 and rate == 170:
                        return solve_recovery(candidate, SolverSettings(max_time_seconds=0.0))
                    return solve_recovery(candidate)

                sensitivity.solve_recovery = observed_solve
                analysis = sensitivity.analyze(problem)
                expected = "incomplete" if pass_number == 3 else "passed"
                if analysis["status"] != expected or analysis["cp_sat_solve_count"] != 201:
                    raise AssertionError("Unexpected sensitivity outcome")
                unknown = [r["labor_cost_per_minute_cents"] for r in analysis["runs"] if r["plan"]["status"] == "UNKNOWN"]
                if unknown != ([170] if pass_number == 3 else []):
                    raise AssertionError("Unexpected solver status")
                if pass_number == 3 and analysis["verified_integer_regimes"]:
                    raise AssertionError("Unverified frontier must remain withheld")
                pass_summaries.append({"pass": pass_number, "status": analysis["status"], "unknown_rates": unknown, "solves": 201})
        finally:
            sensitivity.solve_recovery = normal_solve
        result.update(passes=pass_summaries, cp_sat_solves=603)
    elif mode in {"solver-loop", "threaded"}:
        def loop(worker_number):
            local = RecoveryProblem.model_validate(payload)
            counts = {"OPTIMAL": 0, "UNKNOWN": 0}
            for index in range(LOOP_SOLVES):
                emit({"progress": "before_solve", "worker": worker_number, "iteration": index})
                zero = index == 12
                plan = solve_recovery(local, SolverSettings(max_time_seconds=0.0 if zero else 10.0))
                expected = "UNKNOWN" if zero else "OPTIMAL"
                if plan.status.value != expected:
                    raise AssertionError("Unexpected solver status")
                if not zero and plan.modeled_value_cents != 17500:
                    raise AssertionError("Changed frozen-case optimum")
                if zero and (plan.selected_actions or plan.modeled_value_cents is not None):
                    raise AssertionError("Zero-time solve must remain unverified")
                counts[expected] += 1
            if problem_fingerprint(local) != original:
                raise AssertionError("Solver mutated its problem")
            return {"worker": worker_number, "solves": LOOP_SOLVES, "statuses": counts}

        if mode == "threaded":
            with ThreadPoolExecutor(max_workers=2) as pool:
                loops = list(pool.map(loop, (1, 2)))
        else:
            loops = [loop(1)]
        result.update(workers=loops, cp_sat_solves=sum(x["solves"] for x in loops), shared_solver_objects=False)
    else:
        raise ValueError("Unknown worker mode")
    if problem_fingerprint(problem) != original:
        raise AssertionError("Diagnostic mutated the source problem")
    return {**result, "source_problem_unchanged": True, "inference_calls": 0, "application_store_writes": 0}


def child_command(*arguments: str) -> list[str]:
    return [str(PYTHON), "-B", "-X", "faulthandler", *arguments]


def run_child(name: str, command: list[str], output: Path, deadline: float) -> dict:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        return {"name": name, "status": "not_started_matrix_deadline", "command": command}
    started = time.monotonic()
    log = output / f"{name}.log"
    timeout = min(PER_CHILD_SECONDS, remaining)
    with log.open("xb") as stream:
        process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout=timeout)
            status = "passed" if code == 0 else "failed"
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            code, status = process.returncode, "timeout"
    return {
        "name": name, "status": status, "command": command,
        "returncode": code, "returncode_hex": f"0x{code & 0xFFFFFFFF:08X}",
        "elapsed_seconds": round(time.monotonic() - started, 3), "timeout_seconds": round(timeout, 3),
        "log": log.name, "log_sha256": digest(log),
    }


def run_spawn_pair(output: Path, deadline: float) -> list[dict]:
    """Two fresh Python processes; stop both owned children if either fails."""
    active = []
    results = []
    command = child_command(str(SCRIPT), "--worker", "solver-loop")
    try:
        for index in (1, 2):
            if time.monotonic() >= deadline:
                return [{"name": "spawn-pair", "status": "not_started_matrix_deadline"}]
            name = f"spawn-{index}"
            log = output / f"{name}.log"
            stream = log.open("xb")
            process = subprocess.Popen(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
            active.append((name, log, stream, process, time.monotonic()))
        while active:
            failed = False
            for row in list(active):
                name, log, stream, process, started = row
                code = process.poll()
                timed_out = time.monotonic() >= min(deadline, started + PER_CHILD_SECONDS)
                if code is None and not timed_out:
                    continue
                if code is None:
                    process.kill()
                    code = process.wait()
                stream.close()
                status = "timeout" if timed_out else ("passed" if code == 0 else "failed")
                results.append({"name": name, "status": status, "command": command, "returncode": code,
                                "returncode_hex": f"0x{code & 0xFFFFFFFF:08X}", "elapsed_seconds": round(time.monotonic() - started, 3),
                                "timeout_seconds": PER_CHILD_SECONDS, "log": log.name, "log_sha256": digest(log)})
                active.remove(row)
                failed = failed or status != "passed"
            if failed:
                break
            if active:
                time.sleep(0.05)
    finally:
        for name, log, stream, process, started in active:
            process.kill()
            code = process.wait()
            stream.close()
            results.append({"name": name, "status": "stopped_after_peer_failure", "command": command,
                            "returncode": code, "elapsed_seconds": round(time.monotonic() - started, 3),
                            "log": log.name, "log_sha256": digest(log)})
    return results


def matrix(path: Path) -> tuple[dict, int]:
    output = new_output(path)
    started = time.monotonic()
    deadline = started + MATRIX_SECONDS
    receipt = {
        "started_at": datetime.now(UTC).isoformat(), "purpose": "Unresolved Windows native crash investigation; not a fix",
        "source_checkpoint": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=10).strip(),
        "source_hashes_before": hashes(SOURCE_FILES), "preserved_evidence_before": hashes(PRIOR_FILES),
        "limits": {"per_child_seconds": PER_CHILD_SECONDS, "matrix_seconds": MATRIX_SECONDS,
                   "exact_pytest_repeats": 3, "collected_prefix_runs": 1, "sensitivity_passes": 3,
                   "validation_batches": VALIDATION_BATCHES, "thread_count": 2, "spawned_process_count": 2, "solves_per_thread_or_process": LOOP_SOLVES},
        "steps": [], "environment_modified": False, "application_runtime_modified": False,
        "inference_calls": 0, "network_requests": 0,
    }

    def checkpoint():
        # Only this newly created receipt is updated; every child log is exclusive.
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    def step(name, arguments):
        row = run_child(name, child_command(*arguments), output, deadline)
        receipt["steps"].append(row)
        checkpoint()
        emit({"step": name, "status": row["status"], "elapsed_seconds": row.get("elapsed_seconds")})
        return row["status"] == "passed"

    try:
        if not step("environment", [str(SCRIPT), "--worker", "environment"]):
            return receipt, 1
        for index in range(1, 4):
            if not step(f"exact-test-{index}", ["-m", "pytest", "-q", "-W", "error", TARGET]):
                return receipt, 1
        if not step("collect", ["-m", "pytest", "--collect-only", "-q"]):
            return receipt, 1
        nodes = [line.strip() for line in (output / "collect.log").read_text(encoding="utf-8", errors="replace").splitlines() if line.startswith("tests/") and "::" in line]
        prefix = nodes[:nodes.index(TARGET) + 1]
        if not 1 <= len(prefix) <= 400 or len(prefix) == len(nodes):
            raise ValueError("Collected prefix is not the bounded subset expected")
        receipt["collected_prefix"] = {"count": len(prefix), "full_collection_count": len(nodes), "nodes": prefix}
        prefix_command = ["-m", "pytest", "-q", "-W", "error", *prefix]
        if len(subprocess.list2cmdline(child_command(*prefix_command))) > 30000:
            raise ValueError("Prefix command exceeds conservative Windows length bound")
        if not step("collected-prefix", prefix_command):
            return receipt, 1
        for mode in ("model-validation", "lifecycle", "threaded"):
            if not step(mode, [str(SCRIPT), "--worker", mode]):
                return receipt, 1
        spawned = run_spawn_pair(output, deadline)
        receipt["steps"].extend(spawned)
        for row in spawned:
            emit({"step": row["name"], "status": row["status"], "elapsed_seconds": row.get("elapsed_seconds")})
        return receipt, 0 if all(x["status"] == "passed" for x in spawned) else 1
    finally:
        receipt["completed_at"] = datetime.now(UTC).isoformat()
        receipt["elapsed_seconds"] = round(time.monotonic() - started, 3)
        receipt["source_hashes_after"] = hashes(SOURCE_FILES)
        receipt["preserved_evidence_after"] = hashes(PRIOR_FILES)
        receipt["source_unchanged"] = receipt["source_hashes_before"] == receipt["source_hashes_after"]
        receipt["prior_evidence_unchanged"] = receipt["preserved_evidence_before"] == receipt["preserved_evidence_after"]
        complete = len(receipt["steps"]) == 11 and all(row["status"] == "passed" for row in receipt["steps"])
        receipt["status"] = "not_reproduced_in_bounded_matrix" if complete and receipt["source_unchanged"] and receipt["prior_evidence_unchanged"] else "incomplete_or_failed"
        receipt["root_cause_confirmed"] = False
        receipt["fix_claimed"] = False
        checkpoint()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--output", type=Path)
    group.add_argument("--worker", choices=("environment", "model-validation", "lifecycle", "solver-loop", "threaded"))
    args = parser.parse_args()
    if args.worker:
        emit({"result": worker(args.worker)})
        return 0
    receipt, code = matrix(args.output)
    emit({"status": receipt["status"], "output": str(args.output), "root_cause_confirmed": False, "fix_claimed": False})
    return code if receipt["status"] == "not_reproduced_in_bounded_matrix" else 1


if __name__ == "__main__":
    raise SystemExit(main())
