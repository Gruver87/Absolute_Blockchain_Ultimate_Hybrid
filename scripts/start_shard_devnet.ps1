# Start 2-node distributed shard devnet (shard 0 + shard 1, separate DBs)
param(
    [switch]$Fresh
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:ABS_REQUIRE_NATIVE_CRYPTO = "true"

& (Join-Path $ProjectRoot "scripts\stop_node.ps1") 2>$null | Out-Null

if ($Fresh) {
    foreach ($f in @("data\shard0.db", "data\shard1.db", "data\shard0.log", "data\shard1.log")) {
        if (Test-Path $f) { Remove-Item $f -Force }
    }
}

Write-Host "Starting shard-0 (assigned_shard_id=0)..." -ForegroundColor Cyan
Start-Process python -ArgumentList @("main.py", "--config", "node.shard0.json") -WindowStyle Hidden

Start-Sleep -Seconds 4

Write-Host "Starting shard-1 (assigned_shard_id=1)..." -ForegroundColor Cyan
Start-Process python -ArgumentList @("main.py", "--config", "node.shard1.json") -WindowStyle Hidden

Start-Sleep -Seconds 6

foreach ($pair in @(
    @{ Url = "http://127.0.0.1:8080/sharding/stats"; Name = "shard-0" },
    @{ Url = "http://127.0.0.1:8081/sharding/stats"; Name = "shard-1" }
)) {
    try {
        $st = Invoke-RestMethod -Uri $pair.Url -TimeoutSec 5
        Write-Host "$($pair.Name): mode=$($st.mode) assigned=$($st.assigned_shard_id) shards=$($st.total_shards)" -ForegroundColor Green
    }
    catch {
        Write-Host "$($pair.Name): not ready yet ($($_.Exception.Message))" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Shard devnet:" -ForegroundColor Cyan
Write-Host "  shard-0  http://127.0.0.1:8080  P2P :5000  DB data/shard0.db"
Write-Host "  shard-1  http://127.0.0.1:8081  P2P :5001  DB data/shard1.db"
Write-Host "Stop: .\scripts\stop_node.ps1"
