"""Authenticated inference transport with controlled CPU providers, never real AI."""

import asyncio
import hashlib
from io import BytesIO
import json
from pathlib import Path
import secrets
import threading
import time
from types import SimpleNamespace

import httpx
from PIL import Image
import pytest

from rekit.auth import Actor, ActorKind, AuthConfig, OperatorCredential, Role, token_digest
from rekit.catalog.models import Catalog
from rekit.evidence.assets import ImageAssetStore
from rekit.evidence.models import PhysicalComponent, ReturnBatch, ReturnRecord
from rekit.evidence.store import EvidenceStore
from rekit.inference.models import InferenceConfiguration
from rekit.inference.provider import VisionTimeout, VisionUnavailable
from rekit.inference.service import InferenceService
from rekit.inference.store import InferenceStore
from rekit.inventory.store import InventoryStore
from rekit.main import create_app, create_configured_app
from rekit.recovery.models import DispositionPolicy


FIXTURES = Path(__file__).parents[1] / "fixtures"
CONTROLLED_OUTPUT = {
    "observations": [{"kind": "appearance", "text": "Controlled CPU test observation, not model inference.", "image_indices": [1]}],
    "candidates": [], "uncertainties": ["The synthetic input does not establish a catalog identity."],
    "additional_views": [{"view": "Revision label close-up", "reason": "The revision is unreadable.", "image_indices": [1]}],
}


class ControlledProvider:
    def __init__(self):
        self.configuration = InferenceConfiguration(
            provider="controlled-test-double", model_repository="test/controlled-vision",
            model_revision="a" * 40, processor_revision="a" * 40,
            runtime={"engine": "CPU test double"}, device="cpu-test-double", prompt_version="test-v1",
            preprocessing={"max_images": 2}, generation={"max_new_tokens": 128},
        )
        self.status = "ready"
        self.calls = []
        self.entered = threading.Event()
        self.release = threading.Event()
        self.release.set()
        self.text = json.dumps(CONTROLLED_OUTPUT)
        self.error = None
        self.result_changes = {}

    def inspect(self, images):
        self.calls.append(tuple(images))
        self.entered.set()
        if not self.release.wait(timeout=10):
            raise RuntimeError("Controlled provider was not released by the test")
        if self.error is not None:
            raise self.error
        return {
            "text": self.text, "provider": self.configuration.provider,
            "model_repository": self.configuration.model_repository,
            "model_revision": self.configuration.model_revision, "device": self.configuration.device,
            "runtime": self.configuration.runtime,
            "metrics": {"input_sha256": [hashlib.sha256(raw).hexdigest() for raw in images],
                        "vision_forward_calls": 1, "test_double": True},
        } | self.result_changes


@pytest.fixture
def workflow(tmp_path, request):
    fixture = json.loads((FIXTURES / "synthetic_recovery.json").read_text(encoding="utf-8"))
    catalog = Catalog.model_validate_json((FIXTURES / fixture["catalog_file"]).read_text(encoding="utf-8"))
    policy = DispositionPolicy.model_validate_json((FIXTURES / fixture["disposition_policy_file"]).read_text(encoding="utf-8"))
    evidence = EvidenceStore(tmp_path / "inference-api.sqlite3", catalog)
    assets = ImageAssetStore(evidence, tmp_path / "images")
    inventory = InventoryStore(evidence, policy)
    evidence.register_batch(ReturnBatch.model_validate(fixture["batch"]))
    evidence.register_return(ReturnRecord.model_validate(fixture["returns"][0]))
    uploads, raw_images = {}, {}
    for index, record in enumerate(fixture["components"][:2]):
        component = PhysicalComponent.model_validate(record["component"])
        evidence.register_component(component)
        with Image.new("RGB", (32, 24), (60 + index * 100, 80, 130)) as image, BytesIO() as buffer:
            image.save(buffer, format="PNG")
            raw = buffer.getvalue()
        raw_images[component.physical_component_id] = raw
        uploads[component.physical_component_id] = assets.upload(
            component.physical_component_id, component.source_return_id, raw, "image/png", "reviewer",
        )
    actors = (
        Actor(actor_id="reviewer", kind=ActorKind.HUMAN, roles=tuple(Role)),
        Actor(actor_id="other-reviewer", kind=ActorKind.HUMAN, roles=tuple(Role)),
        Actor(actor_id="viewer", kind=ActorKind.HUMAN, roles=(Role.VIEWER,)),
        Actor(actor_id="service", kind=ActorKind.SERVICE, roles=(Role.VIEWER, Role.INTAKE)),
    )
    tokens = {actor.actor_id: secrets.token_urlsafe(32) for actor in actors}
    auth = AuthConfig(operators=tuple(OperatorCredential(actor=actor, token_sha256=token_digest(tokens[actor.actor_id])) for actor in actors))
    store = InferenceStore(evidence, assets)
    provider = ControlledProvider()
    service = InferenceService(store, provider, timeout_seconds=getattr(request, "param", 2))
    result = SimpleNamespace(
        fixture=fixture, evidence=evidence, assets=assets, inventory=inventory, store=store,
        provider=provider, service=service, auth=auth, tokens=tokens, uploads=uploads, raw_images=raw_images,
        component_id=next(iter(uploads)),
        app=create_app(inventory, auth=auth, assets=assets, inference=service),
    )
    try:
        yield result
    finally:
        provider.release.set()
        service.close()


def headers(workflow, actor="reviewer"):
    return {"Authorization": f"Bearer {workflow.tokens[actor]}"}


def command(workflow, request_id="api-inspection", **changes):
    return {
        "request_id": request_id,
        "asset_ids": [workflow.uploads[workflow.component_id].asset.asset_id],
        "expected_version": workflow.evidence.current(workflow.component_id).version,
    } | changes


def checked(response, expected=200):
    assert response.status_code == expected, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


async def poll(client, run_id, *, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = checked(await client.get(f"/inference/{run_id}"))
        if run["outcome"] is not None:
            return run
        await asyncio.sleep(0.01)
    raise AssertionError("Controlled inference did not terminalize")


async def wait_entered(provider):
    deadline = time.monotonic() + 2
    while not provider.entered.is_set() and time.monotonic() < deadline:
        await asyncio.sleep(0.01)
    assert provider.entered.is_set()


@pytest.mark.parametrize("image_count", [1, 2])
def test_http_inference_uses_managed_bytes_and_retains_human_verification_gate(workflow, image_count):
    selected_ids = [workflow.uploads[workflow.component_id].asset.asset_id]
    selected_bytes = [workflow.raw_images[workflow.component_id]]
    if image_count == 2:
        component = workflow.evidence.get_component(workflow.component_id)
        with Image.new("RGB", (32, 24), "green") as image, BytesIO() as buffer:
            image.save(buffer, format="PNG")
            raw = buffer.getvalue()
        uploaded = workflow.assets.upload(component.physical_component_id, component.source_return_id,
                                           raw, "image/png", "reviewer")
        selected_ids.append(uploaded.asset.asset_id)
        selected_bytes.append(raw)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            status = checked(await client.get("/inference/status"))
            assert status["provider"] == "controlled-test-double"
            assert status["busy"] is False
            accepted = checked(await client.post(f"/components/{workflow.component_id}/inference", json=command(workflow, asset_ids=selected_ids)), 202)
            run = await poll(client, accepted["start"]["run_id"])
            assert run["outcome"]["status"] == "succeeded"
            assert run["outcome"]["output"] == CONTROLLED_OUTPUT
            assert run["start"]["actor_id"] == "reviewer"
            assert run["start"]["physical_component_id"] == workflow.component_id
            assert run["start"]["inputs"][0]["sha256"] == hashlib.sha256(workflow.raw_images[workflow.component_id]).hexdigest()
            assert len(run["start"]["inputs"]) == image_count
            assert workflow.provider.calls == [tuple(selected_bytes)]
            listed = checked(await client.get(f"/components/{workflow.component_id}/inference"))
            assert listed == [run]
            assert checked(await client.get(f"/inference/{run['start']['run_id']}", headers=headers(workflow, "viewer"))) == run
            history = checked(await client.get(f"/components/{workflow.component_id}/history"))
            assert history["current"]["state"] != "verified"
            assert history["current"]["verification"] is None
            assert not any(event["kind"] == "verification" for event in history["events"])
            inventory = checked(await client.get("/inventory"))
            assert len(inventory["items"]) == 2
            assert all(entry["availability"] == "held" for entry in inventory["items"])
            assert inventory["completed_kits"] == []
            assert checked(await client.get(f"/components/{workflow.component_id}/compatibility?configuration_id=standard-kit"))["compatible"] is False
    asyncio.run(scenario())


@pytest.mark.parametrize("actor,status", [(None, 401), ("viewer", 403), ("service", 403)])
def test_invocation_requires_authenticated_human_reviewer(workflow, actor, status):
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            response = await client.post(f"/components/{workflow.component_id}/inference", json=command(workflow),
                                         headers=headers(workflow, actor) if actor else {})
            checked(response, status)
            if actor is None:
                for path in ("/inference/status", f"/components/{workflow.component_id}/inference", "/inference/unknown-run"):
                    checked(await client.get(path), 401)
        assert workflow.store.list_for_component(workflow.component_id) == ()
        assert workflow.provider.calls == []
    asyncio.run(scenario())


@pytest.mark.parametrize("extra", ["physical_component_id", "operator_id", "image_url", "model_repository"])
def test_client_cannot_override_identity_authority_or_provider_configuration(workflow, extra):
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            checked(await client.post(f"/components/{workflow.component_id}/inference", json=command(workflow) | {extra: "untrusted override"}), 422)
        assert workflow.provider.calls == []
        assert workflow.store.list_for_component(workflow.component_id) == ()
    asyncio.run(scenario())


@pytest.mark.parametrize("invalid", ["unknown_asset", "other_component", "stale_version", "duplicate_asset", "three_assets"])
def test_invalid_ownership_or_evidence_version_never_reaches_provider(workflow, invalid):
    values = command(workflow)
    expected = 409
    if invalid == "unknown_asset":
        values["asset_ids"] = ["asset-" + "f" * 32]
        expected = 404
    elif invalid == "other_component":
        other = next(cid for cid in workflow.uploads if cid != workflow.component_id)
        values["asset_ids"] = [workflow.uploads[other].asset.asset_id]
    elif invalid == "stale_version":
        values["expected_version"] = 1
    else:
        values["asset_ids"] *= 2 if invalid == "duplicate_asset" else 3
        expected = 422

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            checked(await client.post(f"/components/{workflow.component_id}/inference", json=values), expected)
        assert workflow.provider.calls == []
        assert workflow.store.list_for_component(workflow.component_id) == ()
    asyncio.run(scenario())


def test_exact_retry_deduplicates_busy_work_and_other_requests_are_rejected(workflow):
    workflow.provider.release.clear()

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            body = command(workflow)
            route = f"/components/{workflow.component_id}/inference"
            accepted = checked(await client.post(route, json=body), 202)
            await wait_entered(workflow.provider)
            run_id = accepted["start"]["run_id"]
            assert checked(await client.post(route, json=body), 202)["start"]["run_id"] == run_id
            checked(await client.post(route, json=command(workflow, request_id="different-request")), 409)
            checked(await client.post(route, json=body, headers=headers(workflow, "other-reviewer")), 409)
            assert checked(await client.get("/inference/status"))["busy"] is True
            assert len(workflow.provider.calls) == 1
            assert len(workflow.store.list_for_component(workflow.component_id)) == 1
            workflow.provider.release.set()
            finished = await poll(client, run_id)
            assert checked(await client.post(route, json=body), 202) == finished
            assert len(workflow.provider.calls) == 1
    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["malformed", "runtime", "missing_image", "wrong_hash", "wrong_model", "unavailable", "provider_timeout", "nan_metrics", "oversized_metrics"])
def test_failures_are_explicit_provenance_without_verified_facts(workflow, failure):
    expected = "failed"
    if failure == "malformed":
        workflow.provider.text = "not JSON; controlled malformed response"
        expected = "invalid_output"
    elif failure == "runtime":
        workflow.provider.error = RuntimeError("sensitive-debug-marker must not be exposed")
    elif failure == "missing_image":
        asset = workflow.uploads[workflow.component_id].asset
        (workflow.assets.root / f"{asset.asset_id}.png").unlink()
    elif failure == "wrong_hash":
        workflow.provider.result_changes = {"metrics": {"input_sha256": ["0" * 64], "vision_forward_calls": 1}}
    elif failure == "wrong_model":
        workflow.provider.result_changes = {"model_revision": "b" * 40}
    elif failure == "unavailable":
        workflow.provider.error = VisionUnavailable("Controlled unavailable runtime")
        expected = "unavailable"
    elif failure == "provider_timeout":
        workflow.provider.error = VisionTimeout("Controlled cooperative execution timeout")
        expected = "timed_out"
    else:
        metrics = {"input_sha256": [hashlib.sha256(workflow.raw_images[workflow.component_id]).hexdigest()],
                   "vision_forward_calls": 1}
        metrics.update({"duration": float("nan")} if failure == "nan_metrics" else {f"extra_{index}": index for index in range(33)})
        workflow.provider.result_changes = {"metrics": metrics}
    before = workflow.evidence.history(workflow.component_id)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            run = checked(await client.post(f"/components/{workflow.component_id}/inference", json=command(workflow)), 202)
            final = await poll(client, run["start"]["run_id"])
            assert final["outcome"]["status"] == expected
            assert final["outcome"]["failure_reason"]
            assert final["outcome"]["output"] is None
            assert final["outcome"]["applied_event_ids"] == []
            assert "sensitive-debug-marker" not in json.dumps(final)
            assert workflow.evidence.history(workflow.component_id) == before
            if failure == "missing_image":
                assert workflow.provider.calls == []
    asyncio.run(scenario())


def test_new_image_while_request_runs_makes_late_output_stale(workflow):
    workflow.provider.release.clear()

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            run = checked(await client.post(f"/components/{workflow.component_id}/inference", json=command(workflow)), 202)
            await wait_entered(workflow.provider)
            component = workflow.evidence.get_component(workflow.component_id)
            with Image.new("RGB", (24, 24), "green") as image, BytesIO() as buffer:
                image.save(buffer, format="PNG")
                checked(await client.post(f"/components/{workflow.component_id}/images?return_id={component.source_return_id}",
                                          content=buffer.getvalue(), headers={"Content-Type": "image/png"}), 201)
            before = workflow.evidence.history(workflow.component_id)
            workflow.provider.release.set()
            final = await poll(client, run["start"]["run_id"])
            assert final["outcome"]["status"] == "succeeded"
            assert final["outcome"]["stale"] is True
            assert final["outcome"]["applied_event_ids"] == []
            assert workflow.evidence.history(workflow.component_id) == before
    asyncio.run(scenario())


def test_disabled_provider_is_honestly_unavailable_and_manual_api_still_works(workflow):
    app = create_app(workflow.inventory, auth=workflow.auth, assets=workflow.assets)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            status = checked(await client.get("/inference/status"))
            assert status["status"] == "unavailable"
            checked(await client.post(f"/components/{workflow.component_id}/inference", json=command(workflow)), 503)
            assert checked(await client.get(f"/components/{workflow.component_id}/history"))["component"]["physical_component_id"] == workflow.component_id
            assert (await client.get("/health")).json() == {"status": "ok"}
        assert workflow.provider.calls == []
    asyncio.run(scenario())


@pytest.mark.parametrize("workflow", [0.5], indirect=True)
def test_request_deadline_keeps_busy_slot_until_execution_stops_and_discards_late_output(workflow):
    workflow.provider.release.clear()
    before = workflow.evidence.history(workflow.component_id)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            route = f"/components/{workflow.component_id}/inference"
            accepted = checked(await client.post(route, json=command(workflow)), 202)
            await wait_entered(workflow.provider)
            run_id = accepted["start"]["run_id"]
            final = await poll(client, run_id)
            assert final["outcome"]["status"] == "timed_out"
            assert final["outcome"]["applied_event_ids"] == []
            assert checked(await client.get("/inference/status"))["busy"] is True
            checked(await client.post(route, json=command(workflow, request_id="second-while-timed-out")), 409)
            workflow.provider.release.set()
            deadline = time.monotonic() + 2
            while checked(await client.get("/inference/status"))["busy"] and time.monotonic() < deadline:
                await asyncio.sleep(0.01)
            assert checked(await client.get("/inference/status"))["busy"] is False
            assert checked(await client.get(f"/inference/{run_id}")) == final
            assert workflow.evidence.history(workflow.component_id) == before
            assert len(workflow.provider.calls) == 1
    asyncio.run(scenario())


def test_shutdown_terminalizes_active_request_and_suppresses_late_evidence(workflow):
    workflow.provider.release.clear()
    before = workflow.evidence.history(workflow.component_id)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            accepted = checked(await client.post(f"/components/{workflow.component_id}/inference", json=command(workflow)), 202)
            await wait_entered(workflow.provider)
            workflow.service.close()
            final = await poll(client, accepted["start"]["run_id"])
            assert final["outcome"]["status"] == "failed"
            assert final["outcome"]["applied_event_ids"] == []
            assert checked(await client.get("/inference/status"))["status"] == "unavailable"
            workflow.provider.release.set()
            await asyncio.to_thread(workflow.service.close)
            assert checked(await client.get(f"/inference/{accepted['start']['run_id']}")) == final
            assert workflow.evidence.history(workflow.component_id) == before
    asyncio.run(scenario())


def test_worker_start_failure_is_durable_and_does_not_leave_busy_slot(workflow, monkeypatch):
    original_start = threading.Thread.start

    def fail_worker_start(thread):
        if thread.name == "rekit-vision":
            raise RuntimeError("Controlled worker startup failure")
        return original_start(thread)

    monkeypatch.setattr(threading.Thread, "start", fail_worker_start)
    before = workflow.evidence.history(workflow.component_id)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            accepted = checked(await client.post(f"/components/{workflow.component_id}/inference", json=command(workflow)), 202)
            assert accepted["outcome"]["status"] == "failed"
            assert checked(await client.get("/inference/status"))["busy"] is False
            assert workflow.provider.calls == []
            assert workflow.evidence.history(workflow.component_id) == before
    asyncio.run(scenario())


def test_configured_factory_requires_explicit_local_provider_opt_in(workflow, tmp_path, monkeypatch):
    import rekit.inference.provider as provider_module

    auth_path = tmp_path / "authentication.json"
    auth_path.write_text(workflow.auth.model_dump_json(), encoding="utf-8")
    values = {
        "REKIT_DATABASE_PATH": str(workflow.evidence.path),
        "REKIT_CATALOG_PATH": str(FIXTURES / workflow.fixture["catalog_file"]),
        "REKIT_DISPOSITION_POLICY_PATH": str(FIXTURES / workflow.fixture["disposition_policy_file"]),
        "REKIT_AUTH_CONFIG_PATH": str(auth_path), "REKIT_EVIDENCE_DIR": str(workflow.assets.root),
        "REKIT_MODEL_DIR": str(tmp_path / "controlled-model-path"), "REKIT_CUDA_DEVICE": "1",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    constructions = []

    def controlled_provider(model_dir, *, device, catalog):
        constructions.append((model_dir, device, catalog))
        return workflow.provider

    monkeypatch.setattr(provider_module, "LocalVisionProvider", controlled_provider)
    monkeypatch.delenv("REKIT_INFERENCE_PROVIDER", raising=False)
    disabled = create_configured_app()
    assert disabled.state.inference is None
    assert constructions == []
    monkeypatch.setenv("REKIT_INFERENCE_PROVIDER", "local-transformers")
    configured = create_configured_app()
    try:
        assert configured.state.inference is not None
        assert len(constructions) == 1
        assert constructions[0][0] == Path(values["REKIT_MODEL_DIR"])
        assert constructions[0][1] == 1
        assert constructions[0][2] == workflow.evidence.catalog
        assert workflow.provider.calls == []
    finally:
        configured.state.inference.close()
