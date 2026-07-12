# Reconnect and sync live prod mesh before evidence smokes.
param(
    [int]$WaitSec = 180
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

Write-Host "Prod mesh stabilize..." -ForegroundColor Cyan
python scripts/verify_p2p_ci.py `
    --mode prod-mesh3-stabilize `
    --url1 http://127.0.0.1:18180 `
    --url2 http://127.0.0.1:18181 `
    --url3 http://127.0.0.1:18182 `
    --wait $WaitSec
exit $LASTEXITCODE
