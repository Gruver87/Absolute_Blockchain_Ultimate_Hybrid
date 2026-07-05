# Three-node production mesh (ceremony manifest + per-validator wallets)
param(
    [string]$CeremonyDir = "data/ceremony_keys",
    [switch]$NoCloneDb
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
Set-Location $ProjectRoot
. "$ScriptDir\ceremony_env.ps1"

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

function Test-PlaceholderEthRpc {
    param([string]$Url)
    return ($Url -match '(?i)(ваш-ethereum|your-ethereum|your-mainnet|changeme|placeholder|todo|example\.com$|rpc\.example)')
}

$dotEnv = Join-Path (Get-Location) ".env"
if (Import-DotEnvFile $dotEnv) {
    Write-Host "Loaded $dotEnv" -ForegroundColor DarkGray
}

python scripts/deploy_ceremony_prod.py --ceremony-dir $CeremonyDir --mesh
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$metaPath = Join-Path (Get-Location) "data\ceremony_deploy.json"
$meta = Get-Content $metaPath -Raw | ConvertFrom-Json
$env:VALIDATORS_MANIFEST_PATH = "data/validators.manifest.json"
$env:GENESIS_CEREMONY_HASH = $meta.ceremony_hash
Sync-CeremonyDeployEnv -ProjectRoot $ProjectRoot -CeremonyHash $meta.ceremony_hash
$env:BRIDGE_ENABLED = "false"
$env:BRIDGE_PROBE_L1_RPC = "false"

$missing = @()
foreach ($name in @("JWT_SECRET", "RPC_API_KEYS", "BRIDGE_ORACLE_SECRET", "CORS_ORIGINS", "ETH_RPC_URL")) {
    if (-not [Environment]::GetEnvironmentVariable($name)) { $missing += $name }
}
if ($missing.Count -gt 0) {
    Write-Host "Missing required prod env vars: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "  .\scripts\setup_prod_env.ps1 -EthRpcUrl `"https://your-real-ethereum-rpc`"" -ForegroundColor Cyan
    exit 1
}

$ethRpc = [Environment]::GetEnvironmentVariable("ETH_RPC_URL")
if (Test-PlaceholderEthRpc $ethRpc) {
    Write-Host "WARN: ETH_RPC_URL is a placeholder; OK while BRIDGE_PROBE_L1_RPC=false." -ForegroundColor Yellow
}

foreach ($wallet in @(
    "data\prod_mesh\wallets\validator-1.wallet.json",
    "data\prod_mesh\wallets\validator-2.wallet.json",
    "data\prod_mesh\wallets\validator-3.wallet.json",
    "data\validators.manifest.json"
)) {
    if (-not (Test-Path $wallet)) {
        Write-Host "FAIL: missing $wallet (run deploy with --mesh)" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Running production gate..." -ForegroundColor Cyan
python scripts/prod_gate.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$composeFile = "docker-compose.prod.3node.yml"
if ($NoCloneDb) {
    $env:SKIP_DB_SEED = "1"
} else {
    Remove-Item Env:SKIP_DB_SEED -ErrorAction SilentlyContinue
}

Write-Host "Recreating prod 3-node mesh (18180/18181/18182)..." -ForegroundColor Cyan
docker compose -f $composeFile down -v --remove-orphans 2>$null
docker compose -f $composeFile build node1 node2 node3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose -f $composeFile up -d --force-recreate node1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Waiting for node1..." -ForegroundColor Gray
$deadline = (Get-Date).AddMinutes(3)
$ready1 = $false
while ((Get-Date) -lt $deadline) {
    try {
        $resp = Invoke-WebRequest -Uri "http://127.0.0.1:18180/health/ready" -UseBasicParsing -TimeoutSec 5
        if ($resp.StatusCode -eq 200) { $ready1 = $true; break }
    } catch { Start-Sleep -Seconds 5 }
}
if (-not $ready1) {
    docker compose -f $composeFile logs node1 --tail 40
    exit 1
}

if (-not $NoCloneDb) {
    Write-Host "Stopping node1 for consistent RocksDB seed..." -ForegroundColor Gray
    docker compose -f $composeFile stop node1 | Out-Null
    docker compose -f $composeFile --profile seed run --rm node2-db-seed | Out-Null
    docker compose -f $composeFile --profile seed run --rm node3-db-seed | Out-Null
    docker compose -f $composeFile start node1 | Out-Null
    $deadline = (Get-Date).AddMinutes(2)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:18180/health/ready" -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -eq 200) { break }
        } catch { Start-Sleep -Seconds 3 }
    }
}

docker compose -f $composeFile up -d --force-recreate node2 node3
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Waiting for node2/node3 HTTP..." -ForegroundColor Gray
foreach ($port in @(18181, 18182)) {
    $deadline = (Get-Date).AddMinutes(2)
    $ready = $false
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$port/health/live" -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -eq 200) { $ready = $true; break }
        } catch { Start-Sleep -Seconds 3 }
    }
    if (-not $ready) {
        Write-Host "FAIL: mesh node not reachable on port $port" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Waiting for 3-node mesh sync..." -ForegroundColor Cyan
python scripts/verify_p2p_ci.py --mode prod-mesh3-live --url1 http://127.0.0.1:18180 --url2 http://127.0.0.1:18181 --url3 http://127.0.0.1:18182 --wait 360
if ($LASTEXITCODE -ne 0) {
    docker compose -f $composeFile logs node1 --tail 20
    docker compose -f $composeFile logs node2 --tail 20
    docker compose -f $composeFile logs node3 --tail 20
    exit $LASTEXITCODE
}

python scripts/prod_smoke.py http://127.0.0.1:18180
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "OK: prod 3-node mesh" -ForegroundColor Green
Write-Host "  node1 http://127.0.0.1:18180" -ForegroundColor Gray
Write-Host "  node2 http://127.0.0.1:18181" -ForegroundColor Gray
Write-Host "  node3 http://127.0.0.1:18182" -ForegroundColor Gray
