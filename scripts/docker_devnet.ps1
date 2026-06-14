# Start two-node devnet via Docker Compose
param(
    [switch]$RustBridge,
    [switch]$NoCloneDb
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$composeFile = "docker-compose.devnet.yml"
if ($RustBridge) {
    $composeFile = "docker-compose.devnet-rust.yml"
    Write-Host "Docker devnet: node1 bridge_mode=rust ($composeFile)" -ForegroundColor Cyan
}

if ($NoCloneDb) {
    $env:SKIP_DB_SEED = "1"
    Write-Host "Node2 fresh DB (-NoCloneDb: P2P catch-up test)" -ForegroundColor Yellow
} else {
    Remove-Item Env:SKIP_DB_SEED -ErrorAction SilentlyContinue
}

Write-Host "=== Docker devnet (node1 :8080, node2 :8081) ===" -ForegroundColor Cyan

# Free host ports from local start_two_nodes (do not kill Docker port forwards)
Write-Host "Stopping local Python nodes..." -ForegroundColor Gray
Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'python3.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -like '*main.py*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

# Step 1: node1 only (build if needed)
Write-Host "Starting node1..." -ForegroundColor Gray
docker compose -f $composeFile up -d --build node1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker compose failed (node1)" -ForegroundColor Red
    exit 1
}

Write-Host "Waiting for node1..." -ForegroundColor Gray
$ok1 = $false
for ($i = 0; $i -lt 40; $i++) {
    try {
        $st = Invoke-RestMethod "http://127.0.0.1:8080/status" -UseBasicParsing -TimeoutSec 3
        if ($st.node_id -like "docker-node-*") {
            $ok1 = $true
            Write-Host "node1 ready ($($st.node_id))" -ForegroundColor Green
            break
        }
    }
    catch { }
    Start-Sleep -Seconds 3
}
if (-not $ok1) {
    Write-Host "node1 not ready (or local node still on :8080) - run: .\scripts\stop_node.ps1" -ForegroundColor Red
    exit 1
}

# Step 2: clone DB while node1 is stopped (consistent SQLite snapshot)
if (-not $NoCloneDb) {
    Write-Host "Seeding node2 DB from node1 (node1 paused)..." -ForegroundColor Gray
    docker compose -f $composeFile stop node1 | Out-Null
    docker compose -f $composeFile --profile seed run --rm --no-deps node2-db-seed
    if ($LASTEXITCODE -ne 0) {
        Write-Host "node2-db-seed failed" -ForegroundColor Red
        docker compose -f $composeFile start node1 | Out-Null
        exit 1
    }
}

# Step 3: full stack
Write-Host "Starting node1 + node2..." -ForegroundColor Gray
docker compose -f $composeFile up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker compose failed" -ForegroundColor Red
    exit 1
}

Write-Host "Waiting for node2..." -ForegroundColor Gray
$ok2 = $false
for ($i = 0; $i -lt 40; $i++) {
    try {
        $st = Invoke-RestMethod "http://127.0.0.1:8081/status" -UseBasicParsing -TimeoutSec 3
        if ($st.node_id -like "docker-node-*") {
            $ok2 = $true
            Write-Host "node2 ready ($($st.node_id))" -ForegroundColor Green
            break
        }
    }
    catch { }
    Start-Sleep -Seconds 3
}

if ($ok1 -and $ok2) {
    Write-Host "Waiting for P2P handshake (15s)..." -ForegroundColor Gray
    Start-Sleep -Seconds 15
    try {
        $st = Invoke-RestMethod "http://127.0.0.1:8080/status" -UseBasicParsing
        Write-Host "node1 bridge_mode=$($st.bridge_mode) pending=$($st.bridge_pending)" -ForegroundColor Gray
    } catch { }
    python scripts/verify_p2p_ci.py --mode devnet
    exit $LASTEXITCODE
}

Write-Host "Nodes not ready - check: docker compose -f $composeFile logs" -ForegroundColor Yellow
exit 1
