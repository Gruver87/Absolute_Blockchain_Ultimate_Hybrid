# Quick prod mesh probe (:18180-:18182) with optional deep harness check.
param(
    [switch]$Quick,
    [int]$WaitSec = 0
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$argsList = @("scripts/verify_prod_mesh_probe.py")
if ($WaitSec -gt 0) { $argsList += @("--wait", $WaitSec) }
if ($Quick) { $argsList += "--quick" }

python @argsList
exit $LASTEXITCODE
