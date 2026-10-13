"""Explicit real-GPU acceptance through authenticated ASGI HTTP and managed images.

Uses disposable synthetic intake. CPU tests never invoke this command.
"""

import argparse
import asyncio
from datetime import UTC, datetime
import hashlib
from io import BytesIO
import json
from pathlib import Path
import secrets
import sys
from tempfile import TemporaryDirectory
import time

import httpx
from PIL import Image, ImageDraw, ImageFont

from rekit.auth import Actor, ActorKind, AuthConfig, OperatorCredential, Role, token_digest
from rekit.catalog.models import Catalog
from rekit.evidence.assets import ImageAssetStore
from rekit.evidence.store import EvidenceStore
from rekit.inference.adapters.local_transformers import MODEL_REVISION
from rekit.inference.provider import LocalVisionProvider, PROMPT_VERSION
from rekit.inference.service import InferenceService
from rekit.inference.store import InferenceStore
from rekit.inventory.store import InventoryStore
from rekit.main import create_app
from rekit.recovery.models import DispositionPolicy


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
DEFAULT_MODEL_DIR = ROOT / "models" / "Qwen3-VL-2B-Instruct" / MODEL_REVISION


def _console(value: dict) -> None:
    try:
        # ASCII JSON also works on a cp949 console; full Unicode lives in the artifact.
        print(json.dumps(value, ensure_ascii=True), flush=True)
    except (OSError, UnicodeError):
        pass


def _image() -> bytes:
    with Image.new("RGB", (768, 512), "white") as image, BytesIO() as buffer:
        drawing = ImageDraw.Draw(image)
        drawing.text((30, 20), "SYNTHETIC", fill="black", font=ImageFont.load_default(size=44))
        drawing.polygon(((200, 140), (70, 390), (330, 390)), fill="red")
        drawing.ellipse((440, 155, 690, 405), fill="blue")
        drawing.text((30, 460), "Illustration only - not a product photograph", fill="black",
                     font=ImageFont.load_default(size=22))
        image.save(buffer, format="PNG")
        return buffer.getvalue()


def _checked(response: httpx.Response, expected=200):
    if response.status_code != expected:
        raise RuntimeError(f"Acceptance expected HTTP {expected}, received {response.status_code}")
    return response.json()


async def _workflow(app, token: str, fixture: dict, raw: bytes, record: dict, device: int) -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://rekit-acceptance.local",
                                 headers={"Authorization": f"Bearer {token}"}, timeout=180) as client:
        _checked(await client.post("/batches", json=fixture["batch"]), 201)
        returned = fixture["returns"][0]
        _checked(await client.post("/returns", json=returned), 201)
        component = fixture["components"][0]["component"]
        cid = component["physical_component_id"]
        _checked(await client.post("/components", json=component), 201)
        upload = _checked(await client.post(f"/components/{cid}/images?return_id={returned['return_id']}",
                                            content=raw, headers={"Content-Type": "image/png"}), 201)
        record["managed_asset"] = upload["asset"]
        before = _checked(await client.get(f"/components/{cid}/history"))
        body = {"request_id": "real-api-qualification", "asset_ids": [upload["asset"]["asset_id"]],
                "expected_version": before["current"]["version"]}
        route = f"/components/{cid}/inference"
        unauthorized = await client.post(route, json=body, headers={"Authorization": "Bearer invalid"})
        _checked(unauthorized, 401)
        record["status_before"] = _checked(await client.get("/inference/status"))
        admitted = _checked(await client.post(route, json=body), 202)
        run_id = admitted["start"]["run_id"]
        record["run"] = admitted
        deadline = time.monotonic() + 175
        while time.monotonic() < deadline:
            current = _checked(await client.get(f"/inference/{run_id}"))
            record["run"] = current
            if current["outcome"] is not None:
                break
            await asyncio.sleep(0.1)
        else:
            raise RuntimeError("The real inference request did not reach a terminal outcome within 175 seconds")
        outcome = current["outcome"]
        if outcome["status"] != "succeeded":
            raise RuntimeError(f"Actual inference ended with {outcome['status']}; inspect the recorded outcome")
        if outcome["stale"] or not outcome["applied_event_ids"]:
            raise RuntimeError("The real inference result did not append current unverified evidence")
        start = current["start"]
        if (start["physical_component_id"] != cid or start["configuration"]["device"] != f"cuda:{device}"
                or start["inputs"][0]["sha256"] != hashlib.sha256(raw).hexdigest()
                or start["inputs"][0]["observation_id"] != upload["observation"]["observation_id"]):
            raise RuntimeError("Managed-image inference provenance did not match the request")
        metrics = outcome["metrics"]
        if metrics.get("vision_forward_calls", 0) < 1 or metrics.get("peak_allocated_bytes", 0) <= 0:
            raise RuntimeError("The stored run did not establish actual vision/GPU execution")
        configuration = start["configuration"]
        if (configuration["prompt_version"] != PROMPT_VERSION
                or configuration["generation"]["decoding"] != "lm-format-enforcer"
                or metrics.get("schema_sha256") != configuration["generation"]["schema_sha256_1"]
                or metrics.get("schema_version") != configuration["generation"]["schema_version"]
                or metrics.get("decoding") != configuration["generation"]["decoding"]):
            raise RuntimeError("The actual structured decoder did not match current configuration")
        for group in (outcome["output"]["observations"], outcome["output"]["candidates"], outcome["output"]["additional_views"]):
            if any(item["image_indices"] != [1] for item in group):
                raise RuntimeError("Single-image output has an invalid source reference")
        after = _checked(await client.get(f"/components/{cid}/history"))
        inventory = _checked(await client.get("/inventory"))
        compatibility = _checked(await client.get(f"/components/{cid}/compatibility?configuration_id=standard-kit"))
        if (after["current"]["verification"] is not None or after["current"]["state"] == "verified"
                or any(event["kind"] == "verification" for event in after["events"])
                or compatibility["compatible"] or len(inventory["items"]) != 1
                or inventory["items"][0]["availability"] != "held" or inventory["completed_kits"]):
            raise RuntimeError("The inference request bypassed a human or inventory boundary")
        if _checked(await client.post(route, json=body), 202) != current:
            raise RuntimeError("The exact HTTP retry did not return the immutable existing run")
        runs = _checked(await client.get(f"/components/{cid}/inference"))
        if len(runs) != 1 or runs[0] != current:
            raise RuntimeError("The request created an unexpected duplicate inference run")
        # This known fixture is an illustration, not evidence of a product ID or
        # revision. Record explicit human rejection of any actual model guess.
        if outcome["output"]["candidates"]:
            rejection = {"rejection_id": "real-api-unsupported-illustration",
                         "expected_version": after["current"]["version"],
                         "reason": "Synthetic shapes illustration does not establish a physical product identity or revision; the model proposal is unsupported."}
            _checked(await client.post(f"/inference/{run_id}/reject", json=rejection))
            rejected = _checked(await client.get(f"/components/{cid}/history"))
            event = next(item for item in rejected["events"] if item["event_id"] == rejection["rejection_id"])
            if (event["kind"] != "uncertainty" or run_id not in event["payload"]["reason"]
                    or rejected["current"]["verification"] is not None
                    or _checked(await client.get(f"/inference/{run_id}")) != current):
                raise RuntimeError("Human rejection did not preserve the original unverified run")
            record["unsupported_proposal_rejection"] = event
            record["evidence_after_rejection"] = rejected
        record["checks"] = {
            "authenticated_invocation": True, "managed_image_bytes_used": True,
            "actual_vision_execution": True, "physical_identity_preserved": True,
            "current_structured_decoder_verified": True, "image_references_validated": True,
            "exact_retry_reused_run": True, "human_verification_still_required": True,
            "unverified_inventory_held": True, "compatible_without_human_review": False,
        }
        record["evidence_after"] = after
        record["inventory_after"] = inventory
        record["status_after"] = _checked(await client.get("/inference/status"))


def run(model_dir: Path, device: int, output: Path) -> int:
    output = output.resolve()
    if output.suffix.lower() != ".json":
        raise ValueError("Acceptance output must be a JSON file")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary_root = ROOT / "var"
    if temporary_root.is_symlink() or temporary_root.is_junction() or not temporary_root.resolve().is_relative_to(ROOT):
        raise ValueError("Temporary acceptance state must remain inside the repository var directory")
    temporary_root.mkdir(exist_ok=True)
    record = {
        "status": "failed", "started_at": datetime.now(UTC).isoformat(),
        "synthetic": True, "transport": "real ASGI HTTP with in-process application",
        "requested_device": f"cuda:{device}", "real_inference_requests_requested": 1,
        "limitations": [
            "The synthetic image is not a product photograph or recognition-accuracy benchmark.",
            "All model output is unverified; no human identity verification or recovery approval is performed.",
            "Local NVIDIA execution does not qualify AMD ROCm/vLLM inference.",
        ],
    }
    temporary_path = None
    try:
        fixture = json.loads((FIXTURES / "synthetic_recovery.json").read_text(encoding="utf-8"))
        if fixture.get("synthetic") is not True:
            raise ValueError("Acceptance requires explicitly synthetic intake")
        catalog = Catalog.model_validate_json((FIXTURES / fixture["catalog_file"]).read_text(encoding="utf-8"))
        policy = DispositionPolicy.model_validate_json((FIXTURES / fixture["disposition_policy_file"]).read_text(encoding="utf-8"))
        raw = _image()
        image_path = output.with_suffix(".png")
        image_path.write_bytes(raw)
        record["input"] = {"image_path": str(image_path), "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
        token = secrets.token_urlsafe(32)
        auth = AuthConfig(operators=(OperatorCredential(
            actor=Actor(actor_id="real-inference-reviewer", kind=ActorKind.HUMAN, roles=tuple(Role)),
            token_sha256=token_digest(token),
        ),))
        with TemporaryDirectory(prefix="mission03-api-", dir=temporary_root) as directory:
            temporary_path = Path(directory).resolve()
            if temporary_path == temporary_root.resolve() or not temporary_path.is_relative_to(temporary_root.resolve()):
                raise RuntimeError("Unexpected temporary state directory")
            evidence = EvidenceStore(temporary_path / "acceptance.sqlite3", catalog)
            assets = ImageAssetStore(evidence, temporary_path / "images")
            inventory = InventoryStore(evidence, policy)
            provider = LocalVisionProvider(model_dir, device=device, catalog=catalog)
            service = InferenceService(InferenceStore(evidence, assets), provider)
            try:
                app = create_app(inventory, auth=auth, assets=assets, inference=service)
                asyncio.run(_workflow(app, token, fixture, raw, record, device))
            finally:
                service.close()
        record["status"] = "passed"
        exit_code = 0
    except Exception as error:
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        exit_code = 1
    finally:
        record["temporary_state_removed"] = temporary_path is None or not temporary_path.exists()
        record["finished_at"] = datetime.now(UTC).isoformat()
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _console({"status": record["status"], "result": str(output),
              "temporary_state_removed": record["temporary_state_removed"]})
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--device", type=int, default=1)
    parser.add_argument("--output", type=Path, default=ROOT / "var" / "mission03-api-acceptance.json")
    arguments = parser.parse_args()
    try:
        return run(arguments.model_dir, arguments.device, arguments.output)
    except (OSError, ValueError) as error:
        _console({"status": "failed", "error": type(error).__name__, "message": str(error)})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
