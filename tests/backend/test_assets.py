"""Authenticated image intake, immutable provenance, limits, and storage failures."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from io import BytesIO
from pathlib import Path
import secrets

from fastapi import FastAPI
import httpx
from PIL import Image
import pytest

from rekit.auth import Actor, ActorKind, AuthConfig, OperatorCredential, Role, token_digest
from rekit.catalog.models import Catalog
from rekit.evidence.assets import ImageAssetStore, MAX_UPLOAD_BYTES
from rekit.evidence.models import PhysicalComponent, ReturnBatch, ReturnRecord
from rekit.evidence.store import ConflictError, EvidenceStore
from rekit.inventory.store import InventoryStore
from rekit.main import create_app
from rekit.recovery.models import DispositionPolicy


NOW = datetime(2026, 10, 13, 22, tzinfo=timezone.utc)
COMPONENT_ID = "asset-physical-001"
SECOND_COMPONENT_ID = "asset-physical-002"
RETURN_ID = "asset-return-001"
SECOND_RETURN_ID = "asset-return-002"
FIXTURES = Path(__file__).parents[1] / "fixtures"


@dataclass
class AssetWorkflow:
    app: FastAPI
    evidence: EvidenceStore
    assets: ImageAssetStore
    root: Path
    tokens: dict[str, str]


@pytest.fixture
def workflow(tmp_path: Path) -> AssetWorkflow:
    catalog = Catalog.model_validate_json((FIXTURES / "synthetic_catalog.json").read_text(encoding="utf-8"))
    evidence = EvidenceStore(tmp_path / "assets.sqlite3", catalog)
    evidence.register_batch(ReturnBatch(batch_id="asset-batch", received_at=NOW))
    for component_id, return_id in ((COMPONENT_ID, RETURN_ID), (SECOND_COMPONENT_ID, SECOND_RETURN_ID)):
        evidence.register_return(ReturnRecord(
            return_id=return_id, batch_id="asset-batch", product_family_id="demo-kit", received_at=NOW,
        ))
        evidence.register_component(PhysicalComponent(
            physical_component_id=component_id, source_return_id=return_id, registered_at=NOW,
        ))
    policy = DispositionPolicy(policy_id="asset-test-policy", version="1", approved_by="asset-policy-author", approved_at=NOW)
    actors = (
        Actor(actor_id="asset-alice", kind=ActorKind.HUMAN, roles=tuple(Role)),
        Actor(actor_id="asset-bob", kind=ActorKind.HUMAN, roles=(Role.VIEWER, Role.INTAKE)),
        Actor(actor_id="asset-viewer", kind=ActorKind.HUMAN, roles=(Role.VIEWER,)),
        Actor(actor_id="asset-intake", kind=ActorKind.HUMAN, roles=(Role.INTAKE,)),
    )
    tokens = {actor.actor_id: secrets.token_urlsafe(32) for actor in actors}
    auth = AuthConfig(operators=tuple(OperatorCredential(actor=actor, token_sha256=token_digest(tokens[actor.actor_id])) for actor in actors))
    root = tmp_path / "managed-images"
    assets = ImageAssetStore(evidence, root)
    app = create_app(InventoryStore(evidence, policy), auth=auth, assets=assets)
    return AssetWorkflow(app, evidence, assets, root, tokens)


def image_bytes(image_format: str = "PNG", size: tuple[int, int] = (24, 18), color: str = "red") -> bytes:
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format=image_format)
    return output.getvalue()


def headers(workflow: AssetWorkflow, actor: str = "asset-alice", media_type: str | None = None) -> dict[str, str]:
    result = {"Authorization": f"Bearer {workflow.tokens[actor]}"}
    if media_type is not None:
        result["Content-Type"] = media_type
    return result


def checked(response: httpx.Response, status: int = 200):
    assert response.status_code == status, response.text
    return response.json()


async def upload(
    client: httpx.AsyncClient,
    workflow: AssetWorkflow,
    raw: bytes,
    *,
    component_id: str = COMPONENT_ID,
    return_id: str = RETURN_ID,
    media_type: str = "image/png",
    actor: str = "asset-alice",
) -> httpx.Response:
    return await client.post(
        f"/components/{component_id}/images", params={"return_id": return_id},
        content=raw, headers=headers(workflow, actor, media_type),
    )


def persisted_state(workflow: AssetWorkflow):
    with workflow.evidence.transaction() as connection:
        assets = tuple(tuple(row) for row in connection.execute("SELECT * FROM image_assets ORDER BY rowid"))
        events = tuple(tuple(row) for row in connection.execute("SELECT * FROM evidence_events ORDER BY sequence"))
    files = tuple((path.name, path.read_bytes()) for path in sorted(workflow.root.iterdir()) if path.is_file())
    return assets, events, files


def stored_file(workflow: AssetWorkflow, asset: dict) -> Path:
    matches = list(workflow.root.glob(f"{asset['asset_id']}.*"))
    assert len(matches) == 1
    return matches[0]


@pytest.mark.parametrize(("image_format", "media_type"), [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")])
def test_valid_images_store_exact_bytes_with_server_identity_and_actor_provenance(
    workflow: AssetWorkflow, image_format: str, media_type: str,
) -> None:
    async def requests() -> None:
        raw = image_bytes(image_format)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            result = checked(await upload(client, workflow, raw, media_type=media_type), 201)
            asset, observation = result["asset"], result["observation"]
            assert result["duplicate"] is False
            assert asset["asset_id"] != COMPONENT_ID
            assert asset["physical_component_id"] == COMPONENT_ID
            assert asset["return_id"] == RETURN_ID
            assert asset["sha256"] == hashlib.sha256(raw).hexdigest()
            assert asset["byte_size"] == len(raw)
            assert asset["media_type"] == media_type
            assert (asset["width"], asset["height"]) == (24, 18)
            assert asset["uploaded_by"] == "asset-alice"
            assert asset["availability"] == "available"
            assert datetime.fromisoformat(asset["received_at"].replace("Z", "+00:00")).tzinfo is not None
            assert not {"path", "storage_path", "filename"} & set(asset)
            assert observation["physical_component_id"] == COMPONENT_ID
            assert observation["source_return_id"] == RETURN_ID
            assert observation["source_reference"] == "asset-alice"
            assert observation["observation_id"] == asset["observation_id"]
            assert observation["evidence_reference"] == f"asset:{asset['asset_id']}"
            assert checked(await client.get(f"/assets/{asset['asset_id']}", headers=headers(workflow))) == asset
            assert checked(await client.get(f"/components/{COMPONENT_ID}/images", headers=headers(workflow))) == [asset]
            response = await client.get(f"/assets/{asset['asset_id']}/content", headers=headers(workflow))
            assert response.status_code == 200
            assert response.content == raw
            assert response.headers["content-type"] == media_type
            assert response.headers["x-content-type-options"] == "nosniff"
            assert response.headers["cache-control"] == "no-store"
            assert stored_file(workflow, asset).read_bytes() == raw

    asyncio.run(requests())


@pytest.mark.parametrize(("raw", "media_type", "status"), [
    (b"this is not an image", "image/png", 422),
    (image_bytes("JPEG"), "image/png", 415),
    (image_bytes("PNG"), "application/octet-stream", 415),
    (image_bytes("GIF"), "image/gif", 415),
    (image_bytes("PNG")[:20], "image/png", 422),
])
def test_invalid_corrupt_and_mismatched_images_leave_no_asset_or_observation(
    workflow: AssetWorkflow, raw: bytes, media_type: str, status: int,
) -> None:
    async def requests() -> None:
        before = persisted_state(workflow)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            checked(await upload(client, workflow, raw, media_type=media_type), status)
        assert persisted_state(workflow) == before

    asyncio.run(requests())


@pytest.mark.parametrize("limit_kind", ["declared_bytes", "streamed_bytes", "understated_bytes", "side", "pixels"])
def test_upload_limits_reject_before_creating_records_or_files(workflow: AssetWorkflow, limit_kind: str) -> None:
    async def requests() -> None:
        before = persisted_state(workflow)
        route = f"/components/{COMPONENT_ID}/images?return_id={RETURN_ID}"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            if limit_kind == "declared_bytes":
                response = await client.post(route, content=image_bytes(), headers=headers(workflow, media_type="image/png") | {
                    "Content-Length": str(MAX_UPLOAD_BYTES + 1),
                })
            elif limit_kind in ("streamed_bytes", "understated_bytes"):
                async def chunks():
                    chunk = b"x" * (1024 * 1024)
                    for _ in range(MAX_UPLOAD_BYTES // len(chunk) + 1):
                        yield chunk

                request_headers = headers(workflow, media_type="image/png")
                if limit_kind == "understated_bytes":
                    request_headers["Content-Length"] = "1"
                response = await client.post(route, content=chunks(), headers=request_headers)
            else:
                size = (8193, 1) if limit_kind == "side" else (4097, 4096)
                response = await upload(client, workflow, image_bytes(size=size))
            checked(response, 413)
        assert persisted_state(workflow) == before

    asyncio.run(requests())


def test_duplicate_same_component_is_idempotent_and_retains_original_uploader(workflow: AssetWorkflow) -> None:
    async def requests() -> None:
        raw = image_bytes()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            first = checked(await upload(client, workflow, raw), 201)
            before = persisted_state(workflow)
            duplicate = checked(await upload(client, workflow, raw, actor="asset-bob"))
            assert duplicate["duplicate"] is True
            assert duplicate["asset"] == first["asset"]
            assert duplicate["observation"] == first["observation"]
            assert duplicate["asset"]["uploaded_by"] == "asset-alice"
            assert persisted_state(workflow) == before

    asyncio.run(requests())


def test_same_bytes_cannot_be_registered_as_a_different_physical_component(workflow: AssetWorkflow) -> None:
    async def requests() -> None:
        raw = image_bytes()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            checked(await upload(client, workflow, raw), 201)
            before = persisted_state(workflow)
            checked(await upload(client, workflow, raw, component_id=SECOND_COMPONENT_ID, return_id=SECOND_RETURN_ID), 409)
            assert persisted_state(workflow) == before
            assert workflow.evidence.current(SECOND_COMPONENT_ID).version == 1

    asyncio.run(requests())


def test_multiple_views_keep_one_physical_identity_and_separate_evidence(workflow: AssetWorkflow) -> None:
    async def requests() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            results = [checked(await upload(client, workflow, image_bytes(color=color)), 201) for color in ("red", "green", "blue")]
            assets = checked(await client.get(f"/components/{COMPONENT_ID}/images", headers=headers(workflow)))
            assert len(assets) == 3
            assert len({asset["asset_id"] for asset in assets}) == 3
            assert {asset["physical_component_id"] for asset in assets} == {COMPONENT_ID}
            assert len({result["observation"]["observation_id"] for result in results}) == 3
            inventory = checked(await client.get("/inventory", headers=headers(workflow)))
            assert len(inventory["items"]) == 2
            assert {entry["item"]["component"]["physical_component_id"] for entry in inventory["items"]} == {COMPONENT_ID, SECOND_COMPONENT_ID}
            assert {entry["availability"] for entry in inventory["items"]} == {"held"}

    asyncio.run(requests())


@pytest.mark.parametrize(("component_id", "return_id", "status"), [
    (COMPONENT_ID, SECOND_RETURN_ID, 409), ("unknown-component", RETURN_ID, 404),
])
def test_upload_requires_existing_component_and_matching_return(
    workflow: AssetWorkflow, component_id: str, return_id: str, status: int,
) -> None:
    async def requests() -> None:
        before = persisted_state(workflow)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            checked(await upload(client, workflow, image_bytes(), component_id=component_id, return_id=return_id), status)
        assert persisted_state(workflow) == before

    asyncio.run(requests())


def test_unknown_asset_is_not_found_but_missing_registered_file_is_gone(workflow: AssetWorkflow) -> None:
    async def requests() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            unknown_id = "asset-" + "0" * 32
            checked(await client.get(f"/assets/{unknown_id}", headers=headers(workflow)), 404)
            checked(await client.get(f"/assets/{unknown_id}/content", headers=headers(workflow)), 404)
            result = checked(await upload(client, workflow, image_bytes()), 201)
            asset = result["asset"]
            stored_file(workflow, asset).unlink()
            metadata = checked(await client.get(f"/assets/{asset['asset_id']}", headers=headers(workflow)))
            assert metadata["availability"] == "missing"
            assert metadata["sha256"] == asset["sha256"]
            checked(await client.get(f"/assets/{asset['asset_id']}/content", headers=headers(workflow)), 410)
            history = workflow.evidence.history(COMPONENT_ID)
            assert len(history.events) == 1
            assert history.events[0].event_id == asset["observation_id"]

    asyncio.run(requests())


def test_changed_stored_bytes_are_reported_corrupt_and_never_served(workflow: AssetWorkflow) -> None:
    async def requests() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            result = checked(await upload(client, workflow, image_bytes()), 201)
            asset = result["asset"]
            original = stored_file(workflow, asset).read_bytes()
            changed = original[:-1] + bytes([original[-1] ^ 1])
            assert len(changed) == len(original)
            stored_file(workflow, asset).write_bytes(changed)
            before = persisted_state(workflow)
            metadata = checked(await client.get(f"/assets/{asset['asset_id']}", headers=headers(workflow)))
            assert metadata["availability"] == "corrupt"
            response = await client.get(f"/assets/{asset['asset_id']}/content", headers=headers(workflow))
            checked(response, 409)
            assert response.content != changed
            assert str(workflow.root) not in response.text
            assert persisted_state(workflow) == before

    asyncio.run(requests())


def test_asset_upload_and_reads_enforce_authentication_and_distinct_roles(workflow: AssetWorkflow) -> None:
    async def requests() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            result = checked(await upload(client, workflow, image_bytes()), 201)
            asset_id = result["asset"]["asset_id"]
            before = persisted_state(workflow)
            route = f"/components/{COMPONENT_ID}/images?return_id={RETURN_ID}"
            checked(await client.post(route, content=image_bytes(color="blue"), headers={"Content-Type": "image/png"}), 401)
            checked(await client.post(route, content=image_bytes(color="blue"), headers=headers(workflow, "asset-viewer", "image/png")), 403)
            for route in (f"/assets/{asset_id}", f"/assets/{asset_id}/content", f"/components/{COMPONENT_ID}/images"):
                checked(await client.get(route), 401)
                checked(await client.get(route, headers=headers(workflow, "asset-intake")), 403)
            response = await client.get(f"/assets/{asset_id}/content", headers=headers(workflow, "asset-viewer"))
            assert response.status_code == 200
            assert response.content == image_bytes()
            assert persisted_state(workflow) == before

    asyncio.run(requests())


@pytest.mark.parametrize("extra_query", [{"asset_id": "client-selected-id"}, {"path": "../outside.png"}, {"filename": "client.png"}])
def test_upload_rejects_client_storage_identifiers_and_paths(workflow: AssetWorkflow, extra_query: dict) -> None:
    async def requests() -> None:
        before = persisted_state(workflow)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            checked(await client.post(
                f"/components/{COMPONENT_ID}/images", params={"return_id": RETURN_ID} | extra_query,
                content=image_bytes(), headers=headers(workflow, media_type="image/png"),
            ), 422)
        assert persisted_state(workflow) == before

    asyncio.run(requests())


def test_asset_metadata_and_raw_bytes_have_no_mutation_routes(workflow: AssetWorkflow) -> None:
    async def requests() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            result = checked(await upload(client, workflow, image_bytes()), 201)
            asset_id = result["asset"]["asset_id"]
            before = persisted_state(workflow)
            for method in ("PUT", "PATCH", "DELETE"):
                for path in (f"/assets/{asset_id}", f"/assets/{asset_id}/content"):
                    response = await client.request(method, path, content=image_bytes(color="blue"), headers=headers(workflow, media_type="image/png"))
                    assert response.status_code in (404, 405)
            assert persisted_state(workflow) == before

    asyncio.run(requests())


@pytest.mark.parametrize("sql", ["UPDATE image_assets SET payload = '{}'", "DELETE FROM image_assets"])
def test_asset_metadata_is_append_only_at_database_boundary(workflow: AssetWorkflow, sql: str) -> None:
    workflow.assets.upload(COMPONENT_ID, RETURN_ID, image_bytes(), "image/png", "asset-alice")
    before = persisted_state(workflow)
    with pytest.raises(ConflictError):
        with workflow.evidence.transaction() as connection:
            connection.execute(sql)
    assert persisted_state(workflow) == before


@pytest.mark.parametrize("reference_kind", ["wrong_component", "unknown", "malformed", "uppercase"])
def test_managed_reference_requires_a_real_asset_bound_to_the_same_component(
    workflow: AssetWorkflow, reference_kind: str,
) -> None:
    async def requests() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            uploaded = checked(await upload(client, workflow, image_bytes()), 201)
            asset_id = uploaded["asset"]["asset_id"]
            references = {
                "wrong_component": (f"asset:{asset_id}", 409),
                "unknown": ("asset:asset-" + "0" * 32, 404),
                "malformed": ("asset:../../unmanaged.png", 422),
                "uppercase": (f"ASSET:{asset_id}", 422),
            }
            reference, expected_status = references[reference_kind]
            before = persisted_state(workflow)
            payload = {
                "observation_id": "managed-reference-probe", "physical_component_id": SECOND_COMPONENT_ID,
                "source_return_id": SECOND_RETURN_ID, "captured_at": NOW.isoformat(),
                "evidence_reference": reference, "source": "operator", "source_reference": "ignored-client-actor",
            }
            checked(await client.post(f"/components/{SECOND_COMPONENT_ID}/evidence", headers=headers(workflow),
                                      json={"kind": "observation", "payload": payload}), expected_status)
            assert persisted_state(workflow) == before

    asyncio.run(requests())


@pytest.mark.parametrize(("image_format", "media_type"), [("PNG", "image/png"), ("WEBP", "image/webp")])
def test_animated_images_are_rejected_without_silently_selecting_a_frame(
    workflow: AssetWorkflow, image_format: str, media_type: str,
) -> None:
    output = BytesIO()
    Image.new("RGB", (24, 18), "red").save(
        output, format=image_format, save_all=True,
        append_images=[Image.new("RGB", (24, 18), "blue")], duration=100, loop=0,
    )

    async def requests() -> None:
        before = persisted_state(workflow)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            checked(await upload(client, workflow, output.getvalue(), media_type=media_type), 422)
        assert persisted_state(workflow) == before

    asyncio.run(requests())


def test_fsync_failure_cleans_new_file_and_leaves_no_metadata_or_evidence(
    workflow: AssetWorkflow, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_fsync(_descriptor: int) -> None:
        raise OSError("simulated storage synchronization failure")

    async def requests() -> None:
        before = persisted_state(workflow)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            with monkeypatch.context() as scoped:
                scoped.setattr("rekit.evidence.assets.os.fsync", fail_fsync)
                response = await upload(client, workflow, image_bytes())
                checked(response, 503)
                assert str(workflow.root) not in response.text
            assert persisted_state(workflow) == before
            checked(await upload(client, workflow, image_bytes()), 201)
            assert tuple(map(len, persisted_state(workflow))) == (1, 1, 1)

    asyncio.run(requests())


def test_metadata_insert_failure_rolls_back_observation_and_removes_new_file(workflow: AssetWorkflow) -> None:
    with workflow.evidence.transaction() as connection:
        connection.execute("""
            CREATE TRIGGER injected_asset_failure AFTER INSERT ON image_assets
            BEGIN SELECT RAISE(ABORT, 'injected asset metadata failure'); END
        """)

    async def requests() -> None:
        before = persisted_state(workflow)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            checked(await upload(client, workflow, image_bytes()), 409)
            assert persisted_state(workflow) == before
            assert workflow.evidence.current(COMPONENT_ID).version == 1
            with workflow.evidence.transaction() as connection:
                connection.execute("DROP TRIGGER injected_asset_failure")
            checked(await upload(client, workflow, image_bytes()), 201)
            assert tuple(map(len, persisted_state(workflow))) == (1, 1, 1)

    asyncio.run(requests())


def test_concurrent_identical_uploads_create_one_asset_and_one_observation(workflow: AssetWorkflow) -> None:
    async def requests() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            responses = await asyncio.gather(
                upload(client, workflow, image_bytes()),
                upload(client, workflow, image_bytes(), actor="asset-bob"),
            )
            assert sorted(response.status_code for response in responses) == [200, 201]
            first, second = [response.json() for response in responses]
            assert first["asset"] == second["asset"]
            assert first["observation"] == second["observation"]
            assert {first["duplicate"], second["duplicate"]} == {False, True}
            assert tuple(map(len, persisted_state(workflow))) == (1, 1, 1)
            assert workflow.evidence.current(COMPONENT_ID).version == 2

    asyncio.run(requests())


@pytest.mark.parametrize(("damage", "expected_status"), [("missing", 410), ("corrupt", 409)])
def test_duplicate_upload_never_repairs_or_replaces_broken_original_asset(
    workflow: AssetWorkflow, damage: str, expected_status: int,
) -> None:
    async def requests() -> None:
        raw = image_bytes()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            result = checked(await upload(client, workflow, raw), 201)
            path = stored_file(workflow, result["asset"])
            if damage == "missing":
                path.unlink()
            else:
                path.write_bytes(b"broken original")
            before = persisted_state(workflow)
            checked(await upload(client, workflow, raw, actor="asset-bob"), expected_status)
            assert persisted_state(workflow) == before
            assert workflow.evidence.current(COMPONENT_ID).version == 2

    asyncio.run(requests())


@pytest.mark.parametrize(("damage", "expected_status"), [("missing", 410), ("corrupt", 409)])
def test_verification_cannot_rely_on_missing_or_corrupt_managed_image(
    workflow: AssetWorkflow, damage: str, expected_status: int,
) -> None:
    async def requests() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=workflow.app), base_url="http://testserver") as client:
            result = checked(await upload(client, workflow, image_bytes()), 201)
            path = stored_file(workflow, result["asset"])
            if damage == "missing":
                path.unlink()
            else:
                path.write_bytes(b"corrupt")
            before = persisted_state(workflow)
            request = {
                "expected_version": workflow.evidence.current(COMPONENT_ID).version,
                "verification": {
                    "verification_id": "asset-verification", "physical_component_id": COMPONENT_ID,
                    "identity": {"component_type_id": "body", "revision": "A"},
                    "verified_at": NOW.isoformat(), "evidence_observation_ids": [result["observation"]["observation_id"]],
                    "visible_condition": "acceptable", "reason": "Synthetic operator assertion based on the managed image.",
                },
            }
            checked(await client.post(f"/components/{COMPONENT_ID}/verification", json=request, headers=headers(workflow)), expected_status)
            assert persisted_state(workflow) == before
            assert workflow.evidence.current(COMPONENT_ID).verification is None

    asyncio.run(requests())
