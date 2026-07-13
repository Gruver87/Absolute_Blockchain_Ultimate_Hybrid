# Preflight prod mesh before 48h soak — does NOT start the soak.
param(
    [int]$Hours = 48,
    [int]$IntervalSec = 300,
    [switch]$RequireP2pTls
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

Write-Host "Soak preflight (${Hours}h planned) — mesh must be up on :18180-:18182" -ForegroundColor Cyan
$argsList = @("scripts/soak_preflight.py", "--hours", $Hours, "--interval-sec", $IntervalSec)
if ($RequireP2pTls) { $argsList += "--require-p2p-tls" }
python @argsList
exit $LASTEXITCODE
