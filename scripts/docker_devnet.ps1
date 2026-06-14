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
Write-Host "Build + start: docker compose -f $composeFile up --build -d" -ForegroundColor Gray

docker compose -f $composeFile up --build -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker compose failed" -ForegroundColor Red
    exit 1
}

Write-Host "Waiting for nodes..." -ForegroundColor Gray
$ok1 = $false
$ok2 = $false
for ($i = 0; $i -lt 40; $i++) {
    try {
        if (-not $ok1) {
            $null = Invoke-RestMethod "http://127.0.0.1:8080/health/live" -TimeoutSec 3
            $ok1 = $true
            Write-Host "node1 ready" -ForegroundColor Green
        }
        if (-not $ok2) {
            $null = Invoke-RestMethod "http://127.0.0.1:8081/health/live" -TimeoutSec 3
            $ok2 = $true
            Write-Host "node2 ready" -ForegroundColor Green
        }
        if ($ok1 -and $ok2) { break }
    }
    catch { Start-Sleep -Seconds 3 }
}

if ($ok1 -and $ok2) {
    try {
        $st = Invoke-RestMethod "http://127.0.0.1:8080/status" -UseBasicParsing
        Write-Host "node1 bridge_mode=$($st.bridge_mode) pending=$($st.bridge_pending)" -ForegroundColor Gray
    } catch { }
    python scripts/verify_p2p_ci.py --mode devnet
    exit $LASTEXITCODE
}

Write-Host "Nodes not ready - check: docker compose -f $composeFile logs" -ForegroundColor Yellow
exit 1
