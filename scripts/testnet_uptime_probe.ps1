# Public testnet uptime probe — cron-friendly health snapshot.
param(
    [string]$BaseUrl = "http://127.0.0.1:19080",
    [switch]$Append,
    [switch]$NoHarness
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$argsList = @("scripts/testnet_uptime_probe.py", "--base-url", $BaseUrl)
if ($Append) { $argsList += "--append" }
if ($NoHarness) { $argsList += "--no-harness" }

python @argsList
exit $LASTEXITCODE
