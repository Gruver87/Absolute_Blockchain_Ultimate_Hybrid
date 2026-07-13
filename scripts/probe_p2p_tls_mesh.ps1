# Quick P2P TLS probe on prod mesh (:18180-:18182).
param(
    [switch]$StaticOnly,
    [int]$WaitSec = 0
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$argsList = @("scripts/verify_p2p_tls_mesh.py")
if ($StaticOnly) { $argsList += "--static-only" }
if ($WaitSec -gt 0) { $argsList += @("--wait", $WaitSec) }

python @argsList
exit $LASTEXITCODE
