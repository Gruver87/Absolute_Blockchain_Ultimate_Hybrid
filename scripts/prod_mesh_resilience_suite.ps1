# Prod mesh resilience path (probe + stabilize + failover + optional DR) — no soak.
param(
    [switch]$SkipFailover,
    [switch]$SkipDrRehearsal,
    [switch]$QuickProbe,
    [int]$FailoverWaitSec = 360,
    [int]$ProbeWaitSec = 60
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$gitTag = "unknown"
try {
    $desc = git describe --tags --abbrev=0 2>$null
    if ($desc) { $gitTag = $desc.Trim() }
} catch { }

function Step([string]$Name, [scriptblock]$Action) {
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL: $Name" -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "OK: $Name" -ForegroundColor Green
}

Step "mesh_stabilize" {
    & (Join-Path $ScriptDir "mesh_stabilize.ps1")
}

Step "prod_mesh_probe" {
    $probeArgs = @()
    if ($QuickProbe) { $probeArgs += "-Quick" }
    if ($ProbeWaitSec -gt 0) { $probeArgs += @("-WaitSec", $ProbeWaitSec) }
    & (Join-Path $ScriptDir "probe_prod_mesh.ps1") @probeArgs
}

if (-not $SkipFailover) {
    Step "failover_pre_sync" {
        & (Join-Path $ScriptDir "mesh_stabilize.ps1") -WaitSec 120
    }
    Step "failover_drill" {
        & (Join-Path $ScriptDir "prod_mesh_failover.ps1") -WaitSec $FailoverWaitSec
    }
    Step "post_failover_probe" {
        & (Join-Path $ScriptDir "probe_prod_mesh.ps1") -WaitSec 90
    }
}

if (-not $SkipDrRehearsal) {
    Step "dr_restore_rehearsal" {
        & (Join-Path $ScriptDir "dr_restore_rehearsal.ps1") -DockerMesh1
    }
}

python (Join-Path $ScriptDir "record_evidence_run.py") `
    --name prod_mesh_resilience `
    --result PASS `
    --command ".\scripts\prod_mesh_resilience_suite.ps1" `
    --artifact "logs/prod_mesh_probe.json" `
    --git-tag $gitTag `
    2>$null | Out-Null

Write-Host "`nOK: prod mesh resilience suite passed" -ForegroundColor Green
Write-Host "  Full evidence: .\scripts\prod_evidence_suite.ps1" -ForegroundColor DarkGray
Write-Host "  48h soak (later): .\scripts\restart_soak_prod_mesh.ps1 -Hours 48" -ForegroundColor DarkGray
exit 0
