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
            if failure in ("malformed", "wrong_hash", "wrong_model", "nan_metrics", "oversized_metrics"):
                assert final["outcome"]["raw_output"] == workflow.provider.text
            else:
                assert final["outcome"]["raw_output"] is None
            assert workflow.evidence.history(workflow.component_id) == before
            if failure == "missing_image":
                assert workflow.provider.calls == []
    asyncio.run(scenario())


@pytest.mark.parametrize("candidate_present", [False, True])
def test_no_catalog_permission_is_enforced_before_any_evidence_events(workflow, candidate_present):
    configuration = workflow.provider.configuration.model_dump(mode="json")
    configuration["generation"]["identity_candidates_allowed"] = False
    workflow.provider.configuration = InferenceConfiguration.model_validate(configuration)
    payload = json.loads(json.dumps(CONTROLLED_OUTPUT))
    if candidate_present:
        # Even a known catalog ID cannot bypass the admitted no-candidate policy.
        payload["candidates"] = [{"image_indices": [1], "component_type_id": "body", "revision": "A",
                                  "revision_marking": "REV A", "reason": "Controlled unsupported candidate."}]
    workflow.provider.text = json.dumps(payload)
    before = workflow.evidence.history(workflow.component_id)
    inventory_before = workflow.inventory.inventory()

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            body = command(workflow)
            accepted = checked(await client.post(f"/components/{workflow.component_id}/inference", json=body), 202)
            final = await poll(client, accepted["start"]["run_id"])
            assert final["start"]["configuration"]["generation"]["identity_candidates_allowed"] is False
            assert final["outcome"]["raw_output"] == workflow.provider.text
            if candidate_present:
                assert final["outcome"]["status"] == "invalid_output"
                assert final["outcome"]["output"] is None
                assert final["outcome"]["applied_event_ids"] == []
                assert workflow.evidence.history(workflow.component_id) == before
                assert workflow.inventory.inventory() == inventory_before
                assert checked(await client.post(f"/components/{workflow.component_id}/inference", json=body), 202) == final
                assert len(workflow.provider.calls) == 1
            else:
                assert final["outcome"]["status"] == "succeeded"
                assert final["outcome"]["output"] == CONTROLLED_OUTPUT
                assert final["outcome"]["applied_event_ids"]
            assert workflow.evidence.current(workflow.component_id).verification is None
            inventory = checked(await client.get("/inventory"))
            assert all(entry["availability"] == "held" for entry in inventory["items"])
            assert inventory["completed_kits"] == []

    asyncio.run(scenario())


@pytest.mark.parametrize("image_count,mismatch", [
    (1, None), (2, None), (2, "decoding"), (2, "schema_version"),
    (2, "schema_sha256"), (2, "missing_digest"), (2, "missing_configuration"),
])
def test_constrained_execution_must_match_admitted_schema_for_actual_image_count(workflow, image_count, mismatch):
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
    generation = {
        "max_new_tokens": 128, "decoding": "lm-format-enforcer", "schema_version": "controlled-schema-v1",
        "schema_sha256_1": "1" * 64, "schema_sha256_2": "2" * 64,
    }
    metrics = {
        "input_sha256": [hashlib.sha256(raw).hexdigest() for raw in selected_bytes],
        "vision_forward_calls": 1, "decoding": "lm-format-enforcer", "schema_version": "controlled-schema-v1",
        "schema_sha256": generation[f"schema_sha256_{image_count}"], "test_double": True,
    }
    if mismatch == "decoding":
        metrics["decoding"] = "unconstrained"
    elif mismatch == "schema_version":
        metrics["schema_version"] = "different-schema-v2"
    elif mismatch == "schema_sha256":
        # Correctly formed digest, but it is for one image rather than two.
        metrics["schema_sha256"] = generation["schema_sha256_1"]
    elif mismatch == "missing_digest":
        del metrics["schema_sha256"]
    elif mismatch == "missing_configuration":
        # Missing trusted metadata and a matching missing attestation are not proof.
        del generation["schema_sha256_2"]
        del metrics["schema_sha256"]
    workflow.provider.configuration = InferenceConfiguration.model_validate({
        **workflow.provider.configuration.model_dump(mode="json"), "generation": generation,
    })
    workflow.provider.result_changes = {"metrics": metrics}
    before = workflow.evidence.history(workflow.component_id)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            admitted = checked(await client.post(f"/components/{workflow.component_id}/inference",
                                                 json=command(workflow, asset_ids=selected_ids)), 202)
            final = await poll(client, admitted["start"]["run_id"])
            assert final["start"]["configuration"]["generation"] == generation
            assert final["outcome"]["raw_output"] == workflow.provider.text
            assert workflow.provider.calls == [tuple(selected_bytes)]
            if mismatch:
                assert final["outcome"]["status"] == "failed"
                assert final["outcome"]["output"] is None
                assert final["outcome"]["applied_event_ids"] == []
                assert workflow.evidence.history(workflow.component_id) == before
            else:
                assert final["outcome"]["status"] == "succeeded"
                assert final["outcome"]["output"] == CONTROLLED_OUTPUT
                assert final["outcome"]["metrics"]["schema_sha256"] == generation[f"schema_sha256_{image_count}"]
                assert final["outcome"]["applied_event_ids"]
            assert workflow.evidence.current(workflow.component_id).verification is None
            inventory = checked(await client.get("/inventory"))
            assert len(inventory["items"]) == 2
            assert all(entry["availability"] == "held" for entry in inventory["items"])
            assert inventory["completed_kits"] == []
    asyncio.run(scenario())


def test_completed_response_diagnostics_are_bounded_after_provenance_failure(workflow):
    workflow.provider.text = "Controlled raw response. " * 1600
    workflow.provider.result_changes = {"model_revision": "b" * 40}
    before = workflow.evidence.history(workflow.component_id)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            admitted = checked(await client.post(f"/components/{workflow.component_id}/inference", json=command(workflow)), 202)
            final = await poll(client, admitted["start"]["run_id"])
            assert final["outcome"]["status"] == "failed"
            assert final["outcome"]["raw_output"] == workflow.provider.text[:32000]
            assert len(final["outcome"]["raw_output"]) == 32000
            assert final["outcome"]["applied_event_ids"] == []
            assert workflow.evidence.history(workflow.component_id) == before
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


def test_human_rejection_is_audited_idempotent_and_does_not_rewrite_model_output(workflow):
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            admitted = checked(await client.post(f"/components/{workflow.component_id}/inference", json=command(workflow)), 202)
            run = await poll(client, admitted["start"]["run_id"])
            run_id = run["start"]["run_id"]
            body = {"rejection_id": "explicit-human-rejection", "expected_version": run["outcome"]["evidence_version_after"],
                    "reason": "The model interpretation is not supported by the supplied test image."}
            current = checked(await client.post(f"/inference/{run_id}/reject", json=body))
            assert current["state"] == "review_required"
            assert current["verification"] is None
            assert current["version"] == body["expected_version"] + 1
            assert checked(await client.post(f"/inference/{run_id}/reject", json=body)) == current
            checked(await client.post(f"/inference/{run_id}/reject", json=body,
                                      headers=headers(workflow, "other-reviewer")), 409)
            checked(await client.post(f"/inference/{run_id}/reject", json=body | {"reason": "Different reason"}), 409)
            checked(await client.post(f"/inference/{run_id}/reject", json=body | {"expected_version": current["version"]}), 409)
            history = checked(await client.get(f"/components/{workflow.component_id}/history"))
            event = history["events"][-1]
            assert event["event_id"] == body["rejection_id"]
            assert event["kind"] == "uncertainty"
            assert event["payload"]["source"] == "operator"
            assert event["payload"]["source_reference"] == "reviewer"
            assert run_id in event["payload"]["reason"]
            assert checked(await client.get(f"/inference/{run_id}")) == run
            assert checked(await client.get("/inventory"))["items"][0]["availability"] == "held"
    asyncio.run(scenario())


@pytest.mark.parametrize("actor,status", [(None, 401), ("viewer", 403), ("service", 403)])
def test_rejection_requires_authenticated_human_reviewer(workflow, actor, status):
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            checked(await client.post("/inference/unknown-run/reject", json={
                "rejection_id": "unauthorized-rejection", "expected_version": 2, "reason": "Not authorized",
            }, headers=headers(workflow, actor) if actor else {}), status)
    asyncio.run(scenario())


@pytest.mark.parametrize("later_state", ["pending", "failed", "new_image", "human_correction", "stale_version"])
def test_rejection_cannot_change_pending_failed_or_newer_evidence(workflow, later_state):
    if later_state == "pending":
        workflow.provider.release.clear()
    elif later_state == "failed":
        workflow.provider.text = "Controlled invalid JSON"

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            admitted = checked(await client.post(f"/components/{workflow.component_id}/inference", json=command(workflow)), 202)
            run = admitted if later_state == "pending" else await poll(client, admitted["start"]["run_id"])
            if later_state == "new_image":
                with Image.new("RGB", (32, 24), "yellow") as image, BytesIO() as buffer:
                    image.save(buffer, format="PNG")
                    component = workflow.evidence.get_component(workflow.component_id)
                    checked(await client.post(f"/components/{workflow.component_id}/images?return_id={component.source_return_id}",
                                              content=buffer.getvalue(), headers={"Content-Type": "image/png"}), 201)
            elif later_state == "human_correction":
                verification = dict(workflow.fixture["components"][0]["verification"])
                verification.pop("operator_id")
                verification["evidence_observation_ids"] = [workflow.uploads[workflow.component_id].asset.observation_id]
                checked(await client.post(f"/components/{workflow.component_id}/verification", json={
                    "verification": verification, "expected_version": workflow.evidence.current(workflow.component_id).version,
                }))
            before = workflow.evidence.history(workflow.component_id)
            expected = 1 if later_state == "stale_version" else before.current.version
            checked(await client.post(f"/inference/{run['start']['run_id']}/reject", json={
                "rejection_id": "outdated-rejection", "expected_version": expected, "reason": "Unsupported proposal",
            }), 409)
            assert workflow.evidence.history(workflow.component_id) == before
    asyncio.run(scenario())


class RemoteHttpDouble:
    """Only the HTTP transport is controlled; the production provider runs normally."""

    model_id = "test/offline-remote-model"
    token = "offline-remote-token-never-a-real-credential"

    def __init__(self):
        self.calls = []
        self.entered = threading.Event()
        self.release = threading.Event()
        self.release.set()
        self.status = 200
        self.raw = json.dumps(CONTROLLED_OUTPUT)
        self.response_model = self.model_id
        self.error = None

    def __call__(self, endpoint, token, payload, **limits):
        from rekit.inference.adapters.remote_transport import HttpResponse

        self.calls.append((endpoint, token, payload, limits))
        self.entered.set()
        assert self.release.wait(5), "Test must release the controlled transport"
        if self.error is not None:
            raise self.error
        body = json.dumps({"model": self.response_model, "choices": [{
            "index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": self.raw},
        }]}).encode()
        return HttpResponse(status=self.status, body=body, content_type="application/json")


@pytest.fixture
def remote_workflow(workflow):
    from pydantic import SecretStr
    from rekit.inference.adapters.openai_remote import OpenAICompatibleVision, RemoteVisionSettings

    workflow.service.close()
    transport = RemoteHttpDouble()
    settings = RemoteVisionSettings(
        base_url="https://vision.example.test/v1",
        allowed_endpoints=("https://vision.example.test/v1/chat/completions",),
        api_key=SecretStr(transport.token), model_id=transport.model_id,
        model_revision="c" * 40, processor_revision="d" * 40,
    )
    workflow.provider = OpenAICompatibleVision(settings, workflow.evidence.catalog, transport=transport)
    workflow.service = InferenceService(workflow.store, workflow.provider, timeout_seconds=5)
    workflow.app = create_app(workflow.inventory, auth=workflow.auth, assets=workflow.assets, inference=workflow.service)
    workflow.remote_transport = transport
    try:
        yield workflow
    finally:
        transport.release.set()
        workflow.service.close()


@pytest.mark.parametrize("image_count", [1, 2])
def test_remote_api_original_bytes_and_unverified_inventory_boundary(remote_workflow, image_count):
    import base64

    workflow = remote_workflow
    asset_ids = [workflow.uploads[workflow.component_id].asset.asset_id]
    original_bytes = [workflow.raw_images[workflow.component_id]]
    if image_count == 2:
        component = workflow.evidence.get_component(workflow.component_id)
        with Image.new("RGB", (20, 28), "purple") as image, BytesIO() as buffer:
            image.save(buffer, format="PNG")
            raw = buffer.getvalue()
        uploaded = workflow.assets.upload(component.physical_component_id, component.source_return_id, raw, "image/png", "reviewer")
        asset_ids.append(uploaded.asset.asset_id)
        original_bytes.append(raw)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            status = checked(await client.get("/inference/status"))
            assert status["provider"] == "openai-remote"
            assert status["device"] == "remote"
            accepted = checked(await client.post(f"/components/{workflow.component_id}/inference",
                                                 json=command(workflow, asset_ids=asset_ids)), 202)
            run = await poll(client, accepted["start"]["run_id"])
            assert run["outcome"]["status"] == "succeeded"
            assert run["outcome"]["output"] == CONTROLLED_OUTPUT
            assert run["outcome"]["stale"] is False
            assert run["outcome"]["applied_event_ids"]
            assert run["start"]["actor_id"] == "reviewer"
            assert [entry["sha256"] for entry in run["start"]["inputs"]] == [hashlib.sha256(raw).hexdigest() for raw in original_bytes]
            config = run["start"]["configuration"]
            metrics = run["outcome"]["metrics"]
            assert config["runtime"]["revision_verification"] == "not_attested_by_response"
            assert metrics["runtime_hardware_verification"] == "unverified"
            assert metrics["response_model_id_matched"] is True
            assert metrics["schema_sha256"] == config["generation"][f"schema_sha256_{image_count}"]
            assert "vision_forward_calls" not in metrics
            assert workflow.remote_transport.token not in json.dumps(run)
            assert len(workflow.remote_transport.calls) == 1
            sent = json.loads(workflow.remote_transport.calls[0][2])
            encoded_inputs = sent["messages"][0]["content"][:-1]
            assert [base64.b64decode(part["image_url"]["url"].split(",", 1)[1]) for part in encoded_inputs] == original_bytes
            history = checked(await client.get(f"/components/{workflow.component_id}/history"))
            assert history["current"]["verification"] is None
            assert not any(event["kind"] == "verification" for event in history["events"])
            snapshot = checked(await client.get("/inventory"))
            assert all(item["availability"] == "held" for item in snapshot["items"])
            assert snapshot["completed_kits"] == []
            assert checked(await client.get(f"/components/{workflow.component_id}/compatibility?configuration_id=standard-kit"))["compatible"] is False
    asyncio.run(scenario())


@pytest.mark.parametrize("defect,status,code", [
    ("wrong_model", "invalid_output", None), ("invalid_text", "invalid_output", None),
    ("secret_echo", "invalid_output", None), ("authentication", "unavailable", "authentication"),
    ("rate_limited", "unavailable", "rate_limited"), ("unsupported", "unavailable", "unsupported"),
    ("endpoint", "unavailable", "endpoint"), ("timeout", "timed_out", None),
])
def test_remote_api_failures_preserve_evidence_and_sanitize_diagnostics(remote_workflow, defect, status, code):
    from rekit.inference.adapters.remote_transport import RemoteTransportError

    workflow = remote_workflow
    transport = workflow.remote_transport
    if defect == "wrong_model": transport.response_model = "substituted-model"
    elif defect == "invalid_text": transport.raw = '{"observations":[]}'
    elif defect == "secret_echo": transport.raw = transport.token
    elif defect == "timeout": transport.error = RemoteTransportError("timeout")
    else: transport.status = {"authentication": 401, "rate_limited": 429, "unsupported": 400, "endpoint": 500}[defect]
    before = workflow.evidence.history(workflow.component_id)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            accepted = checked(await client.post(f"/components/{workflow.component_id}/inference", json=command(workflow)), 202)
            final = await poll(client, accepted["start"]["run_id"])
            outcome = final["outcome"]
            assert outcome["status"] == status
            assert outcome["output"] is None
            assert outcome["applied_event_ids"] == []
            assert outcome["metrics"].get("remote_error_code") == code
            assert outcome["raw_output"] == (transport.raw if defect == "invalid_text" else None)
            assert transport.token not in json.dumps(final)
            assert len(transport.calls) == 1
            assert workflow.evidence.history(workflow.component_id) == before
            if defect == "authentication":
                verification = dict(workflow.fixture["components"][0]["verification"])
                verification.pop("operator_id")
                verification["evidence_observation_ids"] = [workflow.uploads[workflow.component_id].asset.observation_id]
                current = checked(await client.post(f"/components/{workflow.component_id}/verification", json={
                    "verification": verification, "expected_version": before.current.version,
                }))
                assert current["state"] == "verified"
                assert current["verification"]["operator_id"] == "reviewer"
    asyncio.run(scenario())


@pytest.mark.parametrize("tamper", ["provider", "input_sha256", "schema_sha256"])
def test_remote_api_rejects_tampered_execution_provenance(remote_workflow, monkeypatch, tamper):
    workflow = remote_workflow
    inspect = workflow.provider.inspect

    def changed(images):
        result = inspect(images)
        if tamper == "provider": result["provider"] = "local-transformers"
        elif tamper == "input_sha256": result["metrics"][tamper] = ["0" * 64]
        else: result["metrics"][tamper] = "0" * 64
        return result

    monkeypatch.setattr(workflow.provider, "inspect", changed)
    before = workflow.evidence.history(workflow.component_id)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            accepted = checked(await client.post(f"/components/{workflow.component_id}/inference", json=command(workflow)), 202)
            final = await poll(client, accepted["start"]["run_id"])
            assert final["outcome"]["status"] == "failed"
            assert final["outcome"]["applied_event_ids"] == []
            assert workflow.evidence.history(workflow.component_id) == before
            assert len(workflow.remote_transport.calls) == 1
    asyncio.run(scenario())


def test_remote_api_retry_is_one_call_and_new_evidence_prevents_late_application(remote_workflow):
    workflow = remote_workflow
    transport = workflow.remote_transport
    transport.release.clear()
    request_body = command(workflow)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            route = f"/components/{workflow.component_id}/inference"
            first = checked(await client.post(route, json=request_body), 202)
            await wait_entered(transport)
            retry = checked(await client.post(route, json=request_body), 202)
            assert retry["start"]["run_id"] == first["start"]["run_id"]
            checked(await client.post(route, json=command(workflow, request_id="other-remote-request")), 409)
            component = workflow.evidence.get_component(workflow.component_id)
            with Image.new("RGB", (24, 18), "lime") as image, BytesIO() as buffer:
                image.save(buffer, format="PNG")
                checked(await client.post(f"/components/{workflow.component_id}/images?return_id={component.source_return_id}",
                                          content=buffer.getvalue(), headers={"Content-Type": "image/png"}), 201)
            before = workflow.evidence.history(workflow.component_id)
            transport.release.set()
            final = await poll(client, first["start"]["run_id"])
            assert final["outcome"]["status"] == "succeeded"
            assert final["outcome"]["stale"] is True
            assert final["outcome"]["applied_event_ids"] == []
            assert workflow.evidence.history(workflow.component_id) == before
            assert checked(await client.post(route, json=request_body), 202) == final
            assert len(transport.calls) == 1
    asyncio.run(scenario())


@pytest.mark.parametrize("extra", ["base_url", "api_key", "model_id", "allowed_endpoints", "provider"])
def test_remote_configuration_cannot_be_supplied_by_api_client(remote_workflow, extra):
    workflow = remote_workflow

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver",
                                     headers=headers(workflow)) as client:
            checked(await client.post(f"/components/{workflow.component_id}/inference",
                                      json=command(workflow) | {extra: "untrusted override"}), 422)
            assert workflow.remote_transport.calls == []
            assert workflow.store.list_for_component(workflow.component_id) == ()
    asyncio.run(scenario())


def test_remote_factory_uses_only_explicit_trusted_server_configuration(workflow, tmp_path, monkeypatch):
    from rekit.inference.adapters import openai_remote

    auth_path = tmp_path / "remote-factory-auth.json"
    auth_path.write_text(workflow.auth.model_dump_json(), encoding="utf-8")
    values = {
        "REKIT_DATABASE_PATH": str(workflow.evidence.path),
        "REKIT_CATALOG_PATH": str(FIXTURES / workflow.fixture["catalog_file"]),
        "REKIT_DISPOSITION_POLICY_PATH": str(FIXTURES / workflow.fixture["disposition_policy_file"]),
        "REKIT_AUTH_CONFIG_PATH": str(auth_path), "REKIT_EVIDENCE_DIR": str(workflow.assets.root),
        "REKIT_INFERENCE_PROVIDER": "openai-remote", "REKIT_INFERENCE_BASE_URL": "https://vision.example.test/v1",
        "REKIT_INFERENCE_ALLOWED_ENDPOINTS": "https://vision.example.test/v1/chat/completions",
        "REKIT_INFERENCE_API_KEY": RemoteHttpDouble.token, "REKIT_INFERENCE_MODEL": RemoteHttpDouble.model_id,
        "REKIT_INFERENCE_MODEL_REVISION": "c" * 40, "REKIT_INFERENCE_PROCESSOR_REVISION": "d" * 40,
        "REKIT_INFERENCE_TIMEOUT_SECONDS": "20", "REKIT_INFERENCE_MAX_IMAGES": "2",
    }
    for key, value in values.items(): monkeypatch.setenv(key, value)
    monkeypatch.delenv("REKIT_MODEL_DIR", raising=False)
    real_provider = openai_remote.OpenAICompatibleVision
    transport = RemoteHttpDouble()
    constructions = []

    def controlled_provider(settings, catalog):
        constructions.append((settings, catalog))
        return real_provider(settings, catalog, transport=transport)

    monkeypatch.setattr(openai_remote, "OpenAICompatibleVision", controlled_provider)
    app = create_configured_app()
    try:
        assert len(constructions) == 1
        settings, catalog = constructions[0]
        assert catalog == workflow.evidence.catalog
        assert settings.api_key.get_secret_value() == transport.token
        assert app.state.inference.provider.configuration.provider == "openai-remote"
        assert app.state.inference.timeout_seconds == 35
        assert transport.calls == []
    finally:
        app.state.inference.close()
    monkeypatch.delenv("REKIT_INFERENCE_API_KEY")
    with pytest.raises(RuntimeError, match="configuration is missing or invalid"):
        create_configured_app()
    assert len(constructions) == 1
