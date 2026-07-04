# Full mainnet P0 gate: ceremony deploy + isolated prod mesh + optional docker live.
param(
    [string]$CeremonyDir = "data/ceremony_keys",
    [switch]$SkipDeploy,
    [switch]$SkipProdSmoke,
    [switch]$DockerLive,
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

python @readinessArgs
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($DockerLive) {
    Write-Host ""
    Write-Host "Docker live gate (requires JWT_SECRET, RPC_API_KEYS, ...)" -ForegroundColor Cyan
    & "$ProjectRoot\scripts\docker_prod.ps1" -CeremonyDir $CeremonyDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    python scripts/mainnet_readiness.py --live --ceremony-dir $CeremonyDir --no-strict-audit
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "OK: mainnet live gate (isolated prod-smoke) passed" -ForegroundColor Green
Write-Host "Next: .\scripts\docker_prod.ps1 -CeremonyDir $CeremonyDir" -ForegroundColor Gray
