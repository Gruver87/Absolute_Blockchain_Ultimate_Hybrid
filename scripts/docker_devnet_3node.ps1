# Start three-node testnet via Docker Compose (Wave 52)
param(
    [switch]$NoCloneDb,
    [switch]$Recovery
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$composeFile = "docker-compose.devnet-3node.yml"
Write-Host "Docker 3-node testnet: node1 :8080, node2 :8081, node3 :8082" -ForegroundColor Cyan

function Assert-DevnetPortsAvailable {
    $ports = @(8080, 8081, 8082, 8545, 8546, 8547, 5000, 5001, 5002, 8766, 8767, 8768)
    $blocked = @()
    foreach ($port in $ports) {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        foreach ($conn in $conns) {
            $proc = Get-Process -Id $conn.OwningProcess -ErrorAction SilentlyContinue
            $name = if ($proc) { $proc.ProcessName } else { "unknown" }
            if ($name -ne "com.docker.backend") {
                $blocked += ":$port PID=$($conn.OwningProcess) $name"
            }
        }
    }
    if ($blocked.Count -gt 0) {
        Write-Host "FAIL: devnet host ports are still owned by non-Docker processes:" -ForegroundColor Red
        $blocked | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
        Write-Host "Run .\scripts\stop_node.ps1 or close the listed process, then retry." -ForegroundColor Yellow
        exit 1
    }
}

function Assert-DockerApiNode {
    param([int]$Port, [string]$ExpectedNodeId)
    try {
        $st = Invoke-RestMethod "http://127.0.0.1:$Port/status" -UseBasicParsing -TimeoutSec 5
        if ($st.node_id -ne $ExpectedNodeId) {
            Write-Host "FAIL: :$Port answered as '$($st.node_id)', expected '$ExpectedNodeId'." -ForegroundColor Red
            Write-Host "This usually means a local python main.py is intercepting Docker devnet traffic." -ForegroundColor Yellow
            exit 1
        }
    } catch {
        Write-Host "FAIL: :$Port is not reachable as $ExpectedNodeId" -ForegroundColor Red
        exit 1
    }
}

function Invoke-P2PReconnect {
    param([int[]]$Ports = @(8080, 8081, 8082))
    foreach ($port in $Ports) {
        try {
            $null = Invoke-RestMethod "http://127.0.0.1:$port/p2p/reconnect" `
                -Method POST `
                -Body '{"timeout":20}' `
                -ContentType "application/json" `
                -UseBasicParsing `
                -TimeoutSec 30
        } catch { }
    }
}

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
docker compose -f docker-compose.devnet-rust.yml down -v --remove-orphans 2>$null | Out-Null
docker compose -f docker-compose.devnet.yml down -v --remove-orphans 2>$null | Out-Null
docker compose -f docker-compose.yml down -v --remove-orphans 2>$null | Out-Null
docker compose -f $composeFile down -v --remove-orphans 2>$null | Out-Null

Write-Host "Stopping local Python nodes..." -ForegroundColor Gray
Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'python3.exe'" -ErrorAction SilentlyContinue |
    Where-Object { $_.CommandLine -and $_.CommandLine -like '*main.py*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2
Assert-DevnetPortsAvailable

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
            if ($null -eq $st.api_wave -or [int]$st.api_wave -lt 56) {
                Write-Host "WARN: rebuild for Wave 56: docker compose -f $composeFile build --no-cache" -ForegroundColor Yellow
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
    docker compose -f $composeFile up -d --force-recreate --remove-orphans
} else {
    docker compose -f $composeFile up -d --remove-orphans
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
    Assert-DevnetPortsAvailable
    Assert-DockerApiNode -Port 8080 -ExpectedNodeId "docker-node-1"
    Assert-DockerApiNode -Port 8081 -ExpectedNodeId "docker-node-2"
    Assert-DockerApiNode -Port 8082 -ExpectedNodeId "docker-node-3"
    try {
        $mesh = Invoke-RestMethod "http://127.0.0.1:8080/testnet/mesh" -UseBasicParsing -TimeoutSec 10
        Write-Host "testnet/mesh peer_count=$($mesh.peer_count) mesh_healthy=$($mesh.mesh_healthy)" -ForegroundColor Gray
        if (-not $mesh.mesh_healthy -or [int]$mesh.peer_count -lt 2) {
            Write-Host "P2P mesh not ready; reconnecting known peers..." -ForegroundColor Yellow
            Invoke-P2PReconnect
            Start-Sleep -Seconds 10
            $mesh = Invoke-RestMethod "http://127.0.0.1:8080/testnet/mesh" -UseBasicParsing -TimeoutSec 10
            Write-Host "testnet/mesh after reconnect peer_count=$($mesh.peer_count) mesh_healthy=$($mesh.mesh_healthy)" -ForegroundColor Gray
        }
    } catch {
        Write-Host "testnet/mesh not available yet" -ForegroundColor Yellow
        Invoke-P2PReconnect
        Start-Sleep -Seconds 10
    }
    python scripts/verify_p2p_ci.py --mode devnet3 --wait 300
    $verifyExit = $LASTEXITCODE
    if ($verifyExit -eq 0 -and $Recovery) {
        Write-Host "Running live node restart/rejoin recovery verification..." -ForegroundColor Gray
        python scripts/verify_p2p_ci.py --mode devnet3-recovery --wait 300
        $verifyExit = $LASTEXITCODE
    }
    if ($verifyExit -eq 0) {
        Write-Host "Restoring P2P mesh after verification..." -ForegroundColor Gray
        Invoke-P2PReconnect
        Start-Sleep -Seconds 10
        try {
            $topology = Invoke-RestMethod "http://127.0.0.1:8080/p2p/topology" -UseBasicParsing -TimeoutSec 10
            Write-Host "post-verify topology peer_count=$($topology.peer_count) topology_healthy=$($topology.topology_healthy)" -ForegroundColor Gray
        } catch {
            Write-Host "post-verify topology not available" -ForegroundColor Yellow
        }
    }
    exit $verifyExit
}

Write-Host "Nodes not ready - check: docker compose -f $composeFile logs" -ForegroundColor Yellow
exit 1
