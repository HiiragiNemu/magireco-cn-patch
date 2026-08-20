$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..\..')).Path
python (Join-Path $repo 'tools\apply-rule-popup-cn.py') `
    --repo $repo `
    --state $PSScriptRoot `
    --rollback
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
