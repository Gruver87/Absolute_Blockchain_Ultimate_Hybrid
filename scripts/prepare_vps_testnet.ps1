# VPS public testnet preflight — static checks + optional live seed probe.
param(
    [switch]$Live,
    [string]$BaseUrl = "http://127.0.0.1:19080"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$argsList = @("scripts/vps_testnet_preflight.py")
if ($Live) { $argsList += "--live" }
if ($BaseUrl) { $argsList += @("--base-url", $BaseUrl) }

python @argsList
exit $LASTEXITCODE
