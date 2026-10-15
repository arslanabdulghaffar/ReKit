"""Safety controls for the offline diagnostic; no native stress in this suite."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import subprocess
import time

import pytest


ROOT = Path(__file__).parents[2]
SPEC = spec_from_file_location("native_crash_investigation", ROOT / "evaluation/investigate_native_crash.py")
investigation = module_from_spec(SPEC)
SPEC.loader.exec_module(investigation)


def test_receipt_output_cannot_replace_prior_evidence_or_escape_ignored_root(tmp_path, monkeypatch):
    monkeypatch.setattr(investigation, "ROOT", tmp_path)
    output = investigation.new_output(tmp_path / "var/mission06-offline/new-investigation")
    protected = output / "receipt.json"
    protected.write_text("previous evidence", encoding="utf-8")
    with pytest.raises(FileExistsError):
        investigation.new_output(output)
    assert protected.read_text(encoding="utf-8") == "previous evidence"
    for invalid in (tmp_path / "public", tmp_path / "var/mission06-offline", tmp_path / "var/mission06-offline/../../escaped"):
        with pytest.raises(ValueError, match="under var/mission06-offline"):
            investigation.new_output(invalid)


def test_native_failure_is_retained_as_failure_with_unsigned_windows_code(tmp_path, monkeypatch):
    class Crashed:
        def __init__(self, command, *, cwd, stdout, stderr):
            stdout.write(b"preserved simulated native fault\n")

        def wait(self, timeout=None):
            return 0xC0000005

    monkeypatch.setattr(investigation.subprocess, "Popen", Crashed)
    result = investigation.run_child("simulated-crash", ["not-executed"], tmp_path, time.monotonic() + 10)
    assert result["status"] == "failed"
    assert result["returncode_hex"] == "0xC0000005"
    assert (tmp_path / result["log"]).read_bytes() == b"preserved simulated native fault\n"
    assert result["log_sha256"] == investigation.digest(tmp_path / result["log"])


def test_timeout_kills_only_owned_child_and_preserves_partial_log(tmp_path, monkeypatch):
    events = []

    class Hung:
        returncode = -9

        def __init__(self, command, *, cwd, stdout, stderr):
            stdout.write(b"partial diagnostic progress\n")

        def wait(self, timeout=None):
            events.append(("wait", timeout))
            if timeout is not None:
                raise subprocess.TimeoutExpired("not-executed", timeout)
            return self.returncode

        def kill(self):
            events.append(("kill", None))

    monkeypatch.setattr(investigation.subprocess, "Popen", Hung)
    result = investigation.run_child("simulated-timeout", ["not-executed"], tmp_path, time.monotonic() + 10)
    assert result["status"] == "timeout"
    assert [name for name, _ in events] == ["wait", "kill", "wait"]
    assert 0 < result["timeout_seconds"] <= 10
    assert (tmp_path / result["log"]).read_bytes() == b"partial diagnostic progress\n"


def test_expired_matrix_deadline_starts_no_child(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("A child must not start after the deadline")

    monkeypatch.setattr(investigation.subprocess, "Popen", forbidden)
    result = investigation.run_child("expired", ["not-executed"], tmp_path, time.monotonic() - 1)
    assert result["status"] == "not_started_matrix_deadline"
    assert list(tmp_path.iterdir()) == []


def test_matrix_stops_after_first_failed_child_without_resetting_evidence(tmp_path, monkeypatch):
    monkeypatch.setattr(investigation, "ROOT", tmp_path)
    monkeypatch.setattr(investigation, "hashes", lambda names: {name: "unchanged" for name in names})
    monkeypatch.setattr(investigation.subprocess, "check_output", lambda *args, **kwargs: "source-checkpoint\n")
    calls = []

    def failure(name, command, output, deadline):
        calls.append(name)
        return {"name": name, "status": "failed", "command": command, "returncode": 0xC0000005}

    monkeypatch.setattr(investigation, "run_child", failure)
    receipt, exit_code = investigation.matrix(tmp_path / "var/mission06-offline/stopped")
    assert exit_code == 1
    assert calls == ["environment"]
    assert receipt["status"] == "incomplete_or_failed"
    assert receipt["prior_evidence_unchanged"] is True
    assert receipt["root_cause_confirmed"] is receipt["fix_claimed"] is False
    assert (tmp_path / "var/mission06-offline/stopped/receipt.json").is_file()
