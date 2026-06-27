# Start Docker prod profile (single node, Rust bridge)
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location (Split-Path -Parent $ProjectRoot)

$missing = @()
foreach ($name in @("JWT_SECRET", "RPC_API_KEYS", "BRIDGE_ORACLE_SECRET", "CORS_ORIGINS", "ETH_RPC_URL")) {
    if (-not [Environment]::GetEnvironmentVariable($name)) {
        $missing += $name
    }
}
if ($missing.Count -gt 0) {
    Write-Host "Missing required prod env vars: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "Example:" -ForegroundColor Gray
    Write-Host '  set $env:JWT_SECRET to a random long secret' -ForegroundColor Gray
    Write-Host '  set $env:RPC_API_KEYS to a generated RPC key' -ForegroundColor Gray
    Write-Host '  set $env:BRIDGE_ORACLE_SECRET to a random long secret' -ForegroundColor Gray
    Write-Host '  set $env:CORS_ORIGINS to your HTTPS explorer origin' -ForegroundColor Gray
    Write-Host '  set $env:ETH_RPC_URL to your Ethereum JSON-RPC endpoint' -ForegroundColor Gray
    exit 1
}

$walletPath = Join-Path (Get-Location) "data\wallet.json"
if (-not (Test-Path $walletPath)) {
    Write-Host "Prod wallet is required: $walletPath" -ForegroundColor Red
    Write-Host "Create or mount data\wallet.json before starting production." -ForegroundColor Gray
    exit 1
}

docker compose -f docker-compose.prod.yml up --build -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker failed — start Docker Desktop and retry." -ForegroundColor Red
    exit $LASTEXITCODE
}
Write-Host "Prod node: http://localhost:8080  RPC :8545" -ForegroundColor Green
Write-Host "Logs: docker compose -f docker-compose.prod.yml logs -f" -ForegroundColor Gray
