"""Authentication, role boundaries, and server-owned actor attribution over HTTP."""

import asyncio
from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path
import secrets

from fastapi import FastAPI
import httpx
import pytest

from rekit.auth import Actor, ActorKind, AuthConfig, OperatorCredential, Role, token_digest
from rekit.catalog.models import Catalog
from rekit.evidence.models import Observation, PhysicalComponent, ReturnBatch, ReturnRecord
from rekit.evidence.store import EvidenceStore
from rekit.inventory.store import InventoryStore
from rekit.main import create_app, create_configured_app
from rekit.recovery.models import DispositionPolicy


FIXTURES = Path(__file__).parents[1] / "fixtures"


@dataclass
class ProtectedWorkflow:
    app: FastAPI
    store: InventoryStore
    auth: AuthConfig
    tokens: dict[str, str]
    fixture: dict


@pytest.fixture
def protected(tmp_path: Path) -> ProtectedWorkflow:
    fixture = json.loads((FIXTURES / "synthetic_recovery.json").read_text(encoding="utf-8"))
    catalog = Catalog.model_validate_json((FIXTURES / fixture["catalog_file"]).read_text(encoding="utf-8"))
    policy = DispositionPolicy.model_validate_json((FIXTURES / fixture["disposition_policy_file"]).read_text(encoding="utf-8"))
    evidence = EvidenceStore(tmp_path / "auth.sqlite3", catalog)
    evidence.register_batch(ReturnBatch.model_validate(fixture["batch"]))
    for returned in fixture["returns"]:
        evidence.register_return(ReturnRecord.model_validate(returned))
    for record in fixture["components"]:
        evidence.register_component(PhysicalComponent.model_validate(record["component"]))
        evidence.record_observation(Observation.model_validate(record["observation"]))
        record["verification"].pop("operator_id")
    actors = (
        Actor(actor_id="auth-alice", kind=ActorKind.HUMAN, roles=tuple(Role)),
        Actor(actor_id="auth-bob", kind=ActorKind.HUMAN, roles=tuple(Role)),
        Actor(actor_id="auth-viewer", kind=ActorKind.HUMAN, roles=(Role.VIEWER,)),
        Actor(actor_id="auth-service", kind=ActorKind.SERVICE, roles=(Role.VIEWER, Role.INTAKE, Role.PLANNER)),
    )
    tokens = {actor.actor_id: secrets.token_urlsafe(32) for actor in actors}
    auth = AuthConfig(operators=tuple(
        OperatorCredential(actor=actor, token_sha256=token_digest(tokens[actor.actor_id])) for actor in actors
    ))
    store = InventoryStore(evidence, policy)
    return ProtectedWorkflow(create_app(store, auth=auth), store, auth, tokens, fixture)


def authorization(protected: ProtectedWorkflow, actor: str = "auth-alice") -> dict[str, str]:
    return {"Authorization": f"Bearer {protected.tokens[actor]}"}


def checked(response: httpx.Response, status: int = 200):
    assert response.status_code == status, response.text
    return response.json()


def database_state(protected: ProtectedWorkflow):
    """Compare persisted records, including audit/idempotency rows, after denied requests."""
    tables = (
        "return_batches", "returns", "physical_components", "evidence_events", "recovery_plans",
        "recovery_plan_states", "component_allocations", "recovery_operations",
        "action_completions", "completed_kits", "inventory_audit",
    )
    with protected.store.evidence.transaction() as connection:
        return tuple((table, tuple(tuple(row) for row in connection.execute(f"SELECT * FROM {table} ORDER BY rowid")))
                     for table in tables)


def operator_command(version: int = 1, operation_id: str = "auth-test-operation") -> dict:
    return {"operation_id": operation_id, "expected_version": version, "reason": "Synthetic authenticated operator decision."}


def completion_command(stored: dict, action: dict, index: int) -> dict:
    return operator_command(stored["version"], f"auth-completion-{index}") | {
        "confirmed": True, "component_ids": action["component_ids"],
        "evidence_references": [f"synthetic://auth-completion/{index}"], "completed_kit_id": f"auth-kit-{index}",
    }


async def verify_all(client: httpx.AsyncClient, protected: ProtectedWorkflow, actor: str = "auth-alice") -> None:
    for record in protected.fixture["components"]:
        component_id = record["component"]["physical_component_id"]
        history = checked(await client.get(f"/components/{component_id}/history", headers=authorization(protected, actor)))
        current = checked(await client.post(f"/components/{component_id}/verification", headers=authorization(protected, actor), json={
            "verification": record["verification"], "expected_version": history["current"]["version"],
        }))
        assert current["verification"]["operator_id"] == actor


def test_health_is_public_and_actor_profile_contains_no_credential_material(protected: ProtectedWorkflow) -> None:
    async def workflow() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=protected.app), base_url="http://testserver") as client:
            assert checked(await client.get("/health")) == {"status": "ok"}
            response = await client.get("/auth/me", headers=authorization(protected))
            profile = checked(response)
            assert response.headers["cache-control"] == "no-store"
            assert "authorization" in {field.strip().lower() for field in response.headers["vary"].split(",")}
            assert set(profile) == {"actor_id", "kind", "roles"}
            assert profile["actor_id"] == "auth-alice"
            assert profile["kind"] == "human"
            assert set(profile["roles"]) == {role.value for role in Role}
            for token in protected.tokens.values():
                assert token not in response.text
                assert token_digest(token) not in response.text

    asyncio.run(workflow())


@pytest.mark.parametrize("credential_kind", ["missing", "wrong", "malformed", "wrong-scheme"])
def test_invalid_credentials_are_rejected_without_mutation_or_secret_echo(
    protected: ProtectedWorkflow, credential_kind: str,
) -> None:
    async def workflow() -> None:
        wrong_token = secrets.token_urlsafe(32)
        headers = {
            "missing": {}, "wrong": {"Authorization": f"Bearer {wrong_token}"},
            "malformed": {"Authorization": "Bearer short"},
            "wrong-scheme": {"Authorization": f"Basic {protected.tokens['auth-alice']}"},
        }[credential_kind]
        before = database_state(protected)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=protected.app), base_url="http://testserver") as client:
            for method, route, payload in (
                ("GET", "/inventory", None),
                ("POST", "/plans", {"scenario": protected.fixture["scenario"]}),
            ):
                response = await client.request(method, route, headers=headers, json=payload)
                checked(response, 401)
                assert response.headers["cache-control"] == "no-store"
                assert "authorization" in {field.strip().lower() for field in response.headers["vary"].split(",")}
                assert wrong_token not in response.text
                assert protected.tokens["auth-alice"] not in response.text
        assert database_state(protected) == before

    asyncio.run(workflow())


def test_duplicate_authorization_headers_are_rejected_as_ambiguous(protected: ProtectedWorkflow) -> None:
    async def workflow() -> None:
        before = database_state(protected)
        headers = [
            ("Authorization", f"Bearer {protected.tokens['auth-alice']}"),
            ("Authorization", f"Bearer {protected.tokens['auth-bob']}"),
        ]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=protected.app), base_url="http://testserver") as client:
            checked(await client.post("/plans", json={"scenario": protected.fixture["scenario"]}, headers=headers), 401)
        assert database_state(protected) == before

    asyncio.run(workflow())


def test_reviewer_role_does_not_implicitly_grant_read_intake_planning_or_approval_roles(protected: ProtectedWorkflow) -> None:
    limited = AuthConfig(operators=(OperatorCredential(
        actor=Actor(actor_id="auth-reviewer-only", kind=ActorKind.HUMAN, roles=(Role.REVIEWER,)),
        token_sha256=token_digest(protected.tokens["auth-alice"]),
    ),))
    app = create_app(protected.store, auth=limited)

    async def workflow() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            profile = checked(await client.get("/auth/me", headers=authorization(protected)))
            assert profile == {"actor_id": "auth-reviewer-only", "kind": "human", "roles": ["reviewer"]}
            route, payload = denied_request(protected, "verification")
            current = checked(await client.post(route, json=payload, headers=authorization(protected)))
            assert current["verification"]["operator_id"] == "auth-reviewer-only"
            before = database_state(protected)
            checked(await client.get("/inventory", headers=authorization(protected)), 403)
            for operation in ("evidence", "plan", "approval"):
                route, payload = denied_request(protected, operation)
                checked(await client.post(route, json=payload, headers=authorization(protected)), 403)
            assert database_state(protected) == before

    asyncio.run(workflow())


def denied_request(protected: ProtectedWorkflow, operation: str) -> tuple[str, dict]:
    record = protected.fixture["components"][0]
    component_id = record["component"]["physical_component_id"]
    requests = {
        "batch": ("/batches", protected.fixture["batch"] | {"batch_id": "unauthorized-batch"}),
        "return": ("/returns", protected.fixture["returns"][0] | {"return_id": "unauthorized-return"}),
        "component": ("/components", record["component"] | {"physical_component_id": "unauthorized-component"}),
        "evidence": (f"/components/{component_id}/evidence", {"kind": "observation", "payload": record["observation"]}),
        "verification": (f"/components/{component_id}/verification", {"verification": record["verification"], "expected_version": 2}),
        "plan": ("/plans", {"scenario": protected.fixture["scenario"]}),
        "approval": ("/plans/missing-plan/approve", operator_command()),
        "cancellation": ("/plans/missing-plan/cancel", operator_command()),
        "completion": ("/plans/missing-plan/actions/missing-action/complete", operator_command() | {
            "confirmed": True, "component_ids": [component_id], "evidence_references": ["synthetic://denied"],
            "completed_kit_id": "unauthorized-kit",
        }),
    }
    return requests[operation]


@pytest.mark.parametrize("operation", ["batch", "return", "component", "evidence", "verification", "plan", "approval", "cancellation", "completion"])
def test_viewer_cannot_execute_any_critical_write_route(protected: ProtectedWorkflow, operation: str) -> None:
    async def workflow() -> None:
        before = database_state(protected)
        route, payload = denied_request(protected, operation)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=protected.app), base_url="http://testserver") as client:
            checked(await client.post(route, json=payload, headers=authorization(protected, "auth-viewer")), 403)
        assert database_state(protected) == before

    asyncio.run(workflow())


@pytest.mark.parametrize("operation", ["verification", "approval", "cancellation", "completion"])
def test_service_actor_cannot_claim_human_authority(protected: ProtectedWorkflow, operation: str) -> None:
    async def workflow() -> None:
        route, payload = denied_request(protected, operation)
        payload = deepcopy(payload)
        if operation == "verification":
            payload["verification"]["operator_id"] = "auth-alice"
        else:
            payload["operator_id"] = "auth-alice"
        before = database_state(protected)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=protected.app), base_url="http://testserver") as client:
            checked(await client.post(route, json=payload, headers=authorization(protected, "auth-service")), 403)
        assert database_state(protected) == before

    asyncio.run(workflow())


def test_service_intake_cannot_submit_operator_evidence_but_can_submit_import_metadata(protected: ProtectedWorkflow) -> None:
    async def workflow() -> None:
        record = protected.fixture["components"][0]
        component_id = record["component"]["physical_component_id"]
        payload = record["observation"] | {"observation_id": "auth-service-observation", "source_reference": "auth-alice"}
        before = database_state(protected)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=protected.app), base_url="http://testserver") as client:
            checked(await client.post(f"/components/{component_id}/evidence", headers=authorization(protected, "auth-service"),
                                      json={"kind": "observation", "payload": payload}), 403)
            assert database_state(protected) == before
            payload = payload | {"source": "import", "source_reference": "synthetic-service-import"}
            current = checked(await client.post(f"/components/{component_id}/evidence", headers=authorization(protected, "auth-service"),
                                                json={"kind": "observation", "payload": payload}))
            assert current["state"] == "unresolved"
            assert current["verification"] is None

    asyncio.run(workflow())


def test_human_operator_evidence_reference_is_bound_to_authenticated_actor(protected: ProtectedWorkflow) -> None:
    async def workflow() -> None:
        record = protected.fixture["components"][0]
        component_id = record["component"]["physical_component_id"]
        observation = record["observation"] | {"observation_id": "auth-bound-observation", "source_reference": "auth-bob"}
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=protected.app), base_url="http://testserver") as client:
            checked(await client.post(f"/components/{component_id}/evidence", headers=authorization(protected),
                                      json={"kind": "observation", "payload": observation}))
            history = checked(await client.get(f"/components/{component_id}/history", headers=authorization(protected)))
            assert history["events"][-1]["payload"]["source_reference"] == "auth-alice"
            assert observation["source_reference"] == "auth-bob"

    asyncio.run(workflow())


@pytest.mark.parametrize("operation", ["verification", "approval", "cancellation", "completion"])
def test_sensitive_http_bodies_reject_operator_identity_spoofing(protected: ProtectedWorkflow, operation: str) -> None:
    async def workflow() -> None:
        route, payload = denied_request(protected, operation)
        payload = deepcopy(payload)
        if operation == "verification":
            payload["verification"]["operator_id"] = "forged-operator"
        else:
            payload["operator_id"] = "forged-operator"
        before = database_state(protected)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=protected.app), base_url="http://testserver") as client:
            checked(await client.post(route, json=payload, headers=authorization(protected)), 422)
        assert database_state(protected) == before

    asyncio.run(workflow())


async def successful_command_and_actor_bound_retry(
    client: httpx.AsyncClient, protected: ProtectedWorkflow, route: str, command: dict,
    actor: str, other_actor: str,
) -> dict:
    result = checked(await client.post(route, json=command, headers=authorization(protected, actor)))
    before = database_state(protected)
    assert checked(await client.post(route, json=command, headers=authorization(protected, actor))) == result
    checked(await client.post(route, json=command, headers=authorization(protected, other_actor)), 409)
    assert database_state(protected) == before
    return result


def test_manual_workflow_binds_verification_planning_approval_cancellation_and_completion_actors(
    protected: ProtectedWorkflow,
) -> None:
    async def workflow() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=protected.app), base_url="http://testserver") as client:
            await verify_all(client, protected, "auth-alice")
            proposed = checked(await client.post("/plans", json={"scenario": protected.fixture["scenario"]},
                                                 headers=authorization(protected, "auth-service")), 201)
            plan_id = proposed["plan"]["plan_id"]
            approved = await successful_command_and_actor_bound_retry(
                client, protected, f"/plans/{plan_id}/approve", operator_command(proposed["version"], "auth-approval-bob"),
                "auth-bob", "auth-alice",
            )
            cancelled = await successful_command_and_actor_bound_retry(
                client, protected, f"/plans/{plan_id}/cancel", operator_command(approved["version"], "auth-cancellation-bob"),
                "auth-bob", "auth-alice",
            )
            assert cancelled["state"] == "cancelled"
            audit = checked(await client.get(f"/plans/{plan_id}/audit", headers=authorization(protected)))
            assert [(event["kind"], event["operator_id"]) for event in audit] == [
                ("proposed", "auth-service"), ("approved", "auth-bob"), ("cancelled", "auth-bob"),
            ]

            second = checked(await client.post("/plans", json={"scenario": protected.fixture["scenario"]},
                                               headers=authorization(protected, "auth-alice")), 201)
            second_id = second["plan"]["plan_id"]
            current = checked(await client.post(f"/plans/{second_id}/approve", headers=authorization(protected),
                                                json=operator_command(second["version"], "auth-approval-alice")))
            for index, action in enumerate(second["plan"]["selected_actions"], start=1):
                current = await successful_command_and_actor_bound_retry(
                    client, protected, f"/plans/{second_id}/actions/{action['action_id']}/complete",
                    completion_command(current, action, index), "auth-bob", "auth-alice",
                )
            assert current["state"] == "completed"
            inventory = checked(await client.get("/inventory", headers=authorization(protected)))
            assert len(inventory["completed_kits"]) == 2
            assert {kit["operator_id"] for kit in inventory["completed_kits"]} == {"auth-bob"}
            assert {entry["availability"] for entry in inventory["items"]} == {"consumed"}
            audit = checked(await client.get(f"/plans/{second_id}/audit", headers=authorization(protected)))
            assert [(event["kind"], event["operator_id"]) for event in audit] == [
                ("proposed", "auth-alice"), ("approved", "auth-alice"),
                ("action_completed", "auth-bob"), ("action_completed", "auth-bob"),
            ]

    asyncio.run(workflow())


@pytest.mark.parametrize("revocation", ["credential_removed", "approval_role_removed"])
def test_missing_or_revoked_authorization_cannot_replay_a_previously_successful_command(
    protected: ProtectedWorkflow, revocation: str,
) -> None:
    async def workflow() -> None:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=protected.app), base_url="http://testserver") as client:
            await verify_all(client, protected)
            proposed = checked(await client.post("/plans", headers=authorization(protected),
                                                 json={"scenario": protected.fixture["scenario"]}), 201)
            route = f"/plans/{proposed['plan']['plan_id']}/approve"
            command = operator_command(proposed["version"], "auth-revocation-retry")
            checked(await client.post(route, json=command, headers=authorization(protected, "auth-bob")))
            before = database_state(protected)
            checked(await client.post(route, json=command), 401)

            config = protected.auth.model_dump(mode="json")
            if revocation == "credential_removed":
                config["operators"] = [record for record in config["operators"] if record["actor"]["actor_id"] != "auth-bob"]
                expected_status = 401
            else:
                next(record for record in config["operators"] if record["actor"]["actor_id"] == "auth-bob")["actor"]["roles"] = ["viewer"]
                expected_status = 403
            # Configuration reload/restart is the supported revocation boundary.
            revoked_app = create_app(protected.store, auth=AuthConfig.model_validate(config))
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=revoked_app), base_url="http://testserver") as revoked_client:
                checked(await revoked_client.post(route, json=command, headers=authorization(protected, "auth-bob")), expected_status)
            assert database_state(protected) == before

    asyncio.run(workflow())


@pytest.mark.parametrize("missing_configuration", ["auth", "inventory"])
def test_partially_configured_app_fails_closed_while_health_remains_public(
    protected: ProtectedWorkflow, missing_configuration: str,
) -> None:
    app = create_app(protected.store) if missing_configuration == "auth" else create_app(auth=protected.auth)

    async def workflow() -> None:
        before = database_state(protected)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
            assert checked(await client.get("/health")) == {"status": "ok"}
            checked(await client.get("/inventory", headers=authorization(protected)), 503)
        assert database_state(protected) == before

    asyncio.run(workflow())


@pytest.mark.parametrize("invalid_case", [
    "duplicate_actor", "duplicate_digest", "duplicate_role", "unknown_role",
    "service_reviewer", "service_approver", "service_executor", "invalid_digest", "plaintext_token",
])
def test_invalid_auth_configuration_is_rejected_before_database_creation_without_secret_details(
    protected: ProtectedWorkflow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, invalid_case: str,
) -> None:
    config = protected.auth.model_dump(mode="json")
    operators = config["operators"]
    if invalid_case == "duplicate_actor":
        operators[1]["actor"]["actor_id"] = operators[0]["actor"]["actor_id"]
    elif invalid_case == "duplicate_digest":
        operators[1]["token_sha256"] = operators[0]["token_sha256"]
    elif invalid_case == "duplicate_role":
        operators[0]["actor"]["roles"] = ["viewer", "viewer"]
    elif invalid_case == "unknown_role":
        operators[0]["actor"]["roles"] = ["administrator"]
    elif invalid_case.startswith("service_"):
        operators[3]["actor"]["roles"] = [invalid_case.removeprefix("service_")]
    elif invalid_case == "invalid_digest":
        operators[0]["token_sha256"] = "invalid-digest"
    else:
        operators[0]["token"] = protected.tokens["auth-alice"]
    auth_file = tmp_path / "invalid-auth.json"
    auth_file.write_text(json.dumps(config), encoding="utf-8")
    database_path = tmp_path / "must-not-be-created" / "workflow.sqlite3"
    monkeypatch.setenv("REKIT_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("REKIT_CATALOG_PATH", str(FIXTURES / "synthetic_catalog.json"))
    monkeypatch.setenv("REKIT_DISPOSITION_POLICY_PATH", str(FIXTURES / "synthetic_disposition_policy.json"))
    monkeypatch.setenv("REKIT_AUTH_CONFIG_PATH", str(auth_file))
    with pytest.raises(RuntimeError) as failure:
        create_configured_app()
    assert not database_path.parent.exists()
    assert protected.tokens["auth-alice"] not in str(failure.value)
    assert operators[0]["token_sha256"] not in str(failure.value)
