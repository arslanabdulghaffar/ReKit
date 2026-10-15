"""Freeze a private, portable review package from existing recorded local outputs.

This CLI never downloads, runs inference, labels images, or updates inventory.
All generated review records remain pending until a human exports an assessment.
"""

import argparse
from copy import deepcopy
import hashlib
import html
import json
from pathlib import Path

import image_review
import product_review
from product_data import DatasetManifest, load_manifest, verify_images


ROOT = Path(__file__).resolve().parents[1]
VERSION = "rekit-frozen-product-review-v1"
POLICY = "first-12-paired-development-groups-in-recorded-baseline-order-v1"
GROUP_COUNT = 12
QUESTIONS = (
    ("Useful observations", "Which observations would help an operator, and which visible pixels support them? Record useful observations in notes; usefulness is not inferred from valid JSON."),
    ("Unsupported claims", "Does any claim exceed the visible evidence, including identity, revision, hidden function, safety or compatibility? Quote it and cite the input; assess the relevant existing claim field."),
    ("Missed markings", "What readable markings did the model omit or misread? Transcribe the original independently first; compare exact strings in the marking fields only when legible."),
    ("Repeated text", "Does repeated text obscure the answer or repeat a claim without new evidence? Quote examples in notes, or state none observed. Repetition alone is not a correctness judgment."),
    ("Incomplete answers", "Is the answer incomplete for the visible evidence or supplied task? Explain omissions in notes and distinguish a justified abstention from an unsupported guess."),
    ("Additional views", "Would each requested view resolve a specific uncertainty, or is it unnecessary given these images? Judge usefulness in additional_view and explain the evidence."),
)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json(path: Path, value) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as output:
        output.write(json.dumps(value, indent=2, ensure_ascii=True, allow_nan=False) + "\n")


def _private_destination(destination: Path) -> Path:
    destination = destination.absolute()
    allowed = (ROOT / "var").resolve()
    if destination.exists() or not destination.resolve().is_relative_to(allowed):
        raise ValueError("Package requires a fresh directory inside ignored var storage")
    for part in (destination, *destination.parents):
        if part.is_symlink() or part.is_junction():
            raise ValueError("Package path cannot traverse links or junctions")
    return destination


def _case_sources(result: dict, manifest: DatasetManifest, manifest_sha: str) -> dict:
    if result.get("manifest_sha256") != manifest_sha:
        raise ValueError("Recorded result manifest hash changed")
    product_review.template(result)  # duplicate IDs and bounded output/input bindings
    originals = {image.image_id: image for image in manifest.images}
    sources = {}
    for case in result["cases"]:
        inputs = case.get("inputs")
        if not isinstance(inputs, list) or not 1 <= len(inputs) <= 2:
            raise ValueError("Recorded case needs one or two original inputs")
        seen = set()
        for item in inputs:
            original = originals.get(item.get("image_id"))
            if (original is None or original.sha256 != item.get("sha256")
                    or original.group_id != item.get("group_id") or original.image_id in seen):
                raise ValueError("Recorded input differs from original manifest")
            seen.add(original.image_id)
        if len({item["group_id"] for item in inputs}) != 1:
            raise ValueError("A review case must belong to one listing group")
        sources[case["case_id"]] = case
    return sources


def freeze_selection(manifest: DatasetManifest, manifest_sha: str, selection: dict,
                     baseline: dict, after: dict) -> dict:
    """Select by existing collection and order, never predicted correctness."""
    image_review.validate_selection(manifest, manifest_sha, selection)
    existing = {item["image_id"] for item in selection["images"]}
    originals = {image.image_id: image for image in manifest.images}
    before = _case_sources(baseline, manifest, manifest_sha)
    later = _case_sources(after, manifest, manifest_sha)
    eligible, excluded = [], []
    for case_id, case in before.items():
        pair = later.get(case_id)
        reason = None
        if pair is None:
            reason = "missing paired case"
        elif case["inputs"] != pair["inputs"]:
            raise ValueError("Paired cases must use identical ordered original inputs")
        elif any(item["image_id"] not in existing for item in case["inputs"]):
            reason = "outside existing image-review selection"
        elif any(originals[item["image_id"]].split != "development" for item in case["inputs"]):
            reason = "not development split"
        elif any(not isinstance((item.get("execution") or {}).get("text"), str)
                 for item in (case, pair)):
            reason = "one or both recorded outputs unavailable"
        if reason:
            excluded.append({"case_id": case_id, "reason": reason})
        else:
            eligible.append(case_id)
    for case_id in sorted(later.keys() - before.keys()):
        excluded.append({"case_id": case_id, "reason": "missing baseline case"})
    groups = list(dict.fromkeys(before[case_id]["inputs"][0]["group_id"] for case_id in eligible))
    if len(groups) < GROUP_COUNT:
        raise ValueError("Existing review collection lacks 12 paired eligible listing groups")
    selected_groups = groups[:GROUP_COUNT]
    chosen = []
    for case_id in eligible:
        if before[case_id]["inputs"][0]["group_id"] in selected_groups:
            chosen.append(case_id)
        else:
            excluded.append({"case_id": case_id, "reason": "outside first 12 eligible groups"})
    image_ids = list(dict.fromkeys(item["image_id"] for case_id in chosen for item in before[case_id]["inputs"]))
    return {"policy": POLICY, "groups": selected_groups, "case_ids": chosen, "image_ids": image_ids,
            "source_review_groups": len({item["group_id"] for item in selection["images"]}),
            "source_manifest_groups": len({image.group_id for image in manifest.images}),
            "paired_eligible_groups": len(groups), "excluded_cases": excluded,
            "source_review_groups_not_selected": sorted({item["group_id"] for item in selection["images"]} - set(selected_groups)),
            "source_manifest_images_not_selected": len(manifest.images) - len(image_ids),
            "proposed_double_review_groups": selected_groups[:4]}


def _instructions() -> str:
    return "\n".join(f"- **{title}:** {question}" for title, question in QUESTIONS)


def _projection(source: dict, case_ids: list[str], subset_sha: str, run: str, source_sha: str) -> dict:
    """Only case selection, the subset binding and explicit provenance may change."""
    cases = {case["case_id"]: case for case in source["cases"]}
    projected = deepcopy(source)
    projected["manifest_sha256"] = subset_sha
    projected["cases"] = [deepcopy(cases[case_id]) for case_id in case_ids]
    projected["review_package_source"] = {"path": f"source/{run}.json", "sha256": source_sha,
                                          "projection": "cases unchanged; manifest projected to selected original images; historical summary remains source-scoped"}
    return projected


def _landing(frozen: dict, rows: list[dict]) -> str:
    questions = "".join(f"<li><strong>{html.escape(title)}.</strong> {html.escape(question)}</li>" for title, question in QUESTIONS)
    cases = []
    for row in rows:
        links = " ".join(f'<a href="output-{run}/index.html#{html.escape(row["case_id"], quote=True)}">{run} assessment</a> '
                         f'<a href="{row[run]["raw_output_path"]}">{run} exact text</a>' for run in ("baseline", "after"))
        cases.append(f'<tr><td>{html.escape(row["case_id"])}</td><td>{html.escape(row["group_id"])}</td><td>{links}</td></tr>')
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; connect-src 'none'; form-action 'none'; base-uri 'none'">
<title>ReKit frozen independent review</title><style>body{{font:17px/1.55 system-ui;max-width:1060px;margin:auto;padding:24px;color:#152b40;background:#f5f7fa}}section{{background:white;padding:24px;margin:18px 0;border:1px solid #cad4dd;border-radius:12px}}h1,h2{{line-height:1.2}}li{{margin:14px 0}}table{{border-collapse:collapse;width:100%}}td,th{{padding:10px;border-bottom:1px solid #cad4dd;text-align:left;vertical-align:top}}a,code{{overflow-wrap:anywhere}}@media(max-width:650px){{body{{padding:10px}}section{{padding:14px}}table{{font-size:14px}}}}</style></head>
<body><h1>Independent visual assessment</h1><p>12 distinct development listing groups, {len(rows)} paired cases, {len(frozen['image_ids'])} unchanged original images. All judgments are pending.</p>
<section><h2>1. Inspect originals before model outputs</h2><p><a href="image-review/index.html">Open the image-only review gallery</a>. Save your draft and export your own independent image ledger before inspecting predictions. These are public ABO catalog views, composites and reference graphics, not customer returns.</p><p>Identity, hidden function, safety and compatibility cannot be established by appearance alone. Confidence language is not a calibrated probability. The package has no inventory authority and makes no network requests.</p></section>
<section><h2>2. Review both recorded outputs</h2><p>Open the baseline and after pages in separate tabs. Review all six questions below for every case, including outputs that appear good. The variant names disclose chronology; this is not a blinded or representative benchmark. No case has been pre-labeled correct or incorrect.</p><ol>{questions}</ol><p>Use the existing claim judgments and transcription fields; record useful observations, repetition and completeness in notes. Those notes have no automatic numeric score. Inspect claims anywhere in the raw response, not only candidate arrays.</p><table><thead><tr><th>Source case</th><th>Listing group</th><th>Recorded outputs and human forms</th></tr></thead><tbody>{''.join(cases)}</tbody></table></section>
<section><h2>3. Preserve your review</h2><p>Export each assessment to a new private file. Do not replace the frozen pending templates. The README gives validation commands and denominator rules. A second independent reviewer can assess the first four listed groups; no second review or agreement is assumed.</p><p><a href="README.md">Reviewer instructions</a> · <a href="manifest.json">Frozen hashes and source links</a> · <a href="pending-summary.json">Current zero-denominator summary</a></p><p>Existing NVIDIA outputs only. No new model inference, AMD qualification or human assessment was performed by packaging this collection.</p></section></body></html>'''


def create_package(manifest_path: Path, root: Path, selection_path: Path,
                   baseline_path: Path, after_path: Path, destination: Path) -> dict:
    destination = _private_destination(destination)
    manifest = load_manifest(manifest_path)
    verify_images(manifest, root)
    manifest_raw = manifest_path.read_bytes()
    baseline = product_review.read_result(baseline_path)
    after = product_review.read_result(after_path)
    selection = json.loads(image_review._read(selection_path))
    frozen = freeze_selection(manifest, _sha(manifest_raw), selection, baseline, after)
    originals = {image.image_id: image for image in manifest.images}
    subset_data = manifest.model_dump(mode="json")
    subset_data["images"] = [originals[image_id].model_dump(mode="json") for image_id in frozen["image_ids"]]
    subset = DatasetManifest.model_validate(subset_data)
    # The existing gallery must include every selected input, without a new selection policy.
    if {image.image_id for image in image_review.select_images(subset)} != set(frozen["image_ids"]):
        raise ValueError("Existing image-gallery policy would omit a selected original")
    destination.mkdir(parents=True, exist_ok=False)
    for child in ("source", "images", "results", "outputs/baseline", "outputs/after"):
        (destination / child).mkdir(parents=True)
    sources = {}
    for name, path in (("manifest.json", manifest_path), ("selection.json", selection_path),
                       ("baseline.json", baseline_path), ("after.json", after_path)):
        raw = path.read_bytes()
        (destination / "source" / name).write_bytes(raw)
        sources[name] = {"path": f"source/{name}", "sha256": _sha(raw), "bytes": len(raw)}
    _json(destination / "subset-manifest.json", subset.model_dump(mode="json"))
    subset_sha = _sha((destination / "subset-manifest.json").read_bytes())
    for original in subset.images:
        raw = (root / original.local_path).read_bytes()
        if _sha(raw) != original.sha256:
            raise ValueError("Original changed during packaging")
        (destination / original.local_path).write_bytes(raw)
    rows = [{"case_id": case_id, "group_id": next(case for case in baseline["cases"] if case["case_id"] == case_id)["inputs"][0]["group_id"]}
            for case_id in frozen["case_ids"]]
    for run, original_result in (("baseline", baseline), ("after", after)):
        cases = {case["case_id"]: case for case in original_result["cases"]}
        projected = _projection(original_result, frozen["case_ids"], subset_sha, run, sources[f"{run}.json"]["sha256"])
        _json(destination / "results" / f"{run}.json", projected)
        product_review.create_queue(destination / "subset-manifest.json", destination,
                                    destination / "results" / f"{run}.json", destination / f"output-{run}")
        page_path = destination / f"output-{run}" / "index.html"
        page = page_path.read_text(encoding="utf-8")
        for index, row in enumerate(rows, 1):
            case_id = row["case_id"]
            raw = cases[case_id]["execution"]["text"].encode("utf-8")
            relative = f"outputs/{run}/{index:02d}.txt"
            (destination / relative).write_bytes(raw)
            row[run] = {"raw_output_path": relative, "output_sha256": _sha(raw),
                        "source_case_sha256": product_review.digest(cases[case_id]),
                        "assessment_path": f"output-{run}/case-assessments.json", "case_id": case_id}
            page = page.replace(f'<article data-case="{html.escape(case_id, quote=True)}">',
                                f'<article id="{html.escape(case_id, quote=True)}" data-case="{html.escape(case_id, quote=True)}">')
        # Only fresh package HTML is augmented; no preserved source queue is modified.
        page_path.write_text(page, encoding="utf-8", newline="\n")
    for row in rows:
        row["inputs"] = deepcopy(next(case for case in baseline["cases"] if case["case_id"] == row["case_id"])["inputs"])
    image_review.create_gallery(destination / "subset-manifest.json", destination, destination / "image-review")
    (destination / "index.html").write_text(_landing(frozen, rows), encoding="utf-8", newline="\n")
    readme = f'''# Frozen independent review package

Private working evidence. Preserve original files and pending templates. No new inference or human judgments were generated. Model: existing recorded local NVIDIA Qwen results, not AMD. This package is not inventory input.

## Review order

1. Open index.html in a browser. Complete the image-only gallery before predictions.
2. Open each baseline and after case. Their raw-output .txt files preserve the exact recorded UTF-8 text, including repetition and incomplete prose. Full source results retain original model/runtime/timing provenance.
3. Answer all questions below in the existing claim fields, marking comparison and notes. Use undetermined when evidence is insufficient; metadata is not visual truth. Save separate exported files, never overwrite this package.
4. If available, a different human can independently review the first four listing groups. Preserve both assessments; investigate disagreements without replacing either account.

{_instructions()}

## Scope and denominators

Selection policy: {POLICY}. The frozen source image-review selection, source manifest and both source result files are copied byte-for-byte under source/. Selection uses case order and original input identity, not output correctness. Selected groups: {len(frozen['groups'])}; cases per output variant: {len(rows)}; original images: {len(frozen['image_ids'])}. The single and paired fan cases share a group, and baseline/after responses share inputs; do not count these as independent products. Holdout data is excluded. Exclusions and source IDs are in manifest.json.

Image facts and semantic assessments are pending. An eligible semantic denominator includes only human-reviewed supported/unsupported cases for that field; pending, undetermined and absent claims are excluded. Summaries retain each variant separately. Usefulness, missed omissions, repetition and completeness require the qualitative notes; existing metrics do not automatically score them. A paired disagreement denominator includes two distinct human reviewers with determinate judgments for the same field and exact output, including not_present. A not_present versus supported/unsupported pair is a disagreement about claim presence; the not_present assessment remains excluded from that reviewer's semantic-accuracy denominator. Two not_present judgments agree on absence without establishing accuracy. Disagreement is not accuracy, and absent second reviews produce null rates, not zero disagreement.

The subset manifest and results/ are explicitly derived review projections. Individual case objects and raw text are unchanged; the complete source results retain their original manifest hash. The existing image-review selection policy is revalidated on the 13-image subset. All originals keep their source byte hashes and attribution; no model-output text was used as a label.

## Validate from repository root (PowerShell)

```powershell
.\\.venv\\Scripts\\python.exe -B evaluation/package_product_review.py check --package {destination.relative_to(ROOT).as_posix()}
```

After a human exports new private files, pass --baseline-assessments PATH and/or --after-assessments PATH to the same check command. Optional --second-baseline-assessments PATH / --second-after-assessments PATH report field-level disagreements; same-person pairs are excluded. --image-reviews PATH validates an exported image ledger. Validation does not alter any package or review file.

Dataset attribution: {manifest.attribution}
License: {manifest.license_id} {manifest.license_url}
Original source: {manifest.source_url}
Original images are unchanged; historical inference preprocessing may have resized them. All rights and publication decisions remain with the owner.
'''
    (destination / "README.md").write_text(readme, encoding="utf-8", newline="\n")
    pending = _review_summary(destination, frozen, None, None, None, None, None)
    _json(destination / "pending-summary.json", pending)
    files = {path.relative_to(destination).as_posix(): {"sha256": _sha(path.read_bytes()), "bytes": path.stat().st_size}
             for path in sorted(destination.rglob("*")) if path.is_file()}
    _json(destination / "manifest.json", {"schema_version": VERSION, "selection": frozen, "sources": sources,
                                         "cases": rows, "questions": list(QUESTIONS), "files": files,
                                         "human_review_status": "pending", "new_inference_requests": 0})
    return {"status": "created", "package": str(destination), "manifest_sha256": _sha((destination / "manifest.json").read_bytes()),
            **check_package(destination)}


def disagreements(result: dict, first, second) -> dict:
    """Compare determinate judgments, including disagreement about claim presence.

    Unlike supported/unsupported semantic eligibility, a not_present judgment is
    eligible here. Two absent-claim judgments agree; absence versus a supported
    or unsupported claim disagrees. Neither comparison establishes accuracy.
    """
    product_review.summarize(result, first)
    product_review.summarize(result, second)
    left = {row.case_id: row for row in first.reviews}
    right = {row.case_id: row for row in second.reviews}
    metrics = {}
    for field in product_review.FIELDS:
        pairs, excluded = [], []
        for case in result["cases"]:
            case_id = case["case_id"]
            a, b = left.get(case_id), right.get(case_id)
            if a is None or b is None or a.status != "reviewed" or b.status != "reviewed":
                reason = "not reviewed by both"
            elif a.reviewer.strip().casefold() == b.reviewer.strip().casefold():
                reason = "same declared reviewer"
            elif "undetermined" in (getattr(a, field), getattr(b, field)):
                reason = "undetermined judgment"
            else:
                pairs.append(case_id)
                continue
            excluded.append({"case_id": case_id, "reason": reason})
        differing = [case_id for case_id in pairs if getattr(left[case_id], field) != getattr(right[case_id], field)]
        metrics[field] = {"eligible_paired_cases": len(pairs), "disagreeing_cases": differing,
                          "numerator": len(differing) if pairs else None,
                          "rate": len(differing) / len(pairs) if pairs else None, "exclusions": excluded}
    return {"status": "available" if any(row["eligible_paired_cases"] for row in metrics.values()) else "not established",
            "reviewer_identity": "self-declared; not authenticated", "metrics": metrics}


def _review_summary(package: Path, frozen: dict, baseline_path, after_path,
                    second_baseline_path, second_after_path, image_reviews_path) -> dict:
    variants = {}
    for name, first_path, second_path in (("baseline", baseline_path, second_baseline_path), ("after", after_path, second_after_path)):
        result = product_review.read_result(package / "results" / f"{name}.json")
        first = product_review.load_assessments(first_path or package / f"output-{name}" / "case-assessments.json")
        second = product_review.load_assessments(second_path) if second_path else product_review.template(result)
        variants[name] = {**product_review.summarize(result, first), "disagreement": disagreements(result, first, second)}
    manifest, sha = image_review._manifest(package / "subset-manifest.json")
    selection = json.loads(image_review._read(package / "image-review/selection.json"))
    ledger = image_review.ReviewLedger.model_validate_json(image_review._read(image_reviews_path or package / "image-review/image-reviews.json"))
    image_summary = image_review.validate_selected_reviews(manifest, sha, selection, ledger)
    return {"listing_groups": len(frozen["groups"]), "cases_per_variant": len(frozen["case_ids"]),
            "original_images": len(frozen["image_ids"]), "variants": variants, "images": image_summary,
            "qualitative_questions": [title for title, _ in QUESTIONS], "qualitative_ratings": "not automatically scored",
            "selection_exclusions": frozen["excluded_cases"], "accuracy_claim": None}


def check_package(package: Path, baseline_path=None, after_path=None, second_baseline_path=None,
                  second_after_path=None, image_reviews_path=None) -> dict:
    data = json.loads(image_review._read(package / "manifest.json"))
    if data.get("schema_version") != VERSION:
        raise ValueError("Unknown frozen review package version")
    for relative, record in data["files"].items():
        path = package / relative
        if not path.resolve().is_relative_to(package.resolve()) or path.is_symlink() or path.is_junction():
            raise ValueError("Frozen file must remain within package")
        raw = path.read_bytes()
        if len(raw) != record["bytes"] or _sha(raw) != record["sha256"]:
            raise ValueError(f"Frozen package file changed: {relative}")
    source_manifest = load_manifest(package / "source/manifest.json")
    selection = json.loads(image_review._read(package / "source/selection.json"))
    frozen = freeze_selection(source_manifest, _sha((package / "source/manifest.json").read_bytes()), selection,
                              product_review.read_result(package / "source/baseline.json"),
                              product_review.read_result(package / "source/after.json"))
    if frozen != data["selection"]:
        raise ValueError("Frozen selection differs from reproducible source selection")
    subset = load_manifest(package / "subset-manifest.json")
    originals = {image.image_id: image for image in source_manifest.images}
    if [image.model_dump(mode="json") for image in subset.images] != [originals[image_id].model_dump(mode="json") for image_id in frozen["image_ids"]]:
        raise ValueError("Subset images differ from frozen source originals")
    verify_images(subset, package)
    subset_sha = _sha((package / "subset-manifest.json").read_bytes())
    expected_rows = []
    for case_id in frozen["case_ids"]:
        expected_rows.append({"case_id": case_id})
    for run in ("baseline", "after"):
        source = product_review.read_result(package / "source" / f"{run}.json")
        projected = product_review.read_result(package / "results" / f"{run}.json")
        cases = {case["case_id"]: case for case in source["cases"]}
        expected = _projection(source, frozen["case_ids"], subset_sha, run,
                               _sha((package / "source" / f"{run}.json").read_bytes()))
        if projected != expected:
            raise ValueError("Review projection differs from its exact allowed source projection")
        for index, row in enumerate(expected_rows, 1):
            case = cases[row["case_id"]]
            relative = f"outputs/{run}/{index:02d}.txt"
            raw = case["execution"]["text"].encode("utf-8")
            if (package / relative).read_bytes() != raw:
                raise ValueError("Raw text differs from original recorded output")
            row[run] = {"raw_output_path": relative, "output_sha256": _sha(raw),
                        "source_case_sha256": product_review.digest(case),
                        "assessment_path": f"output-{run}/case-assessments.json", "case_id": row["case_id"]}
            row["inputs"] = case["inputs"]
            row["group_id"] = case["inputs"][0]["group_id"]
    if expected_rows != data["cases"]:
        raise ValueError("Frozen case index differs from original source cases")
    return {"status": "verified", **_review_summary(package, frozen, baseline_path, after_path,
                                                     second_baseline_path, second_after_path, image_reviews_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    for name in ("manifest", "root", "selection", "baseline", "after", "output"):
        create.add_argument(f"--{name}", type=Path, required=True)
    check = commands.add_parser("check")
    check.add_argument("--package", type=Path, required=True)
    for name in ("baseline-assessments", "after-assessments", "second-baseline-assessments", "second-after-assessments", "image-reviews"):
        check.add_argument(f"--{name}", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "create":
            result = create_package(args.manifest, args.root, args.selection, args.baseline, args.after, args.output)
        else:
            result = check_package(args.package, args.baseline_assessments, args.after_assessments,
                                   args.second_baseline_assessments, args.second_after_assessments, args.image_reviews)
        print(json.dumps(result, ensure_ascii=True, allow_nan=False))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
