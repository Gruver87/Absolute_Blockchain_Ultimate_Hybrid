# Full mainnet-v1 prod network: 3-node ceremony mesh + bridge/relayer (real Infura L1).
param(
    [string]$CeremonyDir = "data/ceremony_keys"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

Write-Host "=== MAINNET PROD NETWORK (mesh + bridge) ===" -ForegroundColor Cyan
Write-Host "1/2: 3-node ceremony mesh (18180/18181/18182, chain_id 778888)" -ForegroundColor DarkGray
& "$ScriptDir\docker_prod_3node.ps1" -CeremonyDir $CeremonyDir
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "2/2: bridge cutover node + relayer (18080/18545, Infura Mainnet)" -ForegroundColor DarkGray
& "$ScriptDir\docker_prod.ps1" -Bridge
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "OK: full prod network up" -ForegroundColor Green
Write-Host "  Mesh:   http://127.0.0.1:18180  http://127.0.0.1:18181  http://127.0.0.1:18182" -ForegroundColor Gray
Write-Host "  Bridge: http://127.0.0.1:18080  RPC http://127.0.0.1:18545" -ForegroundColor Gray
Write-Host "  Cutover: .\scripts\bridge_l1_cutover.ps1 -ProbeL1; .\scripts\bridge_l1_cutover.ps1 -Live" -ForegroundColor Gray
