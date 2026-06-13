# Start two local ABS nodes for P2P testing (Windows PowerShell)
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

function Wait-NodeReady {
    param(
        [string]$Url,
        [string]$Name,
        [int]$MaxSec = 90
    )
    Write-Host "Waiting for $Name at $Url ..." -ForegroundColor Gray
    for ($elapsed = 0; $elapsed -lt $MaxSec; $elapsed += 3) {
        try {
            $null = Invoke-RestMethod -Uri "$Url/health/live" -TimeoutSec 5
            Write-Host "$Name ready" -ForegroundColor Green
            return $true
        }
        catch {
            Start-Sleep -Seconds 3
        }
    }
    Write-Host "$Name not ready after ${MaxSec}s" -ForegroundColor Red
    return $false
}

Write-Host "=== Absolute Blockchain - two-node devnet ===" -ForegroundColor Cyan
Write-Host "Node 1: P2P :5000  REST :8080  Monitor :8092" -ForegroundColor Gray
Write-Host "Node 2: P2P :5001  REST :8081  Monitor :8093  (bootstrap -> 127.0.0.1:5000)" -ForegroundColor Gray
Write-Host ""

& (Join-Path $ProjectRoot "scripts\stop_node.ps1") 2>$null

# Fresh node2 DB so it joins node1 chain (avoids fork vs node1 long chain)
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

if (-not (Wait-NodeReady -Url "http://127.0.0.1:8080" -Name "node1" -MaxSec 90)) {
    Write-Host "Node 1 failed to start. Check the node1 console window for errors." -ForegroundColor Red
    exit 1
}

$node2 = Start-Process -FilePath "python" -ArgumentList "main.py", "--config", "node2.example.json" `
    -WorkingDirectory $ProjectRoot -PassThru -WindowStyle Normal

if (-not (Wait-NodeReady -Url "http://127.0.0.1:8081" -Name "node2" -MaxSec 60)) {
    Write-Host "Node 2 failed to start. Node 1 is still running." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Node 1 PID: $($node1.Id)  |  Node 2 PID: $($node2.Id)" -ForegroundColor Green
Write-Host "Explorer:     http://localhost:8080" -ForegroundColor Yellow
Write-Host "Check peers:  Invoke-RestMethod http://localhost:8080/peers" -ForegroundColor Yellow
Write-Host "Check peers:  Invoke-RestMethod http://localhost:8081/peers" -ForegroundColor Yellow
Write-Host "Verify P2P:   .\scripts\verify_p2p.ps1  (wait ~30s if peers=0)" -ForegroundColor Yellow
Write-Host "Stop:         .\scripts\stop_node.ps1" -ForegroundColor Yellow
