# Release gate — full blockchain verification before tag/push.
# Add -Mainnet for prod stack + pre-mainnet combined gate.
param(
    [switch]$FullNativeBuild,
    [switch]$Mainnet
)

$args = @("-SkipNativeBuild")
if ($FullNativeBuild) {
    $args = @()
}
& "$PSScriptRoot\test_all.ps1" @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if ($Mainnet) {
    python "$PSScriptRoot\mainnet_readiness.py"
    exit $LASTEXITCODE
}
exit 0
