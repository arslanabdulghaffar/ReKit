"""Local, human-owned review of product evaluation outputs; no inventory authority."""

import argparse
import hashlib
import html
import json
import os
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from product_data import Sha256, Timestamp, load_manifest, verify_images


Judgment = Literal["undetermined", "not_present", "supported", "unsupported"]
FIELDS = ("identity", "revision", "marking", "source_attribution", "additional_view", "uncertainty")
ROOT = Path(__file__).resolve().parents[1]


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False).encode()).hexdigest()


class CaseReview(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    case_id: str = Field(min_length=1, max_length=128)
    output_sha256: Sha256
    input_sha256: list[Sha256] = Field(min_length=1, max_length=2)
    status: Literal["pending", "reviewed"] = "pending"
    reviewer: str | None = Field(default=None, max_length=200)
    reviewed_at: Timestamp | None = None
    independent_human_review: bool = False
    identity: Judgment = "undetermined"
    revision: Judgment = "undetermined"
    marking: Judgment = "undetermined"
    source_attribution: Judgment = "undetermined"
    additional_view: Judgment = "undetermined"
    # Older v1 assessment files omit this field; omission is never a judgment.
    uncertainty: Judgment = "undetermined"
    expected_marking_text: str | None = Field(default=None, max_length=2000)
    model_marking_text: str | None = Field(default=None, max_length=2000)
    correction: str = Field(default="", max_length=4000)
    notes: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def human_boundary(self) -> Self:
        if self.status == "pending":
            if (self.reviewer is not None or self.reviewed_at is not None or self.independent_human_review
                    or any(getattr(self, field) != "undetermined" for field in FIELDS)
                    or self.expected_marking_text is not None or self.model_marking_text is not None
                    or self.correction or self.notes):
                raise ValueError("Pending output reviews cannot assert human judgments")
        elif (not self.independent_human_review or not self.reviewer or not self.reviewer.strip()
              or self.reviewed_at is None or not self.notes.strip()):
            raise ValueError("Reviewed output needs a human, time, declaration and supporting notes")
        if (self.expected_marking_text is None) != (self.model_marking_text is None):
            raise ValueError("A transcription comparison needs both human-assessed strings")
        if self.expected_marking_text is not None and self.marking not in ("supported", "unsupported"):
            raise ValueError("A transcription comparison requires an explicit marking judgment")
        return self


class Assessments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["rekit-product-assessments-v1"] = "rekit-product-assessments-v1"
    result_sha256: Sha256
    reviews: list[CaseReview] = Field(max_length=60)


def template(result: dict) -> Assessments:
    case_ids = [case["case_id"] for case in result["cases"]]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("Evaluation case IDs must be unique")
    reviews = []
    for case in result["cases"]:
        raw = (case.get("execution") or {}).get("text")
        if isinstance(raw, str):
            reviews.append(CaseReview(case_id=case["case_id"],
                                      output_sha256=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                                      input_sha256=[item["sha256"] for item in case["inputs"]]))
    if len({row.case_id for row in reviews}) != len(reviews):
        raise ValueError("Evaluation case IDs must be unique")
    return Assessments(result_sha256=digest(result), reviews=reviews)


def summarize(result: dict, assessments: Assessments) -> dict:
    assessments = Assessments.model_validate_json(assessments.model_dump_json())
    expected = template(result)
    if assessments.result_sha256 != expected.result_sha256:
        raise ValueError("Review belongs to a different execution/configuration record")
    bindings = {row.case_id: row for row in expected.reviews}
    if len({row.case_id for row in assessments.reviews}) != len(assessments.reviews):
        raise ValueError("Duplicate case assessment")
    for row in assessments.reviews:
        original = bindings.get(row.case_id)
        if original is None or (row.output_sha256, row.input_sha256) != (original.output_sha256, original.input_sha256):
            raise ValueError("Review output or ordered source hashes changed")
    reviewed = [row for row in assessments.reviews if row.status == "reviewed"]

    def rate(numerator: int, denominator: int) -> dict:
        return {"numerator": numerator if denominator else None, "denominator": denominator,
                "rate": numerator / denominator if denominator else None,
                "excluded_cases": len(result["cases"]) - denominator}

    metrics = {}
    for field in FIELDS:
        eligible = [row for row in reviewed if getattr(row, field) in ("supported", "unsupported")]
        positive = "supported" if field in ("additional_view", "uncertainty") else "unsupported"
        metrics[field] = rate(sum(getattr(row, field) == positive for row in eligible), len(eligible))
        if field in ("identity", "revision", "marking"):
            metrics[f"{field}_supported"] = rate(
                sum(getattr(row, field) == "supported" for row in eligible), len(eligible))
    transcriptions = [row for row in reviewed if row.expected_marking_text is not None]
    metrics["transcription_exact_match"] = rate(
        sum(row.expected_marking_text == row.model_marking_text for row in transcriptions), len(transcriptions))
    metrics["human_corrections"] = rate(sum(bool(row.correction.strip()) for row in reviewed), len(reviewed))
    return {"reviewed_cases": len(reviewed), "pending_cases": len(result["cases"]) - len(reviewed),
            "unit": "independently assessed cases; not individual claims or product accuracy",
            "metrics": metrics}


def read_result(path: Path) -> dict:
    if path.stat().st_size > 8 * 1024**2:
        raise ValueError("Evaluation result exceeds its review bound")
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict) or not isinstance(result.get("cases"), list) or len(result["cases"]) > 60:
        raise ValueError("Invalid bounded evaluation record")
    return result


def load_assessments(path: Path) -> Assessments:
    with path.open("rb") as source:
        raw = source.read(1024**2 + 1)
    if len(raw) > 1024**2:
        raise ValueError("Review assessment file exceeds its bound")
    return Assessments.model_validate_json(raw)


def create_queue(manifest_path: Path, root: Path, result_path: Path, destination: Path) -> dict:
    if destination.exists() or not destination.resolve().is_relative_to((ROOT / "var").resolve()):
        raise ValueError("Review queue needs a new directory inside ignored var storage")
    manifest = load_manifest(manifest_path)
    verify_images(manifest, root)
    result = read_result(result_path)
    if result.get("manifest_sha256") != hashlib.sha256(manifest_path.read_bytes()).hexdigest():
        raise ValueError("Evaluation manifest hash changed")
    assessments = template(result)
    images = {item.image_id: item for item in manifest.images}
    rows = {row.case_id: row for row in assessments.reviews}
    cards = []
    for case in result["cases"]:
        photographs = []
        for index, source in enumerate(case["inputs"], 1):
            original = images[source["image_id"]]
            if source["sha256"] != original.sha256 or source["group_id"] != original.group_id:
                raise ValueError("Evaluation image provenance differs from manifest")
            relative = Path(os.path.relpath((root / original.local_path).resolve(), destination.resolve())).as_posix()
            photographs.append(f'<figure><figcaption>Input {index}: {html.escape(original.image_id)}</figcaption>'
                               f'<a href="{html.escape(relative, quote=True)}" target="_blank" rel="noopener noreferrer"><img loading="lazy" src="{html.escape(relative, quote=True)}" alt="Original source image {index}"></a>'
                               f'<details><summary>Source provenance</summary><p>Listing {html.escape(original.group_id)}; {original.split}</p>'
                               f'<code>{original.sha256}</code><p>Catalog metadata, not visual truth: {html.escape(json.dumps(original.source_labels, ensure_ascii=False))}</p></details></figure>')
        fields = ""
        if case["case_id"] in rows:
            for name in FIELDS:
                label = {"additional_view": "Would the suggested view help?",
                         "source_attribution": "Do the cited images support the claims?",
                         "uncertainty": "Does the uncertainty or abstention fit the available evidence?"}.get(
                             name, name.replace("_", " ").capitalize())
                fields += f'<label>{label}<select data-field="{name}"><option value="undetermined">Undetermined</option><option value="not_present">No such claim/request</option><option value="supported">Supported / useful</option><option value="unsupported">Unsupported / unhelpful</option></select></label>'
            fields += '<label><input type="checkbox" data-transcription> Compare these transcriptions (an empty string means no readable text)</label><label>Readable marking: human transcription<textarea maxlength="2000" data-field="expected_marking_text"></textarea></label><label>Corresponding model transcription<textarea maxlength="2000" data-field="model_marking_text"></textarea></label><label>Correction, if needed<textarea maxlength="4000" data-field="correction"></textarea></label><label>Review notes: appearance, ambiguity, and supporting pixels<textarea maxlength="4000" data-field="notes"></textarea></label><label><input type="checkbox" data-reviewed> I personally reviewed these images and this output.</label>'
        model = {"status": case["status"], "validated_output": case.get("output"),
                 "raw_output": (case.get("execution") or {}).get("text"), "error": case.get("error")}
        cards.append(f'<article data-case="{html.escape(case["case_id"], quote=True)}"><h2>{html.escape(case["case_id"])}</h2><div class="images">{"".join(photographs)}</div>'
                     '<p>Inspect the original image first. Complete the independent image-review gallery before expanding model output. Assess claims anywhere in the text, including observations and uncertainty, not only the candidate list.</p><p data-image-error role="alert" hidden>Original image unavailable. Restore the original files and run the integrity check before reviewing this case.</p>'
                     f'<details><summary>Model suggestions — unverified</summary><pre>{html.escape(json.dumps(model, indent=2, ensure_ascii=False))}</pre></details><div class="fields">{fields}</div></article>')
    payload = assessments.model_dump_json().replace("<", "\\u003c").replace("&", "\\u0026")
    script = """const pending=JSON.parse(document.getElementById('template').textContent);
for(const image of document.querySelectorAll('article img')){
 image.addEventListener('error',()=>{const card=image.closest('article');card.querySelector('[data-image-error]').hidden=false;const box=card.querySelector('[data-reviewed]');if(box){box.checked=false;box.disabled=true;}});
 if(image.complete && !image.naturalWidth)image.dispatchEvent(new Event('error'));
}
document.getElementById('export').onclick=()=>{
 const result=structuredClone(pending), actor=document.getElementById('reviewer').value.trim();
 for(const row of result.reviews){
  const card=[...document.querySelectorAll('article')].find(x=>x.dataset.case===row.case_id);
  if(!card.querySelector('[data-reviewed]').checked)continue;
  if([...card.querySelectorAll('img')].some(image=>!image.complete || !image.naturalWidth)){alert('Load every original image before exporting a reviewed case. Restore missing files and run the integrity check.');return;}
  if(!actor){alert('Enter the human reviewer name.');return;}
  row.status='reviewed';row.reviewer=actor;row.reviewed_at=new Date().toISOString();row.independent_human_review=true;
  for(const input of card.querySelectorAll('[data-field]'))row[input.dataset.field]=input.value;
  if(!card.querySelector('[data-transcription]').checked){row.expected_marking_text=null;row.model_marking_text=null;}
  if(!row.notes.trim() || (row.expected_marking_text!==null && !['supported','unsupported'].includes(row.marking))){alert('Reviewed cases need support notes; transcription comparisons need an explicit marking judgment.');return;}
 }
 const url=URL.createObjectURL(new Blob([JSON.stringify(result,null,2)+'\\n'],{type:'application/json'}));
 const link=document.createElement('a');link.href=url;link.download='case-assessments.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};"""
    import base64
    script_hash = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self' file:; style-src 'unsafe-inline'; script-src 'sha256-{script_hash}'; connect-src 'none'; form-action 'none'; base-uri 'none'">
<title>ReKit product evidence review</title><style>body{{font:16px system-ui;background:#f4f6f8;color:#18212c;max-width:1100px;margin:auto;padding:24px}}article{{background:white;padding:24px;margin:24px 0;border-radius:12px}}.images,.fields{{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px}}figure{{margin:0}}img{{max-width:100%;max-height:460px;object-fit:contain}}pre,code{{white-space:pre-wrap;overflow-wrap:anywhere}}label{{display:block;margin:12px 0}}textarea,select{{display:block;box-sizing:border-box;width:100%;padding:8px}}button{{padding:12px 20px}}details{{margin:16px 0}}footer{{position:sticky;bottom:0;background:#e6edf4;padding:16px}}</style>
<h1>Review product evidence</h1><p>All judgments start pending. Source imagery includes product views, composites, and reference graphics. These are not returned-kit photographs. Model text may invent identity, markings, hidden function, safety, or compatibility.</p>
<p>Review pixels before predictions. Source attribution asks whether the cited input actually supports a claim. The additional-view judgment asks whether another photo would resolve a stated uncertainty. Judge uncertainty and abstention against the evidence, not model confidence wording. An undetermined judgment stays outside that metric's denominator. This page exports local review files; it cannot approve inventory.</p>
<p>Attribution: {html.escape(manifest.attribution)} <a href="{html.escape(manifest.source_url, quote=True)}">Dataset source</a> · <a href="{html.escape(manifest.license_url, quote=True)}">CC BY 4.0 license</a>. Original image bytes are unchanged. Model preprocessing may resize them.</p>
{''.join(cards)}<footer><label>Human reviewer <input id="reviewer" maxlength="200"></label><button id="export">Download case assessments</button><p>Validate the downloaded file with product_review.py check. Independent image labels remain in the separate image-review ledger.</p></footer>
<script id="template" type="application/json">{payload}</script><script>{script}</script></html>'''
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "index.html").write_text(page, encoding="utf-8")
    (destination / "case-assessments.json").write_text(assessments.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return {"cases": len(result["cases"]), "reviewed": 0, "queue": str(destination / "index.html")}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create")
    create.add_argument("--manifest", type=Path, required=True)
    create.add_argument("--root", type=Path, required=True)
    create.add_argument("--result", type=Path, required=True)
    create.add_argument("--output-dir", type=Path, required=True)
    check = commands.add_parser("check")
    check.add_argument("--result", type=Path, required=True)
    check.add_argument("--assessments", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "create":
        print(json.dumps(create_queue(args.manifest, args.root, args.result, args.output_dir)))
    else:
        assessments = load_assessments(args.assessments)
        print(json.dumps(summarize(read_result(args.result), assessments)))
