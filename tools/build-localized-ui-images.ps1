param(
    [string]$SourceRoot = 'A:\totentanz-frontend\resource\image_web',
    [string]$ProductRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) 'magica\resource\image_web'),
    [string]$EvidenceRoot = (Join-Path (Split-Path -Parent $PSScriptRoot) 'magica\research\totentanz-full-localization-20260817\web-images'),
    [switch]$VerifyOnly
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$script:GeneratedAssets = [System.Collections.Generic.List[object]]::new()

function New-OutlinedPath {
    param(
        [System.Drawing.Graphics]$Graphics,
        [string]$Text,
        [string]$Family,
        [float]$Size,
        [System.Drawing.FontStyle]$Style,
        [System.Drawing.RectangleF]$Box,
        [System.Drawing.Color]$Fill,
        [System.Drawing.Color]$Outline,
        [float]$OutlineWidth,
        [System.Drawing.Color]$Glow,
        [float]$GlowWidth
    )
    $path = [System.Drawing.Drawing2D.GraphicsPath]::new()
    $fmt = [System.Drawing.StringFormat]::new()
    $fmt.Alignment = [System.Drawing.StringAlignment]::Center
    $fmt.LineAlignment = [System.Drawing.StringAlignment]::Center
    $fontFamily = [System.Drawing.FontFamily]::new($Family)
    $path.AddString($Text, $fontFamily, [int]$Style, $Size, $Box, $fmt)
    if ($GlowWidth -gt 0) {
        $glowPen = [System.Drawing.Pen]::new($Glow, $GlowWidth)
        $glowPen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
        $Graphics.DrawPath($glowPen, $path)
        $glowPen.Dispose()
    }
    $outlinePen = [System.Drawing.Pen]::new($Outline, $OutlineWidth)
    $outlinePen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
    $Graphics.DrawPath($outlinePen, $path)
    $brush = [System.Drawing.SolidBrush]::new($Fill)
    $Graphics.FillPath($brush, $path)
    $brush.Dispose()
    $outlinePen.Dispose()
    $fontFamily.Dispose()
    $fmt.Dispose()
    $path.Dispose()
}

function New-CanvasCopy {
    param([string]$Path)
    $src = [System.Drawing.Bitmap]::FromFile($Path)
    $dst = [System.Drawing.Bitmap]::new($src.Width, $src.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $dst.SetResolution($src.HorizontalResolution, $src.VerticalResolution)
    $g = [System.Drawing.Graphics]::FromImage($dst)
    $g.DrawImageUnscaled($src, 0, 0)
    $g.Dispose()
    $src.Dispose()
    return $dst
}

function Set-InterpolatedStrip {
    param(
        [System.Drawing.Bitmap]$Bitmap,
        [int]$X1,
        [int]$X2,
        [int]$Y1,
        [int]$Y2,
        [int]$SampleLeft,
        [int]$SampleRight
    )
    for ($y = $Y1; $y -le $Y2; $y++) {
        $left = $Bitmap.GetPixel($SampleLeft, $y)
        $right = $Bitmap.GetPixel($SampleRight, $y)
        for ($x = $X1; $x -le $X2; $x++) {
            $t = ($x - $X1) / [double][Math]::Max(1, ($X2 - $X1))
            $a = [int][Math]::Round($left.A + (($right.A - $left.A) * $t))
            $r = [int][Math]::Round($left.R + (($right.R - $left.R) * $t))
            $g = [int][Math]::Round($left.G + (($right.G - $left.G) * $t))
            $b = [int][Math]::Round($left.B + (($right.B - $left.B) * $t))
            $Bitmap.SetPixel($x, $y, [System.Drawing.Color]::FromArgb($a, $r, $g, $b))
        }
    }
}

function Set-VerticalFill {
    param(
        [System.Drawing.Bitmap]$Bitmap,
        [int]$X1,
        [int]$X2,
        [int]$Y1,
        [int]$Y2,
        [int]$SampleTop,
        [int]$SampleBottom,
        [int]$SampleX
    )
    $top = $Bitmap.GetPixel($SampleX, $SampleTop)
    $bottom = $Bitmap.GetPixel($SampleX, $SampleBottom)
    for ($y = $Y1; $y -le $Y2; $y++) {
        $t = ($y - $Y1) / [double][Math]::Max(1, ($Y2 - $Y1))
        $a = [int][Math]::Round($top.A + (($bottom.A - $top.A) * $t))
        $r = [int][Math]::Round($top.R + (($bottom.R - $top.R) * $t))
        $g = [int][Math]::Round($top.G + (($bottom.G - $top.G) * $t))
        $b = [int][Math]::Round($top.B + (($bottom.B - $top.B) * $t))
        $color = [System.Drawing.Color]::FromArgb($a, $r, $g, $b)
        for ($x = $X1; $x -le $X2; $x++) { $Bitmap.SetPixel($x, $y, $color) }
    }
}

function Save-Asset {
    param([System.Drawing.Bitmap]$Bitmap, [string]$RelativePath)
    $target = Join-Path $ProductRoot $RelativePath
    $memory = [IO.MemoryStream]::new()
    $Bitmap.Save($memory, [System.Drawing.Imaging.ImageFormat]::Png)
    $expectedBytes = $memory.ToArray()
    $memory.Dispose()
    $sha = [Security.Cryptography.SHA256]::Create()
    $expectedHash = ([BitConverter]::ToString($sha.ComputeHash($expectedBytes))).Replace('-', '').ToLowerInvariant()
    $sha.Dispose()
    if ($VerifyOnly) {
        if (-not (Test-Path -LiteralPath $target)) { throw "missing localized image: $RelativePath" }
        $actual = [System.Drawing.Bitmap]::FromFile($target)
        if ($actual.Width -ne $Bitmap.Width -or $actual.Height -ne $Bitmap.Height) {
            $actual.Dispose(); throw "dimension drift: $RelativePath"
        }
        $actual.Dispose()
        $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash.ToLowerInvariant()
        if ($actualHash -ne $expectedHash) { throw "pixel/byte drift: $RelativePath" }
    } else {
        $dir = Split-Path -Parent $target
        [IO.Directory]::CreateDirectory($dir) | Out-Null
        $tmp = "$target.tmp.png"
        [IO.File]::WriteAllBytes($tmp, $expectedBytes)
        Move-Item -LiteralPath $tmp -Destination $target -Force
    }
    $script:GeneratedAssets.Add([ordered]@{
        path = ($RelativePath -replace '\\','/')
        width = $Bitmap.Width
        height = $Bitmap.Height
        sha256 = $expectedHash
        authority = 'careful-human-translation-on-current-us-canvas'
    })
    $Bitmap.Dispose()
}

function New-Graphics {
    param([System.Drawing.Bitmap]$Bitmap)
    $g = [System.Drawing.Graphics]::FromImage($Bitmap)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $g.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    return $g
}

function New-TransparentLike {
    param([string]$RelativePath)
    $src = [System.Drawing.Bitmap]::FromFile((Join-Path $SourceRoot $RelativePath))
    $bmp = [System.Drawing.Bitmap]::new($src.Width, $src.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $bmp.SetResolution($src.HorizontalResolution, $src.VerticalResolution)
    $src.Dispose()
    return $bmp
}

function Add-CenteredOutlinedText {
    param(
        [System.Drawing.Bitmap]$Bitmap,
        [string]$Text,
        [float]$Size,
        [System.Drawing.Color]$Fill = [System.Drawing.Color]::White,
        [System.Drawing.Color]$Outline = [System.Drawing.Color]::FromArgb(255,90,46,8),
        [float]$OutlineWidth = 2.0,
        [System.Drawing.Color]$Glow = [System.Drawing.Color]::FromArgb(100,255,220,80),
        [float]$GlowWidth = 4.0,
        [float]$X = 0,
        [float]$Y = 0,
        [float]$Width = -1,
        [float]$Height = -1
    )
    if ($Width -lt 0) { $Width = $Bitmap.Width }
    if ($Height -lt 0) { $Height = $Bitmap.Height }
    $g = New-Graphics $Bitmap
    New-OutlinedPath $g $Text 'Microsoft YaHei' $Size ([System.Drawing.FontStyle]::Bold) ([System.Drawing.RectangleF]::new($X,$Y,$Width,$Height)) $Fill $Outline $OutlineWidth $Glow $GlowWidth
    $g.Dispose()
}

function Set-SolidRectangle {
    param([System.Drawing.Bitmap]$Bitmap,[int]$X,[int]$Y,[int]$Width,[int]$Height,[System.Drawing.Color]$Color)
    $g = [System.Drawing.Graphics]::FromImage($Bitmap)
    $brush = [System.Drawing.SolidBrush]::new($Color)
    $g.FillRectangle($brush,$X,$Y,$Width,$Height)
    $brush.Dispose(); $g.Dispose()
}

# Arena: replace the complete text core while preserving the two side ornaments.
$rel = 'page\arena\result\touch_screen.png'
$bmp = New-CanvasCopy (Join-Path $SourceRoot $rel)
$g = New-Graphics $bmp
$g.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
$g.FillRectangle([System.Drawing.Brushes]::Transparent, 19, 0, 204, 32)
$g.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceOver
New-OutlinedPath $g '点击屏幕' 'Microsoft YaHei' 18 ([System.Drawing.FontStyle]::Bold) ([System.Drawing.RectangleF]::new(18, -1, 206, 33)) ([System.Drawing.Color]::FromArgb(255,255,245,151)) ([System.Drawing.Color]::FromArgb(255,240,130,146)) 2.1 ([System.Drawing.Color]::FromArgb(115,255,229,90)) 4.2
$g.Dispose(); Save-Asset $bmp $rel

# Character result labels: the source contains only text and glow, so rebuild on the exact transparent canvas.
foreach ($spec in @(
    @{ Rel='common\chara\result_text_episode_level.png'; Top='事件'; Bottom='等级提升！' },
    @{ Rel='common\chara\result_text_magia_level.png'; Top='Magia'; Bottom='等级提升！' }
)) {
    $src = [System.Drawing.Bitmap]::FromFile((Join-Path $SourceRoot $spec.Rel))
    $bmp = [System.Drawing.Bitmap]::new($src.Width, $src.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $src.Dispose()
    $g = New-Graphics $bmp
    $g.Clear([System.Drawing.Color]::Transparent)
    New-OutlinedPath $g $spec.Top 'Microsoft YaHei' 25 ([System.Drawing.FontStyle]::Bold) ([System.Drawing.RectangleF]::new(0, -3, 282, 48)) ([System.Drawing.Color]::White) ([System.Drawing.Color]::FromArgb(255,255,119,128)) 2.5 ([System.Drawing.Color]::FromArgb(115,255,126,145)) 6
    New-OutlinedPath $g $spec.Bottom 'Microsoft YaHei' 42 ([System.Drawing.FontStyle]::Bold) ([System.Drawing.RectangleF]::new(0, 37, 282, 70)) ([System.Drawing.Color]::White) ([System.Drawing.Color]::FromArgb(255,236,53,72)) 3.8 ([System.Drawing.Color]::FromArgb(150,255,104,128)) 8
    $g.Dispose(); Save-Asset $bmp $spec.Rel
}

# Campaign banners: retain the original small campaign label and side ornaments.
foreach ($rel in @('campaign\login_bonus\common\campaign_result_tx.png','campaign\story\common\campaign_result_tx.png')) {
    $bmp = New-CanvasCopy (Join-Path $SourceRoot $rel)
    Set-VerticalFill $bmp 50 383 18 101 12 112 216
    $g = New-Graphics $bmp
    New-OutlinedPath $g '获得奖励' 'Microsoft YaHei' 58 ([System.Drawing.FontStyle]::Bold) ([System.Drawing.RectangleF]::new(40, 18, 353, 88)) ([System.Drawing.Color]::FromArgb(255,255,231,116)) ([System.Drawing.Color]::FromArgb(255,92,49,5)) 4.5 ([System.Drawing.Color]::FromArgb(110,255,232,132)) 8
    $g.Dispose(); Save-Asset $bmp $rel
}

# Global books: remove only the Latin title and keep the original frame/illustration.
foreach ($spec in @(
    @{ Rel='common\global\global_kimochi_a.png'; Text='心魔战'; Fill=[System.Drawing.Color]::FromArgb(255,255,232,116); Outline=[System.Drawing.Color]::FromArgb(255,64,38,114) },
    @{ Rel='common\global\global_patrol_a.png'; Text='巡逻'; Fill=[System.Drawing.Color]::FromArgb(255,255,232,116); Outline=[System.Drawing.Color]::FromArgb(255,46,103,40) }
)) {
    $bmp = New-CanvasCopy (Join-Path $SourceRoot $spec.Rel)
    # The Latin title occupies y≈190..232; stop above the decorative ribbon.
    Set-InterpolatedStrip $bmp 107 247 184 252 103 251
    $g = New-Graphics $bmp
    New-OutlinedPath $g $spec.Text 'Microsoft YaHei' 35 ([System.Drawing.FontStyle]::Bold) ([System.Drawing.RectangleF]::new(98, 198, 156, 52)) $spec.Fill $spec.Outline 2.6 ([System.Drawing.Color]::FromArgb(90,0,0,0)) 5
    $g.Dispose(); Save-Asset $bmp $spec.Rel
}

# Current-server banners.  Only the text panels are covered; characters, item art,
# prices, quantities and decorative frames remain pixel-identical outside them.
$rel = 'banner\announce\banner_0500_m.png'
$bmp = New-CanvasCopy (Join-Path $SourceRoot $rel)
Set-SolidRectangle $bmp 380 7 135 31 ([System.Drawing.Color]::FromArgb(255,92,73,165))
Set-SolidRectangle $bmp 270 42 368 39 ([System.Drawing.Color]::FromArgb(255,72,56,143))
Set-SolidRectangle $bmp 248 82 392 43 ([System.Drawing.Color]::FromArgb(255,72,56,143))
Set-SolidRectangle $bmp 185 137 440 30 ([System.Drawing.Color]::FromArgb(255,225,224,241))
Add-CenteredOutlinedText $bmp '限时7天' 18 ([System.Drawing.Color]::White) ([System.Drawing.Color]::FromArgb(255,230,50,118)) 2 ([System.Drawing.Color]::FromArgb(100,255,255,255)) 4 380 6 135 32
Add-CenteredOutlinedText $bmp '主线剧情获得点数提升！' 21 ([System.Drawing.Color]::White) ([System.Drawing.Color]::FromArgb(255,92,39,152)) 2.2 ([System.Drawing.Color]::FromArgb(100,255,130,230)) 4 270 41 368 41
Add-CenteredOutlinedText $bmp '觉醒强化关卡掉落奖励提升！' 19 ([System.Drawing.Color]::White) ([System.Drawing.Color]::FromArgb(255,92,39,152)) 2.2 ([System.Drawing.Color]::FromArgb(100,255,130,230)) 4 248 81 392 45
Add-CenteredOutlinedText $bmp '挑战相应关卡，培养魔法少女吧！' 12 ([System.Drawing.Color]::FromArgb(255,55,32,96)) ([System.Drawing.Color]::FromArgb(255,225,224,241)) 1 ([System.Drawing.Color]::Transparent) 0 185 136 440 32
Save-Asset $bmp $rel

$rel = 'banner\gacha\gachabanner_0730_m.png'
$bmp = New-CanvasCopy (Join-Path $SourceRoot $rel)
Set-SolidRectangle $bmp 274 22 132 34 ([System.Drawing.Color]::FromArgb(255,128,118,42))
Set-SolidRectangle $bmp 78 54 526 66 ([System.Drawing.Color]::FromArgb(255,92,119,33))
Set-SolidRectangle $bmp 75 112 535 55 ([System.Drawing.Color]::FromArgb(255,139,81,20))
Add-CenteredOutlinedText $bmp '限时7天' 18 ([System.Drawing.Color]::White) ([System.Drawing.Color]::FromArgb(255,144,92,20)) 2 ([System.Drawing.Color]::FromArgb(100,255,255,255)) 4 274 21 132 35
Add-CenteredOutlinedText $bmp '新手冲刺记忆结晶扭蛋' 23 ([System.Drawing.Color]::FromArgb(255,255,247,94)) ([System.Drawing.Color]::FromArgb(255,58,126,24)) 2.2 ([System.Drawing.Color]::FromArgb(100,255,255,255)) 4 78 54 526 63
Add-CenteredOutlinedText $bmp '十连扭蛋必得1张★4记忆结晶！' 13 ([System.Drawing.Color]::White) ([System.Drawing.Color]::FromArgb(255,124,65,15)) 1.8 ([System.Drawing.Color]::FromArgb(100,255,238,115)) 3.5 75 113 535 53
Save-Asset $bmp $rel

$rel = 'banner\common\banner_purchase_001_1_a.png'
$bmp = New-CanvasCopy (Join-Path $SourceRoot $rel)
Set-SolidRectangle $bmp 53 14 347 52 ([System.Drawing.Color]::FromArgb(255,255,160,183))
Set-SolidRectangle $bmp 8 68 430 35 ([System.Drawing.Color]::FromArgb(255,246,132,157))
Add-CenteredOutlinedText $bmp 'Magia通行证30天' 27 ([System.Drawing.Color]::White) ([System.Drawing.Color]::FromArgb(255,226,57,102)) 2.2 ([System.Drawing.Color]::FromArgb(105,255,255,255)) 4 53 13 347 54
Add-CenteredOutlinedText $bmp '魔法石33个＋30天内每日5个＋每日1个DC' 11 ([System.Drawing.Color]::White) ([System.Drawing.Color]::FromArgb(255,189,79,21)) 1.5 ([System.Drawing.Color]::FromArgb(90,255,244,165)) 3 8 67 430 37
Save-Asset $bmp $rel

# Small transparent text sprites.
foreach ($spec in @(
    @{Rel='common\chara\lv_max.png';Text='满级';Size=19;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,244,72,115);Glow=[Drawing.Color]::FromArgb(130,255,108,145)},
    @{Rel='common\chara\result_text_level.png';Text='等级提升！';Size=42;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,236,53,72);Glow=[Drawing.Color]::FromArgb(150,255,104,128)},
    @{Rel='event\eventWalpurgis\result\_anime\text_clear.png';Text='通关';Size=66;Fill=[Drawing.Color]::FromArgb(255,255,253,218);Outline=[Drawing.Color]::FromArgb(255,116,80,25);Glow=[Drawing.Color]::FromArgb(140,255,235,92)},
    @{Rel='event\eventWalpurgis\result\_anime\text_reward.png';Text='奖励';Size=17;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,147,95,36);Glow=[Drawing.Color]::FromArgb(100,255,224,165)},
    @{Rel='page\announce\icon_new.png';Text='新';Size=18;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,243,85,105);Glow=[Drawing.Color]::FromArgb(100,255,134,149)},
    @{Rel='page\announce\icon_new_a.png';Text='新';Size=18;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,243,85,105);Glow=[Drawing.Color]::FromArgb(100,255,134,149)},
    @{Rel='page\arena\next_mirror.png';Text='下一镜层';Size=36;Fill=[Drawing.Color]::FromArgb(255,255,225,90);Outline=[Drawing.Color]::FromArgb(255,90,53,8);Glow=[Drawing.Color]::FromArgb(150,255,223,62)},
    @{Rel='page\arena\result\next_mirror.png';Text='下一镜层';Size=44;Fill=[Drawing.Color]::FromArgb(255,255,189,31);Outline=[Drawing.Color]::FromArgb(255,90,44,0);Glow=[Drawing.Color]::FromArgb(150,255,221,71)},
    @{Rel='page\arena\result\result_lose.png';Text='失败';Size=54;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,105,94,83);Glow=[Drawing.Color]::FromArgb(125,255,242,178)},
    @{Rel='page\arena\result\result_win.png';Text='胜利';Size=59;Fill=[Drawing.Color]::FromArgb(255,255,233,127);Outline=[Drawing.Color]::FromArgb(255,116,44,0);Glow=[Drawing.Color]::FromArgb(145,255,235,85)},
    @{Rel='page\formation\icon_limit_max.png';Text='上限';Size=13;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,235,44,75);Glow=[Drawing.Color]::FromArgb(110,255,95,115)},
    @{Rel='page\gacha\gacha_new.png';Text='新';Size=19;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,255,103,45);Glow=[Drawing.Color]::FromArgb(110,255,218,64)},
    @{Rel='page\mission\icon_mission_clear.png';Text='完成';Size=17;Fill=[Drawing.Color]::FromArgb(255,255,233,116);Outline=[Drawing.Color]::FromArgb(255,154,65,10);Glow=[Drawing.Color]::FromArgb(100,255,140,48)},
    @{Rel='page\mission\mission_clear.png';Text='完成';Size=18;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,226,57,73);Glow=[Drawing.Color]::FromArgb(120,255,111,131)},
    @{Rel='page\patrol\anime\txt_finish.png';Text='完成';Size=58;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,164,139,14);Glow=[Drawing.Color]::FromArgb(170,255,245,63)},
    @{Rel='page\patrol\anime\txt_start.png';Text='开始';Size=58;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,160,77,165);Glow=[Drawing.Color]::FromArgb(170,239,137,255)},
    @{Rel='page\patrol\text_result_header.png';Text='完成';Size=44;Fill=[Drawing.Color]::FromArgb(255,255,245,159);Outline=[Drawing.Color]::FromArgb(255,132,81,1);Glow=[Drawing.Color]::FromArgb(160,255,231,58)},
    @{Rel='page\quest\animation\story_clear.png';Text='通关';Size=27;Fill=[Drawing.Color]::FromArgb(255,255,247,192);Outline=[Drawing.Color]::FromArgb(255,143,71,0);Glow=[Drawing.Color]::FromArgb(105,255,220,59)},
    @{Rel='page\quest\main\icon_challenge.png';Text='挑战';Size=23;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,232,36,144);Glow=[Drawing.Color]::FromArgb(110,255,86,191)},
    @{Rel='page\quest\quest_state_new.png';Text='新';Size=20;Fill=[Drawing.Color]::FromArgb(255,255,238,125);Outline=[Drawing.Color]::FromArgb(255,152,89,7);Glow=[Drawing.Color]::FromArgb(130,255,199,44)},
    @{Rel='page\quest\secondPartLast\clearanime\txt_reward.png';Text='奖励';Size=19;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,145,95,44);Glow=[Drawing.Color]::FromArgb(95,255,224,167)},
    @{Rel='regularEvent\accomplish\common\clearanime\text_clear.png';Text='通关';Size=37;Fill=[Drawing.Color]::FromArgb(255,255,243,168);Outline=[Drawing.Color]::FromArgb(255,130,64,0);Glow=[Drawing.Color]::FromArgb(125,255,221,62)},
    @{Rel='regularEvent\accomplish\common\clearanime\text_reward.png';Text='奖励';Size=28;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,143,92,38);Glow=[Drawing.Color]::FromArgb(90,255,223,165)},
    @{Rel='regularEvent\extermination\common\clearanime\txt_reward.png';Text='奖励';Size=19;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,145,95,44);Glow=[Drawing.Color]::FromArgb(95,255,224,167)},
    @{Rel='regularEvent\groupBattle\common\mission_clear.png';Text='完成';Size=15;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,225,54,75);Glow=[Drawing.Color]::FromArgb(115,255,100,125)},
    @{Rel='regularEvent\groupBattle\common\result\result_title_text.png';Text='战斗结果';Size=34;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,143,95,23);Glow=[Drawing.Color]::FromArgb(140,255,229,99)},
    @{Rel='regularEvent\groupBattle\common\result\touch_screen.png';Text='点击屏幕';Size=21;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,134,69,176);Glow=[Drawing.Color]::FromArgb(135,232,150,255)},
    @{Rel='regularEvent\groupBattle\common\top\text\total_damege_title.png';Text='总伤害';Size=15;Fill=[Drawing.Color]::FromArgb(255,255,204,140);Outline=[Drawing.Color]::FromArgb(255,73,26,100);Glow=[Drawing.Color]::FromArgb(100,239,98,196)},
    @{Rel='regularEvent\groupBattle\common2\text_01.png';Text='后半';Size=34;Fill=[Drawing.Color]::FromArgb(255,255,245,202);Outline=[Drawing.Color]::FromArgb(255,141,95,17);Glow=[Drawing.Color]::FromArgb(125,255,225,100)},
    @{Rel='regularEvent\groupBattle\common2\text_02.png';Text='小组战开始';Size=34;Fill=[Drawing.Color]::FromArgb(255,255,245,202);Outline=[Drawing.Color]::FromArgb(255,141,95,17);Glow=[Drawing.Color]::FromArgb(125,255,225,100)}
)) {
    $bmp = New-TransparentLike $spec.Rel
    Add-CenteredOutlinedText $bmp $spec.Text $spec.Size $spec.Fill $spec.Outline 2.2 $spec.Glow 5
    Save-Asset $bmp $spec.Rel
}

# The episode-level caption is only 16 pixels high; use a single anti-aliased
# fill rather than a thick outlined path so every ideograph remains legible.
$rel = 'page\chara\text_episodelv.png'
$bmp = New-TransparentLike $rel
$g = New-Graphics $bmp
$font = [Drawing.Font]::new('Microsoft YaHei',10,[Drawing.FontStyle]::Bold,[Drawing.GraphicsUnit]::Pixel)
$fmt = [Drawing.StringFormat]::new(); $fmt.Alignment=[Drawing.StringAlignment]::Center; $fmt.LineAlignment=[Drawing.StringAlignment]::Center
$brush = [Drawing.SolidBrush]::new([Drawing.Color]::FromArgb(255,179,116,25))
$g.DrawString('使用道具解锁事件等级',$font,$brush,[Drawing.RectangleF]::new(0,0,$bmp.Width,$bmp.Height),$fmt)
$brush.Dispose();$fmt.Dispose();$font.Dispose();$g.Dispose(); Save-Asset $bmp $rel

# Daily free-ten-pull badge retains its purple emblem but replaces Japanese text.
$rel = 'common\global\gacha_badge_c.png'
$bmp = New-TransparentLike $rel
$g = New-Graphics $bmp
$purple = [Drawing.SolidBrush]::new([Drawing.Color]::FromArgb(255,194,54,199))
$g.FillEllipse($purple,5,5,94,37); $purple.Dispose()
New-OutlinedPath $g '每日1次' 'Microsoft YaHei' 10 ([Drawing.FontStyle]::Bold) ([Drawing.RectangleF]::new(4,4,96,18)) ([Drawing.Color]::White) ([Drawing.Color]::FromArgb(255,148,33,160)) 1.4 ([Drawing.Color]::FromArgb(110,255,255,255)) 3
New-OutlinedPath $g '免费10连' 'Microsoft YaHei' 12 ([Drawing.FontStyle]::Bold) ([Drawing.RectangleF]::new(4,20,96,23)) ([Drawing.Color]::White) ([Drawing.Color]::FromArgb(255,148,33,160)) 1.5 ([Drawing.Color]::FromArgb(110,255,255,255)) 3
$g.Dispose(); Save-Asset $bmp $rel

# Beginner login title: retain the current green ribbon and replace only the title core.
$rel = 'page\loginbonus\day_title_beginner.png'
$bmp = New-CanvasCopy (Join-Path $SourceRoot $rel)
Set-SolidRectangle $bmp 250 2 440 38 ([Drawing.Color]::FromArgb(255,150,207,28))
Add-CenteredOutlinedText $bmp '新手登录奖励' 21 ([Drawing.Color]::White) ([Drawing.Color]::FromArgb(255,72,128,12)) 1.7 ([Drawing.Color]::FromArgb(90,255,255,255)) 3 250 0 440 41
Save-Asset $bmp $rel

# Button-like sprites: preserve frames and overwrite only their text-safe centre.
foreach ($spec in @(
    @{Rel='page\arena\result\btn_replay_preserve.png';Rect=@(34,19,154,39);Bg=[Drawing.Color]::FromArgb(255,170,70,226);Text='保存回放';Size=21;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,77,13,115)},
    @{Rel='page\chara\btn_max.png';Rect=@(12,12,56,27);Bg=[Drawing.Color]::FromArgb(255,255,252,245);Text='已满';Size=19;Fill=[Drawing.Color]::FromArgb(255,151,95,17);Outline=[Drawing.Color]::FromArgb(255,255,252,245)},
    @{Rel='page\patrol\btn_finish_all.png';Rect=@(27,11,114,24);Bg=[Drawing.Color]::FromArgb(255,255,252,245);Text='全部完成';Size=18;Fill=[Drawing.Color]::FromArgb(255,143,94,39);Outline=[Drawing.Color]::FromArgb(255,255,252,245)},
    @{Rel='page\patrol\btn_finish_all_off.png';Rect=@(27,11,114,24);Bg=[Drawing.Color]::FromArgb(255,246,246,246);Text='全部完成';Size=18;Fill=[Drawing.Color]::FromArgb(255,120,120,120);Outline=[Drawing.Color]::FromArgb(255,246,246,246)},
    @{Rel='page\patrol\btn_start_all.png';Rect=@(27,11,114,24);Bg=[Drawing.Color]::FromArgb(255,255,252,245);Text='全部巡逻';Size=18;Fill=[Drawing.Color]::FromArgb(255,143,94,39);Outline=[Drawing.Color]::FromArgb(255,255,252,245)},
    @{Rel='page\patrol\btn_start_all_off.png';Rect=@(27,11,114,24);Bg=[Drawing.Color]::FromArgb(255,246,246,246);Text='全部巡逻';Size=18;Fill=[Drawing.Color]::FromArgb(255,120,120,120);Outline=[Drawing.Color]::FromArgb(255,246,246,246)},
    @{Rel='page\patrol\btn_team_off.png';Rect=@(18,4,96,20);Bg=[Drawing.Color]::FromArgb(255,217,40,112);Text='移除';Size=17;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,217,40,112)},
    @{Rel='page\patrol\btn_teareset.png';Rect=@(18,8,108,25);Bg=[Drawing.Color]::FromArgb(255,255,252,245);Text='解散队伍';Size=18;Fill=[Drawing.Color]::FromArgb(255,143,94,39);Outline=[Drawing.Color]::FromArgb(255,255,252,245)},
    @{Rel='regularEvent\groupBattle\common2\battle_top\btn_group.png';Rect=@(18,20,82,32);Bg=[Drawing.Color]::FromArgb(255,165,42,221);Text='小组';Size=20;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,69,16,102)},
    @{Rel='regularEvent\groupBattle\common2\battle_top\btn_morcwar.png';Rect=@(18,14,83,28);Bg=[Drawing.Color]::FromArgb(255,255,252,245);Text='模拟战';Size=19;Fill=[Drawing.Color]::FromArgb(255,142,91,33);Outline=[Drawing.Color]::FromArgb(255,255,252,245)}
)) {
    $bmp = New-CanvasCopy (Join-Path $SourceRoot $spec.Rel)
    Set-SolidRectangle $bmp $spec.Rect[0] $spec.Rect[1] $spec.Rect[2] $spec.Rect[3] $spec.Bg
    Add-CenteredOutlinedText $bmp $spec.Text $spec.Size $spec.Fill $spec.Outline 1.2 ([Drawing.Color]::Transparent) 0 $spec.Rect[0] $spec.Rect[1] $spec.Rect[2] $spec.Rect[3]
    Save-Asset $bmp $spec.Rel
}

# Patrol status labels retain warning emblems.
foreach ($spec in @(
    @{Rel='page\patrol\text_team_lock.png';Text='此区域尚未开放';Size=22;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,93,93,93);Glow=[Drawing.Color]::FromArgb(100,255,255,255)},
    @{Rel='page\patrol\text_team_onpatrol.png';Text='正在巡逻';Size=23;Fill=[Drawing.Color]::White;Outline=[Drawing.Color]::FromArgb(255,109,55,159);Glow=[Drawing.Color]::FromArgb(130,200,113,255)}
)) {
    $bmp = New-CanvasCopy (Join-Path $SourceRoot $spec.Rel)
    Set-SolidRectangle $bmp 49 0 ($bmp.Width-49) $bmp.Height ([Drawing.Color]::Transparent)
    $g = [Drawing.Graphics]::FromImage($bmp); $g.CompositingMode=[Drawing.Drawing2D.CompositingMode]::SourceCopy
    $g.FillRectangle([Drawing.Brushes]::Transparent,49,0,$bmp.Width-49,$bmp.Height); $g.Dispose()
    Add-CenteredOutlinedText $bmp $spec.Text $spec.Size $spec.Fill $spec.Outline 1.8 $spec.Glow 4 46 0 ($bmp.Width-46) $bmp.Height
    Save-Asset $bmp $spec.Rel
}

# Group battle start button: keep the current octagonal art and numeric recovery label.
$rel = 'regularEvent\groupBattle\common2\battle_top\btn_battle.png'
$bmp = New-CanvasCopy (Join-Path $SourceRoot $rel)
Set-SolidRectangle $bmp 35 36 106 119 ([Drawing.Color]::FromArgb(255,145,28,202))
Add-CenteredOutlinedText $bmp '战斗开始' 21 ([Drawing.Color]::White) ([Drawing.Color]::FromArgb(255,68,12,102)) 1.8 ([Drawing.Color]::FromArgb(95,238,147,255)) 3.5 35 38 106 54
Add-CenteredOutlinedText $bmp '挑战次数' 10 ([Drawing.Color]::White) ([Drawing.Color]::FromArgb(255,68,12,102)) 1.1 ([Drawing.Color]::Transparent) 0 35 92 106 25
Add-CenteredOutlinedText $bmp '16:00时恢复' 8 ([Drawing.Color]::White) ([Drawing.Color]::FromArgb(255,68,12,102)) 1 ([Drawing.Color]::Transparent) 0 35 127 106 22
Save-Asset $bmp $rel

# Keep the resurrection beam but replace its English title.
$rel = 'regularEvent\groupBattle\common\animation\resurrect\title.png'
$bmp = New-CanvasCopy (Join-Path $SourceRoot $rel)
$g = [Drawing.Graphics]::FromImage($bmp); $g.CompositingMode=[Drawing.Drawing2D.CompositingMode]::SourceCopy
$g.FillRectangle([Drawing.Brushes]::Transparent,155,52,484,96); $g.Dispose()
Add-CenteredOutlinedText $bmp '〈首领出现〉' 40 ([Drawing.Color]::White) ([Drawing.Color]::FromArgb(255,116,25,230)) 2.6 ([Drawing.Color]::FromArgb(170,217,128,255)) 7 145 45 504 110
Save-Asset $bmp $rel

# Patrol reward title: keep the gold ribbon ornaments and replace its centre label.
$rel = 'page\patrol\bg_result_title.png'
$bmp = New-CanvasCopy (Join-Path $SourceRoot $rel)
Set-SolidRectangle $bmp 75 2 304 30 ([Drawing.Color]::FromArgb(255,184,139,78))
Add-CenteredOutlinedText $bmp '获得奖励' 18 ([Drawing.Color]::White) ([Drawing.Color]::FromArgb(255,125,79,25)) 1.4 ([Drawing.Color]::FromArgb(80,255,230,152)) 3 75 0 304 34
Save-Asset $bmp $rel

# Seal the complete, deterministic output list and byte verification record.
$orderedAssets = @($script:GeneratedAssets | Sort-Object path)
[IO.Directory]::CreateDirectory($EvidenceRoot) | Out-Null
$manifest = [ordered]@{
    schema = 1
    generator = 'tools/build-localized-ui-images.ps1'
    source_root = $SourceRoot
    product_root = $ProductRoot
    generated_count = $orderedAssets.Count
    current_canvas_recreated_count = 51
    preexisting_generated_count = 7
    verify_only = [bool]$VerifyOnly
    assets = $orderedAssets
}
$json = $manifest | ConvertTo-Json -Depth 8
$manifestPath = Join-Path $EvidenceRoot 'localized_ui_image_manifest.json'
$verificationPath = Join-Path $EvidenceRoot 'localized_ui_image_verification.json'
if (-not $VerifyOnly) {
    [IO.File]::WriteAllText($manifestPath, $json + "`n", [Text.UTF8Encoding]::new($false))
} else {
    $verification = [ordered]@{
        schema = 1
        status = 'pass'
        verified_count = $orderedAssets.Count
        current_canvas_recreated_count = 51
        manifest_path = 'localized_ui_image_manifest.json'
        verified_assets = $orderedAssets
    }
    [IO.File]::WriteAllText($verificationPath, (($verification | ConvertTo-Json -Depth 8) + "`n"), [Text.UTF8Encoding]::new($false))
}

Write-Output ('localized_ui_images={0} current_canvas_recreated=51 verify_only={1}' -f $orderedAssets.Count, [bool]$VerifyOnly)
