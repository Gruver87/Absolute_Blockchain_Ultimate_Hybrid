# Full project audit - one command (Windows)
param(
    [switch]$Quick,
    [switch]$NoTests,
    [switch]$Live,
    [switch]$P2p
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$argsList = @("scripts/full_audit.py")
if ($Quick) { $argsList += "--quick" }
if ($NoTests) { $argsList += "--no-tests" }
if ($Live) { $argsList += "--live" }
if ($P2p) { $argsList += "--p2p" }

Write-Host "=== FULL AUDIT ===" -ForegroundColor Cyan
python @argsList
exit $LASTEXITCODE
