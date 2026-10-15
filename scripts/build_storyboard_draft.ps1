# Render an explicitly silent stills storyboard from a source-bound private manifest.
# Uses the existing installed PowerPoint. No capture, model call or network access.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$ManifestPath,
    [string]$OutputDirectory = '',
    [switch]$ExportMovie
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$privateRoot = [IO.Path]::GetFullPath((Join-Path $repo 'var/mission06-offline'))
$sourceRoot = [IO.Path]::GetFullPath((Join-Path $repo 'var/mission02-acceptance')) + [IO.Path]::DirectorySeparatorChar

function Resolve-LocalPath([string]$Value) {
    if ([IO.Path]::IsPathRooted($Value)) { return [IO.Path]::GetFullPath($Value) }
    return [IO.Path]::GetFullPath((Join-Path $repo $Value))
}

function Assert-NoReparsePoints([string]$AbsolutePath) {
    $current = [IO.Path]::GetFullPath($AbsolutePath)
    while (-not [string]::IsNullOrEmpty($current)) {
        $item = $null
        try { $item = Get-Item -LiteralPath $current -Force -ErrorAction Stop }
        catch [System.Management.Automation.ItemNotFoundException] { }
        if ($null -ne $item -and ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'A storyboard input/output path or ancestor is a reparse point. Use a direct local directory.'
        }
        if ($current -eq [IO.Path]::GetPathRoot($current)) { break }
        $current = [IO.Path]::GetDirectoryName($current)
    }
}

Assert-NoReparsePoints $repo
Assert-NoReparsePoints $privateRoot
Assert-NoReparsePoints $sourceRoot
$manifestFile = Resolve-LocalPath $ManifestPath
if (-not $manifestFile.StartsWith($privateRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'The storyboard manifest must be under repository var/mission06-offline/.'
}
Assert-NoReparsePoints $manifestFile
$manifest = Get-Content -LiteralPath $manifestFile -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.format -ne 'rekit-silent-stills-storyboard-v1' -or $manifest.shots.Count -ne 12 -or
    $manifest.duration_seconds -ne 240 -or $manifest.motion_footage -ne $false -or
    $manifest.audio -ne $false -or ($manifest.shots | Measure-Object -Property duration_seconds -Sum).Sum -ne 240) {
    throw 'Expected a twelve-shot, 240-second, explicitly silent stills storyboard.'
}
foreach ($source in $manifest.sources) {
    $path = Resolve-LocalPath $source.path
    Assert-NoReparsePoints $path
    if (-not $path.StartsWith($sourceRoot, [StringComparison]::OrdinalIgnoreCase) -or
        (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $source.sha256) {
        throw 'A source is missing, outside the approved run root, or has changed bytes.'
    }
}
foreach ($shot in $manifest.shots) {
    if ($shot.duration_seconds -le 0 -or [string]::IsNullOrWhiteSpace($shot.title) -or
        [string]::IsNullOrWhiteSpace($shot.track_label) -or [string]::IsNullOrWhiteSpace($shot.narration)) {
        throw 'Every shot requires a positive duration, title, provenance label and narration sidecar.'
    }
    foreach ($image in $shot.images) {
        if (-not @($manifest.sources | Where-Object { $_.path -eq $image.path }).Count) {
            throw 'Every image must have a hashed source entry.'
        }
    }
}
if ([string]::IsNullOrWhiteSpace($OutputDirectory)) {
    $OutputDirectory = Join-Path $privateRoot ('block-c-video-render-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,6))
}
$output = Resolve-LocalPath $OutputDirectory
if (-not $output.StartsWith($privateRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Output must be a fresh directory under repository var/mission06-offline/.'
}
Assert-NoReparsePoints $output
if (Test-Path -LiteralPath $output) { throw 'Refusing to overwrite existing output.' }
if (Get-Process POWERPNT -ErrorAction SilentlyContinue) { throw 'An existing PowerPoint session must finish before this isolated render.' }
[IO.Directory]::CreateDirectory($output) | Out-Null
$acl = [Security.AccessControl.DirectorySecurity]::new()
$acl.SetAccessRuleProtection($true,$false)
foreach ($identity in @([Security.Principal.WindowsIdentity]::GetCurrent().User,
    [Security.Principal.SecurityIdentifier]::new('S-1-5-18'),
    [Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))) {
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($identity,'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
}
Set-Acl -LiteralPath $output -AclObject $acl
$renderDir = Join-Path $output 'shots'
[IO.Directory]::CreateDirectory($renderDir) | Out-Null
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$app = $null
$deck = $null
$result = $null
$failure = $null
$checks = [Collections.Generic.List[object]]::new()

function Rgb([string]$Hex) {
    return [Convert]::ToInt32($Hex.Substring(0,2),16) + 256 * [Convert]::ToInt32($Hex.Substring(2,2),16) + 65536 * [Convert]::ToInt32($Hex.Substring(4,2),16)
}
$ink = Rgb '153E35'
$cream = Rgb 'F4F6F2'
$muted = Rgb '536B60'

function Text($Slide,[string]$Value,[double]$X,[double]$Y,[double]$W,[double]$H,[double]$Size=22,[bool]$Bold=$false,[int]$Color=$ink) {
    $shape = $Slide.Shapes.AddTextbox(1,$X,$Y,$W,$H)
    $shape.TextFrame.MarginLeft = 0
    $shape.TextFrame.MarginRight = 0
    $shape.TextFrame.MarginTop = 0
    $shape.TextFrame.MarginBottom = 0
    $shape.TextFrame.WordWrap = -1
    $shape.TextFrame.AutoSize = 0
    $shape.TextFrame2.AutoSize = 0
    $range = $shape.TextFrame.TextRange
    $range.Text = $Value
    $range.Font.Name = 'Arial'
    $range.Font.Size = $Size
    $range.Font.Bold = $(if($Bold){-1}else{0})
    $range.Font.Color.RGB = $Color
    $range.ParagraphFormat.SpaceAfter = 0
    $shape.Width = $W
    $shape.Height = $H
    $shape.Left = $X
    $shape.Top = $Y
    return $shape
}

function Source-Image($Slide,$Image) {
    $path = Resolve-LocalPath $Image.path
    Assert-NoReparsePoints $path
    $bitmap = [Drawing.Image]::FromFile($path)
    try { $width=$bitmap.Width; $height=$bitmap.Height } finally { $bitmap.Dispose() }
    $crop = @($Image.crop_pixels)
    $box = @($Image.box_points)
    if ($crop.Count -ne 4 -or $box.Count -ne 4 -or $crop[0] -lt 0 -or $crop[1] -lt 0 -or
        $crop[2] -le 0 -or $crop[3] -le 0 -or $crop[0]+$crop[2] -gt $width -or $crop[1]+$crop[3] -gt $height) {
        throw 'A declared screenshot crop exceeds its original source.'
    }
    $scale = [Math]::Min($box[2]/$crop[2],$box[3]/$crop[3])
    $picture = $Slide.Shapes.AddPicture($path,0,-1,0,0,-1,-1)
    $picture.LockAspectRatio = 0
    $frame = $picture.PictureFormat.Crop
    $frame.ShapeWidth = $crop[2]*$scale
    $frame.ShapeHeight = $crop[3]*$scale
    $frame.ShapeLeft = $box[0]+($box[2]-$frame.ShapeWidth)/2
    $frame.ShapeTop = $box[1]+($box[3]-$frame.ShapeHeight)/2
    $frame.PictureWidth = $width*$scale
    $frame.PictureHeight = $height*$scale
    $frame.PictureOffsetX = ($width/2-$crop[0]-$crop[2]/2)*$scale
    $frame.PictureOffsetY = ($height/2-$crop[1]-$crop[3]/2)*$scale
    $picture.AlternativeText = 'Recorded still. Full source embedded unchanged; native crop disclosed in manifest. ' + $Image.path
}

try {
    $app = New-Object -ComObject PowerPoint.Application
    $deck = $app.Presentations.Add(0)
    $deck.PageSetup.SlideWidth = 960
    $deck.PageSetup.SlideHeight = 540
    $narration = [Collections.Generic.List[string]]::new()
    foreach ($shot in $manifest.shots) {
        $slide = $deck.Slides.Add($deck.Slides.Count+1,12)
        $slide.FollowMasterBackground = 0
        $slide.Background.Fill.Solid()
        $slide.Background.Fill.ForeColor.RGB = $cream
        [void](Text $slide $shot.title 36 24 888 48 30 $true)
        [void](Text $slide $shot.track_label 36 80 888 34 16 $false $muted)
        foreach ($sourceImage in $shot.images) { Source-Image $slide $sourceImage }
        foreach ($block in $shot.text_blocks) {
            [void](Text $slide $block.text $block.box_points[0] $block.box_points[1] $block.box_points[2] $block.box_points[3] $block.font_size $block.bold)
        }
        [void](Text $slide $shot.caption 36 447 888 48 19 $true)
        [void](Text $slide ('RECORDED STILLS / SILENT STORYBOARD   ' + $shot.timecode + '   ' + $shot.number + '/12') 36 509 888 17 11 $true $muted)
        $slide.NotesPage.Shapes.Placeholders.Item(2).TextFrame.TextRange.Text = $shot.narration + "`n`n" + $shot.source_note + "`n`nDraft still sequence. No audio recorded. Provisional narration fit. Original sources and crop coordinates in production-manifest.json."
        $slide.SlideShowTransition.AdvanceOnClick = 0
        $slide.SlideShowTransition.AdvanceOnTime = -1
        $slide.SlideShowTransition.AdvanceTime = $shot.duration_seconds
        $slide.SlideShowTransition.EntryEffect = 0
        foreach ($shape in $slide.Shapes) {
            if ($shape.Left -lt -0.5 -or $shape.Top -lt -0.5 -or $shape.Left+$shape.Width -gt 960.5 -or $shape.Top+$shape.Height -gt 540.5) {
                throw "Shot $($shot.number) contains an out-of-bounds shape."
            }
            if ($shape.HasTextFrame -eq -1 -and $shape.TextFrame.HasText -eq -1 -and
                $shape.TextFrame.TextRange.BoundHeight -gt $shape.Height+1) {
                throw "Shot $($shot.number) contains overflowing text."
            }
        }
        $checks.Add([pscustomobject]@{shot=$shot.number;duration_seconds=$shot.duration_seconds;geometry='passed';text_extents='passed'})
        $narration.Add(('## ' + $shot.number + ' / ' + $shot.timecode + ' / ' + $shot.title + "`n`n" + $shot.narration + "`n"))
    }
    $pptx = Join-Path $output 'ReKit-Block-C-silent-stills-storyboard.pptx'
    $deck.SaveAs($pptx,24)
    foreach ($slide in $deck.Slides) { $slide.Export((Join-Path $renderDir ('shot-{0:00}.png' -f $slide.SlideIndex)),'PNG',1920,1080) }
    [IO.File]::Copy($manifestFile,(Join-Path $output 'production-manifest.json'))
    [IO.File]::WriteAllText((Join-Path $output 'narration.md'),("# ReKit silent storyboard narration`n`nNot recorded. Timing is provisional.`n`n" + ($narration -join "`n")),[Text.UTF8Encoding]::new($false))
    $movie = $null
    if ($ExportMovie) {
        $movie = Join-Path $output 'ReKit-Block-C-silent-stills-draft.mp4'
        $deck.CreateVideo($movie,$true,20,1080,24,85)
        $deadline = [DateTime]::UtcNow.AddMinutes(10)
        while ($deck.CreateVideoStatus -in @(1,2)) {
            if ([DateTime]::UtcNow -gt $deadline) { throw 'Movie export exceeded the bounded ten-minute render window.' }
            Start-Sleep -Milliseconds 500
        }
        if ($deck.CreateVideoStatus -ne 3 -or -not (Test-Path -LiteralPath $movie -PathType Leaf)) { throw 'PowerPoint did not complete movie export.' }
    }
    $appVersion = $app.Version
    $deck.Close()
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($deck)
    $deck = $null
    $app.Quit()
    [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($app)
    $app = $null
    # Normalize Office account metadata only in this newly generated intermediate.
    # Never open or rewrite the original pitch deck or screenshot sources.
    $zip = [IO.Compression.ZipFile]::Open($pptx,[IO.Compression.ZipArchiveMode]::Update)
    try {
        foreach ($part in @('docProps/core.xml','docProps/app.xml')) {
            $entry = $zip.GetEntry($part)
            if ($null -eq $entry) { continue }
            $reader = [IO.StreamReader]::new($entry.Open())
            try { [xml]$xml = $reader.ReadToEnd() } finally { $reader.Dispose() }
            foreach ($node in $xml.SelectNodes('//*')) {
                if ($node.LocalName -in @('creator','lastModifiedBy')) { $node.InnerText = 'NeuralFoundry' }
                if ($node.LocalName -in @('Company','Manager','HyperlinkBase')) { $node.InnerText = '' }
            }
            $entry.Delete()
            $replacement = $zip.CreateEntry($part)
            $writer = [IO.StreamWriter]::new($replacement.Open(),[Text.UTF8Encoding]::new($false))
            try { $writer.Write($xml.OuterXml) } finally { $writer.Dispose() }
        }
    } finally { $zip.Dispose() }
    $result = [ordered]@{
        status='passed';authoring='installed PowerPoint, hidden isolated presentation';powerpoint_version=$appVersion;
        source_manifest_sha256=(Get-FileHash -LiteralPath $manifestFile -Algorithm SHA256).Hash.ToLowerInvariant();
        intermediate_pptx=$pptx;pptx_sha256=(Get-FileHash -LiteralPath $pptx -Algorithm SHA256).Hash.ToLowerInvariant();
        shots=12;scheduled_seconds=240;frame_size=@(1920,1080);frame_rate=24;audio=$false;motion_footage=$false;
        movie=$movie;movie_sha256=$(if($movie){(Get-FileHash -LiteralPath $movie -Algorithm SHA256).Hash.ToLowerInvariant()}else{$null});
        checks=$checks;visual_review='Required separately for every rendered shot and exported movie.';
        metadata='New intermediate creator/lastModifiedBy normalized to NeuralFoundry; company/manager/base cleared.';
        note='Movie is an explicitly labeled silent still sequence. No new inference, capture or human judgments.';
        source_policy='Full original images embedded unchanged; native crops and labels disclosed.'
    }
} catch {
    $failure=$_
    $result=[ordered]@{status='failed';output=$output;error=$_.Exception.Message;visual_review='Not qualified'}
} finally {
    if ($null -ne $deck) { try { $deck.Close() } finally { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($deck) } }
    if ($null -ne $app) { try { $app.Quit() } finally { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($app) } }
    [GC]::Collect(); [GC]::WaitForPendingFinalizers()
    if ($null -ne $result) { [IO.File]::WriteAllText((Join-Path $output 'build-result.json'),($result | ConvertTo-Json -Depth 12),[Text.UTF8Encoding]::new($false)) }
}
if ($null -ne $failure) { throw $failure }
[pscustomobject]@{status='passed';output=$output;movie=$result.movie;report=(Join-Path $output 'build-result.json')} | ConvertTo-Json
