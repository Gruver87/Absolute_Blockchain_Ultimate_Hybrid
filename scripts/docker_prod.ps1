# Start Docker prod profile (mainnet-v1 node; optional bridge relayer sidecar)
param(
    [string]$CeremonyDir = "",
    [switch]$Bridge
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

function Get-HostNodeStatus {
    param([string]$BaseUrl = "http://127.0.0.1:8080")
    try {
        return Invoke-RestMethod -Uri "$BaseUrl/status" -TimeoutSec 3
    } catch {
        return $null
    }
}

function Test-HostReachesDockerProd {
    param(
        [string]$BaseUrl = "http://127.0.0.1:8080",
        [int]$ExpectedChainId = 778888
    )
    $status = Get-HostNodeStatus -BaseUrl $BaseUrl
    if (-not $status) { return $false }
    return ([string]$status.deployment_mode -eq "prod" -and [int]$status.chain_id -eq $ExpectedChainId)
}

function Resolve-DockerProdPorts {
    param([int]$ExpectedChainId = 778888)
    $httpPort = [Environment]::GetEnvironmentVariable("ABS_DOCKER_HTTP_PORT")
    $rpcPort = [Environment]::GetEnvironmentVariable("ABS_DOCKER_RPC_PORT")
    $p2pPort = [Environment]::GetEnvironmentVariable("ABS_DOCKER_P2P_PORT")
    $wsPort = [Environment]::GetEnvironmentVariable("ABS_DOCKER_WS_PORT")
    if ($httpPort -and $rpcPort -and $p2pPort -and $wsPort) {
        return @{
            Http = [int]$httpPort
            Rpc = [int]$rpcPort
            P2p = [int]$p2pPort
            Ws = [int]$wsPort
        }
    }

    $default = @{ Http = 8080; Rpc = 8545; P2p = 5000; Ws = 8766 }
    $status8080 = Get-HostNodeStatus -BaseUrl "http://127.0.0.1:8080"
    if ($status8080) {
        $mode = [string]$status8080.deployment_mode
        $chainId = [int]$status8080.chain_id
        if ($mode -eq "prod" -and $chainId -eq $ExpectedChainId) {
            return $default
        }
        Write-Host "Port 8080 is used by $($status8080.network_name) (chain $chainId) - mapping Docker prod to 18080/18545." -ForegroundColor Yellow
        return @{ Http = 18080; Rpc = 18545; P2p = 15000; Ws = 18766 }
    }
    return $default
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
    Sync-CeremonyDeployEnv -ProjectRoot $ProjectRoot -CeremonyHash $meta.ceremony_hash
    if (Test-Path $dotEnv) {
        Import-DotEnvFile $dotEnv | Out-Null
    }
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
    exit 1
}

function Test-PlaceholderEthRpc {
    param([string]$Url)
    return ($Url -match '(?i)(ваш-ethereum|your-ethereum|your-mainnet|changeme|placeholder|todo|example\.com$|rpc\.example)')
}

$ethRpc = [Environment]::GetEnvironmentVariable("ETH_RPC_URL")
$probeL1 = [Environment]::GetEnvironmentVariable("BRIDGE_PROBE_L1_RPC")
if (Test-PlaceholderEthRpc $ethRpc) {
    if ($probeL1 -match '^(?i)(1|true|yes|on)$' -or $Bridge) {
        Write-Host "FAIL: real ETH_RPC_URL required when bridge/L1 probe is enabled (placeholder detected)." -ForegroundColor Red
        Write-Host "  .\scripts\setup_prod_env.ps1 -EthRpcUrl `"https://your-real-ethereum-rpc`"" -ForegroundColor Cyan
        exit 1
    }
    Write-Host "WARN: ETH_RPC_URL is a placeholder; OK for local smoke while BRIDGE_PROBE_L1_RPC=false." -ForegroundColor Yellow
}

$walletPath = Join-Path (Get-Location) "data\wallet.json"
if (-not (Test-Path $walletPath)) {
    Write-Host "Prod wallet is required: $walletPath" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $manifestPath)) {
    Write-Host "Prod validator manifest is required: $manifestPath" -ForegroundColor Red
    exit 1
}

Write-Host "Running production gate..." -ForegroundColor Cyan
python scripts/prod_gate.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$ports = Resolve-DockerProdPorts
$env:ABS_DOCKER_HTTP_PORT = [string]$ports.Http
$env:ABS_DOCKER_RPC_PORT = [string]$ports.Rpc
$env:ABS_DOCKER_P2P_PORT = [string]$ports.P2p
$env:ABS_DOCKER_WS_PORT = [string]$ports.Ws
$baseUrl = "http://127.0.0.1:$($ports.Http)"

Write-Host "Recreating prod stack on HTTP $($ports.Http), RPC $($ports.Rpc)..." -ForegroundColor Cyan
docker compose -f docker-compose.prod.yml down --remove-orphans 2>$null
$composeArgs = @("-f", "docker-compose.prod.yml", "up", "--build", "-d", "--force-recreate")
if ($Bridge) {
    $env:BRIDGE_ENABLED = "true"
    $env:BRIDGE_PROBE_L1_RPC = "true"
    Write-Host "Bridge profile: relayer sidecar + BRIDGE_ENABLED=true" -ForegroundColor DarkGray
    docker compose --profile bridge @composeArgs
} else {
    $env:BRIDGE_ENABLED = "false"
    $env:BRIDGE_PROBE_L1_RPC = "false"
    docker compose @composeArgs
}
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker failed - start Docker Desktop and retry." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "Waiting for $baseUrl/health/ready (up to 3 min)..." -ForegroundColor Cyan
$deadline = (Get-Date).AddMinutes(3)
$ready = $false
while ((Get-Date) -lt $deadline) {
    try {
        $resp = Invoke-WebRequest -Uri "$baseUrl/health/ready" -UseBasicParsing -TimeoutSec 5
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
    exit 1
}

Write-Host "Node ready at $baseUrl" -ForegroundColor Green
$liveArgs = @("scripts/prod_smoke.py", $baseUrl)
python @liveArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARN: prod smoke failed - inspect bridge/L1 RPC configuration" -ForegroundColor Yellow
    exit $LASTEXITCODE
}

$readinessArgs = @(
    "scripts/mainnet_readiness.py",
    "--live",
    "--base-url", $baseUrl,
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

Write-Host ("Prod node:  " + $baseUrl + "  RPC http://127.0.0.1:" + $ports.Rpc) -ForegroundColor Green
if ($Bridge) {
    Write-Host 'Relayer:   docker compose -f docker-compose.prod.yml --profile bridge logs -f relayer' -ForegroundColor Gray
} else {
    Write-Host 'Bridge:    disabled (mainnet-v1 default). Use -Bridge for L1 cutover lab.' -ForegroundColor Gray
}
Write-Host 'All logs:  docker compose -f docker-compose.prod.yml logs -f' -ForegroundColor Gray
