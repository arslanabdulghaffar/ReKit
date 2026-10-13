"""Runner reporting survives legacy consoles and cleans only its disposable state."""

from importlib.util import module_from_spec, spec_from_file_location
import io
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest


SCRIPT = Path(__file__).parents[2] / "evaluation" / "run_browser_acceptance.py"
specification = spec_from_file_location("rekit_browser_acceptance", SCRIPT)
runner = module_from_spec(specification)
specification.loader.exec_module(runner)


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """Use real temporary files but never launch a server, browser, or subprocess."""
    frontend = tmp_path / "frontend"
    for relative in ("vite/bin/vite.js", "@playwright/test/cli.js"):
        path = frontend / "node_modules" / relative
        path.parent.mkdir(parents=True)
        path.touch()
    run_dir = tmp_path / "run-owned"
    state = run_dir / "state"
    state.mkdir(parents=True)
    (state / "database.sqlite3").write_bytes(b"disposable synthetic state")
    screenshot = run_dir / "desktop.png"
    screenshot.write_bytes(b"safe screenshot marker")
    previous = tmp_path / "previous-run.txt"
    previous.write_text("preserve existing artifacts", encoding="utf-8")
    manifest = {
        "operator_token": "test-only-operator-secret",
        "viewer_token": "test-only-viewer-secret",
        "artifacts_dir": str(run_dir), "state_dir": str(state),
    }
    manifest_path = state / "fixture.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output = f"\u2718 browser failure \U0001f9ea {manifest['operator_token']} {manifest['viewer_token']}\n".encode("utf-8")

    class Process:
        def __init__(self, index):
            self.pid = 10000 + index
            self.returncode = 0
            self.communications = 0

        def communicate(self, *, timeout):
            self.communications += 1
            return output, None

    processes = [Process(index) for index in range(3)]
    started, stopped, environments = [], [], []

    def start(command, *, output, environment=None):
        process = processes[len(started)]
        started.append(process)
        environments.append(environment)
        return process

    monkeypatch.setattr(runner, "FRONTEND", frontend)
    monkeypatch.setattr(runner.shutil, "which", lambda name: "test-node")
    monkeypatch.setattr(runner, "_port_free", lambda port: None)
    monkeypatch.setattr(runner, "_prepare", lambda: (manifest_path, manifest))
    monkeypatch.setattr(runner, "_start", start)
    monkeypatch.setattr(runner, "_ready", lambda *arguments: None)
    monkeypatch.setattr(runner, "_stop", stopped.append)
    return SimpleNamespace(
        run_dir=run_dir, state=state, manifest=manifest, manifest_path=manifest_path,
        screenshot=screenshot, previous=previous, processes=processes,
        started=started, stopped=stopped, environments=environments, output=output,
    )


def read_result(sandbox):
    text = (sandbox.run_dir / "runner-result.json").read_text(encoding="utf-8")
    assert sandbox.manifest["operator_token"] not in text
    assert sandbox.manifest["viewer_token"] not in text
    return json.loads(text)


def assert_cleaned(sandbox, result):
    assert result["temporary_state_removed"] is True
    assert result["credentials_removed"] is True
    assert not sandbox.state.exists()
    assert not sandbox.manifest_path.exists()
    assert sandbox.screenshot.read_bytes() == b"safe screenshot marker"
    assert sandbox.previous.read_text(encoding="utf-8") == "preserve existing artifacts"


@pytest.mark.parametrize("exit_code,status", [(0, "passed"), (1, "failed")])
def test_cp949_console_preserves_exit_utf8_artifacts_redaction_and_cleanup(sandbox, monkeypatch, exit_code, status):
    sandbox.processes[2].returncode = exit_code
    captured = io.BytesIO()
    with io.TextIOWrapper(captured, encoding="cp949", errors="strict") as console:
        with monkeypatch.context() as patch:
            patch.setattr(runner.sys, "stdout", console)
            assert runner.run() == exit_code
        console.flush()
        rendered = captured.getvalue().decode("cp949")
    assert "\\u2718" in rendered
    assert "\\U0001f9ea" in rendered
    assert sandbox.manifest["operator_token"] not in rendered
    assert sandbox.manifest["viewer_token"] not in rendered
    log = (sandbox.run_dir / "browser.log").read_text(encoding="utf-8")
    assert "\u2718 browser failure \U0001f9ea" in log
    assert log.count("[REDACTED]") == 2
    result = read_result(sandbox)
    assert result["status"] == result["browser_status"] == status
    assert result["browser_exit_code"] == exit_code
    assert result["browser_run"] is True
    assert result["cleanup_errors"] == result["reporting_errors"] == []
    assert sandbox.stopped == list(reversed(sandbox.processes))
    assert all(environment["PYTHONIOENCODING"] == "utf-8:backslashreplace" for environment in sandbox.environments)
    assert_cleaned(sandbox, result)


def test_broken_console_cannot_override_browser_result_or_cleanup(sandbox, monkeypatch):
    class BrokenConsole:
        encoding = "utf-8"

        def write(self, value):
            raise BrokenPipeError("detached console")

    with monkeypatch.context() as patch:
        patch.setattr(runner.sys, "stdout", BrokenConsole())
        assert runner.run() == 0
    result = read_result(sandbox)
    assert result["status"] == "passed"
    assert_cleaned(sandbox, result)


def test_startup_failure_reports_sanitized_error_and_cleans_started_child(sandbox, monkeypatch):
    def unavailable(*arguments):
        raise RuntimeError(f"\u2718 startup {sandbox.manifest['operator_token']}")

    monkeypatch.setattr(runner, "_ready", unavailable)
    with pytest.raises(RuntimeError, match="startup") as error:
        runner.run()
    assert sandbox.manifest["operator_token"] not in str(error.value)
    result = read_result(sandbox)
    assert result["status"] == "error"
    assert result["browser_run"] is False
    assert result["browser_exit_code"] is None
    assert "[REDACTED]" in result["error"]
    assert sandbox.stopped == sandbox.processes[:1]
    assert_cleaned(sandbox, result)


def test_timeout_preserves_output_and_records_timeout_without_waiting(sandbox):
    browser = sandbox.processes[2]

    def communicate(*, timeout):
        browser.communications += 1
        if browser.communications == 1:
            assert timeout == 300
            raise subprocess.TimeoutExpired("test-browser", timeout, output=sandbox.output)
        assert timeout == 5
        return sandbox.output, None

    browser.communicate = communicate
    with pytest.raises(RuntimeError, match="300 second limit"):
        runner.run()
    result = read_result(sandbox)
    assert result["status"] == result["browser_status"] == "timed_out"
    assert result["browser_run"] is True
    assert sandbox.stopped == [browser, *reversed(sandbox.processes)]
    assert "\u2718" in (sandbox.run_dir / "browser.log").read_text(encoding="utf-8")
    assert_cleaned(sandbox, result)


def test_child_stop_failure_attempts_remaining_cleanup_and_reports_failure(sandbox, monkeypatch):
    def stop(process):
        sandbox.stopped.append(process)
        if process is sandbox.processes[2]:
            raise OSError(f"stop failed {sandbox.manifest['viewer_token']}")

    monkeypatch.setattr(runner, "_stop", stop)
    with pytest.raises(RuntimeError, match="Could not stop owned process") as error:
        runner.run()
    assert sandbox.manifest["viewer_token"] not in str(error.value)
    result = read_result(sandbox)
    assert result["status"] == "cleanup_failed"
    assert result["browser_status"] == "passed"
    assert result["browser_exit_code"] == 0
    assert len(result["cleanup_errors"]) == 1
    assert sandbox.stopped == list(reversed(sandbox.processes))
    assert_cleaned(sandbox, result)


def test_state_removal_failure_still_removes_credential_file_and_reports_actual_state(sandbox, monkeypatch):
    def removal_failed(path):
        assert path == sandbox.state.resolve()
        raise OSError("synthetic removal failure")

    with monkeypatch.context() as patch:
        patch.setattr(runner.shutil, "rmtree", removal_failed)
        with pytest.raises(RuntimeError, match="remove temporary state"):
            runner.run()
    result = read_result(sandbox)
    assert result["status"] == "cleanup_failed"
    assert result["temporary_state_removed"] is False
    assert result["credentials_removed"] is True
    assert sandbox.state.exists()
    assert not sandbox.manifest_path.exists()
    assert sandbox.screenshot.exists()
    assert sandbox.previous.exists()


def test_log_write_failure_still_records_result_and_cleans_state(sandbox, monkeypatch):
    write_text = Path.write_text

    def write_with_failure(path, *arguments, **keywords):
        if path == sandbox.run_dir / "browser.log":
            raise OSError("synthetic log write failure")
        return write_text(path, *arguments, **keywords)

    monkeypatch.setattr(Path, "write_text", write_with_failure)
    with pytest.raises(RuntimeError, match="Could not write browser.log"):
        runner.run()
    result = read_result(sandbox)
    assert result["status"] == "reporting_failed"
    assert result["browser_status"] == "passed"
    assert len(result["reporting_errors"]) == 1
    assert_cleaned(sandbox, result)
