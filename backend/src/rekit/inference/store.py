"""Immutable inference requests/outcomes in the existing evidence database."""

from datetime import UTC, datetime
import json
from uuid import uuid4

from pydantic import TypeAdapter

from rekit.auth import Actor, ActorKind, Role
from rekit.catalog.models import ComponentIdentity, Identifier
from rekit.evidence.assets import ImageAssetStore
from rekit.evidence.models import AssertionSource, IdentityProposal, Observation, UncertaintyFlag
from rekit.evidence.store import ConflictError, EvidenceStore, NotFoundError, _canonical
from rekit.inference.models import (
    InferenceConfiguration, InferenceOutcome, InferenceRun, InferenceStart, InputAsset,
    InspectionOutput, InspectionRequest,
)


_IDENTIFIER = TypeAdapter(Identifier)
_SCHEMA = (
    """CREATE TABLE IF NOT EXISTS inference_requests (
        run_id TEXT PRIMARY KEY,
        request_id TEXT NOT NULL UNIQUE,
        physical_component_id TEXT NOT NULL REFERENCES physical_components(physical_component_id),
        actor_id TEXT NOT NULL,
        command_json TEXT NOT NULL,
        payload TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS inference_outcomes (
        run_id TEXT PRIMARY KEY REFERENCES inference_requests(run_id),
        completion_json TEXT NOT NULL,
        payload TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS inference_component_runs ON inference_requests(physical_component_id, run_id)",
)


class InferenceStore:
    """Provider code has no database access; only this boundary appends evidence."""

    def __init__(self, evidence: EvidenceStore, assets: ImageAssetStore):
        if assets.evidence.path != evidence.path:
            raise ValueError("Inference assets and evidence must share the same database")
        self.evidence, self.assets = evidence, assets
        with evidence.transaction() as connection:
            for statement in _SCHEMA:
                connection.execute(statement)
            for table in ("inference_requests", "inference_outcomes"):
                for action in ("UPDATE", "DELETE"):
                    connection.execute(
                        f"CREATE TRIGGER IF NOT EXISTS {table}_no_{action.lower()} BEFORE {action} ON {table} "
                        "BEGIN SELECT RAISE(ABORT, 'Inference provenance is immutable'); END"
                    )

    @staticmethod
    def _authorized(actor: Actor) -> Actor:
        actor = Actor.model_validate(actor.model_dump(mode="json", warnings=False))
        if actor.kind != ActorKind.HUMAN or Role.REVIEWER not in actor.roles:
            raise PermissionError("An authenticated human reviewer must request inspection")
        return actor

    @staticmethod
    def _allocated(connection, component_id: str) -> bool:
        if not connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'component_allocations'"
        ).fetchone():
            return False
        return connection.execute(
            "SELECT 1 FROM component_allocations WHERE physical_component_id = ?", (component_id,)
        ).fetchone() is not None

    @staticmethod
    def _get(connection, run_id: str) -> InferenceRun:
        row = connection.execute("SELECT payload FROM inference_requests WHERE run_id = ?", (run_id,)).fetchone()
        if row is None:
            raise NotFoundError("Unknown inference run")
        outcome = connection.execute("SELECT payload FROM inference_outcomes WHERE run_id = ?", (run_id,)).fetchone()
        return InferenceRun(
            start=InferenceStart.model_validate_json(row["payload"]),
            outcome=InferenceOutcome.model_validate_json(outcome["payload"]) if outcome else None,
        )

    def get(self, run_id: str) -> InferenceRun:
        run_id = _IDENTIFIER.validate_python(run_id)
        with self.evidence._read() as connection:
            return self._get(connection, run_id)

    def list_for_component(self, component_id: str) -> tuple[InferenceRun, ...]:
        component_id = _IDENTIFIER.validate_python(component_id)
        with self.evidence._read() as connection:
            self.evidence._component(connection, component_id)
            return tuple(self._get(connection, row["run_id"]) for row in connection.execute(
                "SELECT run_id FROM inference_requests WHERE physical_component_id = ? ORDER BY rowid DESC LIMIT 50",
                (component_id,),
            ).fetchall())

    def replay(self, command: InspectionRequest, actor: Actor) -> InferenceRun | None:
        """Read an actor-bound retry without admitting work while the worker is busy."""
        command = InspectionRequest.model_validate(command.model_dump(mode="json", warnings=False))
        actor = self._authorized(actor)
        with self.evidence._read() as connection:
            row = connection.execute(
                "SELECT run_id, actor_id, command_json FROM inference_requests WHERE request_id = ?",
                (command.request_id,),
            ).fetchone()
            if row is None:
                return None
            if row["actor_id"] != actor.actor_id or row["command_json"] != _canonical(command):
                raise ConflictError("Inspection request ID belongs to a different actor or request")
            return self._get(connection, row["run_id"])

    def begin(self, command: InspectionRequest, actor: Actor,
              configuration: InferenceConfiguration) -> tuple[InferenceRun, bool]:
        command = InspectionRequest.model_validate(command.model_dump(mode="json", warnings=False))
        actor = self._authorized(actor)
        configuration = InferenceConfiguration.model_validate(configuration.model_dump(mode="json", warnings=False))
        encoded = _canonical(command)
        with self.evidence.transaction() as connection:
            existing = connection.execute(
                "SELECT run_id, actor_id, command_json FROM inference_requests WHERE request_id = ?", (command.request_id,)
            ).fetchone()
            if existing:
                if existing["actor_id"] != actor.actor_id or existing["command_json"] != encoded:
                    raise ConflictError("Inspection request ID belongs to a different actor or request")
                return self._get(connection, existing["run_id"]), False
            history = self.evidence._history(connection, command.physical_component_id)
            if history.current.version != command.expected_version:
                raise ConflictError("Inspection requested a stale evidence version")
            if self._allocated(connection, command.physical_component_id):
                raise ConflictError("Reserved or consumed components cannot start new inspection")
            inputs = []
            for asset_id in command.asset_ids:
                asset = self.assets._metadata(connection, asset_id)
                if asset.physical_component_id != command.physical_component_id or asset.return_id != history.component.source_return_id:
                    raise ConflictError("Inspection image belongs to a different physical component or return")
                observation = self.evidence._observation(connection, asset.observation_id, command.physical_component_id)
                if observation.evidence_reference != f"asset:{asset_id}" or observation.source_return_id != asset.return_id:
                    raise ConflictError("Inspection image has inconsistent source observation provenance")
                inputs.append(InputAsset(asset_id=asset.asset_id, sha256=asset.sha256, observation_id=asset.observation_id))
            start = InferenceStart(
                run_id=f"inference-{uuid4().hex}", request_id=command.request_id,
                actor_id=actor.actor_id, physical_component_id=command.physical_component_id,
                source_return_id=history.component.source_return_id, inputs=tuple(inputs),
                evidence_version=command.expected_version, configuration=configuration, started_at=datetime.now(UTC),
            )
            connection.execute(
                "INSERT INTO inference_requests(run_id, request_id, physical_component_id, actor_id, command_json, payload) VALUES (?, ?, ?, ?, ?, ?)",
                (start.run_id, command.request_id, start.physical_component_id, actor.actor_id, encoded, _canonical(start)),
            )
            # Byte integrity is checked outside this transaction before execution.
            # A known asset whose bytes are missing can then retain a failed run.
            return InferenceRun(start=start, outcome=None), True

    def _append_output(self, connection, start: InferenceStart, output: InspectionOutput,
                       completed_at: datetime) -> tuple[str, ...]:
        event_ids, observation_ids = [], []
        for index, asset in enumerate(start.inputs, 1):
            markings = [item.text for item in output.observations if item.kind == "marking" and index in item.image_indices]
            observation = Observation(
                observation_id=f"model-observation-{uuid4().hex}", physical_component_id=start.physical_component_id,
                source_return_id=start.source_return_id, captured_at=completed_at,
                evidence_reference=f"asset:{asset.asset_id}", source=AssertionSource.MODEL,
                source_reference=start.run_id, visible_marking="\n".join(markings)[:2048] or None,
            )
            self.evidence._append(connection, observation.observation_id, "observation", observation)
            event_ids.append(observation.observation_id)
            observation_ids.append(observation.observation_id)
        candidates = output.candidates or (None,)
        for candidate in candidates:
            identity = None
            if candidate is not None and candidate.revision is not None:
                identity = ComponentIdentity(component_type_id=candidate.component_type_id, revision=candidate.revision)
            reason = candidate.reason if candidate else "The model did not establish a supported identity; human review is required"
            if candidate is not None and candidate.revision is None:
                reason = f"Unverified type {candidate.component_type_id}; revision remains unknown. {reason}"
            proposal = IdentityProposal(
                proposal_id=f"model-proposal-{uuid4().hex}", physical_component_id=start.physical_component_id,
                observation_id=observation_ids[candidate.image_indices[0] - 1] if candidate else observation_ids[0],
                proposed_identity=identity, created_at=completed_at, uncertainty_reason=reason,
            )
            self.evidence._append(connection, proposal.proposal_id, "proposal", proposal)
            event_ids.append(proposal.proposal_id)
        flag = UncertaintyFlag(
            flag_id=f"model-review-{uuid4().hex}", physical_component_id=start.physical_component_id,
            reason="AI inspection is unverified. Review the linked images, hypotheses, uncertainty, and additional-view requests before human verification.",
            source=AssertionSource.MODEL, source_reference=start.run_id, created_at=completed_at,
        )
        self.evidence._append(connection, flag.flag_id, "uncertainty", flag)
        return tuple([*event_ids, flag.flag_id])

    def finish(self, run_id: str, *, status: str, output: InspectionOutput | None = None,
               raw_output: str | None = None, failure_reason: str | None = None,
               metrics: dict | None = None) -> InferenceRun:
        """Server-owned terminalization; no client endpoint accepts these arguments."""
        run_id = _IDENTIFIER.validate_python(run_id)
        if output is not None:
            output = InspectionOutput.model_validate(output.model_dump(mode="json", warnings=False))
        supplied = {"status": status, "output": output.model_dump(mode="json") if output else None,
                    "raw_output": raw_output, "failure_reason": failure_reason, "metrics": metrics or {}}
        encoded = json.dumps(supplied, sort_keys=True, separators=(",", ":"), allow_nan=False)
        with self.evidence.transaction() as connection:
            run = self._get(connection, run_id)
            existing = connection.execute("SELECT completion_json FROM inference_outcomes WHERE run_id = ?", (run_id,)).fetchone()
            if existing:
                if existing["completion_json"] != encoded:
                    raise ConflictError("Inference run already has a different immutable outcome")
                return run
            start = run.start
            current = self.evidence._history(connection, start.physical_component_id).current
            stale_reason = None
            if current.version != start.evidence_version:
                stale_reason = "Evidence changed while inspection was running"
            elif self._allocated(connection, start.physical_component_id):
                stale_reason = "The component was reserved or consumed while inspection was running"
            if status == "succeeded" and stale_reason is None:
                try:
                    for asset in start.inputs:
                        current_asset = self.assets._metadata(connection, asset.asset_id)
                        self.assets._read_bytes(current_asset)
                        if current_asset.sha256 != asset.sha256:
                            raise ValueError("Input hash changed")
                except (OSError, ValueError):
                    stale_reason = "Input image integrity or availability changed before the result could be applied"
            completed_at = datetime.now(UTC)
            outcome = InferenceOutcome(
                run_id=run_id, status=status, completed_at=completed_at, output=output,
                raw_output=raw_output, failure_reason=failure_reason, metrics=metrics or {},
                stale=stale_reason is not None, stale_reason=stale_reason,
                applied_event_ids=(), evidence_version_after=current.version,
            )
            # Validate source indices and request/outcome consistency before writes.
            InferenceRun(start=start, outcome=outcome)
            if status == "succeeded" and stale_reason is None:
                applied = self._append_output(connection, start, output, completed_at)
                version_after = self.evidence._history(connection, start.physical_component_id).current.version
                outcome = InferenceOutcome.model_validate({**outcome.model_dump(mode="json"),
                                                           "applied_event_ids": applied, "evidence_version_after": version_after})
            result = InferenceRun(start=start, outcome=outcome)
            connection.execute(
                "INSERT INTO inference_outcomes(run_id, completion_json, payload) VALUES (?, ?, ?)",
                (run_id, encoded, _canonical(outcome)),
            )
            return result
