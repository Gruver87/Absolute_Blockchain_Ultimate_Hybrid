# Release gate — full blockchain verification before tag/push.
# Add -Mainnet for prod stack + pre-mainnet combined gate.
param(
    [switch]$FullNativeBuild,
    [switch]$Mainnet,
    [string]$CeremonyDir = "",
    [switch]$ProdSmokeSpawn,
    [switch]$Live
)

$args = @("-SkipNativeBuild")
if ($FullNativeBuild) {
    $args = @()
}
& "$PSScriptRoot\test_all.ps1" @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($Mainnet) {
    $pyArgs = @("scripts/mainnet_readiness.py")
    if ($CeremonyDir) {
        $pyArgs += @("--ceremony-dir", $CeremonyDir)
    }
    if ($ProdSmokeSpawn) {
        $pyArgs += "--prod-smoke-spawn"
    }
    if ($Live) {
        $pyArgs += @("--live", "--base-url", "http://127.0.0.1:8080")
    }
    python @pyArgs
    exit $LASTEXITCODE
}
exit 0
