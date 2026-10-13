"""Two bounded real-GPU experiments, separate from API/browser acceptance.

Reuse the existing synthetic fixture generator and retain every raw response.
This checks structure and execution; a human must review visual/source claims.
"""

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import shutil

from rekit.catalog.models import Catalog
from rekit.inference.parsing import parse_output
from rekit.inference.provider import LocalVisionProvider

from run_browser_acceptance import ROOT, _checked_directory, _prepare


def run(output: Path, device: int) -> int:
    output = output.resolve()
    if output.exists():
        raise ValueError("Choose a new output file; prior experiment records are preserved")
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest_path, manifest = _prepare(real_inference=True, device=device)
    record = {"started_at": datetime.now(UTC).isoformat(), "synthetic": True,
              "transport": "direct provider qualification, not API or browser acceptance",
              "visual_accuracy": "not measured; source attribution requires manual review", "cases": []}
    status = 1
    try:
        catalog = Catalog.model_validate_json((ROOT / "tests/fixtures/synthetic_catalog.json").read_text(encoding="utf-8"))
        provider = LocalVisionProvider(Path(manifest["model_dir"]), device=device, catalog=catalog)
        record["configuration"] = provider.configuration.model_dump(mode="json")
        first = manifest["fixture"]["components"][0]["component"]["physical_component_id"]
        # Fixed VIEW 2, VIEW 1 order matches the saved v4 failure baseline.
        cases = [("two_label_views", list(reversed(manifest["images"][first]))),
                 ("ambiguous_illustration", [manifest["ambiguous_image"]])]
        for name, paths in cases:
            images = [Path(path).read_bytes() for path in paths]
            entry = {"name": name, "inputs": [{"filename": Path(path).name,
                     "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
                    for path, raw in zip(paths, images)], "json_valid": False, "domain_valid": False}
            record["cases"].append(entry)
            try:
                result = provider.inspect(images)
                entry["execution"] = result
                raw = result["text"].strip()
                syntax_text = raw[7:-3].strip() if raw.startswith("```json\n") and raw.endswith("```") else raw
                try:
                    json.loads(syntax_text)
                    entry["json_valid"] = True
                except (ValueError, TypeError):
                    pass
                parsed = parse_output(result["text"], image_count=len(images))
                if (result["metrics"]["input_sha256"] != [item["sha256"] for item in entry["inputs"]]
                        or result["metrics"]["vision_forward_calls"] < 1):
                    raise ValueError("Actual image execution did not match experiment inputs")
                entry["domain_valid"] = True
                entry["parsed"] = parsed.model_dump(mode="json")
            except Exception as error:
                entry["failure"] = {"type": type(error).__name__, "reason": str(error)}
            output.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        status = 0 if all(case["domain_valid"] for case in record["cases"]) else 1
        record["status"] = "structure_passed" if status == 0 else "failed"
    finally:
        state = _checked_directory(Path(manifest["state_dir"]), Path(manifest["artifacts_dir"]))
        shutil.rmtree(state)
        record["temporary_state_removed"] = not state.exists() and not manifest_path.exists()
        record["finished_at"] = datetime.now(UTC).isoformat()
        output.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": record["status"], "artifact": str(output)}))
    return status


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", type=int, default=1)
    args = parser.parse_args()
    raise SystemExit(run(args.output, args.device))
