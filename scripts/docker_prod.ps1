# Start Docker prod profile (node + L1 relayer sidecar)
param(
    [string]$CeremonyDir = ""
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot

function Import-DotEnvFile {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return $false }
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { return }
        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        $val = $parts[1].Trim().Trim('"').Trim("'")
        if ($key -and -not [Environment]::GetEnvironmentVariable($key)) {
            [Environment]::SetEnvironmentVariable($key, $val, "Process")
        }
    }
    return $true
}

$dotEnv = Join-Path (Get-Location) ".env"
if (Import-DotEnvFile $dotEnv) {
    Write-Host "Loaded $dotEnv" -ForegroundColor DarkGray
}

if ($CeremonyDir) {
    & "$ScriptDir\deploy_ceremony_prod.ps1" -CeremonyDir $CeremonyDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $env:VALIDATORS_MANIFEST_PATH = "data/validators.manifest.json"
}

$missing = @()
foreach ($name in @("JWT_SECRET", "RPC_API_KEYS", "BRIDGE_ORACLE_SECRET", "CORS_ORIGINS", "ETH_RPC_URL")) {
    if (-not [Environment]::GetEnvironmentVariable($name)) {
        $missing += $name
    }
}
if ($missing.Count -gt 0) {
    Write-Host "Missing required prod env vars: $($missing -join ', ')" -ForegroundColor Red
    Write-Host ""
    Write-Host "Quick setup (generates .env + data\wallet.json):" -ForegroundColor Cyan
    Write-Host "  .\scripts\setup_prod_env.ps1" -ForegroundColor White
    Write-Host ""
    Write-Host "Or set manually in this PowerShell session:" -ForegroundColor Gray
    Write-Host '  $env:JWT_SECRET = "your_jwt_secret_here"' -ForegroundColor Gray
    Write-Host '  $env:RPC_API_KEYS = "your_rpc_api_key_here"' -ForegroundColor Gray
    Write-Host '  $env:BRIDGE_ORACLE_SECRET = "your_bridge_oracle_secret"' -ForegroundColor Gray
    Write-Host '  $env:CORS_ORIGINS = "https://your-explorer.example.com"' -ForegroundColor Gray
    Write-Host '  $env:ETH_RPC_URL = "https://your-ethereum-rpc"' -ForegroundColor Gray
    exit 1
}

$walletPath = Join-Path (Get-Location) "data\wallet.json"
if (-not (Test-Path $walletPath)) {
    Write-Host "Prod wallet is required: $walletPath" -ForegroundColor Red
    Write-Host "Run: .\scripts\setup_prod_env.ps1" -ForegroundColor Cyan
    Write-Host "Or:  .\scripts\deploy_ceremony_prod.ps1 -CeremonyDir data/ceremony_keys" -ForegroundColor Cyan
    exit 1
}

Write-Host "Running production gate..." -ForegroundColor Cyan
python scripts/prod_gate.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose -f docker-compose.prod.yml up --build -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker failed - start Docker Desktop and retry." -ForegroundColor Red
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
    Write-Host "WARN: node not ready yet - check logs: docker compose -f docker-compose.prod.yml logs node" -ForegroundColor Yellow
} else {
    Write-Host "Node ready." -ForegroundColor Green
    $liveArgs = @("scripts/prod_smoke.py", "http://127.0.0.1:8080")
    python @liveArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARN: prod smoke failed - inspect bridge/L1 RPC configuration" -ForegroundColor Yellow
    }
    $readinessArgs = @(
        "scripts/mainnet_readiness.py",
        "--live",
        "--base-url", "http://127.0.0.1:8080",
        "--no-strict-audit"
    )
    if ($CeremonyDir) {
        $readinessArgs += @("--ceremony-dir", $CeremonyDir)
    }
    python @readinessArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARN: mainnet live readiness failed" -ForegroundColor Yellow
        exit $LASTEXITCODE
    }
}

Write-Host "Prod node:  http://localhost:8080  RPC :8545" -ForegroundColor Green
Write-Host 'Relayer:   docker compose -f docker-compose.prod.yml logs -f relayer' -ForegroundColor Gray
Write-Host 'All logs:  docker compose -f docker-compose.prod.yml logs -f' -ForegroundColor Gray
