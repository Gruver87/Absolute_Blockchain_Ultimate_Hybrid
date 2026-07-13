# P2P TLS mesh preflight wrapper.
param(
    [switch]$Live,
    [int]$WaitSec = 0
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$argsList = @("scripts/p2p_tls_preflight.py")
if ($Live) { $argsList += "--live" }
if ($WaitSec -gt 0) { $argsList += @("--wait", $WaitSec) }

python @argsList
exit $LASTEXITCODE
