# Independent visual review: reviewer guide

Review **13 public ABO images, 12 listing groups and 13 cases in each of two
recorded local NVIDIA runs**: 26 output assessments. The single-view and paired-view
fan cases share one product group. These are catalog views, not customer returns
or AMD inference. All frozen assessments remain pending.

## 1. Open the complete package

Use Chrome or Edge. In File Explorer, open:

`A:\hackathon\ReKit\var\mission06-offline\block-b-independent-review\index.html`

Or run this in PowerShell:

```powershell
Start-Process 'A:\hackathon\ReKit\var\mission06-offline\block-b-independent-review\index.html'
```

On another computer, obtain the **entire folder**, with subfolders intact,
through an owner-approved private channel. No installation, sign-in or ReKit
server is needed. Keep the frozen folder unchanged. Review works locally;
attribution links open external websites.

Save downloads in a separate private folder. Examples use
`A:\hackathon\ReKit\var\mission06-offline\reviewers\reviewer-01`; replace
`reviewer-01` with an owner-agreed identifier and use it consistently. Keep
credentials and personal contact details out of notes.

## 2. Inspect originals before predictions

Click **Open the image-only review gallery**. Enter **Reviewer identity**.
For all 13 images:

1. Wait for **Original image loaded.** Use **Open original at full resolution**
   for small details. Stop on missing images and ask the owner to restore them.
2. Describe visible attributes in **Visible attributes / support notes**.
   Answer the three visible-support questions explicitly. Transcribe readable
   markings exactly, one per line. A visible but unreadable marking means Yes
   with no invented transcription; explain the limitation in the ambiguity field.
3. Supply identity/revision labels only when visibly supported. Listing metadata
   is not visual proof. Appearance cannot establish hidden function or safety.
4. Check **I independently reviewed this original image and personally supplied
   these judgments.** only when that statement is true for your own work.

Click **Save non-annotation draft** regularly. It downloads
`image-review-draft.json`, preserving unfinished form text, **not completed
reviews**. To resume, use **Load non-annotation draft**; every declaration resets
and must be considered again. Keep each download under a new versioned name.

Click **Export image review ledger**, saving `image-reviews.json` outside the
package. Only declared images carry judgments; unchecked forms export as empty
pending entries. Save their text as a draft first. Export the image ledger before
opening predictions to avoid influencing your initial observations.

## 3. Assess both recorded outputs

Return to the landing page. Open **baseline assessment** and **after assessment**
in separate tabs. The two pages have the same title, so keep track of the address
ending in `output-baseline/index.html` versus `output-after/index.html`.
All 13 forms are on each page. Compare matching `case-01` through `case-13`.

Expand **Model suggestions — unverified** after inspecting the originals.
`status: succeeded` means the recorded software call succeeded, not that its
claims are true. `validated_output` is structured model content; `raw_output`
is exact response text, also available through **baseline exact text** / **after
exact text**. Assess claims throughout the response.

| Question | Where to record your answer |
| --- | --- |
| Which observations help an operator, and which pixels support them? | **Review notes: appearance, ambiguity, and supporting pixels** |
| Is an identity, revision, marking or cited input unsupported? | Corresponding **Identity**, **Revision**, **Marking** or **Do the cited images support the claims?** choice, with quoted claims and image references in notes |
| Was readable text missed or misread? | Notes; optionally the two transcription fields below |
| Does repetition obscure the answer? | Notes, quoting examples or stating none observed |
| Is the response incomplete, or is abstention justified? | Notes and **Does the uncertainty or abstention fit the available evidence?** |
| Would another requested view resolve a specific uncertainty? | **Would the suggested view help?** and a reason in notes |

Choose **Supported / useful** only where the visible evidence supports the
claim/request; **Unsupported / unhelpful** where it does not. Choose **No such
claim/request** if absent, or **Undetermined** if unsure. Explain mixed claims in
notes: these choices assess cases, not individual claims.

For an exact-text comparison, check **Compare these transcriptions (an empty
string means no readable text)**. Enter your independently observed text in
**Readable marking: human transcription** and the corresponding recorded model
text in **Corresponding model transcription**. This comparison requires an
explicit supported/unsupported **Marking** judgment. Leave it unchecked if the
original is too unclear.

Only after personally assessing a case, supplying support notes and truthfully
meeting the independence requirement, check **I personally reviewed these images
and this output.** The export records an independence declaration automatically.
Identity and independence are self-declared, not authenticated. If prior involvement
prevents that declaration, leave it pending and tell the owner. Do not obtain
judgments from an AI assistant or copy another reviewer's answers.

## 4. Save three separate result files

Enter **Human reviewer** at the bottom of each output page. Click **Download
case assessments** on each. Both downloads use the same default filename,
`case-assessments.json`; immediately rename them outside the package:

- `image-reviews.json` — original-image judgments from step 2.
- `baseline-assessments.json` — the baseline tab's export.
- `after-assessments.json` — the after tab's export.

**Output pages have no autosave, draft save or import.** Unchecked output forms
are omitted from exports. Before closing/reloading, export completed cases and
save unfinished work in private notes. Never declare a review just to save text.
Prefer one session per variant. If splitting work, keep separate dated batches
and tell the owner: the page cannot restore or merge them. Never overwrite an
earlier batch or frozen template. Confirm all files in the browser Downloads list;
a download does not itself establish reviewed cases.

## 5. Have the owner validate the files

From PowerShell at `A:\hackathon\ReKit`, validate the unchanged package and the
three actual exported files (adjust the private review folder as needed):

```powershell
Set-Location 'A:\hackathon\ReKit'
.\.venv\Scripts\python.exe -B evaluation/package_product_review.py check --package var/mission06-offline/block-b-independent-review --image-reviews var/mission06-offline/reviewers/reviewer-01/image-reviews.json --baseline-assessments var/mission06-offline/reviewers/reviewer-01/baseline-assessments.json --after-assessments var/mission06-offline/reviewers/reviewer-01/after-assessments.json
```

Success means exit code `0` and `"status": "verified"`. Inspect
`images.selected_reviewed`, `images.selected_pending`, and each variant's
`reviewed_cases` / `pending_cases`; a full declared set would be 13 / 0 in each.
Valid partial reviews remain partial. On failure, preserve the files and give
the owner the error; do not alter hashes or templates to make them pass.

To check an image draft without declaring any reviews:

```powershell
.\.venv\Scripts\python.exe -B evaluation/image_review.py check --manifest var/mission06-offline/block-b-independent-review/subset-manifest.json --root var/mission06-offline/block-b-independent-review --selection var/mission06-offline/block-b-independent-review/image-review/selection.json --draft var/mission06-offline/reviewers/reviewer-01/image-review-draft.json
```

That returns `valid_non_annotation_draft`, not completed review. For an optional
second reviewer, keep their exports separate; the package checker accepts
`--second-baseline-assessments` and `--second-after-assessments`. The suggested
first four listing groups cover cases **01, 02, 03, 04 and 13** because cases
01 and 13 share the fan group. Review independently before discussing differences.

Validation checks integrity, provenance and format, not independence or correctness.
Pending, undetermined and absent claims are excluded from supported/unsupported
metric denominators; zero eligible cases produce null rates. This development
sample is neither blinded nor representative. Disagreement is not accuracy.

## Readiness check performed for Block C

Installed Chrome `155.0.8059.41` loaded all 13 originals and all 26 exact recorded
outputs. Pending-only exports matched the frozen templates; a clearly labeled
non-annotation QA note survived image draft save/load without any declaration.
The package/export checker and draft checker passed. Nine desktop/mobile
screenshots were visually inspected; there were no page errors, network requests
or document overflow at 390 pixels. Desktop is preferable for the long side-by-side
assessment: the mobile export footer takes substantial screen space.

All **57 frozen files** remain byte-identical, including the manifest SHA-256
`2288cff86398305823c36d75b666c0b9fbb6e95d40c177e808fea7460fe96497`.
All **13 image reviews and 26 output reviews remain pending**. No human judgments,
completed assessments or assertion of independent review were created by QA.
Private receipts and inspected captures:
[`block-c-review-readiness-20261015-191200`](../var/mission06-offline/block-c-review-readiness-20261015-191200/receipt.json).
An earlier QA selector timeout is retained in the separate `190918` directory;
the corrected harness passed without changing the package or application.
