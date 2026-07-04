# Mainnet readiness — prod stack + pre-mainnet audit (run before tag/release).
param(
    [switch]$Live,
    [string]$BaseUrl = "http://127.0.0.1:8080"
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$args = @("scripts/mainnet_readiness.py")
if ($Live) {
    $args += "--live", "--base-url", $BaseUrl
}
python @args
exit $LASTEXITCODE
