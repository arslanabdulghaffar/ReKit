"""Authoritative read models used by the connected operator interface."""

import asyncio
import json
from pathlib import Path
import secrets

import httpx
import pytest

from rekit.auth import Actor, ActorKind, AuthConfig, OperatorCredential, Role, token_digest
from rekit.catalog.models import Catalog
from rekit.evidence.models import PhysicalComponent, ReturnBatch, ReturnRecord
from rekit.evidence.store import EvidenceStore
from rekit.inventory.execution import CancellationCommand
from rekit.inventory.store import InventoryStore
from rekit.main import create_app
from rekit.recovery.models import DispositionPolicy, EconomicScenario


FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.fixture
def workspace(tmp_path):
    fixture = json.loads((FIXTURES / "synthetic_recovery.json").read_text(encoding="utf-8"))
    catalog = Catalog.model_validate_json((FIXTURES / fixture["catalog_file"]).read_text(encoding="utf-8"))
    policy = DispositionPolicy.model_validate_json((FIXTURES / fixture["disposition_policy_file"]).read_text(encoding="utf-8"))
    evidence = EvidenceStore(tmp_path / "workbench.sqlite3", catalog)
    store = InventoryStore(evidence, policy)
    tokens = {"reader": secrets.token_urlsafe(32), "planner": secrets.token_urlsafe(32)}
    auth = AuthConfig(operators=tuple(OperatorCredential(
        actor=Actor(actor_id=actor, kind=ActorKind.HUMAN, roles=(role,)), token_sha256=token_digest(tokens[actor]),
    ) for actor, role in (("reader", Role.VIEWER), ("planner", Role.PLANNER))))
    return create_app(store, auth=auth), store, fixture, tokens


def populate(store, fixture):
    store.evidence.register_batch(ReturnBatch.model_validate(fixture["batch"]))
    for record in fixture["returns"]:
        store.evidence.register_return(ReturnRecord.model_validate(record))
    for record in fixture["components"]:
        store.evidence.register_component(PhysicalComponent.model_validate(record["component"]))


@pytest.mark.parametrize("route", ["/catalog", "/batches", "/returns", "/plans"])
def test_workbench_reads_require_explicit_viewer_role(workspace, route):
    app, store, fixture, tokens = workspace

    async def requests():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            assert (await client.get(route)).status_code == 401
            assert (await client.get(route, headers={"Authorization": f"Bearer {tokens['planner']}"})).status_code == 403
            response = await client.get(route, headers={"Authorization": f"Bearer {tokens['reader']}"})
            assert response.status_code == 200
            assert response.headers["cache-control"] == "no-store"
            assert response.json() == (store.catalog.model_dump(mode="json") if route == "/catalog" else [])
    asyncio.run(requests())


def test_workbench_returns_persisted_intake_and_current_compact_plan_state(workspace):
    app, store, fixture, tokens = workspace
    populate(store, fixture)
    scenario = EconomicScenario.model_validate(fixture["scenario"])
    first = store.request_plan(scenario, requested_by="planner")
    second = store.request_plan(scenario.model_copy(update={"scenario_id": "second-scenario"}), requested_by="planner")
    store.cancel(first.plan.plan_id, CancellationCommand(
        operation_id="cancel-first", operator_id="reviewer", expected_version=first.version, reason="Review changed.",
    ))

    async def requests():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver",
                                     headers={"Authorization": f"Bearer {tokens['reader']}"}) as client:
            assert (await client.get("/batches")).json() == [ReturnBatch.model_validate(fixture["batch"]).model_dump(mode="json")]
            returned = (await client.get("/returns")).json()
            assert {item["return_id"] for item in returned} == {item["return_id"] for item in fixture["returns"]}
            summaries = (await client.get("/plans")).json()
            assert [item["plan_id"] for item in summaries] == [second.plan.plan_id, first.plan.plan_id]
            assert summaries[1]["state"] == "cancelled"
            assert summaries[1]["version"] == first.version + 1
            for summary in summaries:
                assert summary["currency"] == scenario.currency
                assert summary["status"] == "OPTIMAL"
                assert summary["modeled_value_cents"] == 0  # unverified parts are held
                assert summary["created_at"]
                assert "problem" not in summary and "selected_actions" not in summary
            assert (await client.get("/plans?limit=1")).json() == summaries[:1]
            assert (await client.get(f"/plans/{second.plan.plan_id}")).json()["plan"]["problem"]
    asyncio.run(requests())


@pytest.mark.parametrize("limit", ["0", "101", "-1", "1.5", "true"])
def test_workbench_plan_listing_is_bounded(workspace, limit):
    app, _, _, tokens = workspace

    async def requests():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver",
                                     headers={"Authorization": f"Bearer {tokens['reader']}"}) as client:
            assert (await client.get(f"/plans?limit={limit}")).status_code == 422
    asyncio.run(requests())
