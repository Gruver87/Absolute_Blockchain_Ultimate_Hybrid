# Start two local ABS nodes for P2P testing (Windows PowerShell)
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

Write-Host "=== Absolute Blockchain — two-node devnet ===" -ForegroundColor Cyan
Write-Host "Node 1: P2P :5000  REST :8080" -ForegroundColor Gray
Write-Host "Node 2: P2P :5001  REST :8081  (bootstrap -> 127.0.0.1:5000)" -ForegroundColor Gray
Write-Host ""

& (Join-Path $ProjectRoot "scripts\stop_node.ps1") 2>$null

# Fresh node2 DB so it joins node1 chain (avoids fork at height 18 vs 4000+)
$node2Db = Join-Path $ProjectRoot "data\node2\blockchain.db"
foreach ($f in @($node2Db, "$node2Db-shm", "$node2Db-wal")) {
    if (Test-Path $f) { Remove-Item $f -Force -ErrorAction SilentlyContinue }
}
Write-Host "Reset node2 database for clean P2P join" -ForegroundColor Gray

foreach ($dir in @("data", "data\node2")) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
}

$node1 = Start-Process -FilePath "python" -ArgumentList "main.py", "--config", "node.example.json" `
    -WorkingDirectory $ProjectRoot -PassThru -WindowStyle Normal
Start-Sleep -Seconds 4

$node2 = Start-Process -FilePath "python" -ArgumentList "main.py", "--config", "node2.example.json" `
    -WorkingDirectory $ProjectRoot -PassThru -WindowStyle Normal

Write-Host ""
Write-Host "Node 1 PID: $($node1.Id)  |  Node 2 PID: $($node2.Id)" -ForegroundColor Green
Write-Host "Check peers:  curl http://localhost:8080/peers" -ForegroundColor Yellow
Write-Host "Check peers:  curl http://localhost:8081/peers" -ForegroundColor Yellow
Write-Host "Stop:       .\scripts\stop_node.ps1" -ForegroundColor Yellow
