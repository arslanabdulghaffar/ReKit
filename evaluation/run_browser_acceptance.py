"""Run the real local browser scenario with disposable synthetic state.

No inventory is seeded: the browser registers every batch, return, and component.
Only screenshots and credential-free results/logs survive the run.
"""

import argparse
from datetime import UTC, datetime
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


def _prepare(*, real_inference: bool = False, model_dir: Path | None = None,
             device: int = 1) -> tuple[Path, dict]:
    if type(device) is not int or device < 0:
        raise RuntimeError("The GPU device must be a nonnegative index")
    if model_dir is not None and not real_inference:
        raise RuntimeError("A model directory requires explicit --real-inference opt-in")
    _checked_directory(OUTPUT, ROOT)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix="run-ai-" if real_inference else "run-", dir=OUTPUT))
    state = run_dir / "state"
    state.mkdir(mode=0o700)
    try:
        fixture = json.loads((FIXTURES / "synthetic_recovery.json").read_text(encoding="utf-8"))
        if fixture.get("synthetic") is not True or fixture["scenario"].get("scenario_estimate") is not True:
            raise RuntimeError("Browser acceptance requires explicitly synthetic inputs")
        image_dir = state / "input-images"
        image_dir.mkdir()
        images = {}
        for index, record in enumerate(fixture["components"]):
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
        }
        if real_inference:
            from rekit.inference.adapters.local_transformers import MODEL_REVISION

            model_dir = model_dir or ROOT / "models" / "Qwen3-VL-2B-Instruct" / MODEL_REVISION
            ambiguous_path = image_dir / "synthetic-ambiguous-view.png"
            with Image.new("RGB", (768, 512), "white") as image:
                drawing = ImageDraw.Draw(image)
                drawing.text((30, 20), "SYNTHETIC", fill="black", font=ImageFont.load_default(size=44))
                drawing.polygon(((200, 140), (70, 390), (330, 390)), fill="red")
                drawing.ellipse((440, 155, 690, 405), fill="blue")
                drawing.text((30, 460), "Illustration only - not a product photograph", fill="black",
                             font=ImageFont.load_default(size=22))
                image.save(ambiguous_path, format="PNG")
            manifest.update(model_dir=str(model_dir.resolve()), device=device,
                            model_revision=MODEL_REVISION, ambiguous_image=str(ambiguous_path))
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
            Path(manifest["model_dir"]), device=manifest["device"], catalog=catalog,
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


def run(*, check_only: bool = False, real_inference: bool = False,
        model_dir: Path | None = None, device: int = 1) -> int:
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
    manifest_path, manifest = _prepare(real_inference=real_inference, model_dir=model_dir, device=device)
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
                for paths in manifest["images"].values():
                    for path in paths:
                        with Image.open(path) as image:
                            image.load()
                            if image.format != "PNG" or image.size != (720, 440):
                                raise RuntimeError("Generated acceptance image is invalid")
                if real_inference:
                    with Image.open(manifest["ambiguous_image"]) as image:
                        image.load()
                        if image.format != "PNG" or image.size != (768, 512):
                            raise RuntimeError("Generated ambiguous image is invalid")
            finally:
                if app.state.inference is not None:
                    app.state.inference.close()
            status = "setup_passed"
            _console(json.dumps({"setup": "passed", "synthetic_images": sum(len(paths) for paths in manifest["images"].values()) + int(real_inference),
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
            browser_output, _ = browser.communicate(timeout=900 if real_inference else 300)
        except subprocess.TimeoutExpired as failure:
            status = "timed_out"
            browser_output = failure.output or b""
            _stop(browser)
            browser_output, _ = browser.communicate(timeout=5)
            raise RuntimeError(f"Browser acceptance exceeded its {900 if real_inference else 300} second limit") from None
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
    parser.add_argument("--real-inference", action="store_true", help="Explicitly run two real GPU inspections inside browser recovery acceptance")
    parser.add_argument("--model-dir", type=Path, help="Server-controlled verified local checkpoint directory; never downloaded by this runner")
    parser.add_argument("--device", type=int, default=1, help="Single CUDA GPU index for the optional real inference scenario")
    parser.add_argument("--serve-state", type=Path, help=argparse.SUPPRESS)
    arguments = parser.parse_args()
    if arguments.serve_state:
        import uvicorn

        manifest = json.loads(arguments.serve_state.read_text(encoding="utf-8"))
        uvicorn.run(_application(manifest), host=HOST, port=8000, log_level="warning", access_log=False)
        return 0
    try:
        return run(check_only=arguments.check, real_inference=arguments.real_inference,
                   model_dir=arguments.model_dir, device=arguments.device)
    except (RuntimeError, OSError) as error:
        _console(f"Acceptance runner failed: {error}", stream=sys.stderr)
        return 1
    except KeyboardInterrupt:
        _console("Acceptance interrupted; inspect runner-result.json for cleanup results.", stream=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
