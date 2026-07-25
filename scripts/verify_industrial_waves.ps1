# Verify industrial hardening waves v1.3.65–v1.3.75
# Usage (repo root):
#   .\scripts\verify_industrial_waves.ps1
#   .\scripts\verify_industrial_waves.ps1 -SkipGate

param(
    [switch]$SkipGate,
    [switch]$SkipPytest
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONPATH = $Root

$argsList = @("scripts/verify_industrial_waves.py")
if ($SkipGate) { $argsList += "--skip-gate" }
if ($SkipPytest) { $argsList += "--skip-pytest" }

python @argsList
exit $LASTEXITCODE
