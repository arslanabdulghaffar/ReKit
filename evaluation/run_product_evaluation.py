"""Bounded real-image provider evaluation; human semantic review stays separate."""

import argparse
from collections import Counter
from datetime import UTC, datetime
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
MODEL_REVISION = "89644892e4d85e24eaac8bacfd4f463576704203"
DEFAULT_MODEL_DIR = ROOT / "models" / "Qwen3-VL-2B-Instruct" / MODEL_REVISION
SCHEMA_VERSION = "rekit-product-evaluation-v1"
MAX_CASES = 13
LIMITATIONS = [
    "No approved catalog is supplied; empty identity candidates are instructed abstention, not recognition accuracy.",
    "Source listing titles and model numbers are metadata, not independently reviewed visual truth.",
    "Semantic claim support, marking accuracy, image attribution and view usefulness require independent human review.",
    "A tiny development-only sample does not establish production performance or AMD execution.",
    "This direct-provider experiment does not create evidence, verify components, or change inventory.",
]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def select_cases(manifest) -> list[dict]:
    """Freeze selection in source-manifest order before inspecting model output."""
    categories = list(dict.fromkeys(image.category for image in manifest.images))
    if len(categories) != 6:
        raise ValueError("Evaluation requires the six source categories")
    cases = []

    def case(kind, images):
        return {"case_id": f"case-{len(cases) + 1:02d}", "kind": kind, "inputs": [
            {key: getattr(image, key) for key in
             ("image_id", "sha256", "group_id", "local_path", "category", "split", "byte_size")}
            for image in images]}

    for category in categories:
        groups, chosen = set(), []
        for image in manifest.images:
            if image.category == category and image.split == "development" and image.group_id not in groups:
                chosen.append(image)
                groups.add(image.group_id)
                if len(chosen) == 2:
                    break
        if len(chosen) != 2:
            raise ValueError(f"Insufficient distinct development groups for {category}")
        for image in chosen:
            cases.append(case("single", [image]))
    groups = {}
    for image in manifest.images:
        if image.split == "development":
            groups.setdefault(image.group_id, []).append(image)
    pair = next((images[:2] for images in groups.values() if len(images) >= 2), None)
    if pair is None:
        raise ValueError("A development-only same-listing image pair is required")
    cases.append(case("joint", pair))
    if len(cases) != MAX_CASES:
        raise ValueError("Evaluation case bound changed unexpectedly")
    return cases


def _make_provider(model_dir: Path, device: int):
    # Importing this script or selecting cases never initializes a GPU runtime.
    from rekit.inference.provider import LocalVisionProvider

    return LocalVisionProvider(model_dir=model_dir, device=device, catalog=None)


def _check_execution(result: dict, configuration: dict, inputs: list[dict]) -> None:
    """Apply the API service's provenance checks before accepting parsed output."""
    from pydantic import TypeAdapter
    from rekit.inference.models import ScalarMap

    if not isinstance(result, dict) or result.get("status") != "succeeded":
        raise ValueError("Provider did not return a successful execution")
    if any(result.get(key) != configuration[key] for key in
           ("provider", "model_repository", "model_revision", "device")):
        raise ValueError("Execution provenance differs from the admitted configuration")
    metrics = result.get("metrics", {})
    if not isinstance(metrics, dict) or metrics.get("input_sha256") != [image["sha256"] for image in inputs]:
        raise ValueError("Execution image hashes differ from the ordered input bytes")
    if configuration["provider"] == "local-transformers":
        calls = metrics.get("vision_forward_calls")
        if type(calls) is not int or calls < 1:
            raise ValueError("Actual vision encoder execution was not established")
    generation = configuration["generation"]
    if generation.get("decoding") == "lm-format-enforcer":
        expected_schema = generation.get(f"schema_sha256_{len(inputs)}")
        if (not isinstance(expected_schema, str) or len(expected_schema) != 64
                or any(character not in "0123456789abcdef" for character in expected_schema)
                or not generation.get("schema_version")
                or metrics.get("decoding") != "lm-format-enforcer"
                or metrics.get("schema_version") != generation["schema_version"]
                or metrics.get("schema_sha256") != expected_schema):
            raise ValueError("Executed decoding schema differs from the admitted configuration")
    scalar_metrics = {key: value for key, value in metrics.items()
                      if isinstance(value, (str, int, float, bool)) or value is None}
    for key, value in result.get("runtime", {}).items():
        if isinstance(value, str):
            scalar_metrics[f"runtime_{key}"] = value
    TypeAdapter(ScalarMap).validate_python(scalar_metrics)


def _distribution(values: list[float]) -> dict:
    values = sorted(values)
    return {"n": len(values), "min": min(values) if values else None,
            "p50": statistics.median(values) if values else None,
            "p95": values[math.ceil(0.95 * len(values)) - 1] if values else None,
            "max": max(values) if values else None}


def _number(value) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def summarize(cases: list[dict]) -> dict:
    attempted = [case for case in cases if case.get("wall_seconds") is not None]
    valid = [case for case in attempted if case["status"] == "succeeded" and case.get("output") is not None]
    outputs = [case["output"] for case in valid]
    metrics = [(case.get("execution") or {}).get("metrics", {}) for case in attempted]
    metrics = [item for item in metrics if isinstance(item, dict)]
    measured = [item for item in metrics if _number(item.get("inference_seconds"))]
    abstentions = sum(not item["candidates"] and bool(item["uncertainties"]) for item in outputs)
    source_records = [row for output in outputs for field in ("observations", "candidates", "additional_views")
                      for row in output[field]]
    counts = {
        "observations": sum(len(item["observations"]) for item in outputs),
        "identity_candidates": sum(len(item["candidates"]) for item in outputs),
        "revision_candidates": sum(candidate.get("revision") is not None for item in outputs for candidate in item["candidates"]),
        "marking_observations": sum(row["kind"] == "marking" for item in outputs for row in item["observations"]),
        "revision_marking_quotes": sum(candidate.get("revision_marking") is not None for item in outputs for candidate in item["candidates"]),
        "source_reference_records": len(source_records),
        "source_reference_links": sum(len(row["image_indices"]) for row in source_records),
        "additional_views": sum(len(item["additional_views"]) for item in outputs),
        "responses_with_candidates_despite_no_catalog": sum(bool(item["candidates"]) for item in outputs),
    }
    semantic = {name: {"rate": None, "numerator": None, "denominator": 0,
                       "status": "not_measured_without_independent_human_review"}
                for name in ("unsupported_identity_claims", "unsupported_revision_claims", "unsupported_marking_claims",
                             "marking_transcription_quality", "incorrect_image_attribution",
                             "useful_additional_views", "human_corrections")}
    memory = {}
    for key in ("load_peak_allocated_bytes", "peak_allocated_bytes", "peak_reserved_bytes"):
        values = [item[key] for item in metrics if type(item.get(key)) is int and item[key] >= 0]
        memory[key] = {"n": len(values), "max": max(values) if values else None}
    return {"requested_cases": len(cases), "attempted_cases": len(attempted),
            "not_attempted_cases": len(cases) - len(attempted),
            "input_presentations": sum(len(case["inputs"]) for case in attempted),
            "unique_images": len({image["image_id"] for case in attempted for image in case["inputs"]}),
            "unique_groups": len({image["group_id"] for case in attempted for image in case["inputs"]}),
            "statuses": dict(Counter(case["status"] for case in cases)),
            "schema_valid_responses": {"numerator": len(valid), "denominator": len(attempted),
                                       "rate": len(valid) / len(attempted) if attempted else None,
                                       "definition": "Strict parsed outputs with verified execution provenance / attempted requests"},
            "instructed_abstention": {"numerator": abstentions, "denominator": len(valid),
                                      "rate": abstentions / len(valid) if valid else None,
                                      "definition": "No candidates and explicit uncertainty; no catalog was supplied"},
            "output_counts": counts, "semantic_metrics": semantic, "reviewed_cases": 0,
            "latency_seconds": {
                "wall_all_attempts": _distribution([case["wall_seconds"] for case in attempted if _number(case["wall_seconds"])]),
                "inference_measured": _distribution([item["inference_seconds"] for item in measured]),
                "inference_cold": _distribution([item["inference_seconds"] for item in measured if item.get("model_loaded_this_request") is True]),
                "inference_warm": _distribution([item["inference_seconds"] for item in measured if item.get("model_loaded_this_request") is False]),
                "p95_method": "nearest rank: sorted[ceil(0.95*n)-1]",
            }, "gpu_memory_bytes": memory,
            "exclusions": {"semantic_review": "All cases are pending independent human review",
                           "latency_and_memory": "Absent measurements are excluded, never substituted with zero"}}


def _save(output: Path, record: dict) -> None:
    """Replace only this run's reserved artifact, preserving the last complete JSON."""
    text = json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output.parent,
                                         prefix=output.name + ".", suffix=".pending", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        os.replace(temporary, output)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def _read_input(root: Path, image: dict) -> bytes:
    path = root / image["local_path"]
    if not path.resolve().is_relative_to(root.resolve()) or path.is_symlink() or path.is_junction():
        raise ValueError("Evaluation input escaped its verified storage")
    with path.open("rb") as stream:
        raw = stream.read(10 * 1024**2 + 1)
    if len(raw) != image["byte_size"] or hashlib.sha256(raw).hexdigest() != image["sha256"]:
        raise ValueError("Evaluation input bytes changed after preflight")
    return raw


def run(*, manifest_path: Path, image_root: Path, model_dir: Path, device: int, output: Path) -> int:
    output = output.resolve()
    if output.suffix.lower() != ".json" or not output.is_relative_to((ROOT / "var").resolve()):
        raise ValueError("Evaluation output must be a new JSON file under ignored repository var storage")
    if type(device) is not int or device < 0:
        raise ValueError("CUDA device must be a nonnegative integer")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write("{}\n")
    record = {"schema_version": SCHEMA_VERSION, "started_at": _now(), "status": "running",
              "transport": "direct provider, not API or browser acceptance", "catalog_supplied": False,
              "independent_human_review": False, "limitations": LIMITATIONS,
              "case_plan": [], "cases": []}
    _save(output, record)
    complete = False
    try:
        from product_data import DatasetManifest, MAX_MANIFEST_BYTES, verify_images

        with manifest_path.open("rb") as stream:
            manifest_bytes = stream.read(MAX_MANIFEST_BYTES + 1)
        if len(manifest_bytes) > MAX_MANIFEST_BYTES:
            raise ValueError("Source manifest exceeds its bound")
        manifest = DatasetManifest.model_validate_json(manifest_bytes)
        record["manifest_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
        record["dataset"] = {key: getattr(manifest, key) for key in
                             ("dataset", "source_url", "license_id", "license_url", "attribution")}
        record["integrity"] = verify_images(manifest, image_root)
        record["case_plan"] = select_cases(manifest)
        record["cases"] = [{**case, "status": "pending", "wall_seconds": None, "execution": None, "output": None}
                           for case in record["case_plan"]]
        _save(output, record)
        provider = _make_provider(model_dir, device)
        from rekit.inference.models import InferenceConfiguration
        from rekit.inference.parsing import parse_output
        from rekit.inference.provider import VisionTimeout, VisionUnavailable

        configuration = InferenceConfiguration.model_validate(provider.configuration.model_dump(mode="json"))
        record["configuration"] = configuration.model_dump(mode="json")
        _save(output, record)
        for case in record["cases"]:
            started = time.perf_counter()
            case["started_at"] = _now()
            case["status"] = "running"
            _save(output, record)
            try:
                images = [_read_input(image_root, image) for image in case["inputs"]]
                result = provider.inspect(images)
                case["execution"] = result
                case["wall_seconds"] = time.perf_counter() - started
                # Retain actual output even when subsequent provenance/parsing fails.
                _save(output, record)
                _check_execution(result, record["configuration"], case["inputs"])
                try:
                    parsed = parse_output(result.get("text"), image_count=len(images),
                                          allow_candidates=configuration.generation.get("identity_candidates_allowed", True))
                except (ValueError, TypeError) as error:
                    case["status"] = "invalid_output"
                    case["error"] = {"type": type(error).__name__, "reason": str(error)}
                else:
                    case["status"] = "succeeded"
                    case["output"] = parsed.model_dump(mode="json")
            except Exception as error:
                case["status"] = ("timed_out" if isinstance(error, VisionTimeout) else
                                  "unavailable" if isinstance(error, VisionUnavailable) else "failed")
                case["error"] = {"type": type(error).__name__, "reason": str(error)}
            finally:
                if case["wall_seconds"] is None:
                    case["wall_seconds"] = time.perf_counter() - started
                case["finished_at"] = _now()
                record["summary"] = summarize(record["cases"])
                _save(output, record)
            if case["status"] == "unavailable":
                break
        complete = True
        record["status"] = "completed" if all(case["status"] == "succeeded" for case in record["cases"]) else "completed_with_failures"
    except Exception as error:
        record["status"] = "failed"
        record["error"] = {"type": type(error).__name__, "reason": str(error)}
        complete = True
    finally:
        if not complete:
            record["status"] = "interrupted"
        for case in record["cases"]:
            if case["status"] == "pending":
                case["status"] = "not_attempted"
        record["finished_at"] = _now()
        record["summary"] = summarize(record["cases"])
        _save(output, record)
    return 0 if record["status"] == "completed" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROOT / "evaluation/fixtures/abo-manifest.json")
    parser.add_argument("--root", type=Path, default=ROOT / "var/evaluation/abo")
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--device", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        status = run(manifest_path=arguments.manifest, image_root=arguments.root,
                     model_dir=arguments.model_dir, device=arguments.device, output=arguments.output)
        print(json.dumps({"exit_code": status, "artifact": str(arguments.output)}, ensure_ascii=True))
        return status
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "failed", "error_type": type(error).__name__}, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
