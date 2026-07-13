# Preflight prod mesh before 48h soak — does NOT start the soak.
param(
    [int]$Hours = 48,
    [int]$IntervalSec = 300
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

Write-Host "Soak preflight (${Hours}h planned) — mesh must be up on :18180-:18182" -ForegroundColor Cyan
python scripts/soak_preflight.py --hours $Hours --interval-sec $IntervalSec
exit $LASTEXITCODE
