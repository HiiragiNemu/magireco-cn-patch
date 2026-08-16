param(
    [string]$ProductRoot = ""
)

$ErrorActionPreference = 'Stop'

if (-not $ProductRoot) {
    $ProductRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path
} else {
    $ProductRoot = (Resolve-Path -LiteralPath $ProductRoot).Path
}

$RollbackTool = Join-Path $ProductRoot 'tools\rollback-pass20-product-stage.py'
if (-not (Test-Path -LiteralPath $RollbackTool -PathType Leaf)) {
    throw "Rollback tool is missing: $RollbackTool"
}

& python $RollbackTool --stage-root $PSScriptRoot --product-root $ProductRoot
if ($LASTEXITCODE -ne 0) {
    throw "Pass22 rollback failed with exit code $LASTEXITCODE"
}
