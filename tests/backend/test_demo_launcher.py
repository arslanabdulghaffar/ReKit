"""Local demo preflight and mode mapping without GPU work, services or downloads."""

from copy import deepcopy
from importlib.util import module_from_spec, spec_from_file_location
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "evaluation" / "run_demo.py"


@pytest.fixture
def demo(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "evaluation"))
    spec = spec_from_file_location("rekit_demo_launcher_tests", SCRIPT)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def mocked_preflight(demo, monkeypatch):
    calls = []
    runner = SimpleNamespace(_port_free=lambda port: calls.append(("port", port)),
        _load_product_sources=lambda: {"product_sources": [{}, {}], "dataset_manifest_sha256": "a" * 64},
        run=lambda **kwargs: calls.append(("run", kwargs)) or 0)
    monkeypatch.setattr(demo, "_python", lambda: {"version": "3.12.10", "repository_venv": True})
    monkeypatch.setattr(demo, "_frontend", lambda: {"node_version": "26.0.0"})
    monkeypatch.setattr(demo, "_fixtures", lambda: {"synthetic": True})
    monkeypatch.setattr(demo, "_runner", lambda: runner)
    return calls, runner


def test_synthetic_preflight_never_calls_ai_helpers_or_creates_state(demo, mocked_preflight, monkeypatch):
    for name in ("_product", "_cuda"):
        monkeypatch.setattr(demo, name, lambda *args: pytest.fail("Synthetic mode must not import AI dependencies"))
    mocked_preflight[1]._load_product_sources = lambda: pytest.fail("Synthetic mode must not require ABO images")
    result = demo.preflight("synthetic-recovery")
    assert mocked_preflight[0] == [("port", 8000), ("port", 5173)]
    assert result["mode"] == "synthetic-recovery" and not result["real_product_images"]
    assert result["model_loaded"] is result["model_executed"] is result["state_created"] is False
    assert "gpu" not in result and "model" not in result


@pytest.mark.parametrize("mode,real", [("synthetic-recovery", False), ("product-ai", True)])
def test_run_maps_only_explicit_modes_to_accepted_runner(demo, monkeypatch, capsys, mode, real):
    calls = []
    monkeypatch.setattr(demo, "preflight", lambda name, **kwargs: calls.append(("check", name, kwargs)) or {"status": "preflight_passed"})
    monkeypatch.setattr(demo, "_runner", lambda: SimpleNamespace(run=lambda **kwargs: calls.append(("run", kwargs)) or 7))
    assert demo.run(mode, headed=True, slow_mo_ms=125, hold_seconds=30, device=0) == 7
    assert calls[0] == ("check", mode, {"device": 0, "headed": True, "slow_mo_ms": 125, "hold_seconds": 30})
    assert calls[1] == ("run", {"real_inference": real, "real_product_images": real,
                              "device": 0, "headed": True, "slow_mo_ms": 125, "hold_seconds": 30})
    assert json.loads(capsys.readouterr().out)["status"] == "preflight_passed"


def test_check_runs_preflight_including_ports_but_never_starts_runner(demo, mocked_preflight, capsys):
    assert demo.run("synthetic-recovery", check=True) == 0
    assert mocked_preflight[0] == [("port", 8000), ("port", 5173)]
    assert json.loads(capsys.readouterr().out)["state_created"] is False


@pytest.mark.parametrize("kwargs", [
    {"mode": "automatic"}, {"device": -1}, {"device": True}, {"headed": 1},
    {"slow_mo_ms": -1}, {"slow_mo_ms": 501}, {"slow_mo_ms": 1.5}, {"slow_mo_ms": True},
    {"hold_seconds": -1}, {"hold_seconds": 121}, {"hold_seconds": 0.5},
    {"slow_mo_ms": 1}, {"hold_seconds": 1},
])
def test_invalid_presentation_or_mode_fails_before_any_preflight(demo, monkeypatch, kwargs):
    monkeypatch.setattr(demo, "_python", lambda: pytest.fail("Invalid options must fail before preflight"))
    values = {"mode": "synthetic-recovery", **kwargs}
    with pytest.raises(demo.DemoError, match="Choose|Device|Headed|motion|hold|Final"):
        demo.preflight(**values)


def test_port_conflict_is_sanitized_and_never_kills_or_starts_process(demo, mocked_preflight, capsys):
    def busy(_port):
        raise OSError("SECRET-ENV-CREDENTIAL")
    mocked_preflight[1]._port_free = busy
    with pytest.raises(demo.DemoError, match="no existing process was stopped") as raised:
        demo.run("synthetic-recovery", check=True)
    assert "SECRET" not in str(raised.value) and mocked_preflight[0] == []
    assert capsys.readouterr().out == ""


def test_python_requires_repository_venv_and_supported_minor(demo, tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "ROOT", tmp_path)
    (tmp_path / "pyproject.toml").write_text('[project]\ndependencies=["example==1.2.3"]\n', encoding="utf-8")
    runtime = SimpleNamespace(prefix=str(tmp_path / ".venv"), version_info=(3, 12, 10))
    monkeypatch.setattr(demo, "sys", runtime)
    monkeypatch.setattr(demo, "version", lambda name: "1.2.3")
    assert demo._python()["core_dependencies"] == {"example": "1.2.3"}
    runtime.version_info = (3, 13, 0)
    with pytest.raises(demo.DemoError, match="Python 3.12"):
        demo._python()
    runtime.version_info = (3, 12, 10)
    runtime.prefix = str(tmp_path / "other-environment")
    with pytest.raises(demo.DemoError, match="repository"):
        demo._python()


@pytest.mark.parametrize("actual", ["9.9.9", "SECRET-ENV-CREDENTIAL", None])
def test_package_version_mismatch_and_missing_are_safe(demo, monkeypatch, actual):
    def installed(_name):
        if actual is None:
            raise RuntimeError("SECRET-ENV-CREDENTIAL")
        return actual
    monkeypatch.setattr(demo, "version", installed)
    with pytest.raises(demo.DemoError) as raised:
        demo._versions(["example==1.2.3"])
    assert "SECRET" not in str(raised.value)


@pytest.fixture
def frontend(demo, tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "ROOT", tmp_path)
    directory = tmp_path / "frontend"
    directory.mkdir()
    package = {"dependencies": {"react": "19.3.0"}, "devDependencies": {"vite": "8.3.4", "@playwright/test": "1.64.0"}}
    (directory / "package.json").write_text(json.dumps(package), encoding="utf-8")
    for name, value in {**package["dependencies"], **package["devDependencies"]}.items():
        path = directory / "node_modules" / name
        path.mkdir(parents=True)
        (path / "package.json").write_text(json.dumps({"version": value}), encoding="utf-8")
    (directory / "node_modules" / "vite" / "bin").mkdir()
    (directory / "node_modules" / "vite" / "bin" / "vite.js").write_text("", encoding="utf-8")
    (directory / "node_modules" / "@playwright" / "test" / "cli.js").write_text("", encoding="utf-8")
    browser = tmp_path / "SECRET-browser-path.exe"
    browser.write_bytes(b"controlled fake executable; never launched")
    monkeypatch.setenv("REKIT_BROWSER_EXECUTABLE", str(browser))
    monkeypatch.setattr(demo.shutil, "which", lambda name: "controlled-node")
    calls = []
    def execute(command, **kwargs):
        calls.append((command, kwargs))
        return SimpleNamespace(returncode=0, stdout="v26.0.0\n", stderr="unused SECRET")
    monkeypatch.setattr(demo.subprocess, "run", execute)
    return directory, browser, calls


def test_frontend_uses_local_exact_versions_and_safe_browser_report(demo, frontend):
    result = demo._frontend()
    assert result["node_version"] == "26.0.0"
    assert result["browser"] == {"source": "configured", "installed": True}
    assert "SECRET" not in json.dumps(result)
    assert frontend[2][0][0] == ["controlled-node", "--version"]
    assert frontend[2][0][1]["timeout"] == 10


@pytest.mark.parametrize("change", ["old_node", "bad_node", "node_failure", "missing_node", "package_mismatch", "missing_cli", "browser_directory"])
def test_frontend_failure_is_sanitized_without_installation(demo, frontend, monkeypatch, change):
    directory, browser, calls = frontend
    if change in ("old_node", "bad_node", "node_failure"):
        monkeypatch.setattr(demo.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(
            returncode=1 if change == "node_failure" else 0,
            stdout="v25.9.0" if change == "old_node" else "SECRET-BAD-OUTPUT", stderr="SECRET-ENV-CREDENTIAL"))
    elif change == "missing_node":
        monkeypatch.setattr(demo.shutil, "which", lambda name: None)
    elif change == "package_mismatch":
        (directory / "node_modules" / "react" / "package.json").write_text('{"version":"SECRET"}', encoding="utf-8")
    elif change == "missing_cli":
        (directory / "node_modules" / "vite" / "bin" / "vite.js").unlink()
    else:
        browser.unlink()
        browser.mkdir()
    with pytest.raises(demo.DemoError) as raised:
        demo._frontend()
    assert "SECRET" not in str(raised.value)
    assert all(command == ["controlled-node", "--version"] for command, _ in calls)


@pytest.fixture
def fixtures(demo, tmp_path, monkeypatch):
    directory = tmp_path / "tests" / "fixtures"
    directory.mkdir(parents=True)
    for name in ("synthetic_catalog.json", "synthetic_disposition_policy.json", "synthetic_recovery.json"):
        shutil.copyfile(ROOT / "tests" / "fixtures" / name, directory / name)
    monkeypatch.setattr(demo, "ROOT", tmp_path)
    return directory


def test_fixtures_validate_in_memory_without_inventory_or_database(demo, fixtures):
    before = {path.name: path.read_bytes() for path in fixtures.iterdir()}
    result = demo._fixtures()
    assert result["synthetic"] is result["fixture_graph_validated"] is True
    assert before == {path.name: path.read_bytes() for path in fixtures.iterdir()}
    assert list(fixtures.parents[1].rglob("*.sqlite3")) == []


@pytest.mark.parametrize("change", ["policy_type", "policy_return", "configuration", "physical_return", "identity", "revision", "observation_link", "incompatible", "not_synthetic"])
def test_fixture_reference_or_verification_failures_stop_before_startup(demo, fixtures, change):
    file = fixtures / ("synthetic_disposition_policy.json" if change.startswith("policy") else "synthetic_recovery.json")
    value = json.loads(file.read_text(encoding="utf-8"))
    if change == "policy_type":
        value["salvage_allowed_component_types"] = ["SECRET-unknown"]
    elif change == "policy_return":
        value["liquidation_allowed_return_ids"] = ["SECRET-unknown"]
    elif change == "configuration":
        value["scenario"]["kits"][0]["configuration_id"] = "SECRET-unknown"
    elif change == "physical_return":
        value["components"][0]["component"]["source_return_id"] = "SECRET-unknown"
    elif change == "identity":
        value["components"][0]["verification"]["identity"]["component_type_id"] = "SECRET-unknown"
    elif change == "revision":
        value["components"][0]["verification"]["identity"]["revision"] = "SECRET-unknown"
    elif change == "observation_link":
        value["components"][0]["verification"]["evidence_observation_ids"] = ["SECRET-unknown"]
    elif change == "incompatible":
        value["components"][2]["verification"]["identity"]["revision"] = "B"
    else:
        value["synthetic"] = False
    file.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(demo.DemoError) as raised:
        demo._fixtures()
    assert "SECRET" not in str(raised.value)


@pytest.fixture
def model_files(demo, tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "ROOT", tmp_path)
    (tmp_path / "requirements-inference.txt").write_text("# ignored\nexample==1.2.3\n", encoding="utf-8")
    monkeypatch.setattr(demo, "version", lambda name: "1.2.3")
    names = sorted({"chat_template.json", "config.json", "generation_config.json", "merges.txt", "preprocessor_config.json",
                    "tokenizer.json", "tokenizer_config.json", "video_preprocessor_config.json", "vocab.json", "model.safetensors"})
    official = {"model_id": "Qwen/Qwen3-VL-2B-Instruct", "revision": "8" * 40,
                "files": [{"name": name, "size": 100 + index, "official_hash": f"synthetic-hash-{index}"} for index, name in enumerate(names)]}
    verified = [{"name": item["name"], "size": item["size"], "sha256": f"{index:064x}"} for index, item in enumerate(official["files"])]
    directory = tmp_path / "models"
    directory.mkdir()
    receipt = {"model_id": official["model_id"], "revision": official["revision"], "files": deepcopy(verified)}
    (directory / "rekit-download.json").write_text(json.dumps(receipt), encoding="utf-8")
    calls = []
    def verify(path, expected):
        calls.append((path, expected))
        return next(item for item in verified if item["name"] == path.name)
    module = SimpleNamespace(_manifest=lambda: deepcopy(official), _verify=verify, DESTINATION=directory)
    monkeypatch.setitem(sys.modules, "download_vision_model", module)
    return module, official, verified, calls, receipt


def test_product_checks_every_official_file_and_exact_receipt_without_downloader(demo, model_files):
    module, official, verified, calls, _ = model_files
    dependencies, model = demo._product()
    assert dependencies == {"example": "1.2.3"}
    assert calls == [(module.DESTINATION / item["name"], item) for item in official["files"]]
    assert model["verified_files"] == 10 and model["verified_bytes"] == sum(item["size"] for item in verified)
    assert model["official_hashes_verified"] is model["receipt_verified"] is True


@pytest.mark.parametrize("change", ["hash_failure", "missing_receipt", "receipt_revision", "receipt_file_hash", "duplicate_receipt_file"])
def test_unverified_or_tampered_model_never_reaches_cuda(demo, model_files, change):
    module, _, _, _, receipt = model_files
    path = module.DESTINATION / "rekit-download.json"
    if change == "hash_failure":
        def fail(*_args):
            raise ValueError("SECRET-MODEL-PATH")
        module._verify = fail
    elif change == "missing_receipt":
        path.unlink()
    else:
        if change == "receipt_revision":
            receipt["revision"] = "SECRET"
        elif change == "receipt_file_hash":
            receipt["files"][0]["sha256"] = "f" * 64
        else:
            receipt["files"].append(deepcopy(receipt["files"][0]))
        path.write_text(json.dumps(receipt), encoding="utf-8")
    with pytest.raises(demo.DemoError, match="no download") as raised:
        demo._product()
    assert "SECRET" not in str(raised.value)


@pytest.fixture
def cuda(demo, monkeypatch):
    queries = []
    fake = SimpleNamespace(__version__="2.9.0+cu128", version=SimpleNamespace(cuda="12.8"),
        cuda=SimpleNamespace(is_available=lambda: True, device_count=lambda: 2,
                             mem_get_info=lambda device: queries.append(device) or (7 * 1024**3, 16 * 1024**3)))
    monkeypatch.setattr(demo, "importlib", SimpleNamespace(import_module=lambda name: fake if name == "torch" else pytest.fail(name)))
    monkeypatch.setattr(demo, "version", lambda name: "0.24.0+cu128")
    return fake, queries


def test_cuda_queries_only_requested_device_and_accepts_exact_memory_threshold(demo, cuda):
    result = demo._cuda(1)
    assert cuda[1] == [1] and result["free_bytes"] == demo.MIN_FREE_VRAM_BYTES
    assert result["device"] == 1 and result["torch_version"] == "2.9.0"


@pytest.mark.parametrize("change", ["unavailable", "wrong_device", "low_memory", "wrong_torch", "wrong_cuda", "wrong_torchvision", "query_failure"])
def test_cuda_failure_has_no_cpu_fallback_or_model_load(demo, cuda, monkeypatch, change):
    fake, queries = cuda
    device = 1
    if change == "unavailable":
        fake.cuda.is_available = lambda: False
    elif change == "wrong_device":
        device = 2
    elif change == "low_memory":
        fake.cuda.mem_get_info = lambda index: (demo.MIN_FREE_VRAM_BYTES - 1, 16 * 1024**3)
    elif change == "wrong_torch":
        fake.__version__ = "SECRET-OTHER-TORCH"
    elif change == "wrong_cuda":
        fake.version.cuda = "SECRET-OTHER-CUDA"
    elif change == "wrong_torchvision":
        monkeypatch.setattr(demo, "version", lambda name: "SECRET-OTHER-TORCHVISION")
    else:
        def fail(_index):
            raise RuntimeError("SECRET-DRIVER-ERROR")
        fake.cuda.mem_get_info = fail
    with pytest.raises(demo.DemoError) as raised:
        demo._cuda(device)
    assert "SECRET" not in str(raised.value)


def test_product_preflight_keeps_controlled_provenance_and_no_model_execution(demo, mocked_preflight, monkeypatch):
    monkeypatch.setattr(demo, "_product", lambda: ({"example": "1.2.3"}, {"verified_files": 10}))
    monkeypatch.setattr(demo, "_cuda", lambda device: {"device": device, "free_bytes": 8 * 1024**3})
    result = demo.preflight("product-ai", device=0, headed=True, slow_mo_ms=500, hold_seconds=120)
    assert result["gpu"]["device"] == 0 and result["sources"]["original_images"] == 2
    assert result["sources"]["original_hashes_verified"] is True
    assert result["model_loaded"] is result["model_executed"] is False
    assert result["presentation"] == {"headed": True, "slow_mo_ms": 500, "hold_seconds": 120}
    assert not any(call[0] == "run" for call in mocked_preflight[0])


def test_main_sanitizes_unknown_failures_instead_of_echoing_environment_values(demo, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--mode", "synthetic-recovery", "--check"])
    def fail(*_args, **_kwargs):
        raise RuntimeError("SECRET-ENV-CREDENTIAL")
    monkeypatch.setattr(demo, "run", fail)
    assert demo.main() == 1
    assert "SECRET" not in capsys.readouterr().out


def test_preflight_failure_never_calls_runner_or_prints_success(demo, monkeypatch, capsys):
    def fail(*_args, **_kwargs):
        raise demo.DemoError("dependencies", "Required local dependency is unavailable.")
    monkeypatch.setattr(demo, "preflight", fail)
    monkeypatch.setattr(demo, "_runner", lambda: pytest.fail("A failed preflight cannot start services"))
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--mode", "product-ai"])
    assert demo.main() == 1
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "preflight_failed" and result["code"] == "dependencies"
