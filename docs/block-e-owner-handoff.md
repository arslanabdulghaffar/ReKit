# Block E: owner capture and reviewer handoff

Use this checklist at accepted Block D commit
`258b169f952bc5cfe1bd71e0ed1a0c1b7867fafd`. All boxes are deliberately unchecked:
they describe owner/reviewer work, not completed recordings or human assessments.
The approved [Block D deck](../var/mission06-submission/block-d-deck-20261015-224720-21fd9f/ReKit-Block-D-candidate.pptx)
and [cover](../var/mission06-submission/block-d-deck-20261015-224720-21fd9f/ReKit-Block-D-cover.png)
remain unchanged. Mission 06 remains open. No new inference is needed for this handoff.

## A. Record and finish the demonstration

The [Block D specification](block-d-capture-edit-specification.md) supplies the
exact 12 shots, captions, narration and credits. Use it alongside this execution
checklist; its four-minute schedule is provisional until a real voice take is
measured. Its software row deliberately identifies the historical Block C
1,485/91 checkpoint, as does the approved deck. Do not silently relabel those
numbers as Block D/E results.

The current media inventory under repository `var/` contains only the selected
Block C silent-stills MP4 and its earlier draft. No browser-motion clip or voice
recording was found there; this was not a search of the whole computer. Existing
screenshots and receipts are real recorded evidence, but they are not motion
footage. The checklist below creates the missing motion and narration manually.

| Stage | Owner action | Continue only when |
| --- | --- | --- |
| 1. Prepare | Run the fresh-folder command below. Copy its printed path into OBS's recording-path field; keep it outside cloud sync. Record source commit and intended filenames in private notes. | Folder exists with owner/SYSTEM/Administrators access; no earlier take will be overwritten. |
| 2. Configure OBS | Open installed `C:\Program Files\obs-studio\bin\64bit\obs64.exe` manually. Create **Profile → New** and **Scene Collection → New**, named `ReKit Block E`. Use 1920×1080, 30 fps, local MKV recording and that folder. Use only **Window Capture**, with Desktop Audio and unused microphones disabled. | Preview shows only the intended browser or a clean nonsensitive test window. No streaming, desktop-wide capture or new plugin is enabled. |
| 3. Check microphone | Add **Audio Input Capture** for the intended microphone. Record 15 seconds of the opening narration. Stop and play the saved file; check readable framing, intelligible voice, no echo or clipped peaks. Target roughly −12 to −6 dB while speaking. | Actual test picture/audio passes. Installation alone is not a verified recorder or microphone. |
| 4. Capture canonical motion | Run the commands below. After automatic sign-in, select the ReKit browser in OBS and start recording. Let automation finish without interacting. Stop before the final hold expires. | No sign-in token, terminal, notification or unrelated window entered the take. Missed opening states use labeled stills, not recreated clicks. |
| 5. Check replay receipts | Preserve the newly printed `artifacts:` directory. Run the receipt check below after launcher cleanup. | Both receipts pass, temporary state/credentials are removed and error lists are empty. A movie file alone does not prove workflow success. |
| 6. Record narration | Read the 12 narration paragraphs in the D specification. Record short takes locally with a second of quiet at each end; name them by shot/take number. Measure actual duration. Keep the AMD paragraph on its own track. | Every spoken claim matches the selected run/source. Actual audio exists and has been heard, not merely scripted. |
| 7. Edit | Use the owner's existing local editor. Place actual motion or clearly labeled source stills on a 1920×1080 timeline, preserving aspect ratio. Use the D captions, simple cuts, readable detail crops and source credits. | The local editor can import the files and export a review copy. Editor availability is not established here; do not install or upload to a cloud editor automatically. |
| 8. Review export | Export a fresh file, e.g. `ReKit-Block-E-review-01.mp4`. Watch and listen from beginning to end. Record actual duration, dimensions, size and SHA-256. | Owner approves the entire picture/audio, provenance, privacy, captions and credits against confirmed event media requirements. Approval to review is not approval to publish or submit. |

- [ ] Stages 1–3 passed; preserve the 15-second sample and settings notes.
- [ ] Stage 4 captured genuine application motion, or the edit explicitly uses stills.
- [ ] Stage 5 receipts passed; source run directory and uncut clip are retained.
- [ ] Stages 6–7 produced measured narration and a fresh review export.
- [ ] Stage 8 passed; record owner decision and any requested corrections privately.

Create the private capture folder first. This changes only a new local directory;
it starts no recorder or inference. Stop on any error. The generated path is the
one to use in OBS and the editor:

```powershell
$ErrorActionPreference = 'Stop'
$captureParent = Get-Item -LiteralPath 'A:\hackathon\ReKit\var\mission06-offline' -Force
$captureAncestor = $captureParent
while ($null -ne $captureAncestor) {
    if ($captureAncestor -isnot [IO.DirectoryInfo] -or
        ($captureAncestor.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Capture parent must be a real directory, without junctions or symlinks.'
    }
    $captureAncestor = $captureAncestor.Parent
}
$captureDir = Join-Path $captureParent.FullName ('block-e-recording-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,6))
if (Test-Path -LiteralPath $captureDir) { throw 'Refusing to reuse an existing recording folder.' }
[void][IO.Directory]::CreateDirectory($captureDir)
$captureAcl = [Security.AccessControl.DirectorySecurity]::new()
$captureAcl.SetAccessRuleProtection($true, $false)
foreach ($captureIdentity in @([Security.Principal.WindowsIdentity]::GetCurrent().User,
    [Security.Principal.SecurityIdentifier]::new('S-1-5-18'),
    [Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))) {
    $captureAcl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new(
        $captureIdentity, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow'))
}
Set-Acl -LiteralPath $captureDir -AclObject $captureAcl
Write-Output $captureDir
```

Use PowerShell at the repository root. The first command checks prerequisites
without starting a browser, loading a model or performing inference:

```powershell
Set-Location 'A:\hackathon\ReKit'
git rev-parse HEAD
.\.venv\Scripts\python.exe -B evaluation/run_demo.py --mode canonical-recovery --check
if ($LASTEXITCODE -ne 0) { throw 'Preflight failed. Resolve the reported prerequisite before recording.' }
.\.venv\Scripts\python.exe -B evaluation/run_demo.py --mode canonical-recovery --headed --slow-mo-ms 300 --hold-seconds 120
if ($LASTEXITCODE -ne 0) { throw 'Replay failed. Preserve its receipts and inspect cleanup before using the take.' }
```

**Start OBS only after the workbench appears.** Never record a populated operator
token field, even masked. Automation may advance before recording starts; the
existing intake still covers that gap honestly. During the final 120-second hold,
manual lineage scrolling is extra footage outside the automated acceptance checks.
The launcher closes its owned processes afterward. It does not record a movie.

After cleanup, paste only the new run folder path at this local prompt:

```powershell
$recordedRun = Read-Host 'Full path printed after artifacts: for this canonical run'
$runReceipt = Get-Content -LiteralPath (Join-Path $recordedRun 'runner-result.json') -Raw | ConvertFrom-Json
$acceptanceReceipt = Get-Content -LiteralPath (Join-Path $recordedRun 'acceptance-result.json') -Raw | ConvertFrom-Json
if ($runReceipt.status -ne 'passed' -or $runReceipt.browser_status -ne 'passed' -or
    $runReceipt.browser_exit_code -ne 0 -or -not $runReceipt.temporary_state_removed -or
    -not $runReceipt.credentials_removed -or $null -ne $runReceipt.error -or
    @($runReceipt.cleanup_errors).Count -ne 0 -or @($runReceipt.reporting_errors).Count -ne 0 -or
    -not $acceptanceReceipt.passed -or -not $acceptanceReceipt.canonical_case -or
    $acceptanceReceipt.inference_executed -or @($acceptanceReceipt.page_errors).Count -ne 0 -or
    $acceptanceReceipt.competing_approval_status -ne 409 -or
    $acceptanceReceipt.completed_kits -ne 2 -or $acceptanceReceipt.consumed_components -ne 4) {
    throw 'Replay or cleanup gate failed. Preserve the take and receipts; do not label it passed.'
}
'Canonical replay and cleanup receipts passed; movie and audio review are still required.'
```

Use original local NVIDIA captures from
`var/mission02-acceptance/run-ai-l0094ajl/`; no new product replay is requested.
For a stills-only canonical edit, use the selected Block C source captures listed
in the D specification. For a fresh motion take, use its own run and receipts.
Do not borrow timings from another run.

Keep these boundaries visible throughout:

- **Local NVIDIA / ABO catalog views / simulated intake** for original-product
  inspection. The recorded output stays unverified and the component held.
- **Separate synthetic recovery / scripted operator roles / CPU optimizer** for
  B-to-A correction, modeled economics, reservation conflict and kit records.
  Saved baseline/high-labor plans are separate proposals; only baseline completes.
- **AMD visual inference pending / Mission 06 open** in a replaceable ending.
  Preserve the original 2/6 ledger. A support reply is not execution evidence.
- Mark stills **RECORDED STILL · 15 OCT 2026**, and tight crops **DETAIL CROP**.
  New motion is **RECORDED APPLICATION REPLAY**. Never fabricate activity over stills.

If necessary, use OBS **File → Remux Recordings** to create an MP4 copy of an MKV;
preserve the original. To record the final export's size and hash after full playback:

```powershell
$reviewMovie = Read-Host 'Full path to the new review movie'
Get-Item -LiteralPath $reviewMovie | Select-Object Name, Length
Get-FileHash -LiteralPath $reviewMovie -Algorithm SHA256
```

Record duration/dimensions from the actual editor or player; these commands do
not validate codecs, audio or timing. The existing 240.220-second silent-stills
draft has no audio and is not the completed demonstration. Keep full ABO/model
credits from the D specification. Confirm the actual submission cutoff and form
limits; no deadline, public URL, license change or submission is established here.

## B. Hand the frozen review package to a genuine reviewer

All **39 assessments remain pending**: 13 images and 13 outputs for each of two
variants, spanning 12 listing groups. The [one-sheet reviewer instructions](block-d-reviewer-handoff.md#for-the-reviewer)
are the handout; the [full field guide](independent-review-guide.md) resolves edge
cases. No new judgments or independence declarations are created by this checklist.

Owner:

- [ ] Agree on reviewer identifier, prior involvement, a private return channel
  and a save folder. Supply the entire unchanged
  `var/mission06-offline/block-b-independent-review/` folder privately.
- [ ] Confirm the reviewer can open `index.html` in Chrome/Edge, inspect an
  original and save downloads. Explain the saving limitation before work starts.
- [ ] Keep a separate folder per person and batch. Suggested first batch:
  `A:\hackathon\ReKit\var\mission06-offline\reviewers\reviewer-01\`.

Reviewer:

- [ ] Inspect originals first; export the image ledger before predictions.
  Describe only visible support and uncertainty. Do not infer hidden function/safety.
- [ ] Assess all cases in each output tab. Distinguish the address endings
  `output-baseline/index.html` and `output-after/index.html`; titles look alike.
  Review useful observations, unsupported claims, missed markings, repetition,
  incomplete answers and whether requested views would help.
- [ ] Declare personal/independent review only if true. The output export includes
  an independence declaration. If unable to make it, leave the case pending and
  tell the owner. Do not use AI-generated judgments or copy another reviewer.
- [ ] Save the following three separate files and confirm their names in Downloads:

| Source button | Exact filename in the agreed private folder |
| --- | --- |
| **Export image review ledger** | `image-reviews.json` |
| Baseline **Download case assessments** | `baseline-assessments.json` |
| After **Download case assessments** | `after-assessments.json` |

Both output downloads default to `case-assessments.json`; rename immediately.
Output pages have **no autosave, draft restore or import**. Undeclared form text
is omitted from exports. Save completed cases before closing; keep unfinished
notes privately rather than declaring completion to save text. Only the image
page has a non-annotation draft; loading it resets declarations. Preserve earlier
batches instead of overwriting or trying to merge them in the page.

Owner, once genuine files arrive:

- [ ] Preserve the supplied files as received. Run the exact read-only command
  in [D's validation section](block-d-reviewer-handoff.md#owner-handoff-and-receipt-checklist)
  with the three actual paths. Require exit `0` and `status: verified`.
- [ ] Report image and per-variant reviewed/pending counts, each metric's eligible
  denominator and exclusions. Valid partial reviews remain partial. Zero eligible
  cases yield null rates; notes are not automatically scored.
- [ ] If a second reviewer participates, preserve both accounts and use the
  existing optional second-review flags. Report disagreement separately from
  semantic metrics and accuracy. Validation does not authenticate independence.

No reviewer files have been supplied in this continuation. Missing human review
remains an evidence gap, not a reason to fill fields automatically.
