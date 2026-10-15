"""Exercise the synthetic canonical case through real, offline ASGI HTTP.

The temporary authenticated actor represents scripted workflow automation, not
independent human review. No inference provider is constructed and no external
HTTP transport is used. Optional output retains only nonsecret review evidence.
"""

import argparse
import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
import secrets
from tempfile import TemporaryDirectory

import httpx

from canonical_case import CASE_PATH, ROOT, compare_plan, load_case, source_images
from rekit.auth import Actor, ActorKind, AuthConfig, OperatorCredential, Role, token_digest
from rekit.catalog.models import Catalog
from rekit.evidence.assets import ImageAssetStore
from rekit.evidence.store import EvidenceStore
from rekit.inventory.store import InventoryStore
from rekit.main import create_app
from rekit.recovery.models import DispositionPolicy, RecoveryPlan


def _checked(response: httpx.Response, expected: int = 200) -> dict | list:
    if response.status_code != expected:
        raise AssertionError(f"Canonical API expected HTTP {expected}, received {response.status_code}: {response.text}")
    return response.json()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


async def exercise_case(client: httpx.AsyncClient, fixture: dict) -> dict:
    """Run existing authenticated APIs against an empty, disposable application."""
    originals = source_images()
    sources = {(image["physical_component_id"], image["view"]): image for image in originals}
    subject = fixture["canonical"]["correction_component_id"]
    receipts = []
    histories_before_correction = {}
    initial_subject = None
    _checked(await client.post("/batches", json=fixture["batch"]), 201)
    for returned in fixture["returns"]:
        _checked(await client.post("/returns", json=returned), 201)

    async def upload(component_id: str, view: int) -> dict:
        source = sources[(component_id, view)]
        receipt = _checked(await client.post(
            f"/components/{component_id}/images", params={"return_id": source["return_id"]},
            content=source["bytes"], headers={"Content-Type": "image/png"},
        ), 201)
        asset = receipt["asset"]
        _require(not receipt["duplicate"] and asset["sha256"] == source["sha256"], "Original upload lost its source hash")
        _require(asset["physical_component_id"] == component_id and asset["return_id"] == source["return_id"], "Original source association changed")
        response = await client.get(f"/assets/{asset['asset_id']}/content")
        _require(response.status_code == 200 and response.content == source["bytes"], "Fetched original image differs from its input bytes")
        receipts.append({"source": {key: value for key, value in source.items() if key != "bytes"}, **receipt})
        return receipt

    for record in fixture["components"]:
        component_id = record["component"]["physical_component_id"]
        _checked(await client.post("/components", json=record["component"]), 201)
        for view in (1, 2):
            await upload(component_id, view)
        before = _checked(await client.get(f"/components/{component_id}/history"))
        _require(before["current"]["verification"] is None, "Image upload automatically verified inventory")
        decision = _checked(await client.get(f"/components/{component_id}/compatibility", params={"configuration_id": "standard-kit"}))
        _require(not decision["compatible"], "Unverified original image authorized compatibility")
        verification = {key: value for key, value in record["verification"].items() if key != "operator_id"}
        verification.update(
            verification_id=f"canonical-initial-{component_id}", verified_at=datetime.now(UTC).isoformat(),
            evidence_observation_ids=[event["event_id"] for event in before["events"] if event["kind"] == "observation"],
            reason="Scripted synthetic human-role assertion for demonstration; no inference, independent review, functionality or safety claim.",
        )
        if component_id == subject:
            verification["identity"] = {"component_type_id": "adapter", "revision": fixture["canonical"]["initial_revision"]}
            verification["reason"] = "Deliberately incorrect scripted B assertion on an ambiguous synthetic view; this is not model output or independent review."
        _checked(await client.post(f"/components/{component_id}/verification", json={"verification": verification, "expected_version": before["current"]["version"]}))
        histories_before_correction[component_id] = _checked(await client.get(f"/components/{component_id}/history"))
        if component_id == subject:
            initial_subject = histories_before_correction[component_id]

    incompatible = _checked(await client.get(f"/components/{subject}/compatibility", params={"configuration_id": "standard-kit"}))
    _require(not incompatible["compatible"] and incompatible["reasons"], "Revision B conflict was not demonstrated")
    rejected_plan = _checked(await client.post("/plans", json={"scenario": fixture["scenario"]}), 201)
    _require(any(subject in rejection["subject"] for rejection in rejected_plan["plan"]["rejections"]), "Planner did not report the revision conflict")
    _require(all(subject not in action["component_ids"] for action in rejected_plan["plan"]["selected_actions"] if action["kind"] == "rebuild"), "Conflicting revision entered a rebuild")

    additional_view = await upload(subject, 3)
    before_correction = _checked(await client.get(f"/components/{subject}/history"))
    _require(before_correction["events"][:len(initial_subject["events"])] == initial_subject["events"], "Additional view rewrote prior evidence")
    _require(before_correction["current"]["state"] != "verified", "New evidence did not trigger re-review")
    correction = {
        "verification_id": "canonical-corrected-adapter-002", "physical_component_id": subject,
        "identity": {"component_type_id": "adapter", "revision": "A"},
        "verified_at": datetime.now(UTC).isoformat(),
        "evidence_observation_ids": [event["event_id"] for event in before_correction["events"] if event["kind"] == "observation"],
        "visible_condition": "acceptable", "supersedes_verification_id": initial_subject["current"]["verification"]["verification_id"],
        "reason": "Scripted synthetic human correction B to A using the additional original close-up and both intake views; original assertions retained. No independent review or functional/safety claim.",
    }
    stale = await client.post(f"/components/{subject}/verification", json={"verification": correction, "expected_version": initial_subject["current"]["version"]})
    _checked(stale, 409)
    _require(_checked(await client.get(f"/components/{subject}/history")) == before_correction, "Stale correction changed history")
    _checked(await client.post(f"/components/{subject}/verification", json={"verification": correction, "expected_version": before_correction["current"]["version"]}))
    corrected = _checked(await client.get(f"/components/{subject}/history"))
    _require(corrected["events"][:-1] == before_correction["events"], "Correction rewrote historical evidence")
    _require(corrected["current"]["verification"]["supersedes_verification_id"] == initial_subject["current"]["verification"]["verification_id"], "Correction lost the previous assertion")
    compatible = _checked(await client.get(f"/components/{subject}/compatibility", params={"configuration_id": "standard-kit"}))
    _require(compatible["compatible"], "Corrected fixture did not satisfy the existing approved policy")
    stale_plan = await client.post(f"/plans/{rejected_plan['plan']['plan_id']}/approve", json={
        "operation_id": "canonical-stale-plan-approval", "expected_version": rejected_plan["version"],
        "reason": "Negative probe: planning evidence changed after the correction.",
    })
    _checked(stale_plan, 409)

    baseline = _checked(await client.post("/plans", json={"scenario": fixture["scenario"]}), 201)
    changed_scenario = deepcopy(fixture["scenario"])
    changed_scenario["labor_cost_per_minute_cents"] = fixture["canonical"]["controlled_labor_cost_per_minute_cents"]
    changed = _checked(await client.post("/plans", json={"scenario": changed_scenario}), 201)
    competing = _checked(await client.post("/plans", json={"scenario": fixture["scenario"]}), 201)
    base_plan = RecoveryPlan.model_validate(baseline["plan"])
    changed_plan = RecoveryPlan.model_validate(changed["plan"])
    expected_problem = base_plan.problem.model_dump(mode="json")
    expected_problem["scenario"]["labor_cost_per_minute_cents"] = changed_scenario["labor_cost_per_minute_cents"]
    _require(expected_problem == changed_plan.problem.model_dump(mode="json"), "Sensitivity changed more than the single approved labor assumption")
    _require(competing["plan"]["input_hash"] == baseline["plan"]["input_hash"], "Competing plan used different inputs")
    comparisons = {"baseline": compare_plan(base_plan), "changed_labor": compare_plan(changed_plan)}
    expectations = fixture["canonical"]["expected"]
    for name, comparison in comparisons.items():
        _require(comparison["solver_status"] == "OPTIMAL", "Canonical solver did not prove optimality")
        for alternative, expected in expectations[name].items():
            _require(comparison["alternatives"][alternative]["modeled_value_cents"] == expected, f"Canonical expected value changed: {name}/{alternative}")
        _require(comparison["selected"]["action_counts"] == expectations[f"{name}_action_counts"], "Controlled labor assumption did not produce the expected plan choice")

    stored = _checked(await client.post(f"/plans/{base_plan.plan_id}/approve", json={
        "operation_id": "canonical-approved", "expected_version": baseline["version"],
        "reason": "Scripted synthetic human-role approval of the baseline plan only.",
    }))
    reserved = _checked(await client.get("/inventory"))
    _require(not reserved["completed_kits"] and len(reserved["items"]) == 4 and all(entry["availability"] == "reserved" for entry in reserved["items"]), "Approval must reserve all four components without creating completed kits")
    duplicate = await client.post(f"/plans/{competing['plan']['plan_id']}/approve", json={
        "operation_id": "canonical-competing-approval", "expected_version": competing["version"],
        "reason": "Negative probe: attempt to allocate already reserved physical components.",
    })
    _checked(duplicate, 409)
    _require(_checked(await client.get("/inventory")) == reserved, "Rejected competing approval changed inventory")
    _require(_checked(await client.get(f"/plans/{changed_plan.plan_id}"))["state"] == "proposed", "Sensitivity proposal was implicitly executed")

    negative_completion = None
    for index, action in enumerate(base_plan.selected_actions, start=1):
        command = {
            "operation_id": f"canonical-complete-{index}", "expected_version": stored["version"],
            "reason": "Scripted synthetic explicit confirmation of reserved identities; not proof of a real physical rebuild or functional/safety inspection.",
            "confirmed": True, "component_ids": list(action.component_ids),
            "evidence_references": [f"synthetic://canonical-evidence-to-kit-v1/completion/{index}"],
            "completed_kit_id": f"canonical-completed-kit-{index}",
        }
        route = f"/plans/{base_plan.plan_id}/actions/{action.action_id}/complete"
        if index == 1:
            negative_completion = await client.post(route, json=command | {"confirmed": False})
            _checked(negative_completion, 422)
            _require(_checked(await client.get("/inventory")) == reserved, "Unconfirmed completion changed inventory")
        stored = _checked(await client.post(route, json=command))
        _require(_checked(await client.post(route, json=command)) == stored, "Exact completion retry was not idempotent")

    final = _checked(await client.get("/inventory"))
    audit = _checked(await client.get(f"/plans/{base_plan.plan_id}/audit"))
    histories = {record["component"]["physical_component_id"]: _checked(await client.get(f"/components/{record['component']['physical_component_id']}/history")) for record in fixture["components"]}
    consumed = [component_id for kit in final["completed_kits"] for component_id in kit["component_ids"]]
    expected_ids = set(histories)
    _require(len(consumed) == len(set(consumed)) == 4 and set(consumed) == expected_ids, "Completed-kit lineage reused or lost a physical component")
    _require(len(final["completed_kits"]) == 2 and stored["state"] == "completed" and all(entry["availability"] == "consumed" for entry in final["items"]), "Canonical final inventory did not complete two kits")
    _require([event["kind"] for event in audit] == ["proposed", "approved", "action_completed", "action_completed"], "Unexpected canonical execution audit sequence")
    for receipt in receipts:
        response = await client.get(f"/assets/{receipt['asset']['asset_id']}/content")
        _require(response.status_code == 200 and sha256(response.content).hexdigest() == receipt["source"]["sha256"], "Final original asset is missing or changed")
    lineage = []
    for kit in final["completed_kits"]:
        lineage.append({**kit, "components": [{
            "physical_component_id": component_id,
            "source_return_id": histories[component_id]["component"]["source_return_id"],
            "evidence_version": histories[component_id]["current"]["version"],
            "verification": histories[component_id]["current"]["verification"],
            "source_images": [receipt["source"] | {"asset_id": receipt["asset"]["asset_id"], "observation_id": receipt["observation"]["observation_id"]}
                              for receipt in receipts if receipt["source"]["physical_component_id"] == component_id],
        } for component_id in kit["component_ids"]]})
    return {
        "fixture_id": fixture["fixture_id"], "synthetic": True, "scenario_estimate": True,
        "inference_enabled": False, "amd_generation_requests": 0,
        "description": fixture["description"], "completed_at": datetime.now(UTC).isoformat(),
        "fixture_sha256": sha256(CASE_PATH.read_bytes()).hexdigest(),
        "original_fixture_sha256": sha256((ROOT / fixture["canonical"]["base_fixture"]).read_bytes()).hexdigest(),
        "image_provenance": receipts, "original_image_count": len(receipts),
        "correction": {"physical_component_id": subject, "before": initial_subject,
                       "before_correction": before_correction, "after": corrected,
                       "additional_original_asset_id": additional_view["asset"]["asset_id"],
                       "prior_compatibility": incompatible, "corrected_compatibility": compatible},
        "economic_comparison": comparisons,
        "controlled_change": {"field": "scenario.labor_cost_per_minute_cents", "before": 25, "after": 200,
                              "all_other_problem_fields_identical": True, "executed": False},
        "baseline_plan": baseline, "changed_labor_plan": changed,
        "negative_checks": {"stale_correction_http": stale.status_code, "stale_plan_approval_http": stale_plan.status_code,
                            "double_allocation_http": duplicate.status_code, "unconfirmed_completion_http": negative_completion.status_code,
                            "prior_evidence_preserved": True, "rejected_operations_left_inventory_unchanged": True},
        "reserved_inventory": reserved, "final_inventory": final, "final_plan_state": stored["state"],
        "completed_kit_lineage": lineage, "evidence_histories": histories, "plan_audit": audit,
        "limitations": ["Synthetic scripted workflow, not real return recovery or independent human validation.",
                        "Completion references are explicit fixture assertions, not photographs of a physical rebuild.",
                        "No AMD or NVIDIA inference, and no claims about hidden functional or safety properties.",
                        "Invented economics, not realized revenue, business savings or measured labor."],
    }


async def run_case() -> dict:
    """Create ephemeral stores and credentials, then remove all mutable state."""
    fixture = load_case()
    fixtures = ROOT / "tests" / "fixtures"
    catalog = Catalog.model_validate_json((fixtures / fixture["catalog_file"]).read_text(encoding="utf-8"))
    policy = DispositionPolicy.model_validate_json((fixtures / fixture["disposition_policy_file"]).read_text(encoding="utf-8"))
    with TemporaryDirectory(prefix="rekit-canonical-") as temporary:
        evidence = EvidenceStore(Path(temporary) / "workflow.sqlite3", catalog)
        inventory = InventoryStore(evidence, policy)
        assets = ImageAssetStore(evidence, Path(temporary) / "original-images")
        token = secrets.token_urlsafe(32)
        auth = AuthConfig(operators=(OperatorCredential(
            actor=Actor(actor_id="canonical-scripted-human", kind=ActorKind.HUMAN, roles=tuple(Role)),
            token_sha256=token_digest(token),
        ),))
        app = create_app(inventory, auth=auth, assets=assets)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://canonical.invalid",
                                     headers={"Authorization": f"Bearer {token}"}) as client:
            result = await exercise_case(client, fixture)
    result["temporary_state_removed"] = not Path(temporary).exists()
    result["credentials_persisted"] = False
    return result


def write_review_artifacts(output: Path, report: dict) -> None:
    """Exclusively create a nonsecret receipt and original-source review package."""
    # Refuse reuse so historical receipts and source files cannot be overwritten.
    output.mkdir(parents=True, exist_ok=False)
    images = output / "original-images"
    images.mkdir()
    expected = {entry["source"]["filename"]: entry["source"]["sha256"] for entry in report["image_provenance"]}
    for source in source_images():
        if expected.get(source["filename"]) != source["sha256"]:
            raise AssertionError("Review export does not match the actual uploaded original")
        with (images / source["filename"]).open("xb") as stream:
            stream.write(source["bytes"])
    with (output / "receipt.json").open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New local directory for nonsecret receipt and nine original synthetic PNGs; never overwrites")
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        parser.error("Output directory already exists; preserve the prior receipt and choose a new directory")
    report = asyncio.run(run_case())
    if args.output is not None:
        write_review_artifacts(args.output, report)
        print(json.dumps({"fixture_id": report["fixture_id"], "status": "passed", "output": str(args.output),
                          "original_images": report["original_image_count"], "final_plan_state": report["final_plan_state"],
                          "modeled_value_cents": report["economic_comparison"]["baseline"]["selected"]["modeled_value_cents"],
                          "temporary_state_removed": report["temporary_state_removed"],
                          "inference_enabled": False}, indent=2))
    else:
        print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
