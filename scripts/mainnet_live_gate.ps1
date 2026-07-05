# Full mainnet P0 gate: ceremony deploy + isolated prod mesh + optional docker live.
param(
    [string]$CeremonyDir = "data/ceremony_keys",
    [switch]$SkipDeploy,
    [switch]$SkipProdSmoke,
    [switch]$DockerLive,
    [switch]$BridgeCutover,
    [switch]$StrictAudit
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

if (-not $SkipDeploy) {
    & "$ProjectRoot\scripts\deploy_ceremony_prod.ps1" -CeremonyDir $CeremonyDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$readinessArgs = @(
    "scripts/mainnet_readiness.py",
    "--ceremony-dir", $CeremonyDir,
    "--no-strict-audit"
)
if ($StrictAudit) {
    $readinessArgs = @("scripts/mainnet_readiness.py", "--ceremony-dir", $CeremonyDir)
}
if (-not $SkipProdSmoke) {
    $readinessArgs += "--prod-smoke-spawn"
}
if ($BridgeCutover) {
    $readinessArgs += "--bridge-cutover"
}

python @readinessArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($DockerLive) {
    Write-Host ""
    Write-Host "Docker live gate (requires JWT_SECRET, RPC_API_KEYS, ...)" -ForegroundColor Cyan
    $dockerArgs = @("-CeremonyDir", $CeremonyDir)
    if ($BridgeCutover) { $dockerArgs += "-Bridge" }
    & "$ProjectRoot\scripts\docker_prod.ps1" @dockerArgs
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    if ($BridgeCutover) {
        Write-Host ""
        Write-Host "Bridge L1 cutover live gate..." -ForegroundColor Cyan
        & "$ProjectRoot\scripts\bridge_l1_cutover.ps1" -Live -ProbeL1
        exit $LASTEXITCODE
    }
    exit 0
}

Write-Host ""
Write-Host "OK: mainnet live gate (isolated prod-smoke) passed" -ForegroundColor Green
Write-Host "Next: .\scripts\docker_prod.ps1 -CeremonyDir $CeremonyDir" -ForegroundColor Gray
Write-Host "      .\scripts\docker_prod_3node.ps1 -CeremonyDir $CeremonyDir" -ForegroundColor Gray
