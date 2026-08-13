[CmdletBinding()]
param(
    [string]$BaselineCommit = "d5e8f75d93f6760a588e592c22a3754d19370c68",
    [string]$ReportPath = "magica/i18n_audit/release_v26_authority/pass18_rollback_verification.json",
    [string]$Python = "python",
    [string]$VerificationContext = "local-worktree"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$RestorePaths = @(
    "i18n/authority-policy.json",
    "madomagi/engine_i18n.tsv",
    "magica/js/libs/cardList.json",
    "magica/js/libs/cardMagiaMap.json",
    "magica/js/libs/charaList.json",
    "magica/js/libs/charaMessageList.json",
    "magica/js/libs/doppelCardMagiaMap.json",
    "magica/js/libs/doppelList.json",
    "magica/js/libs/emotionSkillMap.json",
    "magica/js/libs/itemList.json",
    "magica/js/libs/live2dList.json",
    "magica/js/libs/pieceList.json",
    "magica/js/libs/pieceSkillMap.json",
    "magica/js/libs/sectionList.json",
    "magica/js/libs/shopItemList.json",
    "magica/js/regularEvent/groupBattle/view/BossPageView.js"
)
$DerivedPaths = @(
    "magica/js/libs/jquery-3.7.1.min.js",
    "magica/i18n_audit/release_v26_authority/runtime_layer_manifest.json",
    "magica/i18n_audit/release_v26_authority/RUNTIME_LAYER_SHA256SUMS.txt"
)
$VerifyPaths = @($RestorePaths + $DerivedPaths)

function Invoke-NativeChecked {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList
    )
    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit status $LASTEXITCODE`: $FilePath $($ArgumentList -join ' ')"
    }
}

function Invoke-PythonCodeChecked {
    param(
        [Parameter(Mandatory = $true)][string]$Code,
        [Parameter(Mandatory = $true)][string[]]$ArgumentList
    )

    # Passing multiline source containing quotes through `python -c` is not
    # byte-stable on Windows PowerShell: native argument reconstruction can
    # strip the quotes inside Python list/f-string expressions.  A uniquely
    # named UTF-8 script preserves the source literally on Windows and Unix.
    $TempScript = Join-Path ([IO.Path]::GetTempPath()) (
        "magireco-v26-rollback-{0}.py" -f [Guid]::NewGuid().ToString("N")
    )
    try {
        [IO.File]::WriteAllText(
            $TempScript,
            $Code,
            [Text.UTF8Encoding]::new($false)
        )
        Invoke-NativeChecked -FilePath $Python -ArgumentList (@($TempScript) + $ArgumentList)
    }
    finally {
        if (Test-Path -LiteralPath $TempScript) {
            Remove-Item -LiteralPath $TempScript -Force
        }
    }
}

Push-Location $RepoRoot
try {
    Invoke-NativeChecked -FilePath "git" -ArgumentList @("cat-file", "-e", "$BaselineCommit^{commit}")

    # Read each baseline object as raw bytes. This bypasses checkout/EOL filters, so
    # restored files are byte-identical on both Windows and Unix checkouts.
    $RestoreCode = @'
import pathlib
import subprocess
import sys

repo = pathlib.Path(sys.argv[1]).resolve()
commit = sys.argv[2]
for rel in sys.argv[3:]:
    data = subprocess.check_output(
        ["git", "-C", str(repo), "cat-file", "blob", f"{commit}:{rel}"]
    )
    path = repo / pathlib.PurePosixPath(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
'@
    $RestoreArguments = @($RepoRoot, $BaselineCommit) + $RestorePaths
    Invoke-PythonCodeChecked -Code $RestoreCode -ArgumentList $RestoreArguments

    $BuilderOutput = & $Python (Join-Path $RepoRoot "Build_JS_Injector.py") 2>&1
    $BuilderExit = $LASTEXITCODE
    $BuilderOutput | ForEach-Object { Write-Output $_ }
    if ($BuilderExit -ne 0) {
        throw "Build_JS_Injector.py failed with exit status $BuilderExit"
    }

    $RuntimeOutput = & $Python (Join-Path $RepoRoot "tools/verify-runtime-layer.py") 2>&1
    $RuntimeExit = $LASTEXITCODE
    $RuntimeOutput | ForEach-Object { Write-Output $_ }
    if ($RuntimeExit -ne 0) {
        throw "verify-runtime-layer.py failed with exit status $RuntimeExit"
    }

    $BuilderText = (($BuilderOutput | ForEach-Object { "$_" }) -join "`n") + "`n"
    $RuntimeText = (($RuntimeOutput | ForEach-Object { "$_" }) -join "`n") + "`n"
    $BuilderBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($BuilderText))
    $RuntimeBase64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($RuntimeText))

    $VerifyCode = @'
import hashlib
import json
import pathlib
import subprocess
import sys
import base64

repo = pathlib.Path(sys.argv[1]).resolve()
commit = sys.argv[2]
report_path = pathlib.Path(sys.argv[3])
execution_context = sys.argv[4]
builder_output = base64.b64decode(sys.argv[5]).decode("utf-8")
runtime_output = base64.b64decode(sys.argv[6]).decode("utf-8")
if not report_path.is_absolute():
    report_path = repo / report_path
paths = sys.argv[7:]

rows = []
for rel in paths:
    expected = subprocess.check_output(
        ["git", "-C", str(repo), "cat-file", "blob", f"{commit}:{rel}"]
    )
    actual = (repo / pathlib.PurePosixPath(rel)).read_bytes()
    row = {
        "path": rel,
        "baseline_bytes": len(expected),
        "restored_bytes": len(actual),
        "baseline_sha256": hashlib.sha256(expected).hexdigest(),
        "restored_sha256": hashlib.sha256(actual).hexdigest(),
        "byte_identical": actual == expected,
    }
    rows.append(row)

failed = [row["path"] for row in rows if not row["byte_identical"]]
runtime_manifest = json.loads(
    (repo / "magica/i18n_audit/release_v26_authority/runtime_layer_manifest.json")
    .read_text(encoding="utf-8")
)
result = {
    "schema": "magireco-cn-v26-pass18-rollback-verification/v1",
    "status": "PASS" if not failed else "FAIL",
    "baseline_commit": commit,
    "execution_context": execution_context,
    "restore_method": "git-cat-file-raw-bytes",
    "builder_command": "python Build_JS_Injector.py",
    "builder_exit_status": 0,
    "builder_output": builder_output,
    "runtime_verification_command": "python tools/verify-runtime-layer.py",
    "runtime_verification_exit_status": 0,
    "runtime_verification_output": runtime_output,
    "verified_file_count": len(rows),
    "byte_identical_count": len(rows) - len(failed),
    "failed_paths": failed,
    "runtime_layer": {
        "dictionary_count": len(runtime_manifest["dictionary_order"]),
        "manifest_entry_count": len(runtime_manifest["files"]),
        "line_endings": runtime_manifest["line_endings"],
        "package_id": runtime_manifest["package_id"],
    },
    "files": rows,
}
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text(
    json.dumps(result, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
    newline="\n",
)
print(json.dumps(result, ensure_ascii=False, indent=2))
if failed:
    raise SystemExit(1)
'@
    $VerifyArguments = @(
        $RepoRoot, $BaselineCommit, $ReportPath,
        $VerificationContext, $BuilderBase64, $RuntimeBase64
    ) + $VerifyPaths
    Invoke-PythonCodeChecked -Code $VerifyCode -ArgumentList $VerifyArguments
}
finally {
    Pop-Location
}
