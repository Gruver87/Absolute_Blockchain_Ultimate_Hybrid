# Industrial prod mesh gate: health → failover → signed tx → optional soak.
param(
    [switch]$SkipFailover,
    [switch]$SkipTx,
    [switch]$RunSoak,
    [int]$SoakHours = 24,
    [int]$SoakIntervalSec = 300
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

function Step([string]$Name, [scriptblock]$Action) {
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    & $Action
    if (-not $?) {
        Write-Host "FAIL: $Name" -ForegroundColor Red
        exit 1
    }
    Write-Host "OK: $Name" -ForegroundColor Green
}

Step "health_watch (1 min)" {
    & (Join-Path $ScriptDir "health_watch.ps1") -ProdMesh -DurationMin 1 -IntervalSec 15
}

if (-not $SkipFailover) {
    Step "failover drill" {
        & (Join-Path $ScriptDir "prod_mesh_failover.ps1")
    }
}

if (-not $SkipTx) {
    Step "signed tx smoke" {
        python (Join-Path $ScriptDir "prod_signed_tx_smoke.py")
    }
}

if ($RunSoak) {
    Write-Host "`n=== soak monitor (${SoakHours}h) ===" -ForegroundColor Cyan
    Write-Host "  Running in foreground; use Ctrl+C to stop early." -ForegroundColor DarkGray
    & (Join-Path $ScriptDir "soak_monitor.ps1") -ProdMesh -Hours $SoakHours -IntervalSec $SoakIntervalSec
    if (-not $?) { exit 1 }
    exit 0
}

Write-Host "`nOK: industrial prod mesh gate passed" -ForegroundColor Green
Write-Host "  Overnight soak: .\scripts\prod_mesh_industrial.ps1 -RunSoak -SoakHours 24 -SkipFailover -SkipTx" -ForegroundColor DarkGray
exit 0
