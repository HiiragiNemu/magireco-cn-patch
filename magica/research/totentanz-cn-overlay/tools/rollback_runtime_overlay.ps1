[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,

    [string]$PatchPath = (Join-Path $PSScriptRoot '..\patches\runtime-overlay.patch')
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath $RepoRoot).Path
$patch = (Resolve-Path -LiteralPath $PatchPath).Path

if (-not (Test-Path -LiteralPath (Join-Path $repo '.git'))) {
    throw "RepoRoot is not a Git checkout: $repo"
}

Push-Location $repo
try {
    & git apply --check --reverse --binary --whitespace=nowarn -- $patch
    if ($LASTEXITCODE -ne 0) {
        throw "ROLLBACK_CHECK_FAILED exit=$LASTEXITCODE patch=$patch"
    }

    & git apply --reverse --binary --whitespace=nowarn -- $patch
    if ($LASTEXITCODE -ne 0) {
        throw "ROLLBACK_APPLY_FAILED exit=$LASTEXITCODE patch=$patch"
    }

    Write-Output "ROLLBACK_OK repo=$repo patch=$patch"
}
finally {
    Pop-Location
}
