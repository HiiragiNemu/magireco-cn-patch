[CmdletBinding()]
param([Parameter(Mandatory = $true)][string]$RecordPath)
$ErrorActionPreference = "Stop"
$record = Get-Content -LiteralPath $RecordPath -Raw -Encoding utf8 | ConvertFrom-Json
$count = 0
foreach ($entry in $record.entries) {
  $destination = Join-Path $record.target $entry.relative
  $backupFile = Join-Path $record.backup $entry.relative
  if ($entry.existed) {
    New-Item -ItemType Directory -Path (Split-Path -Parent $destination) -Force | Out-Null
    Copy-Item -LiteralPath $backupFile -Destination $destination -Force
  } elseif (Test-Path -LiteralPath $destination) {
    Remove-Item -LiteralPath $destination -Force
  }
  $count += 1
}
Write-Output "ROLLBACK_OK files=$count target=$($record.target)"
