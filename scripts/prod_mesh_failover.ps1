# Prod 3-node mesh failover drill (stop/start node2).
param(
    [int]$WaitSec = 360
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

Write-Host "Prod mesh failover drill (node2 stop/start)..." -ForegroundColor Cyan
python scripts/verify_p2p_ci.py `
    --mode prod-mesh3-recovery `
    --url1 http://127.0.0.1:18180 `
    --url2 http://127.0.0.1:18181 `
    --url3 http://127.0.0.1:18182 `
    --wait $WaitSec
exit $LASTEXITCODE
