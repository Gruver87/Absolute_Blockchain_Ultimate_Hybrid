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

function Test-LocalNodeBlocksDockerProd {
    param([int]$ExpectedChainId = 778888)
    try {
        $status = Invoke-RestMethod -Uri "http://127.0.0.1:8080/status" -TimeoutSec 3
        $mode = [string]$status.deployment_mode
        $chainId = [int]$status.chain_id
        if ($mode -ne "prod" -or $chainId -ne $ExpectedChainId) {
            $network = [string]$status.network_name
            Write-Host "FAIL: port 8080 is already used by another node ($network, chain $chainId, mode $mode)." -ForegroundColor Red
            Write-Host "Stop the local dev node before Docker prod (close its terminal or stop the python process)." -ForegroundColor Yellow
            Write-Host "Then rerun: .\scripts\docker_prod.ps1" -ForegroundColor Cyan
            return $false
        }
    } catch {
        # Port free or not yet serving /status — OK for Docker bind.
    }
    return $true
}

function Test-HostReachesDockerProd {
    param([int]$ExpectedChainId = 778888)
    try {
        $status = Invoke-RestMethod -Uri "http://127.0.0.1:8080/status" -TimeoutSec 3
        return ([string]$status.deployment_mode -eq "prod" -and [int]$status.chain_id -eq $ExpectedChainId)
    } catch {
        return $false
    }
}

$dotEnv = Join-Path (Get-Location) ".env"
if (Import-DotEnvFile $dotEnv) {
    Write-Host "Loaded $dotEnv" -ForegroundColor DarkGray
}

if ($CeremonyDir) {
    & "$ScriptDir\deploy_ceremony_prod.ps1" -CeremonyDir $CeremonyDir
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$manifestPath = Join-Path (Get-Location) "data\validators.manifest.json"
$deployMetaPath = Join-Path (Get-Location) "data\ceremony_deploy.json"
if ((Test-Path $manifestPath) -and (Test-Path $deployMetaPath)) {
    $meta = Get-Content $deployMetaPath -Raw | ConvertFrom-Json
    $env:VALIDATORS_MANIFEST_PATH = "data/validators.manifest.json"
    $env:GENESIS_CEREMONY_HASH = $meta.ceremony_hash
    Write-Host "Ceremony: data/validators.manifest.json + GENESIS_CEREMONY_HASH from deploy meta" -ForegroundColor DarkGray
} elseif ([Environment]::GetEnvironmentVariable("GENESIS_CEREMONY_HASH")) {
    Write-Host "FAIL: GENESIS_CEREMONY_HASH is set but data/validators.manifest.json is missing." -ForegroundColor Red
    Write-Host "  .\scripts\deploy_ceremony_prod.ps1 -CeremonyDir data/ceremony_keys" -ForegroundColor Cyan
    Write-Host "  Or remove GENESIS_CEREMONY_HASH from .env for template manifest only." -ForegroundColor Gray
    exit 1
} else {
    $env:VALIDATORS_MANIFEST_PATH = "validators.manifest.mainnet-v1.example.json"
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
    Write-Host "  .\scripts\setup_prod_env.ps1 -EthRpcUrl `"https://your-real-ethereum-rpc`"" -ForegroundColor White
    Write-Host ""
    Write-Host "Or set manually in this PowerShell session:" -ForegroundColor Gray
    Write-Host '  $env:JWT_SECRET = "your_jwt_secret_here"' -ForegroundColor Gray
    Write-Host '  $env:RPC_API_KEYS = "your_rpc_api_key_here"' -ForegroundColor Gray
    Write-Host '  $env:BRIDGE_ORACLE_SECRET = "your_bridge_oracle_secret"' -ForegroundColor Gray
    Write-Host '  $env:CORS_ORIGINS = "https://your-explorer.example.com"' -ForegroundColor Gray
    Write-Host '  $env:ETH_RPC_URL = "https://your-real-ethereum-rpc"' -ForegroundColor Gray
    exit 1
}

$ethRpc = [Environment]::GetEnvironmentVariable("ETH_RPC_URL")
if ($ethRpc -match '(?i)(ваш-ethereum|your-ethereum|your-mainnet|changeme|placeholder|todo|example\.com$|rpc\.example)') {
    Write-Host "FAIL: ETH_RPC_URL looks like a placeholder, not a real JSON-RPC endpoint." -ForegroundColor Red
    Write-Host "  .\scripts\setup_prod_env.ps1 -EthRpcUrl `"https://mainnet.infura.io/v3/YOUR_KEY`"" -ForegroundColor Cyan
    Write-Host "  For local stack smoke without L1: set BRIDGE_PROBE_L1_RPC=false in .env" -ForegroundColor Gray
    exit 1
}

$walletPath = Join-Path (Get-Location) "data\wallet.json"
if (-not (Test-Path $walletPath)) {
    Write-Host "Prod wallet is required: $walletPath" -ForegroundColor Red
    Write-Host "Run: .\scripts\setup_prod_env.ps1" -ForegroundColor Cyan
    Write-Host "Or:  .\scripts\deploy_ceremony_prod.ps1 -CeremonyDir data/ceremony_keys" -ForegroundColor Cyan
    exit 1
}
if (-not (Test-Path $manifestPath)) {
    Write-Host "Prod validator manifest is required: $manifestPath" -ForegroundColor Red
    Write-Host "Run: .\scripts\deploy_ceremony_prod.ps1 -CeremonyDir data/ceremony_keys" -ForegroundColor Cyan
    exit 1
}

Write-Host "Running production gate..." -ForegroundColor Cyan
python scripts/prod_gate.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Test-LocalNodeBlocksDockerProd)) { exit 1 }

Write-Host "Recreating prod stack (volume abs-prod-data + ceremony file mounts)..." -ForegroundColor Cyan
docker compose -f docker-compose.prod.yml down 2>$null
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
    docker compose -f docker-compose.prod.yml logs node --tail 40
} else {
    Write-Host "Node ready." -ForegroundColor Green
    if (-not (Test-HostReachesDockerProd)) {
        Write-Host "WARN: host http://127.0.0.1:8080 does not reach Docker prod (local dev node may still be bound)." -ForegroundColor Yellow
        Write-Host "Running prod smoke inside the container instead." -ForegroundColor DarkGray
        docker compose -f docker-compose.prod.yml exec -T node python scripts/prod_smoke.py http://127.0.0.1:8080
    } else {
        $liveArgs = @("scripts/prod_smoke.py", "http://127.0.0.1:8080")
        python @liveArgs
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARN: prod smoke failed - inspect bridge/L1 RPC configuration" -ForegroundColor Yellow
    }
    if (Test-HostReachesDockerProd) {
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
    } else {
        Write-Host "SKIP: mainnet live readiness (stop local dev node on :8080 and rerun)" -ForegroundColor Yellow
    }
}

Write-Host "Prod node:  http://localhost:8080  RPC :8545" -ForegroundColor Green
Write-Host 'Relayer:   docker compose -f docker-compose.prod.yml logs -f relayer' -ForegroundColor Gray
Write-Host 'All logs:  docker compose -f docker-compose.prod.yml logs -f' -ForegroundColor Gray
