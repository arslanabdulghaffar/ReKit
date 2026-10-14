# Native, local PowerPoint authoring. Requires the existing Windows PowerPoint install.
# No network, installation, inference, or application services are used.
[CmdletBinding()]
param(
    [string]$ProductRun = 'var/mission02-acceptance/run-ai-5p7lbguu',
    [string]$RecoveryRun = 'var/mission02-acceptance/run-g563yhm_',
    [string]$OutputDirectory = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$privateRoot = [IO.Path]::GetFullPath((Join-Path $repo 'var/mission05-submission'))
$varRoot = [IO.Path]::GetFullPath((Join-Path $repo 'var')) + [IO.Path]::DirectorySeparatorChar

function Resolve-PrivateInput([string]$RelativePath) {
    $path = [IO.Path]::GetFullPath($(if ([IO.Path]::IsPathRooted($RelativePath)) { $RelativePath } else { Join-Path $repo $RelativePath }))
    if (-not $path.StartsWith($varRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Input must be a previously reviewed run under repository var/.'
    }
    if (-not (Test-Path -LiteralPath $path -PathType Container)) { throw "Missing run directory: $RelativePath" }
    return $path
}

$productPath = Resolve-PrivateInput $ProductRun
$recoveryPath = Resolve-PrivateInput $RecoveryRun
$product = Get-Content -LiteralPath (Join-Path $productPath 'product-inference-results.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$productGate = Get-Content -LiteralPath (Join-Path $productPath 'acceptance-result.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$recovery = Get-Content -LiteralPath (Join-Path $recoveryPath 'acceptance-result.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $product.passed -or -not $productGate.passed -or -not $recovery.passed) { throw 'Only successful evidence runs may be presented.' }
if ($productGate.inference_runs -ne 1 -or $productGate.held_components -ne 1 -or $productGate.completed_kits -ne 0 -or
    $productGate.identity_candidates -ne 0 -or $productGate.independent_human_review -ne $false -or
    $product.actual_run.outcome.status -ne 'succeeded' -or $product.actual_run.start.configuration.provider -ne 'local-transformers') {
    throw 'Product evidence differs from this slide narrative; review and update the authored content first.'
}
if ($recovery.returns -ne 3 -or $recovery.physical_components -ne 4 -or $recovery.completed_kits -ne 2 -or
    $recovery.modeled_value_cents -ne 17500 -or $recovery.reserved_before_completion -ne 4 -or $recovery.consumed_components -ne 4) {
    throw 'Recovery evidence differs from this slide narrative; review and update the authored content first.'
}
$images = @(
    (Join-Path $productPath 'product-originals-desktop.png'),
    (Join-Path $productPath 'product-ai-result-desktop.png'),
    (Join-Path $recoveryPath 'final-inventory.png')
)
foreach ($path in $images) { if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw 'A required source screenshot is missing.' } }

if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $privateRoot ('deck-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,6))
}
$output = [IO.Path]::GetFullPath($(if ([IO.Path]::IsPathRooted($OutputDirectory)) { $OutputDirectory } else { Join-Path $repo $OutputDirectory }))
if (-not $output.StartsWith($privateRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Generated deck output must remain in a new directory under var/mission05-submission/.'
}
if (Test-Path -LiteralPath $output) { throw 'Refusing to overwrite an existing output directory.' }
if (Get-Process POWERPNT -ErrorAction SilentlyContinue) { throw 'Close your own PowerPoint session before running this isolated builder.' }
[IO.Directory]::CreateDirectory($output) | Out-Null
$renderDir = Join-Path $output 'slides'
[IO.Directory]::CreateDirectory($renderDir) | Out-Null
Add-Type -AssemblyName System.Drawing
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
    [void](Text $slide ('NeuralFoundry  /  ReKit' + (' ' * 2) + $middot + '  14 Oct 2026') 48 510 650 19 11 $(if ($Dark) {$cream} else {$muted}))
    [void](Text $slide ($slide.SlideIndex.ToString('00') + ' / 07') 846 510 66 19 11 $(if ($Dark) {$cream} else {$muted}))
    return $slide
}

function Notes($Slide,[string]$Value) {
    $extra = "`nPresentation content and limits: docs/submission-content.md; docs/pitch-deck.md."
    if ($Slide.SlideIndex -in @(2,4)) {
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
    $shape.AlternativeText = 'Actual ReKit screenshot; native PowerPoint crop only. Full original embedded. ' + [IO.Path]::GetFileName($Path)
    $sources.Add([PSCustomObject]@{slide=$Slide.SlideIndex;path=$Path.Substring($repo.Length+1);sha256=(Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant();crop_pixels=$Crop})
}

function Node($Slide,[string]$Title,[string]$Body,[double]$X,[double]$Y,[bool]$Emphasis=$false) {
    $shape = $Slide.Shapes.AddShape(1,$X,$Y,194,112)
    $shape.Fill.Solid()
    $shape.Fill.ForeColor.RGB = $(if ($Emphasis) {$lime} else {$white})
    $shape.Line.ForeColor.RGB = $line
    $shape.Line.Weight = 1
    [void](Text $Slide $Title ($X+12) ($Y+11) 170 28 20 $ink $true)
    [void](Text $Slide $Body ($X+12) ($Y+45) 171 58 16 $ink)
}

function Arrow-Line($Slide,[double]$X1,[double]$Y1,[double]$X2,[double]$Y2) {
    $shape = $Slide.Shapes.AddLine($X1,$Y1,$X2,$Y2)
    $shape.Line.ForeColor.RGB = $ink
    $shape.Line.Weight = 1.6
    $shape.Line.EndArrowheadStyle = 3
}

try {
    $app = New-Object -ComObject PowerPoint.Application
    $deck = $app.Presentations.Add(0)
    $deck.PageSetup.SlideWidth = 960
    $deck.PageSetup.SlideHeight = 540

    $s = New-Slide '' '' $true
    [void](Text $s 'ReKit' 48 43 840 100 80 $cream $true)
    [void](Text $s 'AMD-Powered Visual Recovery Intelligence' 51 153 850 56 32 $cream)
    [void](Text $s 'AMD deployment planned; qualification pending.' 52 219 847 35 20 $lime)
    Rule $s 51 277 858 (Rgb '527565')
    [void](Text $s 'Incomplete returns still contain useful parts.' 51 305 858 86 37 $cream $true)
    [void](Text $s 'Recover compatible kits with visual evidence, human decisions and deterministic allocation.' 52 403 820 64 24 $cream)
    [void](Text $s 'NeuralFoundry  |  Forging Intelligent Systems.' 51 481 840 24 17 $lime)
    Notes $s "Project title: ReKit $dash AMD-Powered Visual Recovery Intelligence. Team NeuralFoundry, tagline Forging Intelligent Systems. Problem statement is a product hypothesis; no market-size, recovery-rate or cost-saving estimate is asserted. Current local inference runs on NVIDIA. AMD remote transport is implemented/offline tested; actual AMD execution remains zero. Sources: README.md; docs/architecture.md; deploy/amd/README.md."

    $s = New-Slide 'One workflow, accountable decisions' 'Track each physical component from original images to completed inventory.'
    Screenshot $s $images[0] 48 153 469 @(266,72,1136,640)
    [void](Text $s 'Actual interface: two catalog views of one simulated intake record.' 49 425 470 44 16 $muted)
    $steps = @(
        @('1  Capture','Unique component ID; original-byte evidence.'),
        @('2  Inspect','Visible AI observations, uncertainty and new-view requests.'),
        @('3  Review','Human identity, revision and condition decisions.'),
        @('4  Recover','Approved BOMs, economic alternatives and exclusive allocation.')
    )
    for ($i=0;$i -lt $steps.Count;$i++) {
        [void](Text $s $steps[$i][0] 558 (153+$i*79) 354 30 23 $ink $true)
        [void](Text $s $steps[$i][1] 558 (185+$i*79) 354 47 18 $muted)
    }
    [void](Text $s 'ABO (c) Amazon.com, CC BY 4.0. Screenshot crop; source images unchanged.' 49 483 861 19 12 $muted)
    Notes $s "Actual Task 3 screenshot: $ProductRun/product-originals-desktop.png, crop x266 y72 w1136 h640. Full screenshot embedded without pixel edits. ABO images are catalog sources, not evidence of an actual returned physical unit. Same-listing membership does not establish a shared physical identity. Source: evaluation/fixtures/abo-manifest.json; https://amazon-berkeley-objects.s3.us-east-1.amazonaws.com/index.html ; https://creativecommons.org/licenses/by/4.0/ . Retain the full builder attribution from docs/real-product-evaluation.md. Human-role browser automation is not an independent semantic label."

    $s = New-Slide 'Models observe. Rules decide.' 'A single evidence and inventory boundary preserves identity, authority and audit.'
    Node $s 'Managed images' "Original bytes`nStable physical ID" 48 165
    Node $s 'AI provider' "NVIDIA: measured`nAMD: offline tests" 272 165
    Node $s 'Evidence' "Validated structure`nStill unverified" 496 165
    Node $s 'Human review' "Confirm or reject`nRequest new evidence" 720 165 $true
    Node $s 'Inventory' "Atomic stock changes`nKit lineage and audit" 48 326 $true
    Node $s 'Approval' "Human operator`nRecheck current state" 272 326
    Node $s 'CP-SAT' "CPU allocation`nBOMs, labor, demand" 496 326
    Node $s 'Compatibility' "Approved BOM/rules`nVerified inputs only" 720 326
    Arrow-Line $s 243 221 269 221
    Arrow-Line $s 467 221 493 221
    Arrow-Line $s 691 221 717 221
    Arrow-Line $s 817 279 817 323
    Arrow-Line $s 718 382 692 382
    Arrow-Line $s 494 382 468 382
    Arrow-Line $s 270 382 244 382
    [void](Text $s 'The model cannot verify identities, approve compatibility or allocate inventory.' 48 465 864 32 21 $ink $true)
    Notes $s 'All architecture labels, nodes and arrows are native editable PowerPoint objects. Flow runs left-to-right on the first row, then right-to-left on the second. SQLite performs the final transactional availability/evidence checks. Inference output is only an unverified observation; deterministic catalog checks, CPU OR-Tools CP-SAT and human approval remain separate. AMD route means implemented HTTPS provider with offline qualification, not deployed ROCm/vLLM. Sources: docs/architecture.md; docs/inference-evidence.md; docs/recovery-planning.md; docs/inventory-workflow.md; deploy/amd/README.md.'

    $s = New-Slide 'Real images. Unverified AI.' "Qwen3-VL-2B $middot NVIDIA RTX 4080 SUPER $middot one joint two-image request"
    Screenshot $s $images[1] 48 154 560 @(287,111,1097,407)
    [void](Text $s 'Actual model output, preserved as returned.' 49 370 558 23 15 $muted)
    [void](Text $s '1 held' 650 157 263 58 44 $ink $true)
    [void](Text $s 'Identity remains unknown' 652 221 259 36 21 $muted)
    [void](Text $s '0 kits' 650 275 263 58 44 $ink $true)
    [void](Text $s 'No automatic verification' 652 338 259 44 21 $muted)
    [void](Text $s 'Repeated appearance text; uncertainty ends mid-thought.' 49 411 861 30 23 $ink $true)
    [void](Text $s 'No catalog candidates are allowed in this mode. This does not measure recognition accuracy.' 49 449 861 44 18 $muted)
    Notes $s "Actual screenshot: $ProductRun/product-ai-result-desktop.png, crop x287 y111 w1097 h407. Actual structured model output contains two appearance claims 'amazon commercial', no identity candidates, one uncertainty ending at The 'amazon', and one back-view request. We neither repair this text nor certify its claims. Scripted operator rejection asks for readable labels and detail views; the component remains held with no verifications/plans/reservations/kits. Input originals: ABO (c) Amazon.com, CC BY 4.0; source/license and builder credits in docs/real-product-evaluation.md. Qwen/Qwen3-VL-2B-Instruct, pinned model revision $($product.actual_run.start.configuration.model_revision), Apache-2.0 declaration: https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct/blob/89644892e4d85e24eaac8bacfd4f463576704203/README.md . Source run ID: $($product.actual_run.start.run_id). Sources: $ProductRun/product-inference-results.json and acceptance-result.json."

    $s = New-Slide 'A separate, controlled recovery example' 'Synthetic components and explicit human-role decisions; real CPU optimization.'
    [void](Text $s "3  $arrow  4  $arrow  2" 49 154 445 76 51 $ink $true)
    [void](Text $s 'returns       unique parts      kits' 52 231 425 28 19 $muted)
    [void](Text $s 'USD 175' 49 286 430 62 47 $ink $true)
    [void](Text $s 'Modeled net disposition value' 51 349 422 29 20 $muted)
    Screenshot $s $images[2] 502 159 410 @(266,850,1137,425)
    [void](Text $s 'Actual completed-kit records and component lineage.' 503 324 407 47 17 $muted)
    Rule $s 49 401 862
    [void](Text $s "Approved BOMs $arrow CP-SAT $arrow 4 reserved $arrow 4 consumed" 49 423 861 34 23 $ink $true)
    [void](Text $s 'Two explicit completion confirmations. Scenario estimates are not sales or customer savings.' 49 466 861 34 18 $muted)
    Notes $s "This is not the ABO product-image scenario. Source: $RecoveryRun/acceptance-result.json (three returns, four unique components, two completed kits, four exclusive reservations before completion, four consumed components, four audit events, actual OR-Tools CP-SAT OPTIMAL result, 17,500 cents modeled value). Screenshot: $RecoveryRun/final-inventory.png, crop x266 y850 w1137 h425. All identities and conditions are scripted synthetic fixture decisions. The arithmetic is two kits at 8,750 cents estimated net value each. No realized sales, savings, physical assembly or hidden-function/safety validation is claimed. Full screenshot is embedded, unaltered, with native PowerPoint crop. Sources: tests/fixtures/synthetic_recovery.json; docs/recovery-planning.md; docs/inventory-workflow.md."

    $s = New-Slide 'Measured execution, honest limits' 'Local qualification snapshot; software checks and model quality are different.' $true
    $m = $product.actual_run.outcome.metrics
    $inferenceTime = '{0:F3} s' -f [double]$m.inference_seconds
    $requestTime = '{0:F3} s' -f [double]$m.request_seconds
    $memory = '{0:F3} GB' -f ([double]$m.peak_allocated_bytes/1000000000)
    $rows = @(@('Observed check','Result'),@('Backend / frontend tests','1,121 / 57 passed'),@('Model generation',$inferenceTime),@('Provider request',$requestTime),@('Peak GPU allocated',$memory))
    $tableShape = $s.Shapes.AddTable(5,2,48,153,548,267)
    $tableShape.Name = 'Editable-measured-results'
    $tableShape.Table.Columns.Item(1).Width = 332
    $tableShape.Table.Columns.Item(2).Width = 216
    for ($r=1;$r -le 5;$r++) {
        for ($c=1;$c -le 2;$c++) {
            $cell = $tableShape.Table.Cell($r,$c)
            $cell.Shape.Fill.Solid()
            $cell.Shape.Fill.ForeColor.RGB = $(if ($r -eq 1) {$lime} else {$ink})
            $cell.Shape.TextFrame.MarginLeft=10; $cell.Shape.TextFrame.MarginRight=8
            $cell.Shape.TextFrame.MarginTop=13; $cell.Shape.TextFrame.MarginBottom=5
            $cell.Shape.TextFrame.TextRange.Text=$rows[$r-1][$c-1]
            $cell.Shape.TextFrame.TextRange.Font.Name='Arial'
            $cell.Shape.TextFrame.TextRange.Font.Size=20
            $cell.Shape.TextFrame.TextRange.Font.Color.RGB=$(if ($r -eq 1) {$ink} else {$cream})
            $cell.Shape.TextFrame.TextRange.Font.Bold=$(if ($r -eq 1) {-1} else {0})
            foreach ($border in 1..4) { $cell.Borders.Item($border).ForeColor.RGB=Rgb '527565'; $cell.Borders.Item($border).Weight=0.6 }
        }
    }
    [void](Text $s 'n = 1 joint request; cold load included in provider time.' 49 432 548 46 17 $cream)
    [void](Text $s '0' 650 152 252 69 56 $lime $true)
    [void](Text $s 'independent human labels' 650 226 260 57 23 $cream)
    [void](Text $s 'Accuracy is not yet measurable.' 650 294 260 68 23 $cream $true)
    [void](Text $s 'No p95, customer savings, hidden-function or safety claim.' 650 378 260 95 20 $cream)
    Notes $s "Measurements from $ProductRun/product-inference-results.json: inference_seconds=$($m.inference_seconds); request_seconds=$($m.request_seconds); peak_allocated_bytes=$($m.peak_allocated_bytes), reported in decimal GB, not GiB or total process/device memory. One joint two-image request, RTX 4080 SUPER cuda:1; PyTorch2.9.0+cu128, CUDA12.8; browser end-to-end49.8 seconds is a separate measurement, not shown as inference latency. Test snapshot supplied by completed Mission05 Task3:1,121 backend /57 frontend; commit898c5ca, both CPU CI jobs in38520155304 passed. Source URLs: https://github.com/arslanabdulghaffar/ReKit/actions/runs/38520155304 (private). Human reviews remain0;19 original-first image selections are pending. No empirical semantic metric denominator exists. No AMD measurement is claimed."

    $s = New-Slide 'AMD is the next execution gate' 'Prepared integration. No AMD execution has been claimed.' $true
    $next = @(
        @('1  Qualify','Authorized hardware, real VLM, immutable revisions and image/schema support.'),
        @('2  Connect','Existing allowlisted HTTPS provider. Server-only secrets; no automatic fallback.'),
        @('3  Measure','Actual images, failures, GPU memory, latency and the full human-review workflow.')
    )
    for ($i=0;$i -lt 3;$i++) {
        $x=49+$i*298
        [void](Text $s $next[$i][0] $x 164 267 38 26 $lime $true)
        [void](Text $s $next[$i][1] $x 216 264 118 22 $cream)
    }
    Rule $s 49 361 862 (Rgb '527565')
    [void](Text $s 'Business potential' 49 384 862 36 26 $lime $true)
    [void](Text $s 'Recover compatible stock with traceable decisions.' 49 430 862 36 29 $cream $true)
    [void](Text $s 'Next: AMD qualification and independent human review before a measured customer pilot.' 49 473 862 30 17 $cream)
    Notes $s 'AMD path is prepared, not activated. openai-remote enforces an exact HTTPS allowlist, bounded worker deadlines, strict local output validation and no automatic retry/fallback. Configured model/processor revisions are declarations, not remote weight or AMD hardware attestation. Actual deployed hardware, Linux/ROCm/vLLM compatibility, vision/schema capabilities and revision provenance require authorized qualification; shared API branding alone is insufficient. Access/credits remain external; no authenticated AMD request, spend, publication or submission occurred in this deck build. Potential business benefits are hypotheses, not measured gains. Sources: deploy/amd/README.md; docs/amd-access.md; docs/hackathon-submission-checklist.md. Maintain Windows CUDA separately from any Linux ROCm environment. Optional Evolus is not implemented.'

    # Native geometry and text extents: no font shrinking or silent autofit.
    foreach ($slide in $deck.Slides) {
        foreach ($shape in $slide.Shapes) {
            if ($shape.Left -lt -0.5 -or $shape.Top -lt -0.5 -or $shape.Left+$shape.Width -gt 960.5 -or $shape.Top+$shape.Height -gt 540.5) {
                throw "Shape outside slide $($slide.SlideIndex): $($shape.Name)"
            }
            if ($shape.HasTextFrame -eq -1 -and $shape.TextFrame.HasText -eq -1) {
                $bound = $shape.TextFrame.TextRange.BoundHeight
                $available = $shape.Height-$shape.TextFrame.MarginTop-$shape.TextFrame.MarginBottom
                if ($bound -gt $available+1) { throw "Text overflows slide $($slide.SlideIndex): $($shape.Name), $bound > $available" }
            }
            if ($shape.HasTable -eq -1) {
                for ($r=1;$r -le $shape.Table.Rows.Count;$r++) {
                    for ($c=1;$c -le $shape.Table.Columns.Count;$c++) {
                        $cellShape=$shape.Table.Cell($r,$c).Shape
                        $available=$cellShape.Height-$cellShape.TextFrame.MarginTop-$cellShape.TextFrame.MarginBottom
                        if ($cellShape.TextFrame.TextRange.BoundHeight -gt $available+1) { throw "Table text overflows on slide $($slide.SlideIndex)." }
                    }
                }
            }
        }
        $checks.Add([PSCustomObject]@{slide=$slide.SlideIndex;shapes=$slide.Shapes.Count;native_geometry='passed';text_extents='passed'})
    }
    $pptx = Join-Path $output 'ReKit-NeuralFoundry-pitch.pptx'
    $deck.SaveAs($pptx,24)
    foreach ($slide in $deck.Slides) {
        $slide.Export((Join-Path $renderDir ('slide-{0:00}.png' -f $slide.SlideIndex)),'PNG',1920,1080)
    }
    $appVersion = $app.Version
    $deck.Close()
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($deck)
    $deck = $null
    $app.Quit()
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($app)
    $app = $null

    # Read the Open XML package: native text/table/diagram objects must remain editable.
    $zip = [IO.Compression.ZipFile]::OpenRead($pptx)
    $xmlChecks = [Collections.Generic.List[object]]::new()
    try {
        for ($i=1;$i -le 7;$i++) {
            $entry=$zip.GetEntry("ppt/slides/slide$i.xml")
            if ($null -eq $entry) { throw 'Expected seven slide XML parts.' }
            $reader=[IO.StreamReader]::new($entry.Open())
            try { [xml]$xml=$reader.ReadToEnd() } finally { $reader.Dispose() }
            $ns=[Xml.XmlNamespaceManager]::new($xml.NameTable)
            $ns.AddNamespace('p','http://schemas.openxmlformats.org/presentationml/2006/main')
            $ns.AddNamespace('a','http://schemas.openxmlformats.org/drawingml/2006/main')
            $nativeText=$xml.SelectNodes('//p:sp[p:txBody/a:p/a:r/a:t]',$ns).Count
            $tables=$xml.SelectNodes('//a:tbl',$ns).Count
            $pictures=$xml.SelectNodes('//p:pic',$ns).Count
            $connectors=$xml.SelectNodes('//p:cxnSp',$ns).Count
            if ($nativeText -lt 5 -or ($i -eq 3 -and $connectors -ne 7) -or ($i -eq 6 -and $tables -ne 1)) { throw "Editability check failed on slide $i." }
            if ($null -eq $zip.GetEntry("ppt/notesSlides/notesSlide$i.xml")) { throw 'A slide is missing source notes.' }
            $xmlChecks.Add([PSCustomObject]@{slide=$i;native_text_shapes=$nativeText;native_tables=$tables;pictures=$pictures;native_connectors=$connectors})
        }
    } finally { $zip.Dispose() }
    $result=[ordered]@{status='passed';authoring='installed PowerPoint COM; hidden presentation';powerpoint_version=$appVersion;
        deck=$pptx;deck_sha256=(Get-FileHash -LiteralPath $pptx -Algorithm SHA256).Hash.ToLowerInvariant();
        slide_count=7;slide_size_points=@(960,540);font='Arial';render_size_pixels=@(1920,1080);
        source_runs=@($ProductRun,$RecoveryRun);sources=$sources;geometry=$checks;editability=$xmlChecks;
        screenshot_policy='Original pixels embedded; native PowerPoint crops disclosed in notes; no fabricated interface.';
        visual_review='Required separately after export; build success alone does not establish visual QA.';
        artifact_tool_runtime='Unavailable; used explicitly authorized installed PowerPoint fallback.'}
} catch {
    $failure=$_
    $result=[ordered]@{status='failed';error=$_.Exception.Message;output=$output;visual_review='Not qualified'}
} finally {
    if ($null -ne $deck) { try { $deck.Close() } finally { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($deck) } }
    if ($null -ne $app) { try { $app.Quit() } finally { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($app) } }
    [GC]::Collect(); [GC]::WaitForPendingFinalizers()
    if ($null -ne $result) {
        [IO.File]::WriteAllText((Join-Path $output 'build-result.json'),($result | ConvertTo-Json -Depth 10),[Text.UTF8Encoding]::new($false))
    }
}
if ($null -ne $failure) { throw $failure }
[PSCustomObject]@{status='passed';deck=$result.deck;slides=$result.slide_count;report=(Join-Path $output 'build-result.json')} | ConvertTo-Json
