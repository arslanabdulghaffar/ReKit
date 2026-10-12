"""HTTP recovery workflow using synthetic operator evidence and the real CPU solver."""

import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

from fastapi import FastAPI
import httpx
import pytest

from rekit.catalog.models import Catalog
from rekit.evidence.store import EvidenceStore
from rekit.inventory.store import InventoryStore
from rekit.main import create_app, create_configured_app
from rekit.recovery.models import DispositionPolicy


FIXTURES = Path(__file__).parents[1] / "fixtures"


@pytest.fixture
def recovery_fixture() -> dict:
    return json.loads((FIXTURES / "synthetic_recovery.json").read_text(encoding="utf-8"))


@pytest.fixture
def api(tmp_path: Path, recovery_fixture: dict) -> FastAPI:
    catalog = Catalog.model_validate_json((FIXTURES / recovery_fixture["catalog_file"]).read_text(encoding="utf-8"))
    policy = DispositionPolicy.model_validate_json(
        (FIXTURES / recovery_fixture["disposition_policy_file"]).read_text(encoding="utf-8")
    )
    return create_app(InventoryStore(EvidenceStore(tmp_path / "api.sqlite3", catalog), policy))


def checked(response: httpx.Response, expected_status: int = 200):
    assert response.status_code == expected_status, response.text
    return response.json()


async def intake(client: httpx.AsyncClient, fixture: dict, *, verify: bool = False) -> None:
    checked(await client.post("/batches", json=fixture["batch"]), 201)
    for returned in fixture["returns"]:
        checked(await client.post("/returns", json=returned), 201)
    for record in fixture["components"]:
        component_id = record["component"]["physical_component_id"]
        checked(await client.post("/components", json=record["component"]), 201)
        current = checked(await client.post(
            f"/components/{component_id}/evidence", json={"kind": "observation", "payload": record["observation"]},
        ))
        if verify:
            checked(await client.post(f"/components/{component_id}/verification", json={
                "verification": record["verification"], "expected_version": current["version"],
            }))


def approval_command(stored: dict, operation_id: str = "synthetic-approval-001") -> dict:
    return {
        "operation_id": operation_id, "operator_id": "synthetic-reviewer",
        "expected_version": stored["version"], "reason": "Synthetic operator reviewed the proposed allocation.",
    }


def completion_command(stored: dict, action: dict, index: int) -> dict:
    return {
        "operation_id": f"synthetic-completion-{index}", "operator_id": "synthetic-reviewer",
        "expected_version": stored["version"], "reason": "Synthetic explicit confirmation of the exact rebuilt contents.",
        "confirmed": True, "component_ids": action["component_ids"],
        "evidence_references": [f"synthetic://completed-kits/{index}"],
        "completed_kit_id": f"synthetic-completed-kit-{index}",
    }


def test_http_three_incomplete_returns_become_two_explicitly_confirmed_kits(api: FastAPI, recovery_fixture: dict) -> None:
    async def workflow() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://testserver") as client:
            fixture = recovery_fixture
            expected = fixture["expected"]
            assert fixture["synthetic"] is True
            assert len(fixture["returns"]) == expected["return_count"] == 3
            await intake(client, fixture)
            initial_inventory = checked(await client.get("/inventory"))
            assert len(initial_inventory["items"]) == expected["physical_component_count"] == 4
            assert {entry["availability"] for entry in initial_inventory["items"]} == {"held"}
            assert initial_inventory["completed_kits"] == []
            for record in fixture["components"]:
                component_id = record["component"]["physical_component_id"]
                compatibility_url = f"/components/{component_id}/compatibility?configuration_id=standard-kit"
                decision = checked(await client.get(compatibility_url))
                assert decision["compatible"] is False
                assert decision["reasons"]
                history = checked(await client.get(f"/components/{component_id}/history"))
                checked(await client.post(f"/components/{component_id}/verification", json={
                    "verification": record["verification"], "expected_version": history["current"]["version"],
                }))
                assert checked(await client.get(compatibility_url))["compatible"] is True

            stored = checked(await client.post("/plans", json={"scenario": fixture["scenario"]}), 201)
            plan = stored["plan"]
            plan_id = plan["plan_id"]
            assert stored["state"] == "proposed"
            assert plan["status"] == "OPTIMAL"
            assert plan["scenario_estimate"] is True
            assert plan["solver_version"]
            for field in ("modeled_value_cents", "cash_recovery_cents", "retained_value_cents", "labor_minutes"):
                assert plan[field] == expected[field]
            actions = plan["selected_actions"]
            assert len(actions) == expected["completed_kit_count"] == 2
            assert {action["kind"] for action in actions} == {"rebuild"}
            assert checked(await client.get(f"/plans/{plan_id}")) == stored
            assert checked(await client.get("/inventory"))["completed_kits"] == []

            approved = checked(await client.post(f"/plans/{plan_id}/approve", json=approval_command(stored)))
            assert approved["state"] == "approved"
            assert approved["version"] == stored["version"] + 1
            reserved = checked(await client.get("/inventory"))
            assert {entry["availability"] for entry in reserved["items"]} == {"reserved"}
            assert {entry["plan_id"] for entry in reserved["items"]} == {plan_id}
            assert reserved["completed_kits"] == []
            current = approved
            for index, action in enumerate(actions, start=1):
                command = completion_command(current, action, index)
                route = f"/plans/{plan_id}/actions/{action['action_id']}/complete"
                completed = checked(await client.post(route, json=command))
                assert completed["version"] == current["version"] + 1
                assert completed["state"] == ("completed" if index == 2 else "approved")
                # A network retry uses the original version and must not duplicate the output.
                assert checked(await client.post(route, json=command)) == completed
                current = completed

            final_inventory = checked(await client.get("/inventory"))
            assert {entry["availability"] for entry in final_inventory["items"]} == {"consumed"}
            kits = final_inventory["completed_kits"]
            assert len(kits) == expected["completed_kit_count"]
            all_component_ids = [identifier for kit in kits for identifier in kit["component_ids"]]
            fixture_ids = {record["component"]["physical_component_id"] for record in fixture["components"]}
            assert len(all_component_ids) == len(set(all_component_ids)) == expected["physical_component_count"]
            assert set(all_component_ids) == fixture_ids
            types = {record["component"]["physical_component_id"]: record["verification"]["identity"]["component_type_id"]
                     for record in fixture["components"]}
            for kit in kits:
                assert kit["plan_id"] == plan_id
                assert kit["configuration_id"] == expected["configuration_id"]
                assert sorted(types[identifier] for identifier in kit["component_ids"]) == ["adapter", "body"]
                assert kit["evidence_references"]
            audit = checked(await client.get(f"/plans/{plan_id}/audit"))
            assert [event["kind"] for event in audit] == ["proposed", "approved", "action_completed", "action_completed"]
            assert [event["plan_version"] for event in audit] == [1, 2, 3, 4]

    asyncio.run(workflow())


def test_ambiguous_and_incompatible_evidence_cannot_automatically_form_kits(api: FastAPI, recovery_fixture: dict) -> None:
    async def workflow() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://testserver") as client:
            await intake(client, recovery_fixture)
            for record in recovery_fixture["components"][:2]:
                component_id = record["component"]["physical_component_id"]
                history = checked(await client.get(f"/components/{component_id}/history"))
                checked(await client.post(f"/components/{component_id}/verification", json={
                    "verification": record["verification"], "expected_version": history["current"]["version"],
                }))
            ambiguous = recovery_fixture["components"][2]
            component_id = ambiguous["component"]["physical_component_id"]
            for revision in ("A", "B"):
                current = checked(await client.post(f"/components/{component_id}/evidence", json={
                    "kind": "proposal", "payload": {
                        "proposal_id": f"synthetic-operator-hypothesis-{revision}", "physical_component_id": component_id,
                        "observation_id": ambiguous["observation"]["observation_id"],
                        "proposed_identity": {"component_type_id": "adapter", "revision": revision},
                        "created_at": ambiguous["observation"]["captured_at"],
                    },
                }))
            assert current["state"] == "review_required"
            assert current["verification"] is None
            incompatible = recovery_fixture["components"][3]
            wrong_verification = deepcopy(incompatible["verification"])
            wrong_verification["identity"]["revision"] = "B"
            wrong_id = incompatible["component"]["physical_component_id"]
            history = checked(await client.get(f"/components/{wrong_id}/history"))
            checked(await client.post(f"/components/{wrong_id}/verification", json={
                "verification": wrong_verification, "expected_version": history["current"]["version"],
            }))
            for identifier in (component_id, wrong_id):
                decision = checked(await client.get(f"/components/{identifier}/compatibility?configuration_id=standard-kit"))
                assert decision["compatible"] is False
                assert decision["reasons"]
            plan = checked(await client.post("/plans", json={"scenario": recovery_fixture["scenario"]}), 201)
            assert not any(action["kind"] == "rebuild" for action in plan["plan"]["selected_actions"])
            assert checked(await client.get("/inventory"))["completed_kits"] == []

    asyncio.run(workflow())


def test_http_not_found_conflict_validation_and_path_identity_errors(api: FastAPI, recovery_fixture: dict) -> None:
    async def workflow() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://testserver") as client:
            checked(await client.get("/plans/missing-plan"), 404)
            await intake(client, recovery_fixture, verify=True)
            first, second = recovery_fixture["components"][:2]
            component_id = first["component"]["physical_component_id"]
            checked(await client.get(f"/components/{component_id}/compatibility?configuration_id=unknown-config"), 422)
            checked(await client.post(f"/components/{component_id}/evidence", json={
                "kind": "observation", "payload": second["observation"],
            }), 422)
            checked(await client.post(f"/components/{component_id}/verification", json={
                "verification": second["verification"], "expected_version": 3,
            }), 422)
            checked(await client.post("/components", json=first["component"] | {"physical_component_id": " "}), 422)
            stale = first["verification"] | {"verification_id": "synthetic-stale-verification"}
            checked(await client.post(f"/components/{component_id}/verification", json={
                "verification": stale, "expected_version": 1,
            }), 409)
            invalid_scenario = deepcopy(recovery_fixture["scenario"])
            invalid_scenario["kits"][0]["configuration_id"] = "unknown-config"
            response = await client.post("/plans", json={"scenario": invalid_scenario})
            assert checked(response, 422)["detail"]
            assert "Traceback" not in response.text
            plan = checked(await client.post("/plans", json={"scenario": recovery_fixture["scenario"]}), 201)
            command = approval_command(plan)
            plan_id = plan["plan"]["plan_id"]
            approved = checked(await client.post(f"/plans/{plan_id}/approve", json=command))
            assert checked(await client.post(f"/plans/{plan_id}/approve", json=command)) == approved
            checked(await client.post(f"/plans/{plan_id}/approve", json=command | {"reason": "Changed request"}), 409)
            checked(await client.post(f"/plans/{plan_id}/cancel", json={
                "operation_id": "synthetic-stale-cancel", "operator_id": "synthetic-reviewer",
                "expected_version": 1, "reason": "Synthetic stale command.",
            }), 409)
            assert len(checked(await client.get(f"/plans/{plan_id}/audit"))) == 2

    asyncio.run(workflow())


@pytest.mark.parametrize("authority_field", ["catalog", "policy", "inventory"])
def test_planning_rejects_client_supplied_authority(api: FastAPI, recovery_fixture: dict, authority_field: str) -> None:
    async def workflow() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://testserver") as client:
            response = await client.post("/plans", json={"scenario": recovery_fixture["scenario"], authority_field: {}})
            checked(response, 422)
            assert checked(await client.get("/inventory")) == {"items": [], "completed_kits": []}

    asyncio.run(workflow())


@pytest.mark.parametrize("confirmation", [None, False, 1])
def test_http_completion_requires_explicit_boolean_confirmation(api: FastAPI, recovery_fixture: dict, confirmation: object) -> None:
    async def workflow() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://testserver") as client:
            await intake(client, recovery_fixture, verify=True)
            proposed = checked(await client.post("/plans", json={"scenario": recovery_fixture["scenario"]}), 201)
            plan_id = proposed["plan"]["plan_id"]
            approved = checked(await client.post(f"/plans/{plan_id}/approve", json=approval_command(proposed)))
            action = approved["plan"]["selected_actions"][0]
            command = completion_command(approved, action, 1)
            if confirmation is None:
                command.pop("confirmed")
            else:
                command["confirmed"] = confirmation
            checked(await client.post(f"/plans/{plan_id}/actions/{action['action_id']}/complete", json=command), 422)
            inventory = checked(await client.get("/inventory"))
            assert inventory["completed_kits"] == []
            assert {entry["availability"] for entry in inventory["items"]} == {"reserved"}
            assert len(checked(await client.get(f"/plans/{plan_id}/audit"))) == 2

    asyncio.run(workflow())


def test_business_validation_error_does_not_echo_server_inventory_or_catalog(api: FastAPI, recovery_fixture: dict) -> None:
    async def workflow() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://testserver") as client:
            await intake(client, recovery_fixture, verify=True)
            incomplete_scenario = deepcopy(recovery_fixture["scenario"])
            incomplete_scenario["components"].pop()
            response = await client.post("/plans", json={"scenario": incomplete_scenario})
            detail = checked(response, 422)["detail"]
            assert isinstance(detail, list)
            assert all(set(error) <= {"loc", "msg", "type"} for error in detail)
            assert "synthetic-body-001" not in response.text
            assert "synthetic-demo-catalog" not in response.text
            assert "synthetic://captures" not in response.text

    asyncio.run(workflow())


def configure_environment(monkeypatch: pytest.MonkeyPatch, database_path: Path) -> None:
    monkeypatch.setenv("REKIT_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("REKIT_CATALOG_PATH", str(FIXTURES / "synthetic_catalog.json"))
    monkeypatch.setenv("REKIT_DISPOSITION_POLICY_PATH", str(FIXTURES / "synthetic_disposition_policy.json"))


def test_default_app_is_unconfigured_and_fresh_import_does_not_create_a_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "uncreated" / "default.sqlite3"
    configure_environment(monkeypatch, database_path)
    default_app = create_app()

    async def requests() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=default_app), base_url="http://testserver") as client:
            assert checked(await client.get("/health")) == {"status": "ok"}
            checked(await client.get("/inventory"), 503)

    asyncio.run(requests())
    subprocess.run(
        [sys.executable, "-B", "-c", "import rekit.main"], cwd=tmp_path,
        env=os.environ.copy(), check=True, capture_output=True, text=True, timeout=20,
    )
    assert not database_path.parent.exists()


@pytest.mark.parametrize("missing_name", ["REKIT_DATABASE_PATH", "REKIT_CATALOG_PATH", "REKIT_DISPOSITION_POLICY_PATH"])
def test_configured_factory_requires_all_paths_before_creating_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing_name: str,
) -> None:
    database_path = tmp_path / "uncreated" / "factory.sqlite3"
    configure_environment(monkeypatch, database_path)
    monkeypatch.delenv(missing_name)
    with pytest.raises(RuntimeError, match=missing_name):
        create_configured_app()
    assert not database_path.parent.exists()


def test_configured_factory_loads_trusted_fixture_files_and_temp_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "configured.sqlite3"
    configure_environment(monkeypatch, database_path)
    configured = create_configured_app()

    async def requests() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=configured), base_url="http://testserver") as client:
            assert checked(await client.get("/health")) == {"status": "ok"}
            assert checked(await client.get("/inventory")) == {"items": [], "completed_kits": []}

    asyncio.run(requests())
    assert database_path.is_file()


def test_http_unknown_identity_stays_held_and_cannot_be_operator_verified(api: FastAPI, recovery_fixture: dict) -> None:
    async def workflow() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://testserver") as client:
            await intake(client, recovery_fixture)
            record = recovery_fixture["components"][0]
            component_id = record["component"]["physical_component_id"]
            unknown_identity = {"component_type_id": "synthetic-unknown-part", "revision": "A"}
            current = checked(await client.post(f"/components/{component_id}/evidence", json={
                "kind": "proposal", "payload": {
                    "proposal_id": "synthetic-unknown-identity-proposal", "physical_component_id": component_id,
                    "observation_id": record["observation"]["observation_id"],
                    "proposed_identity": unknown_identity, "created_at": record["observation"]["captured_at"],
                },
            }))
            assert current["state"] == "unresolved"
            assert current["verification"] is None
            before = checked(await client.get(f"/components/{component_id}/history"))
            checked(await client.post(f"/components/{component_id}/verification", json={
                "verification": record["verification"] | {"identity": unknown_identity},
                "expected_version": current["version"],
            }), 422)
            assert checked(await client.get(f"/components/{component_id}/history")) == before
            decision = checked(await client.get(f"/components/{component_id}/compatibility?configuration_id=standard-kit"))
            assert decision["compatible"] is False
            proposed = checked(await client.post("/plans", json={"scenario": recovery_fixture["scenario"]}), 201)
            assert {action["kind"] for action in proposed["plan"]["selected_actions"]} == {"hold"}
            inventory = checked(await client.get("/inventory"))
            assert len(inventory["items"]) == recovery_fixture["expected"]["physical_component_count"]
            assert {entry["availability"] for entry in inventory["items"]} == {"held"}
            assert inventory["completed_kits"] == []

    asyncio.run(workflow())


def test_http_repeated_observations_and_identity_correction_preserve_stock_and_history(
    api: FastAPI, recovery_fixture: dict,
) -> None:
    async def workflow() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://testserver") as client:
            await intake(client, recovery_fixture, verify=True)
            record = recovery_fixture["components"][2]
            component_id = record["component"]["physical_component_id"]
            new_observation = record["observation"] | {
                "observation_id": "synthetic-adapter-close-up", "evidence_reference": "synthetic://captures/adapter-close-up",
                "visible_revision": "B",
            }
            request = {"kind": "observation", "payload": new_observation}
            current = checked(await client.post(f"/components/{component_id}/evidence", json=request))
            assert current["state"] == "review_required"
            assert current["verification"]["verification_id"] == record["verification"]["verification_id"]
            before_retry = checked(await client.get(f"/components/{component_id}/history"))
            assert checked(await client.post(f"/components/{component_id}/evidence", json=request)) == current
            assert checked(await client.get(f"/components/{component_id}/history")) == before_retry
            correction = record["verification"] | {
                "verification_id": "synthetic-corrected-adapter-identity",
                "identity": {"component_type_id": "adapter", "revision": "B"},
                "supersedes_verification_id": record["verification"]["verification_id"],
                "evidence_observation_ids": [record["observation"]["observation_id"], new_observation["observation_id"]],
                "reason": "Synthetic operator correction after reading the additional close-up.",
            }
            corrected = checked(await client.post(f"/components/{component_id}/verification", json={
                "verification": correction, "expected_version": current["version"],
            }))
            assert corrected["version"] == current["version"] + 1
            assert corrected["verification"]["identity"]["revision"] == "B"
            history = checked(await client.get(f"/components/{component_id}/history"))
            assertions = [event["payload"] for event in history["events"] if event["kind"] == "verification"]
            assert [assertion["verification_id"] for assertion in assertions] == [
                record["verification"]["verification_id"], correction["verification_id"],
            ]
            assert [assertion["identity"]["revision"] for assertion in assertions] == ["A", "B"]
            assert assertions[1]["supersedes_verification_id"] == assertions[0]["verification_id"]
            inventory = checked(await client.get("/inventory"))
            ids = [entry["item"]["component"]["physical_component_id"] for entry in inventory["items"]]
            assert len(ids) == len(set(ids)) == recovery_fixture["expected"]["physical_component_count"]
            decision = checked(await client.get(f"/components/{component_id}/compatibility?configuration_id=standard-kit"))
            assert decision["compatible"] is False

    asyncio.run(workflow())


def test_http_insufficient_inventory_cannot_invent_a_second_kit(api: FastAPI, recovery_fixture: dict) -> None:
    async def workflow() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://testserver") as client:
            reduced = deepcopy(recovery_fixture)
            missing_id = "synthetic-body-002"
            reduced["components"] = [record for record in reduced["components"]
                                     if record["component"]["physical_component_id"] != missing_id]
            reduced["scenario"]["components"] = [estimate for estimate in reduced["scenario"]["components"]
                                                  if estimate["physical_component_id"] != missing_id]
            await intake(client, reduced, verify=True)
            proposed = checked(await client.post("/plans", json={"scenario": reduced["scenario"]}), 201)
            plan = proposed["plan"]
            assert plan["status"] == "OPTIMAL"
            assert reduced["scenario"]["kits"][0]["demand_limit"] == 2
            assert sum(action["kind"] == "rebuild" for action in plan["selected_actions"]) == 1
            assert sum(action["kind"] == "retain" for action in plan["selected_actions"]) == 1
            assigned = [identifier for action in plan["selected_actions"] for identifier in action["component_ids"]]
            assert len(assigned) == len(set(assigned)) == 3
            assert missing_id not in assigned
            assert plan["cash_recovery_cents"] == 8750
            assert plan["retained_value_cents"] == 200
            assert plan["modeled_value_cents"] == 8950
            assert checked(await client.get("/inventory"))["completed_kits"] == []

    asyncio.run(workflow())


def test_http_uneconomic_rebuild_retains_donors_without_claiming_cash(api: FastAPI, recovery_fixture: dict) -> None:
    async def workflow() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://testserver") as client:
            await intake(client, recovery_fixture, verify=True)
            scenario = deepcopy(recovery_fixture["scenario"])
            scenario["kits"][0]["selling_price_cents"] = 500
            proposed = checked(await client.post("/plans", json={"scenario": scenario}), 201)
            plan = proposed["plan"]
            assert plan["status"] == "OPTIMAL"
            assert {action["kind"] for action in plan["selected_actions"]} == {"retain"}
            assert plan["retained_value_cents"] == plan["modeled_value_cents"] == 1600
            assert plan["cash_recovery_cents"] == 0
            assert plan["labor_minutes"] == 0
            assert checked(await client.get("/inventory"))["completed_kits"] == []

    asyncio.run(workflow())


def test_concurrent_http_approvals_reserve_shared_components_for_only_one_plan(api: FastAPI, recovery_fixture: dict) -> None:
    async def workflow() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://testserver") as client:
            await intake(client, recovery_fixture, verify=True)
            first = checked(await client.post("/plans", json={"scenario": recovery_fixture["scenario"]}), 201)
            second = checked(await client.post("/plans", json={"scenario": recovery_fixture["scenario"]}), 201)
            responses = await asyncio.gather(
                client.post(f"/plans/{first['plan']['plan_id']}/approve", json=approval_command(first, "synthetic-racing-approval-1")),
                client.post(f"/plans/{second['plan']['plan_id']}/approve", json=approval_command(second, "synthetic-racing-approval-2")),
            )
            assert sorted(response.status_code for response in responses) == [200, 409]
            winner = next(response.json() for response in responses if response.status_code == 200)
            inventory = checked(await client.get("/inventory"))
            assert {entry["availability"] for entry in inventory["items"]} == {"reserved"}
            assert {entry["plan_id"] for entry in inventory["items"]} == {winner["plan"]["plan_id"]}
            ids = [entry["item"]["component"]["physical_component_id"] for entry in inventory["items"]]
            assert len(ids) == len(set(ids)) == recovery_fixture["expected"]["physical_component_count"]
            assert inventory["completed_kits"] == []
            audit_events = []
            for stored in (first, second):
                audit_events.extend(checked(await client.get(f"/plans/{stored['plan']['plan_id']}/audit")))
            assert sum(event["kind"] == "approved" for event in audit_events) == 1

    asyncio.run(workflow())


def test_http_stale_evidence_blocks_approval_without_partial_reservation(api: FastAPI, recovery_fixture: dict) -> None:
    async def workflow() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://testserver") as client:
            await intake(client, recovery_fixture, verify=True)
            proposed = checked(await client.post("/plans", json={"scenario": recovery_fixture["scenario"]}), 201)
            record = recovery_fixture["components"][0]
            component_id = record["component"]["physical_component_id"]
            changed_observation = record["observation"] | {
                "observation_id": "synthetic-post-plan-observation", "evidence_reference": "synthetic://captures/post-plan-view",
            }
            checked(await client.post(f"/components/{component_id}/evidence", json={"kind": "observation", "payload": changed_observation}))
            before_inventory = checked(await client.get("/inventory"))
            plan_id = proposed["plan"]["plan_id"]
            before_audit = checked(await client.get(f"/plans/{plan_id}/audit"))
            checked(await client.post(f"/plans/{plan_id}/approve", json=approval_command(proposed)), 409)
            assert checked(await client.get(f"/plans/{plan_id}")) == proposed
            assert checked(await client.get("/inventory")) == before_inventory
            assert checked(await client.get(f"/plans/{plan_id}/audit")) == before_audit
            assert not any(entry["availability"] == "reserved" for entry in before_inventory["items"])

    asyncio.run(workflow())


def test_http_cancellation_releases_reservations_and_prevents_later_completion(api: FastAPI, recovery_fixture: dict) -> None:
    async def workflow() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=api), base_url="http://testserver") as client:
            await intake(client, recovery_fixture, verify=True)
            proposed = checked(await client.post("/plans", json={"scenario": recovery_fixture["scenario"]}), 201)
            plan_id = proposed["plan"]["plan_id"]
            approved = checked(await client.post(f"/plans/{plan_id}/approve", json=approval_command(proposed)))
            command = {
                "operation_id": "synthetic-cancellation", "operator_id": "synthetic-reviewer",
                "expected_version": approved["version"], "reason": "Synthetic operator cancelled before rebuilding began.",
            }
            cancelled = checked(await client.post(f"/plans/{plan_id}/cancel", json=command))
            assert cancelled["state"] == "cancelled"
            assert cancelled["version"] == approved["version"] + 1
            assert checked(await client.post(f"/plans/{plan_id}/cancel", json=command)) == cancelled
            inventory = checked(await client.get("/inventory"))
            assert {entry["availability"] for entry in inventory["items"]} == {"available"}
            assert all(entry["plan_id"] is None and entry["action_id"] is None for entry in inventory["items"])
            action = cancelled["plan"]["selected_actions"][0]
            checked(await client.post(
                f"/plans/{plan_id}/actions/{action['action_id']}/complete", json=completion_command(cancelled, action, 1),
            ), 409)
            assert checked(await client.get("/inventory")) == inventory
            assert inventory["completed_kits"] == []
            assert [event["kind"] for event in checked(await client.get(f"/plans/{plan_id}/audit"))] == [
                "proposed", "approved", "cancelled",
            ]

    asyncio.run(workflow())
