# Long-running prod mesh soak: polls health_watch logic and writes a summary report.
param(
    [int]$Hours = 24,
    [int]$IntervalSec = 300,
    [switch]$ProdMesh,
    [string]$LogFile = "logs/soak_monitor.log",
    [string]$ReportFile = "logs/soak_report.json",
    # Rebuild report from an existing soak log (no health_watch run).
    [switch]$RescoreOnly,
    [int]$HealthWatchExit = -1
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

function Test-MeshWarnsAreTransient {
    param([string[]]$Lines, [string]$TsPrefix)
    $warns = @($Lines | Select-String -Pattern "$TsPrefix WARN mesh misaligned")
    if ($warns.Count -eq 0) { return $true }
    foreach ($w in $warns) {
        $heights = @([regex]::Matches($w.Line, 'h\d+=(\d+)') | ForEach-Object { [int]$_.Groups[1].Value })
        if ($heights.Count -lt 2) { return $false }
        $delta = ($heights | Measure-Object -Maximum).Maximum - ($heights | Measure-Object -Minimum).Minimum
        # ±1 (or equal heights with tip-hash race) is transient under sequential HTTP polls.
        if ($delta -gt 1) { return $false }
    }
    return $true
}

$durationMin = [Math]::Max(1, $Hours * 60)
$started = Get-Date -Format "o"
if ($RescoreOnly) {
    Write-Host "Soak rescore-only: log=$LogFile report=$ReportFile" -ForegroundColor Cyan
} else {
    Write-Host "Soak monitor: ${Hours}h interval=${IntervalSec}s log=$LogFile" -ForegroundColor Cyan
    Write-Host "  Press Ctrl+C to stop early; partial report will be written." -ForegroundColor DarkGray
}

$exitCode = 0
if (-not $RescoreOnly) {
    $hwArgs = @{
        DurationMin = $durationMin
        IntervalSec = $IntervalSec
        LogFile     = $LogFile
    }
    if ($ProdMesh) { $hwArgs.ProdMesh = $true }

    try {
        & (Join-Path $ScriptDir "health_watch.ps1") @hwArgs
        if ($null -ne $LASTEXITCODE) { $exitCode = $LASTEXITCODE }
    } catch {
        Write-Host "FAIL: health_watch error: $($_.Exception.Message)" -ForegroundColor Red
        $exitCode = 1
    }
} elseif ($HealthWatchExit -ge 0) {
    $exitCode = $HealthWatchExit
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
$meshWarnsTransient = Test-MeshWarnsAreTransient -Lines $lines -TsPrefix $ts

# Prefer timestamps from the soak log when rescoring a completed run.
if ($RescoreOnly -and $startedWatch) {
    $startMatch = ($lines | Select-String -Pattern "$ts health_watch start" | Select-Object -First 1)
    if ($startMatch -and $startMatch.Line -match '^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})') {
        try { $started = ([datetime]::ParseExact($Matches[1], 'yyyy-MM-dd HH:mm:ss', $null)).ToString('o') } catch { }
    }
}
if ($RescoreOnly -and $finishedWatch) {
    $doneMatch = ($lines | Select-String -Pattern "$ts health_watch done" | Select-Object -Last 1)
    if ($doneMatch -and $doneMatch.Line -match '^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})') {
        try { $ended = ([datetime]::ParseExact($Matches[1], 'yyyy-MM-dd HH:mm:ss', $null)).ToString('o') } catch { }
    }
    if ($HealthWatchExit -lt 0) { $exitCode = 0 }
}

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
    mesh_warns_transient_ok = $meshWarnsTransient
    cycles_observed = [double](($lines | Select-String -Pattern "$ts OK port").Count) / [Math]::Max(1, $(if ($ProdMesh) { 3 } else { 1 }))
    passed = (
        $exitCode -eq 0 -and
        $startedWatch -and
        $finishedWatch -and
        $ok -gt 0 -and
        $fail -eq 0 -and
        $meshWarnsTransient
    )
    pass_notes = $(
        if ($meshWarn -eq 0) {
            "strict mesh_warn=0"
        } elseif ($meshWarnsTransient) {
            "mesh_warn=$meshWarn accepted: all height deltas <=1 (sequential poll skew)"
        } else {
            "mesh_warn=$meshWarn includes height delta >1"
        }
    )
}

$reportDir = Split-Path -Parent $ReportFile
if ($reportDir -and -not (Test-Path $reportDir)) {
    New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
}
$json = $report | ConvertTo-Json -Depth 4
$reportFull = if ([System.IO.Path]::IsPathRooted($ReportFile)) { $ReportFile } else { Join-Path $Root $ReportFile }
[System.IO.File]::WriteAllText($reportFull, $json + "`n", [System.Text.UTF8Encoding]::new($false))

if ($report.passed) {
    Write-Host "OK: soak passed (report: $ReportFile) $($report.pass_notes)" -ForegroundColor Green
} else {
    Write-Host "WARN: soak issues fail=$fail mesh_warn=$meshWarn transient_ok=$meshWarnsTransient (report: $ReportFile)" -ForegroundColor Yellow
}

exit $(if ($report.passed) { 0 } else { 1 })
