"""Runner reporting survives legacy consoles and cleans only its disposable state."""

import asyncio
import builtins
from importlib.util import module_from_spec, spec_from_file_location
import io
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

import httpx
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
    monkeypatch.setattr(runner, "_prepare", lambda **options: (manifest_path, manifest))
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


@pytest.fixture
def prepared_root(tmp_path, monkeypatch):
    """Real disposable fixtures, separate from the child-process test doubles."""
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "OUTPUT", tmp_path / "acceptance")
    monkeypatch.setattr(runner, "_start", lambda *args, **kwargs: pytest.fail("A CPU test started a service"))
    monkeypatch.setattr(runner, "_port_free", lambda port: pytest.fail("Check-only setup probed a live port"))
    return tmp_path


@pytest.fixture
def optional_imports_blocked(monkeypatch):
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"torch", "torchvision", "transformers", "tokenizers", "safetensors", "accelerate"}:
            raise AssertionError(f"CPU runner setup imported optional model runtime {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)


@pytest.fixture
def provider_constructions(monkeypatch):
    from rekit.inference.models import InferenceConfiguration
    from rekit.inference import provider

    constructed = []

    class ConstructorOnlyProvider:
        def __init__(self, model_dir, *, device, catalog):
            self.arguments = {"model_dir": model_dir, "device": device, "catalog": catalog}
            self.status = "unloaded"
            self.configuration = InferenceConfiguration(
                provider="constructor-test-double", model_repository="test/no-model",
                model_revision="a" * 40, processor_revision="a" * 40,
                runtime={"engine": "CPU constructor test only"}, device=f"cuda:{device}",
                prompt_version="test-only", preprocessing={"max_images": 2},
                generation={"max_new_tokens": 1},
            )
            constructed.append(self)

        def inspect(self, images):
            pytest.fail("Check-only setup executed inference")

    monkeypatch.setattr(provider, "LocalVisionProvider", ConstructorOnlyProvider)
    return constructed


def test_default_application_has_no_provider_optional_import_or_seeded_stock(
    prepared_root, optional_imports_blocked, provider_constructions, monkeypatch,
):
    # Ambient developer configuration cannot turn the default CPU scenario into AI.
    monkeypatch.setenv("REKIT_INFERENCE_PROVIDER", "local-transformers")
    monkeypatch.setenv("REKIT_MODEL_DIR", str(prepared_root / "must-not-be-loaded"))
    manifest_path, manifest = runner._prepare()
    assert manifest["real_inference"] is False
    assert "ambiguous_image" not in manifest
    assert "model_dir" not in manifest
    assert sum(len(paths) for paths in manifest["images"].values()) == 8
    app = runner._application(manifest)
    assert provider_constructions == []
    assert app.state.inference is None
    assert app.state.inventory.inventory().items == ()
    async def check_http():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
            assert (await client.get("/inference/status")).status_code == 401
            response = await client.get("/inference/status", headers={"Authorization": f"Bearer {manifest['viewer_token']}"})
            assert response.json()["status"] == "unavailable"
            assert response.json()["provider"] is None

    asyncio.run(check_http())
    assert manifest_path.is_file()


@pytest.mark.parametrize("explicit_directory", [False, True])
def test_opt_in_manifest_has_one_ambiguous_fixture_and_only_server_owned_model_path(
    prepared_root, optional_imports_blocked, explicit_directory,
):
    from PIL import Image
    from rekit.inference.adapters.local_transformers import MODEL_REVISION

    model_dir = prepared_root / "trusted-model" if explicit_directory else None
    manifest_path, manifest = runner._prepare(real_inference=True, model_dir=model_dir, device=0)
    expected_model = model_dir or prepared_root / "models" / "Qwen3-VL-2B-Instruct" / MODEL_REVISION
    assert manifest["real_inference"] is True
    assert manifest["model_dir"] == str(expected_model.resolve())
    assert manifest["device"] == 0
    assert Path(manifest["artifacts_dir"]).name.startswith("run-ai-")
    state = Path(manifest["state_dir"]).resolve()
    paths = [Path(path) for group in manifest["images"].values() for path in group]
    ambiguous = Path(manifest["ambiguous_image"])
    assert len(paths) == 8
    assert ambiguous not in paths
    assert all(path.resolve().is_relative_to(state) for path in [*paths, ambiguous, manifest_path])
    assert len(list((state / "input-images").glob("*.png"))) == 9
    with Image.open(ambiguous) as image:
        image.load()
        assert image.format == "PNG"
        assert image.size == (768, 512)
        assert image.getpixel((200, 250)) == (255, 0, 0)
        assert image.getpixel((550, 250)) == (0, 0, 255)
    assert not expected_model.exists(), "Fixture generation must never download or create weights"
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == manifest


def test_opt_in_application_constructs_one_lazy_provider_with_trusted_catalog(
    prepared_root, optional_imports_blocked, provider_constructions,
):
    model_dir = prepared_root / "explicit-server-checkpoint"
    _, manifest = runner._prepare(real_inference=True, model_dir=model_dir, device=0)
    app = runner._application(manifest)
    assert len(provider_constructions) == 1
    provider = provider_constructions[0]
    assert provider.arguments["model_dir"] == model_dir.resolve()
    assert provider.arguments["device"] == 0
    assert provider.arguments["catalog"] == app.state.inventory.evidence.catalog
    assert provider.arguments["catalog"].synthetic is True
    assert app.state.inference.store.assets is app.state.assets
    assert app.state.inventory.inventory().items == ()
    async def check_http():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                operator = {"Authorization": f"Bearer {manifest['operator_token']}"}
                status = await client.get("/inference/status", headers=operator)
                assert status.status_code == 200
                assert status.json()["status"] == "unloaded"
                assert status.json()["busy"] is False
                assert (await client.get("/inventory", headers=operator)).json()["items"] == []
                viewer = {"Authorization": f"Bearer {manifest['viewer_token']}"}
                denied = await client.post("/components/does-not-exist/inference", headers=viewer, json={
                    "request_id": "test-forbidden", "asset_ids": ["asset-" + "a" * 32], "expected_version": 1,
                })
                assert denied.status_code == 403

    asyncio.run(check_http())
    assert app.state.inference.status()["status"] == "unavailable"
    assert not model_dir.exists()


@pytest.mark.parametrize("real_inference", [False, True])
def test_check_only_cleans_all_generated_state_and_never_executes_model_or_services(
    prepared_root, optional_imports_blocked, provider_constructions, monkeypatch, capsys, real_inference,
):
    recorded = []
    original_prepare = runner._prepare

    def prepare(**options):
        result = original_prepare(**options)
        recorded.append(result)
        return result

    monkeypatch.setattr(runner, "_prepare", prepare)
    assert runner.run(check_only=True, real_inference=real_inference) == 0
    manifest_path, manifest = recorded[0]
    assert not manifest_path.exists()
    assert not Path(manifest["state_dir"]).exists()
    run_dir = Path(manifest["artifacts_dir"])
    result = json.loads((run_dir / "runner-result.json").read_text(encoding="utf-8"))
    assert result["status"] == "setup_passed"
    assert result["browser_run"] is False
    assert result["real_inference_enabled"] is real_inference
    assert result["temporary_state_removed"] is result["credentials_removed"] is True
    assert len(provider_constructions) == int(real_inference)
    console = capsys.readouterr().out
    summary = json.loads(console)
    assert summary["model_executed"] is False
    assert summary["real_inference_enabled"] is real_inference
    assert summary["synthetic_images"] == (9 if real_inference else 8)
    assert summary["registered_components"] == 0
    preserved = console + "".join(path.read_text(encoding="utf-8") for path in run_dir.iterdir() if path.is_file())
    assert manifest["operator_token"] not in preserved
    assert manifest["viewer_token"] not in preserved
    assert not list(run_dir.rglob("*.png"))
    assert not list(run_dir.rglob("*.sqlite3"))


@pytest.mark.parametrize("arguments", [
    ["--check", "--model-dir", "not-authorized-without-opt-in"],
    ["--check", "--real-inference", "--device", "-1"],
])
def test_invalid_cli_configuration_fails_before_generating_state(monkeypatch, arguments, capsys):
    monkeypatch.setattr(runner.sys, "argv", ["run_browser_acceptance.py", *arguments])
    monkeypatch.setattr(runner, "_prepare", lambda **options: pytest.fail("Invalid options generated temporary credentials"))
    assert runner.main() == 1
    assert "Acceptance runner failed:" in capsys.readouterr().err


def test_explicit_ai_browser_timeout_is_bounded_and_preserves_cleanup(sandbox):
    sandbox.manifest["real_inference"] = True
    browser = sandbox.processes[2]

    def communicate(*, timeout):
        browser.communications += 1
        if browser.communications == 1:
            assert timeout == 900
            raise subprocess.TimeoutExpired("controlled-ai-browser", timeout, output=sandbox.output)
        assert timeout == 5
        return sandbox.output, None

    browser.communicate = communicate
    with pytest.raises(RuntimeError, match="900 second limit"):
        runner.run(real_inference=True)
    result = read_result(sandbox)
    assert result["status"] == "timed_out"
    assert result["real_inference_enabled"] is True
    assert_cleaned(sandbox, result)
