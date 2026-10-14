"""Preflight and replay one isolated local demo; never install, download or warm up AI."""

import argparse
import importlib
from importlib.metadata import version
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib


ROOT = Path(__file__).resolve().parents[1]
MIN_FREE_VRAM_BYTES = 7 * 1024**3
MODES = ("product-ai", "synthetic-recovery")


class DemoError(RuntimeError):
    """Only controlled messages reach console; dependency errors may contain secrets."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _options(mode: str, device: int, headed: bool, slow_mo_ms: int, hold_seconds: int) -> None:
    if mode not in MODES:
        raise DemoError("options", "Choose product-ai or synthetic-recovery explicitly.")
    if type(device) is not int or device < 0:
        raise DemoError("options", "Device must be a nonnegative integer.")
    if type(headed) is not bool:
        raise DemoError("options", "Headed mode must be an explicit boolean.")
    for value, maximum, name in ((slow_mo_ms, 500, "Slow motion"), (hold_seconds, 120, "Final hold")):
        if type(value) is not int or not 0 <= value <= maximum:
            raise DemoError("options", f"{name} must be an integer from 0 through {maximum}.")
    if (slow_mo_ms or hold_seconds) and not headed:
        raise DemoError("options", "Slow motion and final hold require --headed.")


def _json(path: Path, maximum: int = 1024**2):
    with path.open("rb") as source:
        raw = source.read(maximum + 1)
    if len(raw) > maximum:
        raise ValueError("Bounded configuration exceeded")
    return json.loads(raw)


def _versions(requirements: list[str]) -> dict:
    installed = {}
    for requirement in requirements:
        match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9._-]{0,79})==([0-9][A-Za-z0-9.+_-]{0,79})", requirement)
        if match is None:
            raise DemoError("dependencies", "Demo dependencies must have exact supported version pins.")
        name, expected = match.groups()
        try:
            actual = version(name)
        except Exception:
            raise DemoError("dependencies", f"Required local package {name} is unavailable; review environment setup manually.") from None
        if actual != expected:
            raise DemoError("dependencies", f"Required local package {name} differs from its repository pin; no packages were changed.")
        installed[name] = actual
    return installed


def _python() -> dict:
    if sys.version_info[:2] != (3, 12) or Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        raise DemoError("python", "Use this repository's .venv Python 3.12 interpreter; no environment was created or changed.")
    try:
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        dependencies = _versions(project["project"]["dependencies"])
    except DemoError:
        raise
    except Exception:
        raise DemoError("dependencies", "Local Python dependency configuration could not be validated.") from None
    return {"version": ".".join(str(part) for part in sys.version_info[:3]), "repository_venv": True,
            "core_dependencies": dependencies}


def _frontend() -> dict:
    node = shutil.which("node")
    if node is None:
        raise DemoError("node", "Node.js 26 or newer is required; no global software was installed.")
    try:
        process = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=10,
                                 creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                                 check=False)
        match = re.fullmatch(r"v(\d+)\.(\d+)\.(\d+)\s*", process.stdout)
        if process.returncode != 0 or match is None or int(match[1]) < 26:
            raise ValueError("Unsupported Node version")
    except Exception:
        raise DemoError("node", "Node.js version check failed; version 26 or newer is required.") from None
    try:
        package = _json(ROOT / "frontend" / "package.json")
        dependencies = {**package["dependencies"], **package["devDependencies"]}
        for name, expected in dependencies.items():
            if not re.fullmatch(r"(?:@[A-Za-z0-9._-]+/)?[A-Za-z0-9._-]+", name):
                raise ValueError("Invalid dependency name")
            if not isinstance(expected, str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?", expected):
                raise ValueError("Unpinned frontend dependency")
            installed = _json(ROOT / "frontend" / "node_modules" / name / "package.json")
            if installed.get("version") != expected:
                raise ValueError("Frontend dependency version mismatch")
        for path in ("vite/bin/vite.js", "@playwright/test/cli.js"):
            if not (ROOT / "frontend" / "node_modules" / path).is_file():
                raise ValueError("Missing local browser tool")
    except Exception:
        raise DemoError("frontend", "Pinned local frontend dependencies are missing or inconsistent; no installation was attempted.") from None
    candidates = (
        (os.environ.get("REKIT_BROWSER_EXECUTABLE"), "configured"),
        ("C:/Program Files/Google/Chrome/Application/chrome.exe", "chrome"),
        ("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "edge"),
    )
    # Match the accepted Playwright config's first existing path, including an
    # explicitly supplied override. Never echo the environment-supplied path.
    selected = next(((Path(path), label) for path, label in candidates if path and Path(path).exists()), None)
    if selected is None or not selected[0].is_file():
        raise DemoError("browser", "An installed Chrome or Edge executable is required; no browser was downloaded.")
    return {"node_version": ".".join(match.groups()), "dependencies": dependencies,
            "browser": {"source": selected[1], "installed": True}}


def _fixtures() -> dict:
    """Validate the fixture graph in memory; create no database or verified stock."""
    try:
        from rekit.catalog.compatibility import check_compatibility
        from rekit.catalog.models import Catalog
        from rekit.evidence.models import (CurrentEvidence, Observation, OperatorVerification,
                                           PhysicalComponent, ReturnBatch, ReturnRecord, validate_intake)
        from rekit.inventory.models import InventoryItem
        from rekit.recovery.models import DispositionPolicy, EconomicScenario, RecoveryProblem, ReturnContents

        directory = ROOT / "tests" / "fixtures"
        raw = _json(directory / "synthetic_recovery.json")
        catalog = Catalog.model_validate_json((directory / "synthetic_catalog.json").read_bytes())
        policy = DispositionPolicy.model_validate_json((directory / "synthetic_disposition_policy.json").read_bytes())
        if (raw.get("synthetic") is not True or catalog.synthetic is not True
                or raw.get("catalog_file") != "synthetic_catalog.json"
                or raw.get("disposition_policy_file") != "synthetic_disposition_policy.json"
                or raw["scenario"].get("scenario_estimate") is not True):
            raise ValueError("Demo fixtures must be explicitly synthetic")
        batch = ReturnBatch.model_validate(raw["batch"])
        returns = [ReturnRecord.model_validate(item) for item in raw["returns"]]
        components = [PhysicalComponent.model_validate(item["component"]) for item in raw["components"]]
        validate_intake(catalog, [batch], returns, components)
        returned_by_id = {item.return_id: item for item in returns}
        for record, component in zip(raw["components"], components, strict=True):
            observation = Observation.model_validate(record["observation"])
            verification = OperatorVerification.model_validate(record["verification"])
            catalog.validate_identity(verification.identity)
            if (observation.physical_component_id != component.physical_component_id
                    or observation.source_return_id != component.source_return_id
                    or verification.physical_component_id != component.physical_component_id
                    or verification.evidence_observation_ids != (observation.observation_id,)):
                raise ValueError("Synthetic verification evidence references do not match")
            configuration = returned_by_id[component.source_return_id].declared_configuration_id
            if configuration is None or not check_compatibility(
                    catalog, configuration, verification.identity, verification.visible_condition).compatible:
                raise ValueError("Synthetic fixture verification fails approved compatibility")
        items = tuple(InventoryItem(component=item, evidence=CurrentEvidence(physical_component_id=item.physical_component_id))
                      for item in components)
        contents = tuple(ReturnContents(return_id=returned.return_id,
            component_ids=tuple(item.physical_component_id for item in components if item.source_return_id == returned.return_id))
            for returned in returns)
        RecoveryProblem(catalog=catalog, inventory=items, return_contents=contents,
            scenario=EconomicScenario.model_validate(raw["scenario"]), policy=policy)
    except Exception:
        raise DemoError("fixtures", "Synthetic catalog, intake, economics or disposition-policy references are invalid.") from None
    return {"catalog_id": catalog.catalog_id, "catalog_version": catalog.version, "policy_id": policy.policy_id,
            "policy_version": policy.version, "synthetic": True, "fixture_graph_validated": True}


def _product() -> tuple[dict, dict]:
    try:
        requirements = [line.strip() for line in (ROOT / "requirements-inference.txt").read_text(encoding="utf-8").splitlines()
                        if line.strip() and not line.lstrip().startswith("#")]
        dependencies = _versions(requirements)
        from download_vision_model import _manifest, _verify, DESTINATION

        official = _manifest()
        verified = [_verify(DESTINATION / item["name"], item) for item in official["files"]]
        receipt = _json(DESTINATION / "rekit-download.json")
        if (receipt.get("model_id") != official["model_id"] or receipt.get("revision") != official["revision"]
                or not isinstance(receipt.get("files"), list)
                or sorted(receipt["files"], key=lambda item: item["name"]) != sorted(verified, key=lambda item: item["name"])):
            raise ValueError("Model receipt differs from pinned verified files")
    except DemoError:
        raise
    except Exception:
        raise DemoError("model", "The ten pinned local model files and verification receipt must be present and unchanged; no download was attempted.") from None
    return dependencies, {"repository": official["model_id"], "revision": official["revision"],
                          "verified_files": len(verified), "verified_bytes": sum(item["size"] for item in verified),
                          "official_hashes_verified": True, "receipt_verified": True}


def _cuda(device: int) -> dict:
    try:
        if version("torchvision").split("+")[0] != "0.24.0":
            raise DemoError("dependencies", "The qualified local demo requires the existing torchvision 0.24.0 package; no environment was changed.")
        torch = importlib.import_module("torch")
        if str(torch.__version__).split("+")[0] != "2.9.0" or torch.version.cuda != "12.8":
            raise DemoError("cuda", "The qualified local demo requires the existing PyTorch 2.9.0 / CUDA 12.8 environment; no environment was changed.")
        if not torch.cuda.is_available() or device >= torch.cuda.device_count():
            raise DemoError("cuda", "The requested CUDA device is unavailable; no CPU fallback was selected.")
        free, total = torch.cuda.mem_get_info(device)
        if type(free) is not int or type(total) is not int or not 0 <= free <= total:
            raise ValueError("Invalid CUDA memory query")
        if free < MIN_FREE_VRAM_BYTES:
            raise DemoError("vram", "The requested CUDA device needs at least 7 GiB free; no model was loaded.")
    except DemoError:
        raise
    except Exception:
        raise DemoError("cuda", "The local CUDA preflight query failed; no model was loaded.") from None
    return {"torch_version": "2.9.0", "torchvision_version": "0.24.0", "cuda_version": "12.8", "device": device,
            "free_bytes": free, "total_bytes": total, "minimum_free_bytes": MIN_FREE_VRAM_BYTES}


def _runner():
    return importlib.import_module("run_browser_acceptance")


def preflight(mode: str, *, device: int = 1, headed: bool = False,
              slow_mo_ms: int = 0, hold_seconds: int = 0) -> dict:
    _options(mode, device, headed, slow_mo_ms, hold_seconds)
    report = {"status": "preflight_passed", "mode": mode, "python": _python(),
              "frontend": _frontend(), "fixtures": _fixtures(),
              "presentation": {"headed": headed, "slow_mo_ms": slow_mo_ms, "hold_seconds": hold_seconds},
              "model_loaded": False, "model_executed": False, "state_created": False,
              "real_product_images": mode == "product-ai", "simulated_intake": True}
    try:
        runner = _runner()
        for port in (8000, 5173):
            runner._port_free(port)
    except Exception:
        raise DemoError("ports", "Both loopback ports 127.0.0.1:8000 and :5173 must be free; no existing process was stopped.") from None
    report["loopback_ports"] = [8000, 5173]
    if mode == "product-ai":
        report["inference_dependencies"], report["model"] = _product()
        report["gpu"] = _cuda(device)
        try:
            sources = runner._load_product_sources()
            report["sources"] = {"original_images": len(sources["product_sources"]),
                                  "manifest_sha256": sources["dataset_manifest_sha256"],
                                  "original_hashes_verified": True}
        except Exception:
            raise DemoError("images", "The original development image pair is unavailable or changed; no images were downloaded.") from None
    return report


def run(mode: str, *, check: bool = False, headed: bool = False, slow_mo_ms: int = 0,
        hold_seconds: int = 0, device: int = 1) -> int:
    if type(check) is not bool:
        raise DemoError("options", "Check mode must be an explicit boolean.")
    report = preflight(mode, device=device, headed=headed, slow_mo_ms=slow_mo_ms, hold_seconds=hold_seconds)
    print(json.dumps(report, ensure_ascii=True), flush=True)
    if check:
        return 0
    return _runner().run(real_inference=mode == "product-ai", real_product_images=mode == "product-ai",
                         device=device, headed=headed, slow_mo_ms=slow_mo_ms, hold_seconds=hold_seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", required=True, choices=MODES)
    parser.add_argument("--check", action="store_true", help="Read-only preflight; no state, servers, browser or model load")
    parser.add_argument("--headed", action="store_true", help="Show the actual browser replay")
    parser.add_argument("--slow-mo-ms", type=int, default=0, help="Browser action pacing, 0..500; requires --headed")
    parser.add_argument("--hold-seconds", type=int, default=0, help="Final-page inspection time, 0..120; requires --headed")
    parser.add_argument("--device", type=int, default=1, help="CUDA device index for product-ai only")
    args = parser.parse_args()
    try:
        return run(args.mode, check=args.check, headed=args.headed, slow_mo_ms=args.slow_mo_ms,
                   hold_seconds=args.hold_seconds, device=args.device)
    except DemoError as error:
        print(json.dumps({"status": "preflight_failed", "code": error.code, "error": str(error)}, ensure_ascii=True))
        return 1
    except KeyboardInterrupt:
        print(json.dumps({"status": "interrupted", "error": "Demo interrupted; inspect the runner cleanup receipt."}))
        return 130
    except Exception:
        # Runner already retains its redacted diagnostics. Unknown exception text
        # is not echoed because a dependency may embed an environment credential.
        print(json.dumps({"status": "failed", "error": "Demo failed; inspect the credential-free runner artifacts."}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
