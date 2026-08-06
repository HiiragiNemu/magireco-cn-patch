[CmdletBinding()]
param(
  [Parameter(Mandatory = $true)][string]$TargetMagica,
  [Parameter(Mandatory = $true)][string]$BackupRoot
)
$ErrorActionPreference = "Stop"
$overlay = Join-Path $PSScriptRoot "overlay"
$overlayPrefix = $overlay.TrimEnd([char[]]@('\', '/')) + [IO.Path]::DirectorySeparatorChar
$target = [IO.Path]::GetFullPath($TargetMagica)
$backup = [IO.Path]::GetFullPath($BackupRoot)
New-Item -ItemType Directory -Path $target -Force | Out-Null
New-Item -ItemType Directory -Path $backup -Force | Out-Null
$entries = @()
$files = Get-ChildItem -LiteralPath $overlay -Recurse -File
foreach ($file in $files) {
  $relative = $file.FullName.Substring($overlayPrefix.Length)
  $destination = Join-Path $target $relative
  $backupFile = Join-Path $backup $relative
  $existed = Test-Path -LiteralPath $destination
  if ($existed) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $backupFile) -Force | Out-Null
    Copy-Item -LiteralPath $destination -Destination $backupFile -Force
  }
  New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
  Copy-Item -LiteralPath $file.FullName -Destination $destination -Force
  $entries += [ordered]@{ relative = $relative; existed = $existed }
}
$record = [ordered]@{ target = $target; backup = $backup; entries = $entries }
$recordPath = Join-Path $backup "application_record.json"
$record | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $recordPath -Encoding utf8
Write-Output "APPLY_OK files=$($files.Count) target=$target backup=$backup record=$recordPath"
