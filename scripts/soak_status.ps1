# Quick status of the active prod mesh soak (no wait).
param(
    [string]$LogGlob = "logs/soak_48h_*.log",
    [string]$ReportFile = "logs/soak_report.json"
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$logs = Get-ChildItem -Path (Join-Path $Root $LogGlob) -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending
if (-not $logs) {
    Write-Host "No soak log matching $LogGlob" -ForegroundColor Yellow
    exit 1
}

if ($logs.Count -gt 1) {
    Write-Host "WARN: multiple soak logs found - stop duplicate soak processes if unintended" -ForegroundColor Yellow
    $logs | ForEach-Object { Write-Host "  - $($_.Name) (modified $($_.LastWriteTime))" -ForegroundColor DarkGray }
}

$log = $logs[0].FullName
$lines = Get-Content $log -Encoding UTF8 -ErrorAction SilentlyContinue
$ts = '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
$startLine = ($lines | Select-String -Pattern "$ts health_watch start" | Select-Object -Last 1)
$lastMesh = ($lines | Select-String -Pattern "$ts OK mesh aligned" | Select-Object -Last 1)
$lastFail = ($lines | Select-String -Pattern "$ts FAIL" | Select-Object -Last 1)
$failCount = ($lines | Select-String -Pattern "$ts FAIL").Count
$meshOk = ($lines | Select-String -Pattern "$ts OK mesh aligned").Count
$done = ($lines | Select-String -Pattern "$ts health_watch done" | Select-Object -Last 1)

Write-Host "Soak status" -ForegroundColor Cyan
Write-Host "  log: $($logs[0].Name)" -ForegroundColor DarkGray
if ($startLine) { Write-Host "  started: $($startLine.Line)" -ForegroundColor DarkGray }
if ($lastMesh) { Write-Host "  latest:  $($lastMesh.Line)" -ForegroundColor Green }
if ($lastFail) { Write-Host "  last_fail: $($lastFail.Line)" -ForegroundColor $(if ($failCount -gt 0) { "Yellow" } else { "DarkGray" }) }
Write-Host "  mesh_ok_cycles=$meshOk fail_lines=$failCount" -ForegroundColor DarkGray

if ($done) {
    Write-Host "  state: FINISHED" -ForegroundColor Green
} else {
    Write-Host "  state: IN_PROGRESS" -ForegroundColor Yellow
}

if (Test-Path $ReportFile) {
    try {
        $rep = Get-Content $ReportFile -Raw | ConvertFrom-Json
        Write-Host "  report: $ReportFile hours=$($rep.hours_requested) passed=$($rep.passed)" -ForegroundColor DarkGray
    } catch { }
}

exit 0
