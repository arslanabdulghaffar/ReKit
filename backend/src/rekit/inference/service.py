"""One process-local inference slot; GPU execution never holds a SQLite transaction."""

import hashlib
import math
import re
import threading
import time

from pydantic import TypeAdapter

from rekit.auth import Actor
from rekit.evidence.store import ConflictError
from rekit.inference.models import InferenceRun, InspectionRequest, ScalarMap
from rekit.inference.parsing import MAX_OUTPUT_CHARACTERS, parse_output
from rekit.inference.provider import VisionInvalidOutput, VisionProvider, VisionTimeout, VisionUnavailable
from rekit.inference.store import InferenceStore


class InferenceService:
    """Keep model weights warm, bound admission, and discard late completions."""

    def __init__(self, store: InferenceStore, provider: VisionProvider, timeout_seconds: float = 150):
        if not math.isfinite(timeout_seconds) or not 0.01 <= timeout_seconds <= 180:
            raise ValueError("Inference request deadline must be between 0.01 and 180 seconds")
        self.store, self.provider = store, provider
        self.timeout_seconds = timeout_seconds
        self._guard = threading.RLock()
        self._active: str | None = None
        self._thread: threading.Thread | None = None
        self._timer: threading.Timer | None = None
        self._closed = False
        self._persistence_failed = False

    def status(self) -> dict:
        with self._guard:
            config = self.provider.configuration
            return {"status": "unavailable" if self._closed or self._persistence_failed else self.provider.status,
                    "busy": self._active is not None, "provider": config.provider,
                    "model_repository": config.model_repository, "model_revision": config.model_revision,
                    "device": config.device, "request_timeout_seconds": self.timeout_seconds}

    def submit(self, command: InspectionRequest, actor: Actor) -> InferenceRun:
        with self._guard:
            retry = self.store.replay(command, actor)
            if retry is not None:
                return retry
            if self._closed or self._persistence_failed:
                raise ConflictError("The inference worker is unavailable; manual inspection remains available")
            if self._active is not None:
                raise ConflictError("The inference worker is busy; retry when the active computation finishes")
            run, created = self.store.begin(command, actor, self.provider.configuration)
            if not created:
                return run
            self._active = run.start.run_id
            self._timer = threading.Timer(self.timeout_seconds, self._deadline, args=(run.start.run_id,))
            self._timer.daemon = True
            self._thread = threading.Thread(target=self._execute, args=(run,), daemon=True, name="rekit-vision")
            try:
                self._timer.start()
                self._thread.start()
            except Exception:
                self._timer.cancel()
                self._terminal(run.start.run_id, status="failed", failure_reason="The inference worker could not start")
                self._active = None
                return self.store.get(run.start.run_id)
            return run

    def _terminal(self, run_id: str, **outcome) -> None:
        """Call under the guard. A database error disables admission, never invents success."""
        try:
            if self.store.get(run_id).outcome is None:
                self.store.finish(run_id, **outcome)
        except Exception as error:
            try:
                self.store.finish(run_id, status="failed",
                                  failure_reason=f"The inference outcome could not be saved ({type(error).__name__})")
            except Exception:
                self._persistence_failed = True

    def _deadline(self, run_id: str) -> None:
        with self._guard:
            if self._active == run_id:
                self._terminal(run_id, status="timed_out",
                               failure_reason="The request deadline expired; any late model result will be discarded")
                # Ownership remains with the actual computation until _execute exits.

    @staticmethod
    def _metrics(result: dict) -> dict:
        values = {key: value for key, value in result.get("metrics", {}).items()
                  if isinstance(value, (str, int, float, bool)) or value is None}
        for key, value in result.get("runtime", {}).items():
            if isinstance(value, str):
                values[f"runtime_{key}"] = value
        return TypeAdapter(ScalarMap).validate_python(values)

    def _execute(self, run: InferenceRun) -> None:
        run_id = run.start.run_id
        started = time.perf_counter()
        diagnostic_raw = None
        try:
            images = []
            for source in run.start.inputs:
                asset, raw = self.store.assets.read(source.asset_id)
                if asset.sha256 != source.sha256 or hashlib.sha256(raw).hexdigest() != source.sha256:
                    raise ValueError("Managed input integrity changed")
                images.append(raw)
            with self._guard:
                if self.store.get(run_id).outcome is not None or self._closed:
                    return
            result = self.provider.inspect(images)
            raw_output = result.get("text")
            if isinstance(raw_output, str):
                diagnostic_raw = raw_output[:MAX_OUTPUT_CHARACTERS]
            config = run.start.configuration
            if any(key not in result or result[key] != getattr(config, key)
                   for key in ("provider", "model_repository", "model_revision", "device")):
                raise ValueError("Inference provider provenance did not match the admitted configuration")
            if (result.get("metrics", {}).get("input_sha256") != [item.sha256 for item in run.start.inputs]
                    or (config.provider == "local-transformers"
                        and result.get("metrics", {}).get("vision_forward_calls", 0) < 1)):
                raise ValueError("Inference provider input hashes did not match the admitted images")
            if config.generation.get("decoding") in {"lm-format-enforcer", "json-schema-request"}:
                schema_version = config.generation.get("schema_version")
                schema_digest = config.generation.get(f"schema_sha256_{len(images)}")
                if (not isinstance(schema_version, str) or not schema_version.strip()
                        or not isinstance(schema_digest, str) or re.fullmatch(r"[a-f0-9]{64}", schema_digest) is None
                        or result.get("metrics", {}).get("decoding") != config.generation["decoding"]
                        or result.get("metrics", {}).get("schema_version") != schema_version
                        or result.get("metrics", {}).get("schema_sha256") != schema_digest):
                    raise ValueError("Provider schema provenance did not match the admitted configuration")
            metrics = self._metrics(result)
            metrics["request_seconds"] = time.perf_counter() - started
            try:
                output = parse_output(raw_output, image_count=len(images),
                                      allow_candidates=config.generation.get("identity_candidates_allowed", True))
            except (ValueError, TypeError):
                outcome = {"status": "invalid_output", "raw_output": diagnostic_raw,
                           "failure_reason": "Model output did not satisfy the inspection schema; no evidence was applied",
                           "metrics": metrics}
            else:
                outcome = {"status": "succeeded", "output": output, "raw_output": raw_output, "metrics": metrics}
        except VisionTimeout:
            outcome = {"status": "timed_out", "failure_reason": "The model exceeded its execution deadline"}
        except VisionInvalidOutput as error:
            raw = error.raw_output
            outcome = {"status": "invalid_output",
                       "raw_output": raw[:MAX_OUTPUT_CHARACTERS] if isinstance(raw, str) else None,
                       "failure_reason": "The provider response failed its strict output contract; no evidence was applied"}
        except VisionUnavailable as error:
            reasons = {
                "authentication": "Remote authentication was rejected.",
                "rate_limited": "The remote endpoint is rate limited; no automatic retry was made.",
                "unsupported": "The remote endpoint rejected the model, images, or structured-output contract.",
                "endpoint": "The remote HTTPS endpoint is unavailable.",
                "busy": "The remote provider already has an active request.",
            }
            code = error.reason_code
            reason = reasons.get(code, "The configured inference provider is unavailable.")
            outcome = {"status": "unavailable", "failure_reason": reason + " Manual inspection remains available.",
                       "metrics": {"remote_error_code": code} if code in reasons else {}}
        except Exception as error:
            outcome = {"status": "failed", "raw_output": diagnostic_raw,
                       "failure_reason": f"Inspection failed ({type(error).__name__}); no model evidence was applied"}
        finally:
            with self._guard:
                if "outcome" in locals():
                    if time.perf_counter() - started >= self.timeout_seconds:
                        outcome = {"status": "timed_out", "failure_reason": "The request deadline expired; any late model result will be discarded"}
                    self._terminal(run_id, **outcome)
                if self._timer is not None:
                    self._timer.cancel()
                self._active = None

    def close(self) -> None:
        """Stop admission and evidence application; Python cannot interrupt a CUDA kernel."""
        with self._guard:
            self._closed = True
            if self._timer is not None:
                self._timer.cancel()
            if self._active is not None:
                self._terminal(self._active, status="failed", failure_reason="The application shut down during inspection")
            thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=1)
