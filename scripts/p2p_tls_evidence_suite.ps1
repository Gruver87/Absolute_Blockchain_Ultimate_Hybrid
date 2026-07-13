# P2P TLS evidence path: generate certs, start TLS mesh, verify, optional failover.
param(
    [switch]$SkipMeshStart,
    [switch]$WithFailover,
    [switch]$SkipBuild,
    [string]$CeremonyDir = "data/ceremony_keys",
    [int]$FailoverWaitSec = 360,
    [int]$VerifyWaitSec = 120
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

Step "p2p_tls_preflight_static" {
    python (Join-Path $ScriptDir "p2p_tls_preflight.py")
}

if (-not $SkipMeshStart) {
    $meshArgs = @("-CeremonyDir", $CeremonyDir)
    if ($SkipBuild) { $meshArgs += "-SkipBuild" }
    Step "docker_prod_3node_p2ptls" {
        & (Join-Path $ScriptDir "docker_prod_3node_p2ptls.ps1") @meshArgs
    }
}

Step "verify_p2p_tls_mesh" {
    python (Join-Path $ScriptDir "verify_p2p_tls_mesh.py") --wait $VerifyWaitSec
}

Step "verify_prod_mesh_probe" {
    & (Join-Path $ScriptDir "probe_prod_mesh.ps1") -WaitSec 60
}

if ($WithFailover) {
    Step "failover_drill_tls" {
        & (Join-Path $ScriptDir "prod_mesh_failover.ps1") -WaitSec $FailoverWaitSec
    }
    Step "post_failover_tls_verify" {
        python (Join-Path $ScriptDir "verify_p2p_tls_mesh.py") --wait 90
    }
}

python (Join-Path $ScriptDir "record_evidence_run.py") `
    --name p2p_tls_mesh_evidence `
    --result PASS `
    --command ".\scripts\p2p_tls_evidence_suite.ps1" `
    --artifact "logs/p2p_tls_mesh_verify.json" `
    --git-tag $gitTag `
    2>$null | Out-Null

Write-Host "`nOK: P2P TLS evidence suite passed" -ForegroundColor Green
Write-Host "  Resilience: .\scripts\prod_mesh_resilience_suite.ps1 -P2pTls" -ForegroundColor DarkGray
Write-Host "  48h soak (later): .\scripts\prepare_48h_soak.ps1 -RequireP2pTls" -ForegroundColor DarkGray
exit 0
