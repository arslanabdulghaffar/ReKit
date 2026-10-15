# Block D: independent-review handoff

Prepared from accepted Block C, commit
`5c6f437ce1ad6fe0e9a84e9450cac2bcf7ec4568`. This sheet accompanies the unchanged
12-group package. **All 39 assessments are pending:** 13 original-image reviews,
13 baseline-output reviews and 13 after-output reviews. No review is supplied
by this document. The [full guide](independent-review-guide.md) explains every
field and the optional image-draft validation.

## For the reviewer

Your task is to explain what the images actually support and where the recorded
model answers help, overreach or miss something. These are public product-listing
images and local NVIDIA model outputs, not customer-return photographs or AMD
results. There are 13 cases from 12 listing groups; two fan cases share a group.
You may leave an answer undetermined. A useful review does not need to be positive.

1. **Open the whole package.** In Chrome or Edge, open
   `A:\hackathon\ReKit\var\mission06-offline\block-b-independent-review\index.html`.
   On another computer, open `index.html` inside the complete privately supplied
   folder. Keep all its subfolders together and unchanged. No sign-in, server or
   installation is needed. Desktop is easier than a phone for this review.
2. **Review originals first.** Select **Open the image-only review gallery**.
   Enter the owner-agreed reviewer identity. Inspect all 13 images; use **Open
   original at full resolution** for small print. Describe visible evidence,
   transcribe legible markings and explain ambiguity. Do not infer hidden
   function, safety or compatibility. Declare independent review only when true
   of your own work. Export the image ledger before looking at predictions.
3. **Review both answers.** Open **baseline assessment** and **after assessment**
   in separate tabs. Check the address ends in `output-baseline/index.html` or
   `output-after/index.html`; their titles look alike. Review matching cases
   01–13, including exact response text. For each, explain useful observations,
   unsupported claims, missed markings, repetition, incompleteness and whether
   the requested extra view would help. Cite the visible detail and quote the
   relevant model phrase in notes. Choose **Undetermined** when unsure and
   **No such claim/request** when absent. Software `succeeded` is not a truth label.
4. **Save three files.** Enter **Human reviewer** on both output pages. Declare
   a case reviewed only after personally assessing it and meeting the stated
   independence requirement. Use the buttons and filenames below. The output
   export automatically includes an independence declaration: if prior involvement
   prevents that declaration, leave it pending and tell the owner. Do not obtain
   answers from an AI assistant or another reviewer.
5. **Return the files privately.** Send the three exports through the agreed
   private channel, with a note identifying any unfinished cases or saving
   problems. No email address, contact information or credentials belong in
   assessment notes. Keep your originals until the owner confirms validation.

Save outside the frozen package. The owner prepares this folder; another
computer may use an agreed private equivalent:

`A:\hackathon\ReKit\var\mission06-offline\reviewers\reviewer-01\`

| Page / button | Save as, inside that folder |
| --- | --- |
| Image gallery / **Export image review ledger** | `image-reviews.json` |
| Baseline tab / **Download case assessments** | `baseline-assessments.json` |
| After tab / **Download case assessments** | `after-assessments.json` |

Both output pages download `case-assessments.json` by default. Rename immediately
so baseline and after cannot be confused; confirm all three in the browser's
Downloads list. Do not replace frozen templates or an earlier export. For later
batches, use a new dated subfolder with these same three names.

**Saving limitation:** output pages have no autosave, draft reload or import.
Unchecked cases' text is omitted from exports. Export completed cases before
closing; keep unfinished output notes privately, without declaring a review just
to save them. The image page alone has **Save non-annotation draft** and **Load
non-annotation draft**; loading resets declarations. A draft is not an assessment.
Prefer one session per output variant. Tell the owner about partial batches;
the pages cannot merge or restore them.

## Owner handoff and receipt checklist

- [ ] Agree on an actual reviewer, their identifier and any prior involvement.
  Independence is self-declared, not established by this checklist or the software.
- [ ] Supply the complete unchanged package and this sheet privately. Agree on
  a private save folder and return channel. Do not send the repository, credentials
  or unrelated artifacts when only this package is needed.
- [ ] Confirm the reviewer can open an original, distinguish the two output tabs
  and save downloads. Explain the saving limitation before work starts.
- [ ] Receive and preserve the three files without editing judgments or declarations.
  Keep each reviewer and batch separate; request missing files rather than inventing them.
- [ ] Run the read-only validation below against the actual supplied files.
  Preserve failures and ask the reviewer to correct their own export when necessary.
- [ ] Report actual reviewed/pending counts, each metric's eligible denominator
  and exclusions. Review usefulness, omissions, repetition and completeness notes
  explicitly; these notes are not automatically scored.
- [ ] If a second genuine reviewer participates, preserve both accounts and use
  the optional second-review flags in the full guide. Report disagreements without
  replacing either account or treating agreement as accuracy.

From PowerShell at the repository root, after the files actually arrive:

```powershell
Set-Location 'A:\hackathon\ReKit'
.\.venv\Scripts\python.exe -B evaluation/package_product_review.py check --package var/mission06-offline/block-b-independent-review --image-reviews var/mission06-offline/reviewers/reviewer-01/image-reviews.json --baseline-assessments var/mission06-offline/reviewers/reviewer-01/baseline-assessments.json --after-assessments var/mission06-offline/reviewers/reviewer-01/after-assessments.json
```

Require exit code `0` and `"status": "verified"`; read `images.selected_reviewed`
and `images.selected_pending`, then both `variants.*.reviewed_cases` and
`pending_cases`. Full declared coverage would be 13 reviewed / 0 pending in each
of the three sets, but valid partial coverage remains partial. Validation checks
format, frozen hashes and provenance; it does not certify visual truth or independence.

For semantic metrics, pending, undetermined and absent claims are excluded;
zero eligible cases gives a null rate. For disagreement, two different reviewers
must judge the same output and field determinately. Claim absence can participate
in disagreement even though it is excluded from that reviewer's semantic metric.
The sample is neither blinded nor representative; 13 cases are not 13 independent
products. Keep baseline and after results separate.

Block D's read-only package check returned `verified`, 12 groups, 13 originals,
0/13 reviewed images and 0/13 reviewed cases in each output variant. All metric
denominators remain zero. Manifest SHA-256 remains
`2288cff86398305823c36d75b666c0b9fbb6e95d40c177e808fea7460fe96497`.
No actual human export was supplied or validated in preparing this sheet.
