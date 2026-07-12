# Public testnet gate wrapper (static + optional live probe).
param(
    [switch]$Live,
    [string]$BaseUrl = "http://127.0.0.1:9080",
    [double]$RequireSoakHours = 0
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$argsList = @("scripts/public_testnet_gate.py")
if ($Live) { $argsList += "--live" }
if ($BaseUrl) { $argsList += @("--base-url", $BaseUrl) }
if ($RequireSoakHours -gt 0) {
    $argsList += @("--require-soak-hours", $RequireSoakHours)
}

python @argsList
exit $LASTEXITCODE
