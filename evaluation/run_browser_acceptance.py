"""Run the real local browser scenario with disposable synthetic state.

No inventory is seeded: the browser registers every batch, return, and component.
Only screenshots and credential-free results/logs survive the run.
"""

import argparse
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import ProxyHandler, Request, build_opener

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
FIXTURES = ROOT / "tests" / "fixtures"
OUTPUT = ROOT / "var" / "mission02-acceptance"
HOST = "127.0.0.1"
API_URL = f"http://{HOST}:8000"
BASE_URL = f"http://{HOST}:5173"
PRODUCT_IMAGE_IDS = ("71rr7OjqWqL", "812Xgtrv0EL")
PRODUCT_COMPONENT_ID = "photo-demo-unit"


def _presentation(*, headed: bool = False, slow_mo_ms: int = 0, hold_seconds: int = 0) -> dict:
    if (type(headed) is not bool or type(slow_mo_ms) is not int or not 0 <= slow_mo_ms <= 500
            or type(hold_seconds) is not int or not 0 <= hold_seconds <= 120):
        raise RuntimeError("Demo presentation needs a boolean headed flag, 0..500 ms pacing and 0..120 seconds hold")
    if not headed and (slow_mo_ms or hold_seconds):
        raise RuntimeError("Demo pacing and final inspection require --headed")
    return {"headed": headed, "slow_mo_ms": slow_mo_ms, "hold_seconds": hold_seconds}


def _console(text: str, *, stream=None) -> None:
    """Best-effort console output; durable UTF-8 diagnostics are written separately."""
    stream = sys.stdout if stream is None else stream
    try:
        encoding = getattr(stream, "encoding", None) or "utf-8"
        safe = text.encode(encoding, errors="backslashreplace").decode(encoding)
        stream.write(safe + ("" if safe.endswith("\n") else "\n"))
        stream.flush()
    except (OSError, UnicodeError, LookupError, ValueError):
        # A legacy encoding, closed pipe, or detached console must not change the
        # browser result or prevent cleanup and machine-readable reporting.
        pass


def _redact(text: str, manifest: dict) -> str:
    for key in ("operator_token", "viewer_token"):
        text = text.replace(manifest[key], "[REDACTED]")
    return text


def _checked_directory(path: Path, parent: Path) -> Path:
    """Check the exact owned path before creating or recursively removing state."""
    resolved = path.resolve()
    if resolved == parent.resolve() or not resolved.is_relative_to(parent.resolve()):
        raise RuntimeError("Acceptance output must stay inside its owned parent directory")
    cursor = path
    while cursor != parent:
        if cursor.is_symlink() or cursor.is_junction():
            raise RuntimeError("Acceptance state must not traverse a link or junction")
        cursor = cursor.parent
    return resolved


def _load_product_sources() -> dict:
    """Read and verify the fixed development pair; never fetch or alter images."""
    from product_data import DatasetManifest, MAX_MANIFEST_BYTES, verify_images

    manifest_path = ROOT / "evaluation" / "fixtures" / "abo-manifest.json"
    with manifest_path.open("rb") as source:
        raw = source.read(MAX_MANIFEST_BYTES + 1)
    if len(raw) > MAX_MANIFEST_BYTES:
        raise RuntimeError("The product-image source manifest exceeds its bound")
    try:
        dataset = DatasetManifest.model_validate_json(raw)
        by_id = {image.image_id: image for image in dataset.images}
        selected = [by_id[image_id] for image_id in PRODUCT_IMAGE_IDS]
        if any(image.split != "development" for image in selected) or len({image.group_id for image in selected}) != 1:
            raise ValueError("The selected pair must come from one development listing")
        image_root = ROOT / "var" / "evaluation" / "abo"
        verify_images(dataset.model_copy(update={"images": selected}), image_root)
    except (KeyError, ValueError) as error:
        raise RuntimeError(f"Product-image setup failed: {error}") from None
    return {
        "images": {PRODUCT_COMPONENT_ID: [str((image_root / image.local_path).resolve()) for image in selected]},
        "product_sources": [image.model_dump(mode="json") for image in selected],
        "dataset": dataset.dataset,
        "dataset_attribution": dataset.attribution,
        "dataset_source": dataset.source_url,
        "dataset_license": {"id": dataset.license_id, "url": dataset.license_url},
        "dataset_manifest_sha256": hashlib.sha256(raw).hexdigest(),
    }


def _prepare(*, real_inference: bool = False, real_product_images: bool = False, model_dir: Path | None = None,
             device: int = 1, headed: bool = False, slow_mo_ms: int = 0,
             hold_seconds: int = 0) -> tuple[Path, dict]:
    presentation = _presentation(headed=headed, slow_mo_ms=slow_mo_ms, hold_seconds=hold_seconds)
    if type(real_inference) is not bool or type(real_product_images) is not bool:
        raise RuntimeError("Inference and real-product options must be explicit booleans")
    if real_product_images and not real_inference:
        raise RuntimeError("Real product images require explicit --real-inference opt-in")
    if type(device) is not int or device < 0:
        raise RuntimeError("The GPU device must be a nonnegative index")
    if model_dir is not None and not real_inference:
        raise RuntimeError("A model directory requires explicit --real-inference opt-in")
    product_sources = _load_product_sources() if real_product_images else None
    _checked_directory(OUTPUT, ROOT)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="run-ai-" if real_inference else "run-", dir=OUTPUT))
    state = run_dir / "state"
    state.mkdir(mode=0o700)
    try:
        fixture = json.loads((FIXTURES / "synthetic_recovery.json").read_text(encoding="utf-8"))
        if fixture.get("synthetic") is not True or fixture["scenario"].get("scenario_estimate") is not True:
            raise RuntimeError("Browser acceptance requires explicitly synthetic inputs")
        if real_product_images:
            timestamp = fixture["batch"]["received_at"]
            fixture = {
                "fixture_id": "simulated-intake-real-product-images", "synthetic": True,
                "description": "Simulated intake only. Original ABO source images have no verified identity or condition.",
                "catalog_file": fixture["catalog_file"], "disposition_policy_file": fixture["disposition_policy_file"],
                "batch": {"batch_id": "photo-demo-batch", "received_at": timestamp},
                "returns": [{"return_id": "photo-demo-return", "batch_id": "photo-demo-batch",
                             "product_family_id": fixture["returns"][0]["product_family_id"],
                             "declared_configuration_id": None, "received_at": timestamp}],
                "components": [{"component": {"physical_component_id": PRODUCT_COMPONENT_ID,
                                              "source_return_id": "photo-demo-return", "registered_at": timestamp}}],
            }
        image_dir = state / "input-images"
        image_dir.mkdir()
        images = {}
        for index, record in enumerate([] if real_product_images else fixture["components"]):
            component_id = record["component"]["physical_component_id"]
            identity = record["verification"]["identity"]
            paths = []
            for view in (1, 2):
                image = Image.new("RGB", (720, 440), "#eef1e9")
                drawing = ImageDraw.Draw(image)
                drawing.text((24, 24), "SYNTHETIC TEST IMAGE - NOT A PRODUCT PHOTOGRAPH", fill="#171c17")
                drawing.rounded_rectangle((90 + view * 8, 100, 625, 280), radius=20,
                                          fill="#344939" if identity["component_type_id"] == "body" else "#8b662c")
                drawing.text((120, 155), f"{component_id} / VIEW {view}", fill="white")
                drawing.text((120, 190), f"INVENTED {identity['component_type_id']} / REV {identity['revision']}", fill="white")
                footer = ("Synthetic label fixture; no recognition or safety claim." if real_inference
                          else "Manual synthetic review only. No inference or safety claim.")
                drawing.text((24, 355), footer, fill="#171c17")
                path = image_dir / f"component-{index + 1}-view-{view}.png"
                image.save(path, format="PNG")
                paths.append(str(path))
            images[component_id] = paths
        manifest = {
            "synthetic": True, "base_url": BASE_URL, "api_url": API_URL,
            "operator_token": secrets.token_urlsafe(32), "viewer_token": secrets.token_urlsafe(32),
            "operator_id": "browser-reviewer", "viewer_id": "browser-viewer",
            "fixture": fixture, "images": images, "artifacts_dir": str(run_dir),
            "state_dir": str(state),
            "real_inference": real_inference,
            "real_product_images": real_product_images, "simulated_intake": True,
            "demo_presentation": presentation,
        }
        if product_sources is not None:
            manifest.update(product_sources)
        if real_inference:
            from rekit.inference.adapters.local_transformers import MODEL_REVISION

            model_dir = model_dir or ROOT / "models" / "Qwen3-VL-2B-Instruct" / MODEL_REVISION
            manifest.update(model_dir=str(model_dir.resolve()), device=device,
                            model_revision=MODEL_REVISION)
            if not real_product_images:
                ambiguous_path = image_dir / "synthetic-ambiguous-view.png"
                with Image.new("RGB", (768, 512), "white") as image:
                    drawing = ImageDraw.Draw(image)
                    drawing.text((30, 20), "SYNTHETIC", fill="black", font=ImageFont.load_default(size=44))
                    drawing.polygon(((200, 140), (70, 390), (330, 390)), fill="red")
                    drawing.ellipse((440, 155, 690, 405), fill="blue")
                    drawing.text((30, 460), "Illustration only - not a product photograph", fill="black",
                                 font=ImageFont.load_default(size=22))
                    image.save(ambiguous_path, format="PNG")
                manifest["ambiguous_image"] = str(ambiguous_path)
        manifest_path = state / "fixture.json"
        descriptor = os.open(manifest_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as file:
            json.dump(manifest, file)
        return manifest_path, manifest
    except BaseException:
        shutil.rmtree(_checked_directory(state, run_dir))
        raise


def _application(manifest: dict):
    from rekit.auth import Actor, ActorKind, AuthConfig, OperatorCredential, Role, token_digest
    from rekit.catalog.models import Catalog
    from rekit.evidence.assets import ImageAssetStore
    from rekit.evidence.store import EvidenceStore
    from rekit.inventory.store import InventoryStore
    from rekit.main import create_app
    from rekit.recovery.models import DispositionPolicy

    state = _checked_directory(Path(manifest["state_dir"]), OUTPUT)
    catalog = Catalog.model_validate_json((FIXTURES / "synthetic_catalog.json").read_text(encoding="utf-8"))
    policy = DispositionPolicy.model_validate_json((FIXTURES / "synthetic_disposition_policy.json").read_text(encoding="utf-8"))
    evidence = EvidenceStore(state / "acceptance.sqlite3", catalog)
    inventory = InventoryStore(evidence, policy)
    assets = ImageAssetStore(evidence, state / "stored-images")
    auth = AuthConfig(operators=tuple(
        OperatorCredential(
            actor=Actor(actor_id=manifest[f"{name}_id"], kind=ActorKind.HUMAN, roles=roles),
            token_sha256=token_digest(manifest[f"{name}_token"]),
        ) for name, roles in (("operator", tuple(Role)), ("viewer", (Role.VIEWER,)))
    ))
    if inventory.inventory().items or evidence.list_batches() or evidence.list_returns():
        raise RuntimeError("Browser acceptance must start with empty inventory and intake records")
    inference = None
    if manifest.get("real_inference") is True:
        from rekit.inference.provider import LocalVisionProvider
        from rekit.inference.service import InferenceService
        from rekit.inference.store import InferenceStore

        inference = InferenceService(InferenceStore(evidence, assets), LocalVisionProvider(
            Path(manifest["model_dir"]), device=manifest["device"],
            catalog=None if manifest.get("real_product_images") is True else catalog,
        ))
    return create_app(inventory, auth=auth, assets=assets, inference=inference)


def _port_free(port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        if os.name == "nt":
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            probe.bind((HOST, port))
        except OSError:
            raise RuntimeError(f"Required IPv4 port {HOST}:{port} is busy; no process was stopped") from None


def _start(command: list[str], *, output, environment: dict[str, str] | None = None) -> subprocess.Popen:
    return subprocess.Popen(
        command, cwd=FRONTEND, env=environment, stdin=subprocess.DEVNULL,
        stdout=output, stderr=subprocess.STDOUT,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        start_new_session=os.name != "nt",
    )


def _stop(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        # The only target is a still-running child created by this runner.
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW, timeout=15, check=False,
        )
    else:
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            process.kill()
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)


def _ready(process: subprocess.Popen, url: str, token: str) -> None:
    opener = build_opener(ProxyHandler({}))
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("An acceptance server exited before becoming ready; inspect its local log")
        try:
            request = Request(url, headers={"Authorization": f"Bearer {token}"})
            with opener.open(request, timeout=1) as response:
                actor = json.load(response)
                if actor.get("actor_id") == "browser-reviewer":
                    return
        except (URLError, TimeoutError, ValueError, OSError):
            pass
        time.sleep(0.15)
    raise RuntimeError("An acceptance server did not become ready within 45 seconds")


def _finish(manifest_path: Path, manifest: dict, processes: list, logs: list,
            *, status: str, browser_output: bytes, browser_exit_code: int | None,
            error: str | None) -> None:
    """Preserve diagnostics and cleanup outcomes even when one cleanup step fails."""
    run_dir, state = Path(manifest["artifacts_dir"]), Path(manifest["state_dir"])
    cleanup_errors, reporting_errors = [], []
    for process in reversed(processes):
        try:
            _stop(process)
        except (OSError, subprocess.SubprocessError) as failure:
            cleanup_errors.append(f"Could not stop owned process {process.pid}: {failure}")
    for log in logs:
        try:
            log.close()
        except OSError as failure:
            cleanup_errors.append(f"Could not close an acceptance log: {failure}")
    text = _redact(browser_output.decode("utf-8", errors="replace"), manifest)
    try:
        (run_dir / "browser.log").write_text(text, encoding="utf-8")
    except OSError as failure:
        reporting_errors.append(f"Could not write browser.log: {failure}")
    state_removed = credentials_removed = False
    try:
        checked_state = _checked_directory(state, run_dir)
        try:
            manifest_path.unlink(missing_ok=True)
        finally:
            # Removing the owned directory is also attempted if unlink failed.
            shutil.rmtree(checked_state)
    except (OSError, RuntimeError) as failure:
        cleanup_errors.append(f"Could not completely remove temporary state: {failure}")
    finally:
        state_removed = not state.exists()
        credentials_removed = not manifest_path.exists()
    result = {
        "status": "cleanup_failed" if cleanup_errors else "reporting_failed" if reporting_errors else status,
        "browser_status": status, "browser_exit_code": browser_exit_code,
        "browser_run": len(processes) == 3, "synthetic": True,
        "real_inference_enabled": manifest.get("real_inference", False),
        "real_product_images": manifest.get("real_product_images", False), "simulated_intake": True,
        "demo_presentation": manifest.get("demo_presentation", _presentation()),
        "finished_at": datetime.now(UTC).isoformat(),
        "temporary_state_removed": state_removed, "credentials_removed": credentials_removed,
        "error": _redact(error, manifest) if error else None,
        "cleanup_errors": [_redact(message, manifest) for message in cleanup_errors],
        "reporting_errors": [_redact(message, manifest) for message in reporting_errors],
    }
    try:
        (run_dir / "runner-result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    except OSError as failure:
        reporting_errors.append(f"Could not write runner-result.json: {failure}")
    # Console availability/encoding cannot suppress the result file above.
    if text:
        _console(text)
    if cleanup_errors or reporting_errors:
        raise RuntimeError(_redact("; ".join(cleanup_errors + reporting_errors), manifest))


def run(*, check_only: bool = False, real_inference: bool = False, real_product_images: bool = False,
        model_dir: Path | None = None, device: int = 1, headed: bool = False,
        slow_mo_ms: int = 0, hold_seconds: int = 0) -> int:
    _presentation(headed=headed, slow_mo_ms=slow_mo_ms, hold_seconds=hold_seconds)
    # Budget pacing for up to 1,000 browser actions plus the bounded final hold.
    browser_timeout = (900 if real_inference else 300) + slow_mo_ms + hold_seconds
    if type(real_inference) is not bool or type(real_product_images) is not bool:
        raise RuntimeError("Inference and real-product options must be explicit booleans")
    if real_product_images and not real_inference:
        raise RuntimeError("Real product images require explicit --real-inference opt-in")
    if type(device) is not int or device < 0:
        raise RuntimeError("The GPU device must be a nonnegative index")
    if model_dir is not None and not real_inference:
        raise RuntimeError("A model directory requires explicit --real-inference opt-in")
    node = shutil.which("node")
    vite = FRONTEND / "node_modules" / "vite" / "bin" / "vite.js"
    playwright = FRONTEND / "node_modules" / "@playwright" / "test" / "cli.js"
    if not check_only:
        if node is None or not vite.is_file() or not playwright.is_file():
            raise RuntimeError("Install the pinned local frontend dependencies before browser acceptance")
        for port in (8000, 5173):
            _port_free(port)
    manifest_path, manifest = _prepare(real_inference=real_inference, real_product_images=real_product_images,
                                       model_dir=model_dir, device=device, headed=headed,
                                       slow_mo_ms=slow_mo_ms, hold_seconds=hold_seconds)
    run_dir, state = Path(manifest["artifacts_dir"]), Path(manifest["state_dir"])
    processes, logs = [], []
    status = "error"
    browser_output = b""
    browser_exit_code = None
    error_detail = None
    try:
        if check_only:
            app = _application(manifest)
            try:
                for paths in ([] if real_product_images else manifest["images"].values()):
                    for path in paths:
                        with Image.open(path) as image:
                            image.load()
                            if image.format != "PNG" or image.size != (720, 440):
                                raise RuntimeError("Generated acceptance image is invalid")
                if real_inference and not real_product_images:
                    with Image.open(manifest["ambiguous_image"]) as image:
                        image.load()
                        if image.format != "PNG" or image.size != (768, 512):
                            raise RuntimeError("Generated ambiguous image is invalid")
            finally:
                if app.state.inference is not None:
                    app.state.inference.close()
            status = "setup_passed"
            _console(json.dumps({"setup": "passed", "synthetic_images": 0 if real_product_images else sum(len(paths) for paths in manifest["images"].values()) + int(real_inference),
                                 "real_product_images": real_product_images, "simulated_intake": True,
                                 "original_product_images": len(manifest.get("product_sources", [])),
                                 "registered_components": len(app.state.inventory.inventory().items), "browser_run": False,
                                 "real_inference_enabled": real_inference, "model_executed": False}))
            return 0
        environment = os.environ.copy()
        environment["REKIT_BROWSER_FIXTURE"] = str(manifest_path)
        environment["PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD"] = "1"
        environment["PYTHONIOENCODING"] = "utf-8:backslashreplace"
        for name in ("backend", "frontend"):
            logs.append((run_dir / f"{name}.log").open("wb"))
        backend = _start([sys.executable, str(Path(__file__).resolve()), "--serve-state", str(manifest_path)],
                         output=logs[0], environment=environment)
        processes.append(backend)
        _ready(backend, f"{API_URL}/auth/me", manifest["operator_token"])
        frontend = _start([node, str(vite), "--host", HOST, "--port", "5173", "--strictPort"],
                          output=logs[1], environment=environment)
        processes.append(frontend)
        _ready(frontend, f"{BASE_URL}/api/auth/me", manifest["operator_token"])
        _console(f"Running real browser acceptance; artifacts: {run_dir}")
        browser = _start([node, str(playwright), "test", "--config", "playwright.config.ts"],
                         output=subprocess.PIPE, environment=environment)
        processes.append(browser)
        try:
            browser_output, _ = browser.communicate(timeout=browser_timeout)
        except subprocess.TimeoutExpired as failure:
            status = "timed_out"
            browser_output = failure.output or b""
            _stop(browser)
            browser_output, _ = browser.communicate(timeout=5)
            raise RuntimeError(f"Browser acceptance exceeded its {browser_timeout} second limit") from None
        browser_exit_code = browser.returncode
        status = "passed" if browser.returncode == 0 else "failed"
        return browser.returncode
    except KeyboardInterrupt:
        status = "interrupted"
        error_detail = "Acceptance interrupted"
        raise
    except Exception as error:
        error_detail = _redact(f"{type(error).__name__}: {error}", manifest)
        raise RuntimeError(error_detail) from None
    finally:
        _finish(manifest_path, manifest, processes, logs, status=status,
                browser_output=browser_output, browser_exit_code=browser_exit_code, error=error_detail)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check disposable fixture setup without starting servers or a browser")
    parser.add_argument("--real-inference", action="store_true", help="Run actual GPU inference: two synthetic inspections, or one joint inspection with --real-product-images")
    parser.add_argument("--real-product-images", action="store_true", help="Use a verified original ABO pair with simulated intake; requires --real-inference")
    parser.add_argument("--model-dir", type=Path, help="Server-controlled verified local checkpoint directory; never downloaded by this runner")
    parser.add_argument("--device", type=int, default=1, help="Single CUDA GPU index for the optional real inference scenario")
    parser.add_argument("--headed", action="store_true", help="Show the owned browser for a local demonstration")
    parser.add_argument("--slow-mo-ms", type=int, default=0, help="Pace visible browser actions by 0..500 ms; requires --headed")
    parser.add_argument("--hold-seconds", type=int, default=0, help="Keep the successful final page open for 0..120 seconds; requires --headed")
    parser.add_argument("--serve-state", type=Path, help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if arguments.serve_state:
        import uvicorn

        manifest = json.loads(arguments.serve_state.read_text(encoding="utf-8"))
        uvicorn.run(_application(manifest), host=HOST, port=8000, log_level="warning", access_log=False)
        return 0
    try:
        return run(check_only=arguments.check, real_inference=arguments.real_inference,
                   real_product_images=arguments.real_product_images,
                   model_dir=arguments.model_dir, device=arguments.device, headed=arguments.headed,
                   slow_mo_ms=arguments.slow_mo_ms, hold_seconds=arguments.hold_seconds)
    except (RuntimeError, OSError) as error:
        _console(f"Acceptance runner failed: {error}", stream=sys.stderr)
        return 1
    except KeyboardInterrupt:
        _console("Acceptance interrupted; inspect runner-result.json for cleanup results.", stream=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
