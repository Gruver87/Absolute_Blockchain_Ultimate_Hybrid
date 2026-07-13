# Prod mesh resilience path (probe + stabilize + failover + optional DR) — no soak.
param(
    [switch]$SkipFailover,
    [switch]$SkipDrRehearsal,
    [switch]$QuickProbe,
    [switch]$P2pTls,
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

function Test-ProdMeshPreflight {
    $reachable = $false
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:18180/health/ready" -TimeoutSec 4
        $reachable = ($r.status -eq "ready")
    } catch { }

    if ($reachable) { return }

    Write-Host "FAIL: prod mesh not reachable on :18180" -ForegroundColor Red
    $ps = docker compose -p abs-prod-mesh3 -f docker-compose.prod.3node.yml ps --format json 2>$null
    if ($ps) {
        $rows = @($ps | ConvertFrom-Json)
        foreach ($row in $rows) {
            $state = "$($row.State)"
            $svc = "$($row.Service)"
            if ($state -match "restarting|exited|dead") {
                Write-Host "  Docker $svc : $state" -ForegroundColor Yellow
            }
        }
        $logs = docker compose -p abs-prod-mesh3 -f docker-compose.prod.3node.yml logs node1 --tail 8 2>$null
        if ($logs -match "RPC_API_KEYS contains placeholder") {
            Write-Host "  Cause: RPC_API_KEYS placeholder in .env" -ForegroundColor Yellow
            Write-Host "  Fix:   .\scripts\rotate_prod_secrets.ps1 -Force" -ForegroundColor White
            Write-Host "         docker compose -p abs-prod-mesh3 -f docker-compose.prod.3node.yml up -d --force-recreate node1 node2 node3" -ForegroundColor White
        } elseif ($logs) {
            Write-Host "  node1 logs (last lines):" -ForegroundColor DarkGray
            $logs | Select-Object -Last 4 | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
        }
    } else {
        Write-Host "  Start mesh: .\scripts\docker_prod_3node.ps1 -CeremonyDir data/ceremony_keys -SkipBuild" -ForegroundColor White
    }
    exit 1
}

Test-ProdMeshPreflight

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

if ($P2pTls) {
    Step "verify_p2p_tls_mesh" {
        python (Join-Path $ScriptDir "verify_p2p_tls_mesh.py") --wait $ProbeWaitSec
    }
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
