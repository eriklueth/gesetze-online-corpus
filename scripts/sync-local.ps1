# Daily driver for the local Windows box.
#
# Runs: snapshot -> verify -> commit-events -> push of both repos.
# Intended to be scheduled via Windows Task Scheduler, see README.
#
# Exit codes:
#   0 ok (with or without changes)
#   1 snapshot failed
#   2 verify failed
#   3 push failed
#
# Notes:
#   - Requires the tools repo at $ToolsRoot and the data repo at $DataRepo.
#   - Sends stdout/stderr into a rotating log at $LogDir.

[CmdletBinding()]
param(
    [string]$ToolsRoot = "C:\Projekte\gesetze-online-corpus",
    [string]$DataRepo  = "C:\Projekte\gesetze-corpus-data",
    [string]$LogDir    = "C:\Projekte\gesetze-online-corpus\logs",
    [int]   $Workers   = 4,
    [int]   $KeepLogs  = 30,
    [switch]$SkipPush
)

$ErrorActionPreference = "Continue"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$stamp = (Get-Date -Format "yyyyMMdd-HHmmss")
$log = Join-Path $LogDir "sync-$stamp.log"

function Log($msg) {
    $line = "$(Get-Date -Format o) $msg"
    $line | Tee-Object -FilePath $log -Append | Write-Host
}

Log "=== sync-local start ==="
Log "tools=$ToolsRoot data=$DataRepo workers=$Workers"

$env:GESETZE_DATA_REPO = $DataRepo

Set-Location $ToolsRoot
& python -m gesetze_corpus sync --workers $Workers *>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { Log "snapshot/sync failed (exit=$LASTEXITCODE)"; exit 1 }

& python -m gesetze_corpus verify *>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { Log "verify failed (exit=$LASTEXITCODE)"; exit 2 }

if ($SkipPush) { Log "skip push requested"; exit 0 }

Set-Location $DataRepo
git fetch origin main *>&1 | Tee-Object -FilePath $log -Append | Out-Null
$rev = (& git rev-list --count --left-right "HEAD...origin/main" 2>$null)
if (-not $rev) { $aheadCount = 0 } else { $aheadCount = [int]($rev.Split()[0]) }
if ($aheadCount -eq 0) {
    Log "no new commits to push, done"
    exit 0
}

Log "pushing $aheadCount commits to origin/main"
& git push *>&1 | Tee-Object -FilePath $log -Append
if ($LASTEXITCODE -ne 0) { Log "push failed (exit=$LASTEXITCODE)"; exit 3 }

Log "=== sync-local done ==="

# Rotate logs: keep only the most recent $KeepLogs sync-*.log files.
# Runs on success only - failed runs leave all logs in place for forensics.
try {
    Get-ChildItem $LogDir -Filter "sync-*.log" -File |
        Sort-Object LastWriteTime -Descending |
        Select-Object -Skip $KeepLogs |
        Remove-Item -Force -ErrorAction SilentlyContinue
} catch {
    Log "log rotation failed (non-fatal): $($_.Exception.Message)"
}

exit 0
