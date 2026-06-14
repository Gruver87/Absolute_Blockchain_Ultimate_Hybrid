# Start three-node testnet via Docker Compose (Wave 52)
param(
    [switch]$NoCloneDb
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$composeFile = "docker-compose.devnet-3node.yml"
Write-Host "Docker 3-node testnet: node1 :8080, node2 :8081, node3 :8082" -ForegroundColor Cyan

if ($NoCloneDb) {
    $env:SKIP_DB_SEED = "1"
    Write-Host "Fresh DB on node2/node3 (-NoCloneDb)" -ForegroundColor Yellow
} else {
    Remove-Item Env:SKIP_DB_SEED -ErrorAction SilentlyContinue
}

Write-Host "=== Absolute 3-node devnet (Rust bridge on node1) ===" -ForegroundColor Cyan

$dockerOk = $false
try {
    $null = docker info 2>&1
    if ($LASTEXITCODE -eq 0) { $dockerOk = $true }
} catch { }

if (-not $dockerOk) {
    Write-Host "Docker is not running. Start Docker Desktop and retry." -ForegroundColor Red
    exit 1
}

Write-Host "Stopping conflicting 2-node compose (if any)..." -ForegroundColor Gray
docker compose -f docker-compose.devnet-rust.yml down 2>$null | Out-Null
docker compose -f docker-compose.devnet.yml down 2>$null | Out-Null
docker compose -f $composeFile down -v 2>$null | Out-Null

Write-Host "Stopping local Python nodes..." -ForegroundColor Gray
Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'python3.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -like '*main.py*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

Write-Host "Starting node1..." -ForegroundColor Gray
docker compose -f $composeFile build node1 node2 node3
docker compose -f $composeFile up -d --build node1
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host "Waiting for node1..." -ForegroundColor Gray
$ok1 = $false
for ($i = 0; $i -lt 40; $i++) {
    try {
        $st = Invoke-RestMethod "http://127.0.0.1:8080/status" -UseBasicParsing -TimeoutSec 3
        if ($st.node_id -like "docker-node-*") {
            $ok1 = $true
            Write-Host "node1 ready ($($st.node_id)) api_wave=$($st.api_wave)" -ForegroundColor Green
            if ($null -eq $st.api_wave -or [int]$st.api_wave -lt 52) {
                Write-Host "WARN: rebuild for Wave 52: docker compose -f $composeFile build --no-cache" -ForegroundColor Yellow
            }
            break
        }
    } catch { }
    Start-Sleep -Seconds 3
}
if (-not $ok1) {
    Write-Host "node1 not ready - run: .\scripts\stop_node.ps1" -ForegroundColor Red
    exit 1
}

if (-not $NoCloneDb) {
    Write-Host "Seeding node2 + node3 DB from node1 (node1 paused)..." -ForegroundColor Gray
    docker compose -f $composeFile stop node1 | Out-Null
    docker compose -f $composeFile --profile seed run --rm --no-deps node2-db-seed
    if ($LASTEXITCODE -ne 0) {
        docker compose -f $composeFile start node1 | Out-Null
        exit 1
    }
    docker compose -f $composeFile --profile seed run --rm --no-deps node3-db-seed
    if ($LASTEXITCODE -ne 0) {
        docker compose -f $composeFile start node1 | Out-Null
        exit 1
    }
}

Write-Host "Starting node1 + node2 + node3..." -ForegroundColor Gray
if (-not $NoCloneDb) {
    docker compose -f $composeFile up -d --force-recreate
} else {
    docker compose -f $composeFile up -d
}
if ($LASTEXITCODE -ne 0) { exit 1 }

function Wait-DockerNode {
    param([int]$Port, [string]$Label)
    for ($i = 0; $i -lt 40; $i++) {
        try {
            $st = Invoke-RestMethod "http://127.0.0.1:$Port/status" -UseBasicParsing -TimeoutSec 3
            if ($st.node_id -like "docker-node-*") {
                Write-Host "$Label ready ($($st.node_id))" -ForegroundColor Green
                return $true
            }
        } catch { }
        Start-Sleep -Seconds 3
    }
    return $false
}

$ok2 = Wait-DockerNode -Port 8081 -Label "node2"
$ok3 = Wait-DockerNode -Port 8082 -Label "node3"

if ($ok1 -and $ok2 -and $ok3) {
    Write-Host "Waiting for P2P mesh (60s)..." -ForegroundColor Gray
    Start-Sleep -Seconds 60
    try {
        $mesh = Invoke-RestMethod "http://127.0.0.1:8080/testnet/mesh" -UseBasicParsing
        Write-Host "testnet/mesh peer_count=$($mesh.peer_count) mesh_healthy=$($mesh.mesh_healthy)" -ForegroundColor Gray
    } catch {
        Write-Host "testnet/mesh not available yet" -ForegroundColor Yellow
    }
    python scripts/verify_p2p_ci.py --mode devnet3 --wait 300
    exit $LASTEXITCODE
}

Write-Host "Nodes not ready - check: docker compose -f $composeFile logs" -ForegroundColor Yellow
exit 1
