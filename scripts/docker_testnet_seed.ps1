# Start public testnet seed (chain 77777) via docker-compose.testnet.yml
param(
    [switch]$SkipBuild,
    [switch]$WithValidator,
    [switch]$Down
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$envFile = Join-Path $Root ".env.testnet"
$example = Join-Path $Root ".env.testnet.example"
if (-not (Test-Path $envFile)) {
    if (Test-Path $example) {
        Copy-Item $example $envFile
        Write-Host "Created .env.testnet from example — rotate JWT_SECRET and RPC_API_KEYS" -ForegroundColor Yellow
    } else {
        Write-Host "FAIL: missing .env.testnet (copy .env.testnet.example)" -ForegroundColor Red
        exit 1
    }
}

Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') {
        $k = $matches[1].Trim()
        $v = $matches[2].Trim().Trim('"')
        if ($k) { Set-Item -Path "env:$k" -Value $v }
    }
}

$composeArgs = @("-f", "docker-compose.testnet.yml", "-p", "abs-testnet")
if ($WithValidator) { $composeArgs += "--profile", "validators" }

if ($Down) {
    docker compose @composeArgs down
    exit $LASTEXITCODE
}

if (-not $SkipBuild) {
    docker compose @composeArgs build testnet-seed
    if (-not $?) { exit 1 }
}

docker compose @composeArgs up -d testnet-seed
if (-not $?) { exit 1 }

if ($WithValidator) {
    docker compose @composeArgs up -d testnet-validator
    if (-not $?) { exit 1 }
}

$httpPort = if ($env:TESTNET_HTTP_PORT) { $env:TESTNET_HTTP_PORT } else { "9080" }
$deadline = (Get-Date).AddMinutes(3)
Write-Host "Waiting for testnet seed http://127.0.0.1:$httpPort/health/ready ..."
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-RestMethod -Uri "http://127.0.0.1:$httpPort/health/ready" -TimeoutSec 5
        if ($r.status -eq "ready") { break }
    } catch { }
    Start-Sleep -Seconds 3
}

try {
    $st = Invoke-RestMethod -Uri "http://127.0.0.1:$httpPort/status" -TimeoutSec 5
    Write-Host "OK: testnet seed chain_id=$($st.chain_id) height=$($st.height) peers=$($st.peers)" -ForegroundColor Green
    Write-Host "  HTTP  http://127.0.0.1:$httpPort" -ForegroundColor DarkGray
    $rpcPort = if ($env:TESTNET_RPC_PORT) { $env:TESTNET_RPC_PORT } else { "9085" }
    Write-Host "  RPC   http://127.0.0.1:$rpcPort  (X-API-Key required)" -ForegroundColor DarkGray
    Write-Host "  Next: .\scripts\testnet_readiness.ps1 -Ports $httpPort" -ForegroundColor DarkGray
} catch {
    Write-Host "WARN: seed started but status check failed: $($_.Exception.Message)" -ForegroundColor Yellow
    exit 1
}

exit 0
