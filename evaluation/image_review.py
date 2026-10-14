"""Image-first, human-owned review of a fixed local development selection.

No model output is loaded. Drafts are non-annotation working files; only explicit
human declarations can produce reviewed entries in the existing ReviewLedger.
"""

import argparse
import base64
import hashlib
import html
import json
import os
from pathlib import Path
from typing import Literal
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field

from product_data import (
    DatasetManifest, ImageId, ReviewEntry, ReviewLedger, Sha256,
    MAX_MANIFEST_BYTES, validate_reviews, verify_images,
)


ROOT = Path(__file__).resolve().parents[1]
MAX_REVIEW_BYTES = 1024**2
SELECTION_VERSION = "rekit-image-review-selection-v1"
SELECTION_POLICY = "first-three-development-groups-per-category-plus-first-two-views-v1"
DRAFT_VERSION = "rekit-image-review-draft-v1-NON-ANNOTATION"
FORM_FIELDS = ("marking_visible", "visible_markings", "exact_identity_visually_established",
               "identity_label", "revision_supported", "revision_label", "support_notes", "ambiguity_notes")


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True,
                                     allow_nan=False).encode("utf-8")).hexdigest()


def _read(path: Path, limit: int = MAX_REVIEW_BYTES) -> bytes:
    with Path(path).open("rb") as source:
        raw = source.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("Review file exceeds its byte limit")
    return raw


def _manifest(path: Path) -> tuple[DatasetManifest, str]:
    raw = _read(path, MAX_MANIFEST_BYTES)
    return DatasetManifest.model_validate_json(raw), hashlib.sha256(raw).hexdigest()


def select_images(manifest: DatasetManifest) -> list:
    """Preserve manifest order; use no predictions or asserted visual labels."""
    manifest = DatasetManifest.model_validate_json(manifest.model_dump_json())
    selected, category_groups, group_views = [], {}, {}
    for image in manifest.images:
        if image.split != "development":
            continue
        group_views.setdefault(image.group_id, []).append(image)
        groups = category_groups.setdefault(image.category, set())
        if image.group_id not in groups and len(groups) < 3:
            groups.add(image.group_id)
            selected.append(image)
    first_pair = next((views[:2] for views in group_views.values() if len(views) >= 2), [])
    selected_ids = {image.image_id for image in selected}
    for image in first_pair:
        if image.image_id not in selected_ids:
            selected.append(image)
            selected_ids.add(image.image_id)
    if not selected:
        raise ValueError("The manifest has no development images to review")
    return selected


def build_selection(manifest: DatasetManifest, manifest_sha256: str) -> dict:
    return {"schema_version": SELECTION_VERSION, "policy": SELECTION_POLICY,
            "manifest_sha256": manifest_sha256, "full_image_count": len(manifest.images),
            "images": [{"image_id": image.image_id, "sha256": image.sha256,
                        "group_id": image.group_id, "category": image.category,
                        "split": image.split} for image in select_images(manifest)]}


def validate_selection(manifest: DatasetManifest, manifest_sha256: str, selection: dict) -> dict:
    expected = build_selection(manifest, manifest_sha256)
    if digest(selection) != digest(expected):
        raise ValueError("Selection does not match the exact manifest, policy and ordered source hashes")
    return expected


def pending_ledger(selection: dict) -> ReviewLedger:
    return ReviewLedger(reviews=[ReviewEntry(image_id=item["image_id"], sha256=item["sha256"])
                                 for item in selection["images"]])


def validate_selected_reviews(manifest: DatasetManifest, manifest_sha256: str,
                              selection: dict, ledger: ReviewLedger) -> dict:
    selection = validate_selection(manifest, manifest_sha256, selection)
    ledger = ReviewLedger.model_validate_json(ledger.model_dump_json())
    expected = [(item["image_id"], item["sha256"]) for item in selection["images"]]
    if [(row.image_id, row.sha256) for row in ledger.reviews] != expected:
        raise ValueError("Review ledger must contain exactly the selected images in selection order")
    if any(row.review_status == "pending" and (row.support_notes or row.ambiguity_notes)
           for row in ledger.reviews):
        raise ValueError("Unchecked image facts belong in a draft, not pending review entries")
    summary = validate_reviews(ledger, manifest)
    count = len(expected)
    return {"selected_images": count, "selected_groups": len({item["group_id"] for item in selection["images"]}),
            "selected_reviewed": summary["reviewed"], "selected_pending": count - summary["reviewed"],
            "full_images": len(manifest.images), "full_pending": summary["pending"],
            "not_selected": len(manifest.images) - count,
            "semantic_accuracy": None,
            "accuracy_status": "not measured by image-label collection; requires eligible output assessments"}


class DraftRow(BaseModel):
    """Form strings only: no declaration, review status, timestamp or truth fields."""
    model_config = ConfigDict(extra="forbid", strict=True)
    image_id: ImageId
    sha256: Sha256
    marking_visible: Literal["", "yes", "no"] = ""
    visible_markings: str = Field(default="", max_length=64032)
    exact_identity_visually_established: Literal["", "yes", "no"] = ""
    identity_label: str = Field(default="", max_length=2000)
    revision_supported: Literal["", "yes", "no"] = ""
    revision_label: str = Field(default="", max_length=2000)
    support_notes: str = Field(default="", max_length=4000)
    ambiguity_notes: str = Field(default="", max_length=4000)


class ReviewDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    schema_version: Literal["rekit-image-review-draft-v1-NON-ANNOTATION"] = DRAFT_VERSION
    manifest_sha256: Sha256
    selection_sha256: Sha256
    reviewer: str = Field(default="", max_length=2000)
    forms: list[DraftRow] = Field(max_length=60)


def validate_draft(manifest: DatasetManifest, manifest_sha256: str,
                   selection: dict, draft: ReviewDraft) -> ReviewDraft:
    selection = validate_selection(manifest, manifest_sha256, selection)
    draft = ReviewDraft.model_validate_json(draft.model_dump_json())
    if len((draft.model_dump_json(indent=2) + "\n").encode("utf-8")) > MAX_REVIEW_BYTES:
        raise ValueError("Draft export exceeds its 1 MiB byte limit")
    expected = [(item["image_id"], item["sha256"]) for item in selection["images"]]
    if (draft.manifest_sha256 != manifest_sha256 or draft.selection_sha256 != digest(selection)
            or [(row.image_id, row.sha256) for row in draft.forms] != expected):
        raise ValueError("Draft belongs to a different source manifest or ordered selection")
    return draft


_SCRIPT = r"""
const config = __CONFIG__;
const fields = config.fields;
const cards = [...document.querySelectorAll('article[data-image-id]')];
const reviewer = document.getElementById('reviewer');
const notice = document.getElementById('notice');
let dirty = false;
function say(message, error=false) { notice.textContent=message; notice.dataset.error=String(error); }
function field(card, name) { return card.querySelector('[data-field="'+name+'"]'); }
function values(card) { return Object.fromEntries(fields.map(name=>[name,field(card,name).value])); }
function changed() { dirty=true; }
document.addEventListener('input',changed);
document.addEventListener('change',changed);
window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
for (const card of cards) {
  const picture=card.querySelector('img');
  const state=card.querySelector('[data-image-state]');
  function loaded() { const ok=picture.complete && picture.naturalWidth>0;
    card.dataset.loaded=String(ok);state.textContent=ok?'Original image loaded.':'Image missing or unreadable. Reviewed export is blocked for this image.';
    state.dataset.error=String(!ok);
  }
  picture.addEventListener('load',loaded);picture.addEventListener('error',loaded);loaded();
}
function save(name, value) {
  const serialized=JSON.stringify(value,null,2)+'\n';
  if(new TextEncoder().encode(serialized).length>config.maxBytes)throw Error('Export exceeds the 1 MiB limit.');
  const url=URL.createObjectURL(new Blob([serialized],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download=name;link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function keys(value, expected) {
  return value && typeof value==='object' && !Array.isArray(value)
    && JSON.stringify(Object.keys(value).sort())===JSON.stringify([...expected].sort());
}
function formValid(row) {
  if(!keys(row,['image_id','sha256',...fields]))throw Error('Invalid draft form fields.');
  for(const name of fields) {
    const value=row[name];const cap=['support_notes','ambiguity_notes'].includes(name)?4000:name==='visible_markings'?64032:2000;
    if(typeof value!=='string' || [...value].length>cap)throw Error('Draft field exceeds its limit.');
    if(['marking_visible','exact_identity_visually_established','revision_supported'].includes(name)
       && !['','yes','no'].includes(value))throw Error('Invalid draft choice.');
  }
}
function checkDraft(draft) {
  if(!keys(draft,['schema_version','manifest_sha256','selection_sha256','reviewer','forms'])
     || draft.schema_version!==config.draftVersion || draft.manifest_sha256!==config.selection.manifest_sha256
     || draft.selection_sha256!==config.selectionDigest || typeof draft.reviewer!=='string'
     || [...draft.reviewer].length>2000 || !Array.isArray(draft.forms) || draft.forms.length!==cards.length)
    throw Error('This is not a matching non-annotation draft.');
  draft.forms.forEach((row,index)=>{formValid(row);const original=config.selection.images[index];
    if(row.image_id!==original.image_id || row.sha256!==original.sha256)throw Error('Draft image order or source hash changed.');});
}
document.getElementById('save-draft').addEventListener('click',()=>{try{
  const draft={schema_version:config.draftVersion,manifest_sha256:config.selection.manifest_sha256,
    selection_sha256:config.selectionDigest,reviewer:reviewer.value,
    forms:cards.map((card,index)=>({image_id:config.selection.images[index].image_id,
      sha256:config.selection.images[index].sha256,...values(card)}))};
  checkDraft(draft);save('image-review-draft.json',draft);dirty=false;
  say('Non-annotation draft downloaded. No human declarations or reviewed labels were saved in this draft.');
}catch(error){say(error.message,true);}});
document.getElementById('load-draft').addEventListener('change',async event=>{try{
  const file=event.target.files[0];if(!file)return;
  if(file.size>config.maxBytes)throw Error('Draft exceeds the 1 MiB limit.');
  const draft=JSON.parse(await file.text());checkDraft(draft);
  reviewer.value=draft.reviewer;
  cards.forEach((card,index)=>{for(const name of fields)field(card,name).value=draft.forms[index][name];
    field(card,'declaration').checked=false;});
  dirty=true;say('Draft loaded. All review declarations are reset. Inspect each original again before explicitly declaring a review.');
}catch(error){say(error.message,true);}finally{event.target.value='';}});
function text(value,limit,name) {
  if(!value || [...value].length>limit || value!==value.trim())throw Error(name+' must be nonblank, trimmed and within its limit.');
  return value;
}
document.getElementById('export-reviews').addEventListener('click',()=>{try{
  let reviewed=0,discarded=0;
  const ledger=structuredClone(config.pending);
  cards.forEach((card,index)=>{
    const value=values(card);
    if(!field(card,'declaration').checked){if(Object.values(value).some(Boolean))discarded++;return;}
    const id=config.selection.images[index].image_id;
    if(card.dataset.loaded!=='true')throw Error(id+': original image must load before reviewed export.');
    const actor=text(reviewer.value.trim(),2000,'Reviewer identity');
    for(const name of ['marking_visible','exact_identity_visually_established','revision_supported'])
      if(!['yes','no'].includes(value[name]))throw Error(id+': explicitly answer every visible-support question.');
    const markings=value.visible_markings.split(/\r?\n/).map(line=>line.trim()).filter(Boolean);
    if(markings.length>32 || new Set(markings).size!==markings.length)throw Error(id+': enter at most 32 distinct marking lines.');
    markings.forEach(line=>text(line,2000,'Marking'));
    const visible=value.marking_visible==='yes',identity=value.exact_identity_visually_established==='yes',revision=value.revision_supported==='yes';
    if(!visible && markings.length)throw Error(id+': no visible marking cannot have a transcription.');
    if(identity!==Boolean(value.identity_label.trim()) || revision!==Boolean(value.revision_label.trim()))
      throw Error(id+': labels require matching explicit visible support.');
    if(revision && (!visible || !markings.length))throw Error(id+': revision needs a readable visible marking.');
    if(!value.support_notes.trim() || [...value.support_notes].length>4000 || [...value.ambiguity_notes].length>4000)
      throw Error(id+': visible attributes / support notes are required and notes must fit their limits.');
    ledger.reviews[index]={...ledger.reviews[index],review_status:'reviewed',reviewer:actor,
      reviewed_at:new Date().toISOString(),independent_human_review:true,visible_markings:markings,
      marking_visible:visible,exact_identity_visually_established:identity,
      identity_label:identity?text(value.identity_label.trim(),2000,'Identity label'):null,
      revision_supported:revision,revision_label:revision?text(value.revision_label.trim(),2000,'Revision label'):null,
      support_notes:value.support_notes,ambiguity_notes:value.ambiguity_notes};reviewed++;
  });
  const bytes=new TextEncoder().encode(JSON.stringify(ledger));
  if(bytes.length>config.maxBytes)throw Error('Review export exceeds the 1 MiB limit.');
  save('image-reviews.json',ledger);
  dirty=discarded>0;
  say('Downloaded '+reviewed+' explicitly reviewed and '+(cards.length-reviewed)+' pending entries. '+discarded+
    ' unchecked forms had their facts omitted; save a draft to retain them. Run the CLI check before using these labels.');
}catch(error){say(error.message,true);}});
"""


def _document(manifest: DatasetManifest, selection: dict, root: Path, destination: Path) -> str:
    escape = html.escape
    originals = {image.image_id: image for image in manifest.images}
    cards = []
    for index, item in enumerate(selection["images"], 1):
        image = originals[item["image_id"]]
        url = escape(quote(os.path.relpath((root / image.local_path).resolve(), destination), safe="/\\").replace("\\", "/"), quote=True)
        image_id = escape(image.image_id, quote=True)

        def choice(name: str, label: str) -> str:
            return (f'<label>{label}<select data-field="{name}"><option value="">Choose explicitly</option>'
                    '<option value="yes">Yes — visibly supported</option>'
                    '<option value="no">No — not visually established</option></select></label>')

        cards.append(f'''<article data-image-id="{image_id}" data-loaded="false">
<h2>{index}. Image {image_id}</h2>
<a href="{url}" target="_blank" rel="noopener noreferrer"><img src="{url}" alt="Original image {image_id}"></a>
<p data-image-state role="status">Loading original image…</p><p><a href="{url}" target="_blank" rel="noopener noreferrer">Open original at full resolution</a></p>
<details><summary>Source provenance (not visual truth)</summary><p>Group: {escape(image.group_id)}; development split.<br>SHA-256: <code>{image.sha256}</code></p>
<a href="{escape(image.source_url, quote=True)}" target="_blank" rel="noopener noreferrer">Original dataset source</a></details>
<fieldset><legend>Your independent image observations</legend>
<label>Visible attributes / support notes<textarea data-field="support_notes" maxlength="4000" rows="3"></textarea></label>
{choice('marking_visible', 'Any marking visibly present?')}
<label>Readable markings, one exact transcription per line<textarea data-field="visible_markings" maxlength="64032" rows="3"></textarea></label>
<p>A visible but unreadable marking: choose Yes and leave transcriptions empty. Do not infer hidden or cropped text.</p>
{choice('exact_identity_visually_established', 'Exact identity visually established?')}
<label>Visibly supported identity label<input data-field="identity_label" maxlength="2000"></label>
{choice('revision_supported', 'Revision supported by a readable marking?')}
<label>Supported revision label<input data-field="revision_label" maxlength="2000"></label>
<label>Ambiguity, unreadable areas, missing views / evidence<textarea data-field="ambiguity_notes" maxlength="4000" rows="3"></textarea></label>
<label class="declaration"><input type="checkbox" data-field="declaration"> I independently reviewed this original image and personally supplied these judgments.</label>
</fieldset></article>''')
    config = {"fields": FORM_FIELDS, "selection": selection, "selectionDigest": digest(selection),
              "draftVersion": DRAFT_VERSION, "maxBytes": MAX_REVIEW_BYTES,
              "pending": pending_ledger(selection).model_dump(mode="json")}
    script = _SCRIPT.replace("__CONFIG__", json.dumps(config, ensure_ascii=True).replace("<", "\\u003c"))
    script_hash = base64.b64encode(hashlib.sha256(script.encode("utf-8")).digest()).decode("ascii")
    csp = f"default-src 'none'; img-src 'self' file:; style-src 'unsafe-inline'; script-src 'sha256-{script_hash}'; connect-src 'none'; base-uri 'none'; form-action 'none'"
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="{escape(csp, quote=True)}"><title>Independent product image review</title>
<style>body{{font:16px/1.5 system-ui,sans-serif;color:#172638;background:#edf2f6;margin:0}}main{{max-width:1060px;margin:auto;padding:24px}}h1,h2{{line-height:1.2}}article,.intro{{background:white;border:1px solid #b8c7d5;border-radius:10px;padding:24px;margin:20px 0}}img{{display:block;max-width:100%;max-height:540px;object-fit:contain;margin:auto}}label{{display:block;margin:14px 0}}input:not([type=checkbox]),textarea,select{{box-sizing:border-box;display:block;width:100%;font:inherit;padding:8px;border:1px solid #71849a;border-radius:4px}}input[type=checkbox]{{width:20px;height:20px;vertical-align:middle}}fieldset{{border:0;padding:0}}button{{font:inherit;padding:10px 16px;margin:6px 8px 6px 0;cursor:pointer}}code,p,a{{overflow-wrap:anywhere}}[data-error=true]{{color:#a01624;font-weight:600}}.warning{{border-left:4px solid #a46c05;padding:10px;background:#fff7df}}#notice{{white-space:pre-wrap}}@media(max-width:600px){{main{{padding:10px}}article,.intro{{padding:16px}}button{{width:100%;margin:6px 0}}}}</style></head>
<body><main><section class="intro"><h1>Independent product image review</h1>
<p>{len(selection['images'])} selected development images / {len(manifest.images)} source images. All entries start pending. This gallery contains no model predictions or source listing labels.</p>
<p>Inspect the original before any model-output review. Describe only visible attributes. An unestablished identity or revision is not proof of incompatibility; photographs do not establish hidden function or safety.</p>
<p>Record readable text exactly; use the ambiguity field for missing angles, unreadable markings, similar-looking items, or uncertainty. A declaration is your statement of independent review, not independently authenticated identity.</p>
<label>Reviewer identity<input id="reviewer" maxlength="2000" autocomplete="off"></label>
<button id="save-draft" type="button">Save non-annotation draft</button>
<label>Load non-annotation draft<input id="load-draft" type="file" accept="application/json,.json"></label>
<p>Drafts retain form text only. Loading a draft resets all review declarations. Keep downloaded files private and run the CLI check to validate source bytes and annotations.</p>
<p class="warning">Final export includes facts only for explicitly declared reviews. All unchecked forms export as empty pending entries; save a draft first to retain their text. Missing images block affected reviewed entries. Accuracy is not measured by this gallery.</p>
<button id="export-reviews" type="button">Export image review ledger</button><p id="notice" role="status">No independent reviews have been recorded.</p>
<details><summary>Dataset attribution and selection</summary><p>{escape(manifest.attribution)}</p><p>{escape(manifest.license_id)} — <a href="{escape(manifest.license_url, quote=True)}" target="_blank" rel="noopener noreferrer">License</a></p><p>Selection policy: {SELECTION_POLICY}<br>Manifest SHA-256: <code>{selection['manifest_sha256']}</code></p></details>
</section>{''.join(cards)}</main><script>{script}</script></body></html>'''


def create_gallery(manifest_path: Path, root: Path, destination: Path) -> dict:
    destination = Path(destination).absolute()
    allowed = (ROOT / "var").absolute()
    if destination.exists() or not destination.resolve().is_relative_to(allowed.resolve()):
        raise ValueError("Image review needs a new directory inside ignored var storage")
    if any(path.is_symlink() or path.is_junction() for path in (destination, *destination.parents)
           if path == allowed or path.is_relative_to(allowed)):
        raise ValueError("Image review output cannot traverse links or junctions")
    manifest, sha = _manifest(manifest_path)
    verify_images(manifest, root)
    selection = build_selection(manifest, sha)
    ledger = pending_ledger(selection)
    document = _document(manifest, selection, Path(root), destination)
    destination.mkdir(parents=True, exist_ok=False)
    for name, value in (("selection.json", json.dumps(selection, indent=2)),
                        ("image-reviews.json", ledger.model_dump_json(indent=2)),
                        ("index.html", document)):
        with (destination / name).open("x", encoding="utf-8", newline="\n") as output:
            output.write(value + "\n")
    return {"status": "created", "output": str(destination),
            **validate_selected_reviews(manifest, sha, selection, ledger)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="Create a new local image-only gallery")
    check = commands.add_parser("check", help="Verify sources, selection and human-owned review/draft files")
    for command in (create, check):
        command.add_argument("--manifest", type=Path, required=True)
        command.add_argument("--root", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    check.add_argument("--selection", type=Path, required=True)
    files = check.add_mutually_exclusive_group(required=True)
    files.add_argument("--reviews", type=Path)
    files.add_argument("--draft", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "create":
            result = create_gallery(args.manifest, args.root, args.output)
        else:
            manifest, sha = _manifest(args.manifest)
            verify_images(manifest, args.root)
            selection = json.loads(_read(args.selection))
            validate_selection(manifest, sha, selection)
            if args.reviews:
                ledger = ReviewLedger.model_validate_json(_read(args.reviews))
                result = {"status": "verified", **validate_selected_reviews(manifest, sha, selection, ledger)}
            else:
                draft = ReviewDraft.model_validate_json(_read(args.draft))
                validate_draft(manifest, sha, selection, draft)
                result = {"status": "valid_non_annotation_draft", "selected_images": len(selection["images"]),
                          "independent_reviews_created": 0, "semantic_accuracy": None}
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
