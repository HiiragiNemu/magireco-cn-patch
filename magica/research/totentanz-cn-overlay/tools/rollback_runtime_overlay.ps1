[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [Parameter(Mandatory = $true)]
    [string]$RepoRoot,

    [string]$BaselineRef = '3c983a778429d5e56a2569aa28ea8c622d988c63',

    [string]$PatchPath
)

$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path -LiteralPath $RepoRoot).Path

if (-not (Test-Path -LiteralPath (Join-Path $repo '.git'))) {
    throw "RepoRoot is not a Git checkout: $repo"
}

$targets = @(
    '.gitattributes',
    'Build_JS_Injector.py',
    'magica',
    '.github/workflows/sync-and-upload.yml'
)

Push-Location $repo
try {
    $baselineCommit = (& git rev-parse --verify "$BaselineRef`^{commit}" 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $baselineCommit) {
        throw "BASELINE_NOT_FOUND ref=$BaselineRef"
    }

    & git merge-base --is-ancestor $baselineCommit HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "BASELINE_NOT_ANCESTOR baseline=$baselineCommit head=$(& git rev-parse HEAD)"
    }

    $dirty = @(& git status --porcelain=v1 --untracked-files=all -- $targets)
    if ($LASTEXITCODE -ne 0) {
        throw "STATUS_CHECK_FAILED exit=$LASTEXITCODE"
    }
    if ($dirty.Count -gt 0) {
        throw "ROLLBACK_REFUSED_DIRTY_TARGETS`n$($dirty -join [Environment]::NewLine)"
    }

    if ($PatchPath) {
        $patch = (Resolve-Path -LiteralPath $PatchPath -ErrorAction Stop).Path
        & git apply --check --reverse --binary --whitespace=nowarn -- $patch
        if ($LASTEXITCODE -ne 0) {
            throw "ROLLBACK_CHECK_FAILED exit=$LASTEXITCODE patch=$patch"
        }
        if ($PSCmdlet.ShouldProcess($repo, "reverse binary overlay patch $patch")) {
            & git apply --reverse --binary --whitespace=nowarn -- $patch
            if ($LASTEXITCODE -ne 0) {
                throw "ROLLBACK_APPLY_FAILED exit=$LASTEXITCODE patch=$patch"
            }
        }
        $method = "binary-patch:$patch"
    }
    else {
        if ($PSCmdlet.ShouldProcess($repo, "restore overlay targets from $baselineCommit")) {
            & git restore --source=$baselineCommit --staged --worktree -- $targets
            if ($LASTEXITCODE -ne 0) {
                throw "ROLLBACK_RESTORE_FAILED exit=$LASTEXITCODE baseline=$baselineCommit"
            }
        }
        $method = "git-restore:$baselineCommit"
    }

    if (-not $WhatIfPreference) {
        & git diff --exit-code -- $baselineCommit -- $targets
        if ($LASTEXITCODE -ne 0) {
            throw "ROLLBACK_VERIFY_WORKTREE_FAILED exit=$LASTEXITCODE baseline=$baselineCommit"
        }
        & git diff --cached --exit-code -- $baselineCommit -- $targets
        if ($LASTEXITCODE -ne 0) {
            throw "ROLLBACK_VERIFY_INDEX_FAILED exit=$LASTEXITCODE baseline=$baselineCommit"
        }
    }

    $head = (& git rev-parse HEAD).Trim()
    Write-Output "ROLLBACK_OK repo=$repo baseline=$baselineCommit head=$head method=$method"
}
finally {
    Pop-Location
}
