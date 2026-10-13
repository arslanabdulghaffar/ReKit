"""Transactional inference provenance using controlled CPU data, never model inference."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace

from PIL import Image
from pydantic import ValidationError
import pytest

from rekit.auth import Actor, ActorKind, Role
from rekit.catalog.models import Catalog
from rekit.evidence.assets import AssetMissingError, ImageAssetStore
from rekit.evidence.models import AssertionSource, OperatorVerification, PhysicalComponent, ReturnBatch, ReturnRecord, VerificationState
from rekit.evidence.store import ConflictError, EvidenceStore, NotFoundError
from rekit.inference.models import InferenceConfiguration, InspectionOutput, InspectionRequest
from rekit.inference.store import InferenceStore
from rekit.inventory.execution import ApprovalCommand, CompletionCommand
from rekit.inventory.models import InventoryEligibility
from rekit.inventory.store import InventoryStore
from rekit.recovery.models import DispositionPolicy, EconomicScenario


FIXTURES = Path(__file__).parents[1] / "fixtures"
ACTOR = Actor(actor_id="inference-reviewer", kind=ActorKind.HUMAN, roles=tuple(Role))


def image_bytes(color) -> bytes:
    with Image.new("RGB", (24, 18), color) as image, BytesIO() as output:
        image.save(output, format="PNG")
        return output.getvalue()


@pytest.fixture
def workflow(tmp_path):
    fixture = json.loads((FIXTURES / "synthetic_recovery.json").read_text(encoding="utf-8"))
    catalog = Catalog.model_validate_json((FIXTURES / fixture["catalog_file"]).read_text(encoding="utf-8"))
    policy = DispositionPolicy.model_validate_json((FIXTURES / fixture["disposition_policy_file"]).read_text(encoding="utf-8"))
    evidence = EvidenceStore(tmp_path / "inference.sqlite3", catalog)
    assets = ImageAssetStore(evidence, tmp_path / "images")
    inventory = InventoryStore(evidence, policy)
    evidence.register_batch(ReturnBatch.model_validate(fixture["batch"]))
    for returned in fixture["returns"]:
        evidence.register_return(ReturnRecord.model_validate(returned))
    uploads = {}
    for index, record in enumerate(fixture["components"]):
        component = PhysicalComponent.model_validate(record["component"])
        evidence.register_component(component)
        uploads[component.physical_component_id] = assets.upload(
            component.physical_component_id, component.source_return_id,
            image_bytes((index * 40, 80, 120)), "image/png", ACTOR.actor_id,
        )
    component_id = fixture["components"][0]["component"]["physical_component_id"]
    configuration = InferenceConfiguration(
        provider="controlled-test-double", model_repository="test/controlled-vision",
        model_revision="a" * 40, processor_revision="a" * 40,
        runtime={"source": "CPU contract test; no model execution"}, device="cpu-test-double",
        prompt_version="inspection-test-v1", preprocessing={"max_side": 768},
        generation={"do_sample": False, "max_new_tokens": 128},
    )
    return SimpleNamespace(
        fixture=fixture, evidence=evidence, assets=assets, inventory=inventory,
        store=InferenceStore(evidence, assets), uploads=uploads, component_id=component_id,
        configuration=configuration,
    )


def request(workflow, request_id="inspection-request", **changes):
    values = {
        "request_id": request_id, "physical_component_id": workflow.component_id,
        "asset_ids": (workflow.uploads[workflow.component_id].asset.asset_id,),
        "expected_version": workflow.evidence.current(workflow.component_id).version,
    }
    values.update(changes)
    return InspectionRequest.model_validate(values)


def begin(workflow, command=None):
    return workflow.store.begin(command or request(workflow), ACTOR, workflow.configuration)


def verify_component(workflow, component_id=None, verification_id=None):
    component_id = component_id or workflow.component_id
    fixture = next(record for record in workflow.fixture["components"]
                   if record["component"]["physical_component_id"] == component_id)
    current = workflow.evidence.current(component_id)
    values = fixture["verification"] | {
        "operator_id": ACTOR.actor_id,
        "verified_at": datetime.now(UTC),
        "evidence_observation_ids": (workflow.uploads[component_id].observation.observation_id,),
        "supersedes_verification_id": current.verification.verification_id if current.verification else None,
    }
    if verification_id is not None:
        values["verification_id"] = verification_id
    verification = OperatorVerification.model_validate(values)
    return workflow.evidence.verify(verification, expected_version=current.version)


def approve_inventory(workflow):
    for component_id in workflow.uploads:
        if workflow.evidence.current(component_id).state != VerificationState.VERIFIED:
            verify_component(workflow, component_id)
    proposal = workflow.inventory.request_plan(EconomicScenario.model_validate(workflow.fixture["scenario"]),
                                               requested_by=ACTOR.actor_id)
    approved = workflow.inventory.approve(proposal.plan.plan_id, ApprovalCommand(
        operation_id="inference-test-approval", operator_id=ACTOR.actor_id,
        expected_version=proposal.version, reason="Controlled test plan reviewed by a human.",
    ))
    assert len(approved.plan.selected_actions) == 2
    return approved


def output(**changes):
    values = {
        "observations": [{"kind": "marking", "text": "SYNTHETIC BODY A", "image_indices": [1]}],
        "candidates": [{"component_type_id": "body", "revision": "A", "revision_marking": "A",
                        "reason": "Controlled candidate for a software contract test.", "image_indices": [1]}],
        "uncertainties": ["Controlled test data; this is not a real model prediction."],
        "additional_views": [{"view": "Underside close-up", "reason": "The underside is not visible.", "image_indices": [1]}],
    }
    values.update(changes)
    return InspectionOutput.model_validate(values)


def finish(workflow, run, inspected=None, **changes):
    arguments = {"status": "succeeded", "output": inspected or output(),
                 "raw_output": "Controlled CPU test output; not real model inference.",
                 "metrics": {"test_double": True}}
    arguments.update(changes)
    return workflow.store.finish(run.start.run_id, **arguments)


def complete_component_action(workflow, approved):
    action = next(action for action in approved.plan.selected_actions if workflow.component_id in action.component_ids)
    return workflow.inventory.complete_action(approved.plan.plan_id, action.action_id, CompletionCommand(
        operation_id="inference-test-completion", operator_id=ACTOR.actor_id,
        expected_version=approved.version, reason="Controlled human completion confirmation.",
        confirmed=True, component_ids=action.component_ids, completed_kit_id="inference-test-kit",
        evidence_references=tuple(workflow.uploads[cid].observation.evidence_reference for cid in action.component_ids),
    ))


def test_success_records_exact_multi_view_provenance_and_requires_fresh_human_review(workflow):
    original_upload = workflow.uploads[workflow.component_id]
    component = workflow.evidence.get_component(workflow.component_id)
    second = workflow.assets.upload(component.physical_component_id, component.source_return_id,
                                     image_bytes("green"), "image/png", ACTOR.actor_id)
    verify_component(workflow)
    before = workflow.evidence.history(workflow.component_id)
    identities = tuple(item.component.physical_component_id for item in workflow.evidence.inventory_items())
    command = request(workflow, asset_ids=(original_upload.asset.asset_id, second.asset.asset_id))
    run, created = begin(workflow, command)
    assert created and run.outcome is None
    assert run.start.request_id == command.request_id
    assert run.start.actor_id == ACTOR.actor_id
    assert run.start.physical_component_id == workflow.component_id
    assert run.start.source_return_id == component.source_return_id
    assert run.start.evidence_version == before.current.version
    assert run.start.configuration == workflow.configuration
    assert run.start.started_at.tzinfo is not None
    for actual, uploaded in zip(run.start.inputs, (original_upload, second), strict=True):
        assert (actual.asset_id, actual.sha256, actual.observation_id) == (
            uploaded.asset.asset_id, uploaded.asset.sha256, uploaded.observation.observation_id,
        )
    assert workflow.evidence.history(workflow.component_id) == before
    inspected = output()
    completed = finish(workflow, run, inspected)
    assert completed.start == run.start
    assert completed.outcome.status == "succeeded"
    assert completed.outcome.output == inspected
    assert completed.outcome.stale is False
    after = workflow.evidence.history(workflow.component_id)
    appended = after.events[len(before.events):]
    assert after.events[:len(before.events)] == before.events
    assert tuple(event.event_id for event in appended) == completed.outcome.applied_event_ids
    model_observations = [event.payload for event in appended if event.kind == "observation"]
    assert len(model_observations) == 2
    assert {item.evidence_reference for item in model_observations} == {f"asset:{asset}" for asset in command.asset_ids}
    assert all(item.source == AssertionSource.MODEL and item.source_reference == run.start.run_id for item in model_observations)
    assert all(item.physical_component_id == workflow.component_id for item in model_observations)
    assert after.current.state == VerificationState.REVIEW_REQUIRED
    assert after.current.verification == before.current.verification
    assert after.current.version == completed.outcome.evidence_version_after > before.current.version
    items = workflow.evidence.inventory_items()
    assert tuple(item.component.physical_component_id for item in items) == identities
    assert next(item for item in items if item.component.physical_component_id == workflow.component_id).eligibility == InventoryEligibility.HELD
    assert InferenceStore(workflow.evidence, workflow.assets).get(run.start.run_id) == completed


@pytest.mark.parametrize("kind", ["unknown", "missing_revision", "conflicting"])
def test_unknown_partial_and_conflicting_candidates_remain_unverified(workflow, kind):
    candidates = []
    if kind == "missing_revision":
        candidates = [{"component_type_id": "body", "reason": "Revision is not visible.", "image_indices": [1]}]
    elif kind == "conflicting":
        candidates = [
            {"component_type_id": "body", "revision": revision, "revision_marking": revision,
             "reason": "Controlled conflicting candidate.", "image_indices": [1]}
            for revision in ("A", "B")
        ]
    run, _ = begin(workflow)
    completed = finish(workflow, run, output(candidates=candidates, uncertainties=["Identity or revision remains ambiguous."]))
    history = workflow.evidence.history(workflow.component_id)
    proposals = [event.payload for event in history.events if event.kind == "proposal"]
    if kind in ("unknown", "missing_revision"):
        assert len(proposals) == 1 and proposals[0].proposed_identity is None
        assert proposals[0].uncertainty_reason
    else:
        assert {proposal.proposed_identity.revision for proposal in proposals} == {"A", "B"}
    assert completed.outcome.output.uncertainties
    assert history.current.state != VerificationState.VERIFIED
    assert history.current.verification is None
    assert any(event.kind == "uncertainty" and event.payload.source_reference == run.start.run_id for event in history.events)


@pytest.mark.parametrize("change", ["new_image", "human_verification"])
def test_late_result_keeps_output_but_does_not_override_new_evidence(workflow, change):
    run, _ = begin(workflow)
    if change == "new_image":
        component = workflow.evidence.get_component(workflow.component_id)
        workflow.assets.upload(component.physical_component_id, component.source_return_id,
                               image_bytes("green"), "image/png", ACTOR.actor_id)
    else:
        verify_component(workflow)
    before = workflow.evidence.history(workflow.component_id)
    completed = finish(workflow, run)
    assert completed.outcome.status == "succeeded"
    assert completed.outcome.output == output()
    assert completed.outcome.stale is True
    assert completed.outcome.stale_reason
    assert completed.outcome.applied_event_ids == ()
    assert completed.outcome.evidence_version_after == before.current.version
    assert workflow.evidence.history(workflow.component_id) == before


@pytest.mark.parametrize("status", ["failed", "unavailable", "timed_out", "invalid_output"])
def test_failure_provenance_is_durable_without_evidence_mutation(workflow, status):
    run, _ = begin(workflow)
    before = workflow.evidence.history(workflow.component_id)
    completed = workflow.store.finish(run.start.run_id, status=status,
                                      raw_output="Controlled malformed response" if status == "invalid_output" else None,
                                      failure_reason="Controlled explicit execution failure.", metrics={"test_double": True})
    assert completed.outcome.status == status
    assert completed.outcome.failure_reason == "Controlled explicit execution failure."
    assert completed.outcome.output is None
    assert completed.outcome.applied_event_ids == ()
    assert completed.outcome.metrics == {"test_double": True}
    assert workflow.store.get(run.start.run_id) == completed
    assert workflow.evidence.history(workflow.component_id) == before


def test_known_asset_with_missing_bytes_can_retain_failed_run(workflow):
    asset = workflow.uploads[workflow.component_id].asset
    (workflow.assets.root / f"{asset.asset_id}.png").unlink()
    run, created = begin(workflow)
    assert created and run.start.inputs[0].sha256 == asset.sha256
    with pytest.raises(AssetMissingError):
        workflow.assets.read(asset.asset_id)
    before = workflow.evidence.history(workflow.component_id)
    completed = workflow.store.finish(run.start.run_id, status="failed", failure_reason="Source image bytes are missing.")
    assert completed.outcome.status == "failed"
    assert workflow.store.get(run.start.run_id) == completed
    assert workflow.evidence.history(workflow.component_id) == before


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
def test_input_damage_before_finish_prevents_applying_result(workflow, damage):
    run, _ = begin(workflow)
    asset = workflow.uploads[workflow.component_id].asset
    path = workflow.assets.root / f"{asset.asset_id}.png"
    if damage == "missing":
        path.unlink()
    else:
        path.write_bytes(b"controlled corrupted bytes")
    before = workflow.evidence.history(workflow.component_id)
    completed = finish(workflow, run)
    assert completed.outcome.stale and completed.outcome.stale_reason
    assert completed.outcome.applied_event_ids == ()
    assert workflow.evidence.history(workflow.component_id) == before


def test_terminal_replay_survives_later_correction_and_missing_image(workflow):
    command = request(workflow)
    run, _ = begin(workflow, command)
    completed = finish(workflow, run)
    verify_component(workflow)
    asset = workflow.uploads[workflow.component_id].asset
    (workflow.assets.root / f"{asset.asset_id}.png").unlink()
    before = workflow.evidence.history(workflow.component_id)
    assert finish(workflow, run) == completed
    assert begin(workflow, command) == (completed, False)
    with pytest.raises(ConflictError):
        finish(workflow, run, raw_output="Different historical response.")
    assert workflow.evidence.history(workflow.component_id) == before


@pytest.mark.parametrize("consumed", [False, True])
def test_allocated_component_cannot_begin_inspection(workflow, consumed):
    approved = approve_inventory(workflow)
    if consumed:
        complete_component_action(workflow, approved)
    before = workflow.inventory.inventory()
    with pytest.raises(ConflictError):
        begin(workflow)
    assert workflow.store.list_for_component(workflow.component_id) == ()
    assert workflow.inventory.inventory() == before


@pytest.mark.parametrize("consumed", [False, True])
def test_allocation_during_inference_makes_result_stale_without_changing_inventory(workflow, consumed):
    for component_id in workflow.uploads:
        verify_component(workflow, component_id)
    run, _ = begin(workflow)
    approved = approve_inventory(workflow)
    if consumed:
        complete_component_action(workflow, approved)
    before_history = workflow.evidence.history(workflow.component_id)
    before_inventory = workflow.inventory.inventory()
    before_audit = workflow.inventory.audit(approved.plan.plan_id)
    completed = finish(workflow, run)
    assert completed.outcome.stale
    assert completed.outcome.applied_event_ids == ()
    assert completed.outcome.output == output()
    assert workflow.evidence.history(workflow.component_id) == before_history
    assert workflow.inventory.inventory() == before_inventory
    assert workflow.inventory.audit(approved.plan.plan_id) == before_audit


@pytest.mark.parametrize("malformed", ["model_copy", "source_index"])
def test_invalid_output_cannot_partially_append_or_terminalize(workflow, malformed):
    run, _ = begin(workflow)
    before = workflow.evidence.history(workflow.component_id)
    if malformed == "model_copy":
        inspected = output().model_copy(update={"uncertainties": ("x" * 601,)})
    else:
        inspected = output(observations=[{"kind": "marking", "text": "Wrong image reference.", "image_indices": [2]}])
    with pytest.raises(ValueError):
        finish(workflow, run, inspected)
    assert workflow.store.get(run.start.run_id) == run
    assert workflow.evidence.history(workflow.component_id) == before
    assert finish(workflow, run).outcome.status == "succeeded"


def test_result_and_evidence_are_one_transaction_when_append_fails(workflow):
    run, _ = begin(workflow)
    before = workflow.evidence.history(workflow.component_id)
    with workflow.evidence.transaction() as connection:
        connection.execute("CREATE TRIGGER reject_inference_proposal AFTER INSERT ON evidence_events "
                           "WHEN NEW.kind = 'proposal' BEGIN SELECT RAISE(FAIL, 'controlled proposal failure'); END")
    with pytest.raises(ConflictError, match="controlled proposal failure"):
        finish(workflow, run)
    assert workflow.evidence.history(workflow.component_id) == before
    assert workflow.store.get(run.start.run_id) == run
    with workflow.evidence.transaction() as connection:
        connection.execute("DROP TRIGGER reject_inference_proposal")
    assert finish(workflow, run).outcome.status == "succeeded"


@pytest.mark.parametrize("table", ["inference_requests", "inference_outcomes"])
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
def test_stored_inference_provenance_cannot_be_rewritten(workflow, table, operation):
    run, _ = begin(workflow)
    completed = finish(workflow, run)
    sql = f"UPDATE {table} SET payload = payload" if operation == "UPDATE" else f"DELETE FROM {table}"
    with pytest.raises(ConflictError, match="immutable"):
        with workflow.evidence.transaction() as connection:
            connection.execute(sql)
    assert workflow.store.get(run.start.run_id) == completed


def test_duplicate_request_is_actor_payload_bound_and_survives_new_evidence(workflow):
    command = request(workflow)
    original, created = begin(workflow, command)
    assert created is True
    component = workflow.evidence.get_component(workflow.component_id)
    workflow.assets.upload(component.physical_component_id, component.source_return_id,
                           image_bytes("green"), "image/png", ACTOR.actor_id)
    history = workflow.evidence.history(workflow.component_id)
    repeated, created = begin(workflow, command)
    assert repeated == original
    assert created is False
    assert workflow.evidence.history(workflow.component_id) == history
    assert workflow.store.list_for_component(workflow.component_id) == (original,)
    with pytest.raises(ConflictError):
        begin(workflow, request(workflow))
    other_actor = ACTOR.model_copy(update={"actor_id": "other-reviewer"})
    with pytest.raises(ConflictError):
        workflow.store.begin(command, other_actor, workflow.configuration)


def test_concurrent_identical_begin_creates_one_durable_run(workflow):
    command = request(workflow)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: begin(workflow, command), range(2)))
    assert sorted(created for _, created in results) == [False, True]
    assert results[0][0] == results[1][0]
    reloaded = InferenceStore(workflow.evidence, workflow.assets)
    assert reloaded.list_for_component(workflow.component_id) == (results[0][0],)


@pytest.mark.parametrize("actor", [
    Actor(actor_id="viewer", kind=ActorKind.HUMAN, roles=(Role.VIEWER,)),
    Actor(actor_id="service", kind=ActorKind.SERVICE, roles=(Role.VIEWER, Role.INTAKE)),
])
def test_only_authorized_human_reviewer_can_begin(workflow, actor):
    history = workflow.evidence.history(workflow.component_id)
    with pytest.raises(PermissionError):
        workflow.store.begin(request(workflow), actor, workflow.configuration)
    assert workflow.store.list_for_component(workflow.component_id) == ()
    assert workflow.evidence.history(workflow.component_id) == history


def test_unvalidated_actor_and_request_copies_cannot_bypass_boundaries(workflow):
    forged_actor = ACTOR.model_copy(update={"kind": ActorKind.SERVICE})
    with pytest.raises((ValidationError, PermissionError)):
        workflow.store.begin(request(workflow), forged_actor, workflow.configuration)
    command = request(workflow)
    forged_command = command.model_copy(update={"asset_ids": command.asset_ids * 2})
    with pytest.raises(ValidationError):
        begin(workflow, forged_command)
    assert workflow.store.list_for_component(workflow.component_id) == ()


@pytest.mark.parametrize("invalid_asset", ["unknown", "other_component"])
def test_unknown_or_other_component_assets_do_not_start_a_run(workflow, invalid_asset):
    if invalid_asset == "unknown":
        asset_id = "asset-" + "f" * 32
        error = NotFoundError
    else:
        other_id = next(component_id for component_id in workflow.uploads if component_id != workflow.component_id)
        asset_id = workflow.uploads[other_id].asset.asset_id
        error = ConflictError
    with pytest.raises(error):
        begin(workflow, request(workflow, asset_ids=(asset_id,)))
    assert workflow.store.list_for_component(workflow.component_id) == ()


def test_stale_requested_version_does_not_start_a_run(workflow):
    with pytest.raises(ConflictError):
        begin(workflow, request(workflow, expected_version=1))
    assert workflow.store.list_for_component(workflow.component_id) == ()
