# Run operational evidence scripts against live prod mesh (see docs/EVIDENCE_MATRIX.md).
param(
    [switch]$SkipFailover,
    [switch]$SkipSignedTx,
    [switch]$SkipEvm
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

if (Test-Path (Join-Path $Root ".env")) {
    Get-Content (Join-Path $Root ".env") | ForEach-Object {
        if ($_ -match '^\s*([^#=]+)=(.*)$') {
            $k = $matches[1].Trim()
            $v = $matches[2].Trim().Trim('"')
            if ($k) { Set-Item -Path "env:$k" -Value $v }
        }
    }
}

function Step([string]$Name, [scriptblock]$Action) {
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    & $Action
    if (-not $?) {
        Write-Host "FAIL: $Name" -ForegroundColor Red
        exit 1
    }
    Write-Host "OK: $Name" -ForegroundColor Green
}

Step "mesh health" {
    & (Join-Path $ScriptDir "health_watch.ps1") -ProdMesh -DurationMin 1 -IntervalSec 15
}

if (-not $SkipFailover) {
    Step "failover drill" {
        & (Join-Path $ScriptDir "prod_mesh_failover.ps1")
    }
}

if (-not $SkipSignedTx) {
    Step "signed tx smoke" {
        python (Join-Path $ScriptDir "prod_signed_tx_smoke.py")
    }
}

if (-not $SkipEvm) {
    Step "prod EVM smoke" {
        python (Join-Path $ScriptDir "prod_evm_smoke.py")
    }
}

Write-Host "`nOK: prod evidence suite passed" -ForegroundColor Green
Write-Host "  Soak (24-48h): .\scripts\soak_monitor.ps1 -ProdMesh -Hours 48" -ForegroundColor DarkGray
exit 0
