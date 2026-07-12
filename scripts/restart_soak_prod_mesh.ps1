# Restart 48h prod mesh soak with v1.2.31+ health_watch timeouts (background).
param(
    [int]$Hours = 48,
    [int]$IntervalSec = 300,
    [string]$LogFile = "logs/soak_48h_v1.2.34.log",
    [string]$ReportFile = "logs/soak_report_48h.json",
    [switch]$Foreground,
    [switch]$NoStopExisting
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$logDir = Split-Path -Parent $LogFile
if ($logDir -and -not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
}

Write-Host "Prod mesh soak restart: ${Hours}h interval=${IntervalSec}s" -ForegroundColor Cyan
Write-Host "  log=$LogFile report=$ReportFile" -ForegroundColor DarkGray
Write-Host "  health_watch ProdMesh timeouts: ready=15s status=12s harness=15-30s" -ForegroundColor DarkGray

if (-not $NoStopExisting) {
    & (Join-Path $ScriptDir "stop_soak_monitors.ps1") -Force
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$activeMeta = @{
    log_file = $LogFile
    report_file = $ReportFile
    hours = $Hours
    interval_sec = $IntervalSec
    started_at = (Get-Date -Format "o")
    git_tag = "v1.2.39"
}
$activePath = Join-Path $Root "logs/soak_active.json"
$activeMeta | ConvertTo-Json | Set-Content -Path $activePath -Encoding UTF8

$soakScript = Join-Path $ScriptDir "soak_monitor.ps1"
$soakArgs = @(
    "-Hours", $Hours,
    "-IntervalSec", $IntervalSec,
    "-ProdMesh",
    "-LogFile", $LogFile,
    "-ReportFile", $ReportFile
)

python scripts/record_evidence_run.py `
    --name soak_monitor_48h `
    --result IN_PROGRESS `
    --command ".\scripts\restart_soak_prod_mesh.ps1 -Hours $Hours" `
    --artifact $LogFile `
    --git-tag v1.2.39 `
    2>$null | Out-Null

if ($Foreground) {
    & $soakScript @soakArgs
    exit $LASTEXITCODE
}

$outLog = Join-Path $Root "logs/soak_background.out.log"
$errLog = Join-Path $Root "logs/soak_background.err.log"

Start-Process -FilePath "powershell.exe" `
    -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", $soakScript,
        "-Hours", $Hours,
        "-IntervalSec", $IntervalSec,
        "-ProdMesh",
        "-LogFile", $LogFile,
        "-ReportFile", $ReportFile
    ) `
    -WorkingDirectory $Root `
    -WindowStyle Hidden `
    -RedirectStandardOutput $outLog `
    -RedirectStandardError $errLog

Write-Host "OK: soak started in background" -ForegroundColor Green
Write-Host "  stdout: $outLog" -ForegroundColor DarkGray
Write-Host "  tail:   Get-Content $LogFile -Tail 20 -Wait" -ForegroundColor DarkGray
Write-Host "  report: $ReportFile (on completion)" -ForegroundColor DarkGray
exit 0
