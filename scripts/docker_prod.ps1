# Start Docker prod profile (node + L1 relayer sidecar)
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
    Write-Host "  Set JWT_SECRET to a generated long value (32+ chars)" -ForegroundColor Gray
    Write-Host "  Set RPC_API_KEYS to a generated API key" -ForegroundColor Gray
    Write-Host "  Set BRIDGE_ORACLE_SECRET to a generated long value" -ForegroundColor Gray
    Write-Host "  Set CORS_ORIGINS to your HTTPS explorer origin" -ForegroundColor Gray
    Write-Host "  Set ETH_RPC_URL to your Ethereum JSON-RPC endpoint" -ForegroundColor Gray
    exit 1
}

$walletPath = Join-Path (Get-Location) "data\wallet.json"
if (-not (Test-Path $walletPath)) {
    Write-Host "Prod wallet is required: $walletPath" -ForegroundColor Red
    Write-Host "Create or mount data\wallet.json before starting production." -ForegroundColor Gray
    exit 1
}

Write-Host "Running production gate..." -ForegroundColor Cyan
python scripts/prod_gate.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose -f docker-compose.prod.yml up --build -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker failed — start Docker Desktop and retry." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Waiting for /health/ready (up to 3 min)..." -ForegroundColor Cyan
$deadline = (Get-Date).AddMinutes(3)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8080/health/ready" -UseBasicParsing -TimeoutSec 5
        if ($resp.StatusCode -eq 200) {
            $body = $resp.Content | ConvertFrom-Json
            if ($body.status -eq "ready") {
                $ready = $true
                break
            }
        }
    } catch {
        Start-Sleep -Seconds 5
        continue
    }
    Start-Sleep -Seconds 5
}

if (-not $ready) {
    Write-Host "WARN: node not ready yet — check logs: docker compose -f docker-compose.prod.yml logs node" -ForegroundColor Yellow
} else {
    Write-Host "Node ready." -ForegroundColor Green
    python scripts/prod_smoke.py http://127.0.0.1:8080
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARN: prod smoke failed — inspect bridge/L1 RPC configuration" -ForegroundColor Yellow
    }
}

Write-Host "Prod node:  http://localhost:8080  RPC :8545" -ForegroundColor Green
Write-Host "Relayer:   docker compose -f docker-compose.prod.yml logs -f relayer" -ForegroundColor Gray
Write-Host "All logs:  docker compose -f docker-compose.prod.yml logs -f" -ForegroundColor Gray
