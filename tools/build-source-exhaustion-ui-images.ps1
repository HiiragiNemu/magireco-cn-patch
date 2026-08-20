param(
    [string]$OldRoot = 'A:\magicaOLD\resource\image_web',
    [string]$CurrentRoot = 'A:\totentanz-frontend\resource\image_web',
    [string]$ProductRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) 'magica\resource\image_web'),
    [string]$EvidenceRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) 'magica\research\totentanz-full-localization-20260817\current-canvas-image-round2'),
    [switch]$VerifyOnly
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$script:Rows = [System.Collections.Generic.List[object]]::new()

function New-Canvas([int]$Width, [int]$Height) {
    return [Drawing.Bitmap]::new($Width, $Height, [Drawing.Imaging.PixelFormat]::Format32bppArgb)
}

function Save-Checked([Drawing.Bitmap]$Bitmap, [string]$RelativePath, [string]$Authority, [string]$Method) {
    $target = Join-Path $ProductRoot $RelativePath
    $memory = [IO.MemoryStream]::new()
    $Bitmap.Save($memory, [Drawing.Imaging.ImageFormat]::Png)
    $expected = $memory.ToArray()
    $memory.Dispose()
    if ($VerifyOnly) {
        if (-not (Test-Path -LiteralPath $target)) { throw "missing image: $RelativePath" }
        $actual = [IO.File]::ReadAllBytes($target)
        if (-not [Linq.Enumerable]::SequenceEqual([byte[]]$actual, [byte[]]$expected)) {
            throw "image bytes drifted: $RelativePath"
        }
    } else {
        [IO.Directory]::CreateDirectory((Split-Path -Parent $target)) | Out-Null
        $temporary = "$target.tmp"
        [IO.File]::WriteAllBytes($temporary, $expected)
        Move-Item -LiteralPath $temporary -Destination $target -Force
    }
    $script:Rows.Add([ordered]@{
        path = ($RelativePath -replace '\\','/')
        width = $Bitmap.Width
        height = $Bitmap.Height
        bytes = $expected.Length
        authority = $Authority
        method = $Method
    })
    $Bitmap.Dispose()
}

function Copy-OldToCanvas([string]$RelativePath, [int]$Width, [int]$Height, [int]$X, [int]$Y) {
    $source = [Drawing.Bitmap]::FromFile((Join-Path $OldRoot $RelativePath))
    $bitmap = New-Canvas $Width $Height
    $graphics = [Drawing.Graphics]::FromImage($bitmap)
    $graphics.CompositingMode = [Drawing.Drawing2D.CompositingMode]::SourceCopy
    $graphics.DrawImageUnscaled($source, $X, $Y)
    $graphics.Dispose(); $source.Dispose()
    Save-Checked $bitmap $RelativePath 'official-cn-legacy-client-image' 'official pixels placed without scaling on current-size transparent canvas'
}

# Minor transparent-border geometry drift: preserve every official-CN source pixel.
Copy-OldToCanvas 'page\arena\infinite_floor_bg.png' 120 121 0 0
Copy-OldToCanvas 'page\arena\matching\enemy_icon_equal.png' 81 30 0 0
Copy-OldToCanvas 'page\arena\matching\enemy_icon_lower.png' 81 31 0 0
Copy-OldToCanvas 'page\collection\witch_header.png' 300 51 0 0
Copy-OldToCanvas 'page\gacha\tag_chara_s.png' 128 27 0 0
Copy-OldToCanvas 'page\memoria\memoria_limitbreak_run.png' 106 111 1 1

# The small result-layer badge changed aspect ratio. Scale the complete official
# sprite once to the current dimensions rather than cropping either Chinese line.
$rel = 'page\arena\result\infinite_floor_bg_s.png'
$source = [Drawing.Bitmap]::FromFile((Join-Path $OldRoot $rel))
$bitmap = New-Canvas 75 83
$graphics = [Drawing.Graphics]::FromImage($bitmap)
$graphics.CompositingMode = [Drawing.Drawing2D.CompositingMode]::SourceCopy
$graphics.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$graphics.PixelOffsetMode = [Drawing.Drawing2D.PixelOffsetMode]::HighQuality
$graphics.DrawImage($source, [Drawing.Rectangle]::new(0,0,75,83), 0,0,$source.Width,$source.Height,[Drawing.GraphicsUnit]::Pixel)
$graphics.Dispose(); $source.Dispose()
Save-Checked $bitmap $rel 'official-cn-legacy-client-image' 'complete official sprite resized to current canvas dimensions'

# The memoria tag has one transparent row above its content; remove only that row.
$rel = 'page\gacha\tag_memoria_s.png'
$source = [Drawing.Bitmap]::FromFile((Join-Path $OldRoot $rel))
$bitmap = New-Canvas 128 25
$graphics = [Drawing.Graphics]::FromImage($bitmap)
$graphics.CompositingMode = [Drawing.Drawing2D.CompositingMode]::SourceCopy
$graphics.DrawImage($source, [Drawing.Rectangle]::new(0,0,128,25), 0,1,128,25,[Drawing.GraphicsUnit]::Pixel)
$graphics.Dispose(); $source.Dispose()
Save-Checked $bitmap $rel 'official-cn-legacy-client-image' 'removed one transparent border row for current canvas dimensions'

# The legacy source for this one label is still Japanese. Preserve the current
# canvas and ornament, erase only the English word, then add a careful Chinese label.
$rel = 'page\arena\reward\reward_header_a.png'
$source = [Drawing.Bitmap]::FromFile((Join-Path $CurrentRoot $rel))
$bitmap = New-Canvas $source.Width $source.Height
$graphics = [Drawing.Graphics]::FromImage($bitmap)
$graphics.DrawImageUnscaled($source,0,0)
$background = $source.GetPixel(205,18)
$brush = [Drawing.SolidBrush]::new($background)
$graphics.FillRectangle($brush, 50, 0, 150, 36)
$brush.Dispose()
$font = [Drawing.Font]::new('Microsoft YaHei',18,[Drawing.FontStyle]::Bold,[Drawing.GraphicsUnit]::Pixel)
$format = [Drawing.StringFormat]::new()
$format.Alignment = [Drawing.StringAlignment]::Near
$format.LineAlignment = [Drawing.StringAlignment]::Center
$textBrush = [Drawing.SolidBrush]::new([Drawing.Color]::White)
$graphics.TextRenderingHint = [Drawing.Text.TextRenderingHint]::AntiAliasGridFit
$graphics.DrawString('奖励一览',$font,$textBrush,[Drawing.RectangleF]::new(55,0,140,36),$format)
$textBrush.Dispose(); $format.Dispose(); $font.Dispose(); $graphics.Dispose(); $source.Dispose()
Save-Checked $bitmap $rel 'careful-human-translation-on-current-us-canvas' 'current canvas and ornament retained; visible English label replaced only'

$rows = @($script:Rows | Sort-Object path)
[IO.Directory]::CreateDirectory($EvidenceRoot) | Out-Null
$result = [ordered]@{
    schema = 'magireco-current-canvas-image-round2/v1'
    status = 'PASS'
    verify_only = [bool]$VerifyOnly
    assets = $rows.Count
    official_cn_assets = @($rows | Where-Object authority -eq 'official-cn-legacy-client-image').Count
    new_human_assets = @($rows | Where-Object authority -eq 'careful-human-translation-on-current-us-canvas').Count
    product_root = $ProductRoot
    rows = $rows
}
$name = if ($VerifyOnly) { 'verification.json' } else { 'manifest.json' }
[IO.File]::WriteAllText((Join-Path $EvidenceRoot $name), (($result | ConvertTo-Json -Depth 8) + "`n"), [Text.UTF8Encoding]::new($false))
$result | ConvertTo-Json -Depth 8
