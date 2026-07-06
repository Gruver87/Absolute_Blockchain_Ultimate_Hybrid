# Long-running prod mesh soak: polls health_watch logic and writes a summary report.
param(
    [int]$Hours = 24,
    [int]$IntervalSec = 300,
    [switch]$ProdMesh,
    [string]$LogFile = "logs/soak_monitor.log",
    [string]$ReportFile = "logs/soak_report.json"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$durationMin = [Math]::Max(1, $Hours * 60)
$started = Get-Date -Format "o"
Write-Host "Soak monitor: ${Hours}h interval=${IntervalSec}s log=$LogFile" -ForegroundColor Cyan
Write-Host "  Press Ctrl+C to stop early; partial report will be written." -ForegroundColor DarkGray

$hwArgs = @{
    DurationMin = $durationMin
    IntervalSec = $IntervalSec
    LogFile     = $LogFile
}
if ($ProdMesh) { $hwArgs.ProdMesh = $true }

$exitCode = 0
try {
    & (Join-Path $ScriptDir "health_watch.ps1") @hwArgs
    if ($null -ne $LASTEXITCODE) { $exitCode = $LASTEXITCODE }
} catch {
    Write-Host "FAIL: health_watch error: $($_.Exception.Message)" -ForegroundColor Red
    $exitCode = 1
}

$ended = Get-Date -Format "o"
$lines = @()
if (Test-Path $LogFile) {
    $lines = Get-Content $LogFile -Encoding UTF8
}

$ts = '^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}'
$ok = ($lines | Select-String -Pattern "$ts OK port").Count
$warn = ($lines | Select-String -Pattern "$ts WARN").Count
$fail = ($lines | Select-String -Pattern "$ts FAIL").Count
$meshOk = ($lines | Select-String -Pattern "$ts OK mesh aligned").Count
$meshWarn = ($lines | Select-String -Pattern "$ts WARN mesh misaligned").Count
$startedWatch = ($lines | Select-String -Pattern "$ts health_watch start").Count -gt 0
$finishedWatch = ($lines | Select-String -Pattern "$ts health_watch done").Count -gt 0

$report = @{
    started_at = $started
    ended_at = $ended
    hours_requested = $Hours
    interval_sec = $IntervalSec
    log_file = $LogFile
    counts = @{
        ok_lines = $ok
        warn_lines = $warn
        fail_lines = $fail
        mesh_ok_lines = $meshOk
        mesh_warn_lines = $meshWarn
    }
    health_watch_exit = $exitCode
    cycles_observed = [int]($lines | Select-String -Pattern "$ts OK port").Count / [Math]::Max(1, $(if ($ProdMesh) { 3 } else { 1 }))
    passed = (
        $exitCode -eq 0 -and
        $startedWatch -and
        $finishedWatch -and
        $ok -gt 0 -and
        $fail -eq 0 -and
        $meshWarn -eq 0
    )
}

$reportDir = Split-Path -Parent $ReportFile
if ($reportDir -and -not (Test-Path $reportDir)) {
    New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
}
$report | ConvertTo-Json -Depth 4 | Set-Content -Path $ReportFile -Encoding UTF8

if ($report.passed) {
    Write-Host "OK: soak passed (report: $ReportFile)" -ForegroundColor Green
} else {
    Write-Host "WARN: soak issues fail=$fail mesh_warn=$meshWarn (report: $ReportFile)" -ForegroundColor Yellow
}

exit $(if ($report.passed) { 0 } else { 1 })
