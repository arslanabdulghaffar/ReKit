"""An exact historical retry is not a new decision about unavailable image evidence."""

import asyncio
from io import BytesIO
import json
from pathlib import Path
import secrets

import httpx
from PIL import Image
import pytest

from rekit.auth import Actor, ActorKind, AuthConfig, OperatorCredential, Role, token_digest
from rekit.catalog.models import Catalog
from rekit.evidence.assets import ImageAssetStore
from rekit.evidence.store import EvidenceStore
from rekit.inventory.store import InventoryStore
from rekit.main import create_app
from rekit.recovery.models import DispositionPolicy


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_exact_actor_bound_retries_survive_asset_loss_but_new_decisions_do_not(tmp_path, damage):
    fixtures = Path(__file__).parents[1] / "fixtures"
    fixture = json.loads((fixtures / "synthetic_recovery.json").read_text(encoding="utf-8"))
    catalog = Catalog.model_validate_json((fixtures / fixture["catalog_file"]).read_text(encoding="utf-8"))
    policy = DispositionPolicy.model_validate_json((fixtures / fixture["disposition_policy_file"]).read_text(encoding="utf-8"))
    evidence = EvidenceStore(tmp_path / "retries.sqlite3", catalog)
    assets = ImageAssetStore(evidence, tmp_path / "images")
    tokens = {name: secrets.token_urlsafe(32) for name in ("alice", "bob")}
    auth = AuthConfig(operators=tuple(OperatorCredential(
        actor=Actor(actor_id=name, kind=ActorKind.HUMAN, roles=tuple(Role)), token_sha256=token_digest(token),
    ) for name, token in tokens.items()))
    store = InventoryStore(evidence, policy)
    app = create_app(store, auth=auth, assets=assets)

    async def workflow():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver",
                                     headers={"Authorization": f"Bearer {tokens['alice']}"}) as client:
            async def post(route, body, status=200):
                response = await client.post(route, json=body)
                assert response.status_code == status, response.text
                return response.json()

            await post("/batches", fixture["batch"], 201)
            for record in fixture["returns"]:
                await post("/returns", record, 201)
            uploads, verifications = {}, {}
            for index, record in enumerate(fixture["components"]):
                component = record["component"]
                cid = component["physical_component_id"]
                await post("/components", component, 201)
                output = BytesIO()
                Image.new("RGB", (10, 10), (index * 40, 80, 120)).save(output, format="PNG")
                response = await client.post(f"/components/{cid}/images?return_id={component['source_return_id']}",
                                             content=output.getvalue(), headers={"Content-Type": "image/png"})
                assert response.status_code == 201, response.text
                uploads[cid] = response.json()
                verification = {key: value for key, value in record["verification"].items() if key != "operator_id"}
                verification["evidence_observation_ids"] = [uploads[cid]["observation"]["observation_id"]]
                verifications[cid] = {"verification": verification, "expected_version": 2}
                await post(f"/components/{cid}/verification", verifications[cid])

            proposal = await post("/plans", {"scenario": fixture["scenario"]}, 201)
            plan_id = proposal["plan"]["plan_id"]
            approval = {"operation_id": "approval", "expected_version": 1, "reason": "Reviewed synthetic plan."}
            approved = await post(f"/plans/{plan_id}/approve", approval)
            action = approved["plan"]["selected_actions"][0]
            cid = action["component_ids"][0]
            completion = {
                "operation_id": "completion", "expected_version": approved["version"], "reason": "Explicit synthetic assembly confirmation.",
                "confirmed": True, "component_ids": action["component_ids"], "completed_kit_id": "completed-first",
                "evidence_references": [uploads[cid]["observation"]["evidence_reference"]],
            }
            route = f"/plans/{plan_id}/actions/{action['action_id']}/complete"
            completed = await post(route, completion)
            asset_id = uploads[cid]["asset"]["asset_id"]
            path = assets.root / f"{asset_id}.png"
            if damage == "missing":
                path.unlink()
            else:
                path.write_bytes(b"changed")
            before_inventory, before_audit, before_history = store.inventory(), store.audit(plan_id), evidence.history(cid)
            assert await post(route, completion) == completed
            assert await post(f"/plans/{plan_id}/approve", approval) == completed
            await post(f"/components/{cid}/verification", verifications[cid])
            await post(f"/components/{cid}/evidence", {"kind": "observation", "payload": uploads[cid]["observation"]})
            replay_other_actor = await client.post(route, json=completion, headers={"Authorization": f"Bearer {tokens['bob']}"})
            assert replay_other_actor.status_code == 409
            await post(route, completion | {"reason": "Changed historical command."}, 409)
            new_verification = verifications[cid]["verification"] | {
                "verification_id": "new-verification", "supersedes_verification_id": verifications[cid]["verification"]["verification_id"],
            }
            await post(f"/components/{cid}/verification", {"verification": new_verification, "expected_version": before_history.current.version},
                       410 if damage == "missing" else 409)
            assert store.inventory() == before_inventory
            assert store.audit(plan_id) == before_audit
            assert evidence.history(cid) == before_history
    asyncio.run(workflow())
