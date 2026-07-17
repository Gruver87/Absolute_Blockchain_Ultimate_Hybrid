# Mainnet readiness - prod stack + pre-mainnet audit (run before tag/release).
# Usage: .\scripts\mainnet_readiness.ps1
#        .\scripts\mainnet_readiness.ps1 -Live
#        .\scripts\mainnet_readiness.ps1 -ProdSmokeSpawn
#        .\scripts\pin_ceremony_hash.ps1; .\scripts\mainnet_readiness.ps1 -CeremonyDir data/ceremony_keys
param(
    [switch]$Live,
    [switch]$ProdSmokeSpawn,
    [string]$CeremonyDir = "",
    [string]$BaseUrl = "http://127.0.0.1:8080"
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$args = @("scripts/mainnet_readiness.py")
if ($Live) {
    $args += "--live", "--base-url", $BaseUrl
}
if ($ProdSmokeSpawn) {
    $args += "--prod-smoke-spawn"
}
if ($CeremonyDir) {
    $args += "--ceremony-dir", $CeremonyDir
}
python @args
exit $LASTEXITCODE
