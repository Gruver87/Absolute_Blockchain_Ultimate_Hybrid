# Start Docker prod profile (single node, Rust bridge)
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Split-Path -Parent $ProjectRoot)

if (-not $env:JWT_SECRET) {
    Write-Host "JWT_SECRET not set — using docker-compose default (change for real prod)" -ForegroundColor Yellow
}
if (-not $env:RPC_API_KEYS) {
    Write-Host "RPC_API_KEYS not set — using docker-compose default" -ForegroundColor Yellow
}

docker compose -f docker-compose.prod.yml up --build -d
Write-Host "Prod node: http://localhost:8080  RPC :8545" -ForegroundColor Green
Write-Host "Logs: docker compose -f docker-compose.prod.yml logs -f" -ForegroundColor Gray
