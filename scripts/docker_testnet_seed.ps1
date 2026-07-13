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

function Get-SeedPortState([int]$Port) {
    try {
        $ready = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health/ready" -TimeoutSec 3
        $st = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/status" -TimeoutSec 3
        if (($ready.status -eq "ready") -and ([int]$st.chain_id -eq 77777)) {
            return @{ State = "AbsRunning"; Status = $st }
        }
        return @{
            State = "Conflict"
            Reason = "port $Port responds but chain_id=$($st.chain_id) is not testnet 77777"
        }
    } catch {
        $msg = $_.Exception.Message
        if ($msg -match 'Unable to connect|actively refused|connection attempt failed') {
            return @{ State = "Free" }
        }
        if ($msg -match '301|302|Moved|about:blank') {
            return @{
                State = "Conflict"
                Reason = "port $Port is used by another app (e.g. NahimicService on Windows :9080). Set TESTNET_HTTP_PORT=19080 in .env.testnet"
            }
        }
        return @{ State = "Free" }
    }
}

$envFile = Join-Path $Root ".env.testnet"
$example = Join-Path $Root ".env.testnet.example"
if (-not (Test-Path $envFile)) {
    if (Test-Path $example) {
        Copy-Item $example $envFile
        Write-Host "Created .env.testnet from example - rotate JWT_SECRET and RPC_API_KEYS" -ForegroundColor Yellow
    } else {
        Write-Host "FAIL: missing .env.testnet (copy .env.testnet.example)" -ForegroundColor Red
        exit 1
    }
}

Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#=]+)=(.*)$') {
        $k = $matches[1].Trim()
        $v = $matches[2].Trim().Trim([char]34).Trim([char]39)
        if ($k) { Set-Item -Path "env:$k" -Value $v }
    }
}

$httpPortNum = if ($env:TESTNET_HTTP_PORT) { [int]$env:TESTNET_HTTP_PORT } else { 19080 }

$portState = Get-SeedPortState -Port $httpPortNum
if ($portState.State -eq "Conflict") {
    Write-Host "FAIL: $($portState.Reason)" -ForegroundColor Red
    exit 1
}
$seedAlreadyRunning = ($portState.State -eq "AbsRunning")

$composeArgs = @("-f", "docker-compose.testnet.yml", "-p", "abs-testnet")
if ($WithValidator) { $composeArgs += "--profile", "validators" }

if ($Down) {
    docker compose @composeArgs down
    exit $LASTEXITCODE
}

if (-not $seedAlreadyRunning) {
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
} else {
    Write-Host "OK: testnet seed already running on :$httpPortNum (chain 77777)" -ForegroundColor Green
}

$httpPort = if ($env:TESTNET_HTTP_PORT) { $env:TESTNET_HTTP_PORT } else { "19080" }
if (-not $seedAlreadyRunning) {
    $deadline = (Get-Date).AddMinutes(3)
    Write-Host "Waiting for testnet seed http://127.0.0.1:$httpPort/health/ready ..."
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-RestMethod -Uri "http://127.0.0.1:$httpPort/health/ready" -TimeoutSec 5
            if ($r.status -eq "ready") { break }
        } catch { }
        Start-Sleep -Seconds 3
    }
}

try {
    $st = Invoke-RestMethod -Uri "http://127.0.0.1:$httpPort/status" -TimeoutSec 5
    Write-Host "OK: testnet seed chain_id=$($st.chain_id) height=$($st.height) peers=$($st.peers)" -ForegroundColor Green
    Write-Host "  HTTP  http://127.0.0.1:$httpPort" -ForegroundColor DarkGray
    $rpcPort = if ($env:TESTNET_RPC_PORT) { $env:TESTNET_RPC_PORT } else { "19085" }
    Write-Host "  RPC   http://127.0.0.1:$rpcPort  (X-API-Key required)" -ForegroundColor DarkGray
    Write-Host "  Next: .\scripts\prepare_vps_testnet.ps1 -Live" -ForegroundColor DarkGray
    Write-Host "  Gate: .\scripts\public_testnet_gate.ps1 -Live -BaseUrl http://127.0.0.1:$httpPort" -ForegroundColor DarkGray
} catch {
    Write-Host "WARN: seed started but status check failed: $($_.Exception.Message)" -ForegroundColor Yellow
    exit 1
}

exit 0
