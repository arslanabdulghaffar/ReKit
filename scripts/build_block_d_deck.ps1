# Separate Block D candidate from accepted Block C and preserved Block B evidence. Original deck preserved.
# Installed PowerPoint only. No network, downloads, inference, or operational inventory.
[CmdletBinding()]
param([string]$OutputDirectory = '')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$privateRoot = [IO.Path]::GetFullPath((Join-Path $repo 'var/mission06-submission'))
$productPath = Join-Path $repo 'var/mission02-acceptance/run-ai-l0094ajl'
$recoveryPath = Join-Path $repo 'var/mission02-acceptance/run-canonical-jheftnar'
$casePath = Join-Path $repo 'var/mission06-offline/canonical-case-b1-first'
$evidencePaths = @(
    (Join-Path $productPath 'product-inference-results.json'),
    (Join-Path $productPath 'acceptance-result.json'),
    (Join-Path $recoveryPath 'acceptance-result.json'),
    (Join-Path $casePath 'receipt.json'),
    (Join-Path $repo 'var/mission06-offline/block-c-final-verification.json')
)
$records = @($evidencePaths | ForEach-Object { Get-Content -LiteralPath $_ -Raw -Encoding UTF8 | ConvertFrom-Json })
$product = $records[0]; $productGate = $records[1]; $recovery = $records[2]; $case = $records[3]; $verification = $records[4]
if (-not $product.passed -or -not $productGate.passed -or -not $recovery.passed -or
    $product.actual_run.start.configuration.provider -ne 'local-transformers' -or
    $productGate.inference_runs -ne 1 -or $productGate.held_components -ne 1 -or $productGate.completed_kits -ne 0 -or
    $recovery.managed_images -ne 9 -or $recovery.competing_approval_status -ne 409 -or
    $recovery.modeled_value_cents -ne 17500 -or $recovery.completed_kits -ne 2 -or $recovery.consumed_components -ne 4 -or
    $verification.head -ne '5c6f437ce1ad6fe0e9a84e9450cac2bcf7ec4568' -or
    $verification.local_validation.backend.passed -ne 1485 -or $verification.local_validation.frontend.passed -ne 91 -or
    -not $case.synthetic -or -not $case.controlled_change.all_other_problem_fields_identical) {
    throw 'Accepted Block C evidence does not match the candidate narrative.'
}
$base = $case.economic_comparison.baseline
$changed = $case.economic_comparison.changed_labor
if ($base.solver_status -ne 'OPTIMAL' -or $changed.solver_status -ne 'OPTIMAL' -or
    $base.alternatives.two_rebuilds.modeled_value_cents -ne 17500 -or $base.alternatives.liquidate_all_returns.modeled_value_cents -ne 10250 -or
    $base.alternatives.retain_all.modeled_value_cents -ne 1600 -or $changed.alternatives.two_rebuilds.modeled_value_cents -ne 7000 -or
    $changed.alternatives.liquidate_all_returns.modeled_value_cents -ne 8500 -or $changed.alternatives.retain_all.modeled_value_cents -ne 1600) {
    throw 'Recorded economic alternatives changed; review the narrative first.'
}
$images = @(
    (Join-Path $recoveryPath 'canonical-correction-history.png'),
    (Join-Path $casePath 'original-images/synthetic-adapter-002-view-3.png'),
    (Join-Path $recoveryPath 'final-inventory.png'),
    (Join-Path $productPath 'product-ai-result-desktop.png')
)
foreach ($path in $images) { if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'Missing original source image.' } }
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $privateRoot ('block-d-deck-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,6))
}
$output = [IO.Path]::GetFullPath($(if ([IO.Path]::IsPathRooted($OutputDirectory)) { $OutputDirectory } else { Join-Path $repo $OutputDirectory }))
if (-not $output.StartsWith($privateRoot + [IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Candidate must stay in a fresh private submission directory.' }
if (Test-Path -LiteralPath $output) { throw 'Refusing to overwrite existing candidate.' }
$cursor = [IO.DirectoryInfo]::new($output)
while ($cursor.FullName -ne $repo) {
    if ($cursor.Exists -and (($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) { throw 'Output cannot traverse a reparse point.' }
    $cursor = $cursor.Parent
    if ($null -eq $cursor) { throw 'Output must remain inside the repository.' }
}
if (Get-Process POWERPNT -ErrorAction SilentlyContinue) { throw 'An existing PowerPoint session is open; do not interfere with it.' }
[IO.Directory]::CreateDirectory($output) | Out-Null
$acl = [Security.AccessControl.DirectorySecurity]::new()
$acl.SetAccessRuleProtection($true,$false)
foreach ($identity in @([Security.Principal.WindowsIdentity]::GetCurrent().User,
    [Security.Principal.SecurityIdentifier]::new('S-1-5-18'),[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))) {
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($identity,'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
}
Set-Acl -LiteralPath $output -AclObject $acl
$renderDir = Join-Path $output 'slides'
[IO.Directory]::CreateDirectory($renderDir) | Out-Null
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem

function Rgb([string]$Hex) {
    return [Convert]::ToInt32($Hex.Substring(0,2),16) + 256 * [Convert]::ToInt32($Hex.Substring(2,2),16) + 65536 * [Convert]::ToInt32($Hex.Substring(4,2),16)
}
$ink = Rgb '153E35'
$cream = Rgb 'F4F6F2'
$lime = Rgb 'D9F18B'
$muted = Rgb '536B60'
$line = Rgb 'CEDACF'
$white = Rgb 'FFFFFF'
$arrow = [char]0x2192
$dash = [char]0x2014
$middot = [char]0x00B7
$checks = [Collections.Generic.List[object]]::new()
$sources = [Collections.Generic.List[object]]::new()
$app = $null
$deck = $null
$failure = $null
$result = $null

function Text($Slide,[string]$Value,[double]$X,[double]$Y,[double]$W,[double]$H,[double]$Size=22,[int]$Color=$ink,[bool]$Bold=$false) {
    $shape = $Slide.Shapes.AddTextbox(1,$X,$Y,$W,$H)
    $shape.Name = 'Text-' + $Slide.SlideIndex + '-' + $Slide.Shapes.Count
    $shape.TextFrame.MarginLeft = 0
    $shape.TextFrame.MarginRight = 0
    $shape.TextFrame.MarginTop = 0
    $shape.TextFrame.MarginBottom = 0
    $shape.TextFrame.WordWrap = -1
    $shape.TextFrame.AutoSize = 0
    $range = $shape.TextFrame.TextRange
    $range.Text = $Value
    $range.Font.Name = 'Arial'
    $range.LanguageID = 1033
    $range.Font.Size = $Size
    $range.Font.Color.RGB = $Color
    $range.Font.Bold = $(if ($Bold) { -1 } else { 0 })
    $range.ParagraphFormat.SpaceAfter = 0
    # AddTextbox initially fits its empty/default line. Restore the authored box
    # after setting text, and disable both Office autofit interfaces explicitly.
    $shape.TextFrame2.AutoSize = 0
    $shape.Width = $W
    $shape.Height = $H
    $shape.Left = $X
    $shape.Top = $Y
    return $shape
}

function Rule($Slide,[double]$X,[double]$Y,[double]$W,[int]$Color=$line) {
    $shape = $Slide.Shapes.AddLine($X,$Y,$X+$W,$Y)
    $shape.Line.ForeColor.RGB = $Color
    $shape.Line.Weight = 1
}

function New-Slide([string]$Title,[string]$Subtitle,[bool]$Dark=$false) {
    $slide = $deck.Slides.Add($deck.Slides.Count+1,12)
    $slide.FollowMasterBackground = 0
    $slide.Background.Fill.Solid()
    $slide.Background.Fill.ForeColor.RGB = $(if ($Dark) {$ink} else {$cream})
    $fg = $(if ($Dark) {$cream} else {$ink})
    if ($Title) { [void](Text $slide $Title 48 35 864 54 34 $fg $true) }
    if ($Subtitle) { [void](Text $slide $Subtitle 49 94 863 48 20 $(if ($Dark) {$lime} else {$muted})) }
    [void](Text $slide ('NeuralFoundry  /  ReKit' + (' ' * 2) + $middot + '  15 Oct 2026') 48 510 650 19 11 $(if ($Dark) {$cream} else {$muted}))
    [void](Text $slide ($slide.SlideIndex.ToString('00') + ' / 07') 846 510 66 19 11 $(if ($Dark) {$cream} else {$muted}))
    return $slide
}

function Notes($Slide,[string]$Value) {
    $extra = "`nEvidence sources: docs/canonical-case.md; docs/reports/winning-quality-block-b.md. Private review candidate; no publication or submission."
    if ($Slide.SlideIndex -eq 6) {
        $extra += "`nFull dataset attribution: $($product.dataset_attribution)`nOriginal downloaded bytes are unchanged; the presentation uses a disclosed screenshot crop. Source: https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/README.md ; license: https://creativecommons.org/licenses/by/4.0/ ."
    }
    $Slide.NotesPage.Shapes.Placeholders.Item(2).TextFrame.TextRange.Text = $Value + $extra
}

function Screenshot($Slide,[string]$Path,[double]$X,[double]$Y,[double]$W,[int[]]$Crop) {
    $bitmap = [Drawing.Image]::FromFile($Path)
    try { $pixelWidth = $bitmap.Width; $pixelHeight = $bitmap.Height } finally { $bitmap.Dispose() }
    if ($Crop.Count -ne 4 -or $Crop[0] -lt 0 -or $Crop[1] -lt 0 -or $Crop[2] -le 0 -or $Crop[3] -le 0 -or
        $Crop[0]+$Crop[2] -gt $pixelWidth -or $Crop[1]+$Crop[3] -gt $pixelHeight) { throw 'Invalid native screenshot crop.' }
    $shape = $Slide.Shapes.AddPicture($Path,0,-1,0,0,-1,-1)
    $shape.Name = 'Screenshot-' + [IO.Path]::GetFileNameWithoutExtension($Path)
    $shape.LockAspectRatio = 0
    # Crop's picture/frame geometry avoids the DPI-dependent legacy CropLeft
    # units. Both source axes share one scale; source pixels are not distorted.
    $scale = $W/$Crop[2]
    $cropFrame = $shape.PictureFormat.Crop
    $cropFrame.ShapeWidth = $W
    $cropFrame.ShapeHeight = $Crop[3]*$scale
    $cropFrame.ShapeLeft = $X
    $cropFrame.ShapeTop = $Y
    $cropFrame.PictureWidth = $pixelWidth*$scale
    $cropFrame.PictureHeight = $pixelHeight*$scale
    $cropFrame.PictureOffsetX = ($pixelWidth/2-$Crop[0]-$Crop[2]/2)*$scale
    $cropFrame.PictureOffsetY = ($pixelHeight/2-$Crop[1]-$Crop[3]/2)*$scale
    $shape.Line.Visible = -1
    $shape.Line.ForeColor.RGB = $line
    $shape.Line.Weight = 0.7
    $shape.AlternativeText = 'Original ReKit visual evidence; native PowerPoint crop only. Full original embedded. ' + [IO.Path]::GetFileName($Path)
    $sources.Add([PSCustomObject]@{slide=$Slide.SlideIndex;path=$Path.Substring($repo.Length+1);sha256=(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant();crop_pixels=$Crop})
}



function Evidence-Table($Slide,$Rows,[double]$X,[double]$Y,[double]$W,[double]$H,$Widths,[double]$Size=22) {
    $shape = $Slide.Shapes.AddTable($Rows.Count,$Rows[0].Count,$X,$Y,$W,$H)
    $shape.Name = 'Editable-evidence-table-' + $Slide.SlideIndex
    for ($c=1;$c -le $Widths.Count;$c++) { $shape.Table.Columns.Item($c).Width = $Widths[$c-1] }
    for ($r=1;$r -le $Rows.Count;$r++) {
        for ($c=1;$c -le $Rows[0].Count;$c++) {
            $cell = $shape.Table.Cell($r,$c)
            $cell.Shape.Fill.Solid()
            $cell.Shape.Fill.ForeColor.RGB = $(if ($r -eq 1) {$ink} else {$white})
            $cell.Shape.TextFrame.MarginLeft=12; $cell.Shape.TextFrame.MarginRight=10
            $cell.Shape.TextFrame.MarginTop=11; $cell.Shape.TextFrame.MarginBottom=7
            $range=$cell.Shape.TextFrame.TextRange
            $range.Text=$Rows[$r-1][$c-1]
            $range.Font.Name='Arial'; $range.LanguageID=1033; $range.Font.Size=$Size
            $range.Font.Color.RGB=$(if ($r -eq 1) {$cream} else {$ink})
            $range.Font.Bold=$(if ($r -eq 1) {-1} else {0})
            foreach ($border in 1..4) { $cell.Borders.Item($border).ForeColor.RGB=$line; $cell.Borders.Item($border).Weight=0.5 }
        }
    }
    return $shape
}
function Money([int]$Cents) { return '$' + ($Cents/100.0).ToString('F2',[Globalization.CultureInfo]::InvariantCulture) }
try {
    $app = New-Object -ComObject PowerPoint.Application
    $deck = $app.Presentations.Add(0)
    $deck.PageSetup.SlideWidth=960; $deck.PageSetup.SlideHeight=540

    $s=New-Slide '' '' $true
    [void](Text $s 'ReKit' 48 45 850 85 68 $cream $true)
    [void](Text $s "One return lacks a part.`nAnother may contain it." 51 161 840 108 40 $cream $true)
    [void](Text $s "Compare rebuilding, liquidation and retention`nusing verified evidence and explicit costs." 52 304 814 83 27 $cream)
    [void](Text $s 'AMD visual inference pending' 52 424 846 37 24 $lime $true)
    [void](Text $s 'NeuralFoundry / Local prototype' 52 475 810 29 19 $cream)
    Notes $s 'Core contribution: a bounded decision workflow joining original component evidence, accountable human corrections, approved BOM compatibility, economic CP-SAT choices and atomic component allocation. This is a product contribution, not a claim of first invention or competitor superiority. Local NVIDIA inspection and synthetic recovery are separately demonstrated. AMD execution and integration remain unqualified. Candidate title does not change the submission form or original deck.'

    $s=New-Slide 'Three incomplete returns, one shared pool' 'Synthetic demonstration with four unique physical components.'
    $rows=@(@('Source return','Contents'),@('Bodies return','2 bodies'),@('Adapter return 1','1 adapter'),@('Adapter return 2','1 adapter'))
    [void](Evidence-Table $s $rows 48 155 510 224 @(300,210) 23)
    [void](Text $s 'Approved kit' 605 155 307 37 26 $ink $true)
    [void](Text $s "1 body, revision A`n1 adapter, revision A" 605 205 307 83 26 $ink)
    [void](Text $s 'Humans verify identity and visible condition before eligibility.' 605 311 307 95 22 $muted)
    [void](Text $s 'More images add evidence. They never create extra stock.' 49 420 860 39 25 $ink $true)
    [void](Text $s 'Invented diagrams and scripted decisions. No physical rebuilding or customer outcome is claimed.' 49 471 862 31 17 $muted)
    Notes $s 'Exact source: evaluation/fixtures/canonical_case.json and tests/fixtures/synthetic_recovery.json; approved synthetic catalog standard-kit BOM requires one body and one adapter, revision A, acceptable visible condition. Source IDs: synthetic-return-bodies -> synthetic-body-001,synthetic-body-002; synthetic-return-adapter-001 -> synthetic-adapter-001; synthetic-return-adapter-002 -> synthetic-adapter-002. Nine original diagram assets belong to four component records. No ABO photographs or model outputs feed these kits.'

    $s=New-Slide 'A new view supports a human correction' 'The approved kit rejects B. The operator records A after inspecting a new close-up.'
    Screenshot $s $images[0] 48 151 864 @(291,185,1086,157)
    Screenshot $s $images[1] 48 291 330 @(0,0,720,440)
    [void](Text $s 'Original synthetic close-up' 416 298 496 37 26 $ink $true)
    [void](Text $s "New evidence: version 5.`nHuman correction: A at version 6." 416 354 496 86 26 $ink)
    [void](Text $s 'Earlier B at version 4 and all three original views remain linked.' 416 456 496 49 19 $muted)
    Notes $s 'Sources: canonical case receipt correction.before/before_correction/after and prior_compatibility/corrected_compatibility; actual Block C browser screenshot canonical-correction-history.png. Top screenshot crop x291 y185 w1086 h157 shows the actual previous/latest component and revision fields. The slide emphasizes the revision row; condition/reason/provenance remain in the full embedded screenshot. The entire original screenshot is embedded. The bottom image is the exact original synthetic adapter view 3 PNG, not a product photograph. Initial B assertion is deliberately incorrect scripted human-role input; no model made it. Approved configuration rejects B. Added original view explicitly marks REV A. Correction preserves prior events and supersedes the previous verification. Visual evidence does not establish function or safety.'

    $s=New-Slide 'Labor cost changes the best recovery plan' 'The same verified inventory, BOM, demand and capacity. Only labor rate changes.'
    $rows=@(@('Complete feasible choice','$0.25 / minute','$2.00 / minute'),
        @('Rebuild two kits',(Money $base.alternatives.two_rebuilds.modeled_value_cents),(Money $changed.alternatives.two_rebuilds.modeled_value_cents)),
        @('Liquidate three returns',(Money $base.alternatives.liquidate_all_returns.modeled_value_cents),(Money $changed.alternatives.liquidate_all_returns.modeled_value_cents)),
        @('Retain four components',(Money $base.alternatives.retain_all.modeled_value_cents),(Money $changed.alternatives.retain_all.modeled_value_cents)))
    $table=Evidence-Table $s $rows 48 155 864 210 @(414,225,225) 24
    foreach ($pair in @(@(2,2),@(3,3))) { $cell=$table.Table.Cell($pair[0],$pair[1]); $cell.Shape.Fill.ForeColor.RGB=$lime; $cell.Shape.TextFrame.TextRange.Font.Bold=-1 }
    [void](Text $s 'At $0.25/min: rebuild. At $2.00/min: liquidate.' 49 388 862 45 29 $ink $true)
    [void](Text $s 'Rebuilding uses 60 labor minutes. Whole-return liquidation uses 10.' 49 438 862 31 22 $ink)
    [void](Text $s 'Same four parts, two-kit demand and 60-minute capacity. CPU CP-SAT proves both optima.' 49 474 862 23 16 $muted)
    [void](Text $s 'Modeled synthetic USD. Retention is noncash. Customer savings remain unmeasured.' 49 496 862 18 13 $muted)
    Notes $s 'All table values come from receipt.json/economic_comparison. Each complete allocation passes the existing evaluate_selection validator with identical frozen inputs. Baseline rebuild: gross 20,000 - labor 1,500 - processing 1,000 = 17,500 cents. Liquidation: 10,500 - 250 = 10,250 cents. Retention: 1,600 cents noncash. Changing only labor from 25 to 200 cents/minute gives rebuild 20,000 - 12,000 - 1,000 = 7,000 cents, liquidation 10,500 - 2,000 = 8,500 cents, retention 1,600 cents. Capacity is 60 minutes, each kit requires 30 minutes, demand limit is two. Body-return liquidation: 5 minutes and 8,000 cents. Adapter returns: 2 minutes and 1,000 cents, 3 minutes and 1,500 cents. Donor value: body 600 cents, adapter 200 cents. Retention is not subtracted twice. Existing CP-SAT 9.15.6755 reports OPTIMAL and zero gaps. Independent exact-cover tests verify these tiny problems. Equal-value physical pairings may exist. This table contains feasible examples, not an exhaustive frontier. Only the baseline plan was approved for completion.'

    $s=New-Slide 'Exclusive reservations, traceable kit records' 'A competing approval returns HTTP 409. The original four-part reservation stays intact.'
    Screenshot $s $images[2] 48 155 864 @(291,940,1086,340)
    [void](Text $s 'Two kit records. Four unique source components.' 49 448 862 41 27 $ink $true)
    [void](Text $s 'Synthetic completion. Evidence links and the approved audit preserve the full history.' 49 489 862 24 17 $muted)
    Notes $s 'Actual Block C final-inventory.png native crop x291 y940 w1086 h340. The crop enlarges both kit headings, all four component IDs, source returns and current evidence links. Audit/completion details remain in the full original embedded screenshot and source app. Browser acceptance records a competing approval returning HTTP 409, unchanged reservations, no extra approval audit, two completed kit records, four consumed components, four baseline audit events and an idempotent completion retry returning HTTP 200. The canonical API also rejects stale correction (409), stale plan approval (409), and unconfirmed completion (422). Links show current evidence. The plan audit retains its immutable approval snapshot. Component pairs reflect this particular successful run, not a unique optimization solution. These are software kit records. No physical assembly is claimed.'

    $s=New-Slide 'Structured vision still needs human review' 'Two original ABO views. One local NVIDIA request. The component stays held.'
    Screenshot $s $images[3] 48 146 864 @(287,111,1097,407)
    [void](Text $s 'Qwen3-VL-2B / RTX 4080 SUPER. Block C tests: 1,485 backend, 91 frontend.' 49 475 862 27 18 $ink $true)
    [void](Text $s 'ABO (c) Amazon.com, CC BY 4.0. Screenshot crop. Simulated intake. Independent accuracy review pending.' 49 500 862 16 11 $muted)
    $m=$product.actual_run.outcome.metrics
    Notes $s "Actual local NVIDIA output: var/mission02-acceptance/run-ai-l0094ajl/product-inference-results.json. Repeated appearance strings, unfinished uncertainty and redundant back-view request remain unedited. One component stays held, with zero verifications, reservations or kits. Empty candidates without a catalog demonstrate enforced contract behavior, not semantic accuracy. Inference $($m.inference_seconds) seconds, provider request $($m.request_seconds) seconds and browser 57.9 seconds are distinct single observations. Model: Qwen/Qwen3-VL-2B-Instruct, revision 89644892e4d85e24eaac8bacfd4f463576704203, Apache-2.0: https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct/blob/89644892e4d85e24eaac8bacfd4f463576704203/README.md . Accepted Block C software counts: 1485 backend, 91 frontend. Commit 5c6f437ce1ad6fe0e9a84e9450cac2bcf7ec4568. CI: https://github.com/arslanabdulghaffar/ReKit/actions/runs/38721022027 (private). The review package has 12 groups, 13 original images and 26 outputs, all pending. Eligible independent semantic denominators remain zero. Qwen model quality remains unqualified. Current Block D checks belong in its separate report. The local NVIDIA capture is the preserved Block B run; Block C verified its environment without another inference request."

    $s=New-Slide 'The recovery decision stays accountable' 'Original evidence remains linked through correction and kit completion.' $true
    [void](Text $s "People verify the evidence.`nApproved rules control compatibility." 49 166 861 93 32 $cream $true)
    [void](Text $s "CP-SAT compares permitted recovery choices.`nAtomic reservations prevent shared parts." 49 287 861 83 27 $cream)
    [void](Text $s 'AMD visual inference pending' 49 397 862 39 27 $lime $true)
    [void](Text $s '2/6 attempts returned HTTP 400. Provider clarification, fresh quota and owner approval are required.' 49 445 862 45 19 $cream)
    [void](Text $s 'Synthetic recovery and local NVIDIA are separate. Independent review and customer validation remain pending.' 49 494 862 20 14 $cream)
    Notes $s 'The original persistent AMD generation ledger remains 2/6. Both MiMo-V2.6-Flash POST attempts returned HTTP 400. No successful AMD visual/schema qualification or application integration exists. The owner reports that technical support directed them to the Chinese Radeon Cloud portal. Unable to access it, the owner submitted account support under Login. No definitive API-contract resolution has arrived. No new AMD call is authorized. The existing remote adapter preserves strict schema/domain validation, server-only credentials, an exact HTTPS allowlist, and no automatic retry, model substitution or fallback. Shared-service GPU, runtime and deployed-revision metadata remain unverified. Any future call requires reliable new information, fresh quota and explicit owner approval. A successful response still needs provenance-linked ReKit application integration before Mission 06 can close. Local NVIDIA execution is separate from AMD. No license, publication, deployment, spending or submission decision was made. Evolus remains optional and unimplemented.'

    foreach ($slide in $deck.Slides) {
        foreach ($shape in $slide.Shapes) {
            if ($shape.Left -lt -0.5 -or $shape.Top -lt -0.5 -or $shape.Left+$shape.Width -gt 960.5 -or $shape.Top+$shape.Height -gt 540.5) { throw "Shape outside slide $($slide.SlideIndex): $($shape.Name)" }
            if ($shape.HasTextFrame -eq -1 -and $shape.TextFrame.HasText -eq -1) {
                $available=$shape.Height-$shape.TextFrame.MarginTop-$shape.TextFrame.MarginBottom
                if ($shape.TextFrame.TextRange.BoundHeight -gt $available+1) { throw "Text overflow on slide $($slide.SlideIndex): $($shape.Name)" }
            }
            if ($shape.HasTable -eq -1) {
                for ($r=1;$r -le $shape.Table.Rows.Count;$r++) { for ($c=1;$c -le $shape.Table.Columns.Count;$c++) {
                    $cellShape=$shape.Table.Cell($r,$c).Shape
                    if ($cellShape.TextFrame.TextRange.BoundHeight -gt $cellShape.Height-$cellShape.TextFrame.MarginTop-$cellShape.TextFrame.MarginBottom+1) { throw "Table overflow on slide $($slide.SlideIndex)" }
                } }
            }
        }
        $checks.Add([PSCustomObject]@{slide=$slide.SlideIndex;shapes=$slide.Shapes.Count;geometry='passed';text_extents='passed'})
    }
    if ($deck.Slides.Count -ne 7) { throw 'Candidate requires exactly seven slides.' }
    $pptx=Join-Path $output 'ReKit-Block-D-candidate.pptx'
    $deck.SaveAs($pptx,24)
    foreach ($slide in $deck.Slides) { $slide.Export((Join-Path $renderDir ('slide-{0:00}.png' -f $slide.SlideIndex)),'PNG',1920,1080) }
    Copy-Item -LiteralPath (Join-Path $renderDir 'slide-01.png') -Destination (Join-Path $output 'ReKit-Block-D-cover.png')
    $version=$app.Version
    $deck.Close(); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($deck); $deck=$null
    $app.Quit(); [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($app); $app=$null
    # Normalize only package metadata after closing Office; preserve native slides/media.
    $metadataZip=[IO.Compression.ZipFile]::Open($pptx,[IO.Compression.ZipArchiveMode]::Update)
    try {
        $entry=$metadataZip.GetEntry('docProps/core.xml')
        $reader=[IO.StreamReader]::new($entry.Open())
        try { [xml]$core=$reader.ReadToEnd() } finally { $reader.Dispose() }
        foreach ($property in @(
            @('dc','title','http://purl.org/dc/elements/1.1/','ReKit - Visual Recovery Intelligence'),
            @('dc','creator','http://purl.org/dc/elements/1.1/','NeuralFoundry'),
            @('cp','lastModifiedBy','http://schemas.openxmlformats.org/package/2006/metadata/core-properties','NeuralFoundry'),
            @('dc','description','http://purl.org/dc/elements/1.1/','Private Block D review candidate. AMD qualification pending.')
        )) {
            $node=$core.DocumentElement.SelectSingleNode("*[local-name()='$($property[1])']")
            if ($null -eq $node) { $node=$core.CreateElement($property[0],$property[1],$property[2]); [void]$core.DocumentElement.AppendChild($node) }
            $node.InnerText=$property[3]
        }
        $entry.Delete()
        $writer=[IO.StreamWriter]::new($metadataZip.CreateEntry('docProps/core.xml').Open(),[Text.UTF8Encoding]::new($false))
        try { $core.Save($writer) } finally { $writer.Dispose() }
    } finally { $metadataZip.Dispose() }
    $zip=[IO.Compression.ZipFile]::OpenRead($pptx)
    $xmlChecks=[Collections.Generic.List[object]]::new()
    try {
        foreach ($i in 1..7) {
            $entry=$zip.GetEntry("ppt/slides/slide$i.xml")
            if ($null -eq $entry) { throw 'Missing slide XML.' }
            $reader=[IO.StreamReader]::new($entry.Open())
            try { [xml]$xml=$reader.ReadToEnd() } finally { $reader.Dispose() }
            $ns=[Xml.XmlNamespaceManager]::new($xml.NameTable)
            $ns.AddNamespace('p','http://schemas.openxmlformats.org/presentationml/2006/main'); $ns.AddNamespace('a','http://schemas.openxmlformats.org/drawingml/2006/main')
            $tables=$xml.SelectNodes('//a:tbl',$ns).Count
            $pictures=$xml.SelectNodes('//p:pic',$ns).Count
            $nativeText=$xml.SelectNodes('//p:sp[p:txBody/a:p/a:r/a:t]',$ns).Count
            if ($nativeText -lt 4 -or ($i -in @(2,4) -and $tables -ne 1) -or $null -eq $zip.GetEntry("ppt/notesSlides/notesSlide$i.xml")) { throw "Editability/source notes failed slide$i" }
            $xmlChecks.Add([PSCustomObject]@{slide=$i;native_text_shapes=$nativeText;native_tables=$tables;pictures=$pictures})
        }
    } finally { $zip.Dispose() }
    $inputReceipts=@($evidencePaths | ForEach-Object { [PSCustomObject]@{path=$_.Substring($repo.Length+1);sha256=(Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash.ToLowerInvariant()} })
    $result=[ordered]@{status='passed';deck=$pptx;deck_sha256=(Get-FileHash -LiteralPath $pptx -Algorithm SHA256).Hash.ToLowerInvariant();slide_count=7;render_size_pixels=@(1920,1080);slide_size_points=@(960,540);font='Arial';powerpoint_version=$version;source_checkpoint=$verification.head;input_receipts=$inputReceipts;sources=$sources;geometry=$checks;editability=$xmlChecks;visual_review='Required separately after native export';authoring='Existing local PowerPoint; artifact runtime unavailable';local_access='Current user, SYSTEM, Administrators';published=$false}
} catch { $failure=$_; $result=[ordered]@{status='failed';error=$_.Exception.Message;output=$output} }
finally {
    if ($null -ne $deck) { try { $deck.Close() } finally { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($deck) } }
    if ($null -ne $app) { try { $app.Quit() } finally { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($app) } }
    [GC]::Collect(); [GC]::WaitForPendingFinalizers()
    if ($null -ne $result) { [IO.File]::WriteAllText((Join-Path $output 'build-result.json'),($result|ConvertTo-Json -Depth 12),[Text.UTF8Encoding]::new($false)) }
}
if ($null -ne $failure) { throw $failure }
[PSCustomObject]@{status=$result.status;deck=$pptx;output=$output}|ConvertTo-Json
