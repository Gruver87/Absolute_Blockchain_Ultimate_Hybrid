# Absolute Blockchain Ultimate Hybrid - ONE-STOP full verification.
#
# Single entry point (alias):
#   .\scripts\test_all.ps1
#   .\scripts\test_all.ps1 -SkipNativeBuild
#
# Local full gate (recommended before push):
#   .\scripts\test_blockchain_full.ps1
#
# Live node already running (python main.py):
#   .\scripts\test_blockchain_full.ps1 -Live
#
# Live + P2P mesh (needs :8080+:8081; single :8080 skips P2P with hint):
#   .\scripts\test_blockchain_full.ps1 -Live -P2P
#
# P2P only (isolated CI on :15080/:15081, no live node needed):
#   .\scripts\test_blockchain_full.ps1 -P2P
#
# Docker compose validation:
#   .\scripts\test_blockchain_full.ps1 -Docker
#
# Everything including Docker image build:
#   .\scripts\test_blockchain_full.ps1 -Docker -DockerBuild -Live -P2P
#
# Skip native wheel rebuild (already built):
#   .\scripts\test_blockchain_full.ps1 -SkipNativeBuild

param(
    [switch]$Live,
    [switch]$P2P,
    [switch]$Docker,
    [switch]$DockerBuild,
    [switch]$BuildRust,
    [switch]$SkipNativeBuild,
    [switch]$NoClean,
    [string]$BaseUrl = "http://127.0.0.1:8080",
    [int]$PytestTimeout = 900,
    [int]$P2PWait = 300,
    [int]$AuditRetries = 1
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

function Run-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    $global:LASTEXITCODE = 0
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found: $Name"
    }
}

function Get-RustBridgeBinary {
    $candidates = @(
        (Join-Path $ProjectRoot "bridge\abs_bridge_bin.exe"),
        (Join-Path $ProjectRoot "bridge\abs_bridge_bin")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }
    return $null
}

function Clear-PythonGeneratedFiles {
    Write-Host "Removing Python cache files..." -ForegroundColor DarkGray
    Get-ChildItem -Path $ProjectRoot -Directory -Recurse -Force -Filter "__pycache__" -ErrorAction SilentlyContinue |
        Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    Get-ChildItem -Path $ProjectRoot -File -Recurse -Force -Include "*.pyc", "*.pyo" -ErrorAction SilentlyContinue |
        Remove-Item -Force -ErrorAction SilentlyContinue
}

function Invoke-FullAuditWithRetry {
    $attempt = 0
    while ($true) {
        $attempt += 1
        Write-Host "Full audit attempt $attempt/$($AuditRetries + 1)" -ForegroundColor Gray
        $global:LASTEXITCODE = 0
        python scripts/full_audit.py --pytest-timeout $PytestTimeout
        if ($LASTEXITCODE -eq 0) {
            return
        }
        if ($attempt -gt $AuditRetries) {
            exit $LASTEXITCODE
        }
        Write-Host "Full audit failed once; cleaning caches and retrying..." -ForegroundColor Yellow
        Clear-PythonGeneratedFiles
        Start-Sleep -Seconds 2
    }
}

function Invoke-JsonEndpoint {
    param(
        [string]$Path,
        [int]$TimeoutSec = 10
    )
    $url = "$BaseUrl$Path"
    Write-Host "GET $url"
    Invoke-RestMethod -Uri $url -UseBasicParsing -TimeoutSec $TimeoutSec | Out-Null
}

Write-Host "Absolute Blockchain Ultimate Hybrid - FULL BLOCKCHAIN TEST" -ForegroundColor Green
Write-Host "Project: $ProjectRoot"
Write-Host "BaseUrl: $BaseUrl"

Require-Command python

Run-Step "Python version" {
    python --version
}

if (-not $SkipNativeBuild) {
    Run-Step "Build Rust/PyO3 native crypto (abs_native)" {
        & (Join-Path $ProjectRoot "scripts\build_native.ps1")
    }
    Set-Location $ProjectRoot
}

Run-Step "Native crypto self-test" {
    python -c "from crypto import native; st=native.native_crypto_status(required=True); assert st['available'] and st['self_test'], st; print('OK native:', st)"
}

Run-Step "Secrets scan" {
    python scripts/check_secrets.py
}

Run-Step "Static production gate" {
    python scripts/prod_gate.py
}

Run-Step "Pre-mainnet audit" {
    python scripts/pre_mainnet_audit.py
}

Run-Step "Native bridge helper" {
    python scripts/native_bridge_helper.py status
}

Run-Step "Rust bridge binary" {
    $bin = Get-RustBridgeBinary
    if ($BuildRust -or -not $bin) {
        Require-Command cargo
        & (Join-Path $ProjectRoot "scripts\build_bridge.ps1")
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        $bin = Get-RustBridgeBinary
    }
    if (-not $bin) {
        throw "Rust bridge binary missing. Re-run with -BuildRust"
    }
    Write-Host "Rust bridge binary: $bin"
    $payload = '{"command":"status","args":{}}'
    $out = $payload | & $bin
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $json = $out | ConvertFrom-Json
    if ($json.status -ne "ready") {
        throw "Rust bridge status is not ready: $out"
    }
    Write-Host "Rust bridge status: $($json.status) source=$($json.source)"
}

Run-Step "Production stack verification" {
    python scripts/verify_prod_stack.py
}

if (-not $NoClean) {
    Run-Step "Clean generated Python cache" {
        Clear-PythonGeneratedFiles
    }
}

Run-Step "Full audit + all pytest (tests/)" {
    Invoke-FullAuditWithRetry
}

Run-Step "Hybrid critical native/consensus/EVM tests" {
    python -m pytest `
        tests/unit/test_native_crypto.py `
        tests/unit/test_state_root_native.py `
        tests/unit/test_secp256k1.py `
        tests/unit/test_chain_integrity.py `
        tests/unit/test_api.py `
        tests/unit/test_prod_config.py `
        tests/unit/test_bridge_health.py `
        tests/unit/test_bridge_relayer_core.py `
        tests/unit/test_prod_compose.py `
        tests/unit/test_prod_smoke.py `
        tests/unit/test_verify_prod_stack.py `
        tests/unit/test_native_consensus_hash.py `
        tests/unit/test_native_peer_validation.py `
        tests/unit/test_evm_keccak_native.py `
        tests/unit/test_evm_native_u256.py `
        tests/unit/test_evm_native_cmp_memory.py `
        tests/unit/test_evm_native_arith_extended.py `
        tests/unit/test_evm_native_read_push.py `
        tests/unit/test_evm_native_jumpdest.py `
        tests/unit/test_evm_native_stack.py `
        tests/unit/test_evm_native_scan.py `
        tests/unit/test_evm_native_pure_runner.py `
        tests/unit/test_evm_host_bridge.py `
        tests/unit/test_evm_prod_handoff.py `
        tests/unit/test_native_deploy_address.py `
        tests/unit/test_mempool_batch_signatures.py `
        tests/unit/test_sync_incremental.py `
        tests/unit/test_rust_bridge_cli.py `
        tests/unit/test_rust_bridge_e2e.py `
        tests/unit/test_validator_loader.py `
        tests/unit/test_eth_filters.py `
        tests/unit/test_eth_ws_subscriptions.py `
        tests/unit/test_evm_cancun_opcodes.py `
        tests/unit/test_evm_blob_opcodes.py `
        tests/unit/test_cross_shard_coordinator.py `
        tests/unit/test_live_resharding.py `
        tests/unit/test_distributed_sharding.py `
        tests/unit/test_validator_key_provider.py `
        -q
}

if ($Live) {
    Run-Step "Live node endpoints" {
        Invoke-JsonEndpoint "/health/live"
        Invoke-JsonEndpoint "/status"
        Invoke-JsonEndpoint "/sync/status"
        Invoke-JsonEndpoint "/features"
        Invoke-JsonEndpoint "/bridge"
        Invoke-JsonEndpoint "/tokenomics"
        Invoke-JsonEndpoint "/chain/state-root/status"
    }

    $liveArgs = @("scripts/full_audit.py", "--live", "--no-tests", "--base-url", $BaseUrl)
    if ($P2P) {
        $liveArgs += "--p2p"
    }
    Run-Step "Live audit" {
        python @liveArgs
    }
}
elseif ($P2P) {
    Run-Step "P2P auto verification" {
        python scripts/verify_p2p_ci.py --mode auto --wait $P2PWait
    }
}

if ($Docker) {
    Require-Command docker

    Run-Step "Docker devnet compose config" {
        docker compose -f docker-compose.devnet.yml config --quiet
    }

    Run-Step "Docker devnet rust compose config" {
        docker compose -f docker-compose.devnet-rust.yml config --quiet
    }

    Run-Step "Docker 3-node devnet compose config" {
        docker compose -f docker-compose.devnet-3node.yml config --quiet
    }

    Run-Step "Docker 5-validator devnet compose config" {
        docker compose -f docker-compose.devnet-5validator.yml config --quiet
    }

    $oldJwt = $env:JWT_SECRET
    $oldRpc = $env:RPC_API_KEYS
    $oldOracle = $env:BRIDGE_ORACLE_SECRET
    $oldCors = $env:CORS_ORIGINS
    $oldEthRpc = $env:ETH_RPC_URL
    try {
        $placeholder = "composeconfigplaceholder"
        if (-not $env:JWT_SECRET) { $env:JWT_SECRET = $placeholder }
        if (-not $env:RPC_API_KEYS) { $env:RPC_API_KEYS = $placeholder }
        if (-not $env:BRIDGE_ORACLE_SECRET) { $env:BRIDGE_ORACLE_SECRET = $placeholder }
        if (-not $env:CORS_ORIGINS) { $env:CORS_ORIGINS = "https://explorer.example.com" }
        if (-not $env:ETH_RPC_URL) { $env:ETH_RPC_URL = "https://rpc.example.com" }

        Run-Step "Docker production compose config" {
            docker compose -f docker-compose.prod.yml config --quiet
        }
    }
    finally {
        $env:JWT_SECRET = $oldJwt
        $env:RPC_API_KEYS = $oldRpc
        $env:BRIDGE_ORACLE_SECRET = $oldOracle
        $env:CORS_ORIGINS = $oldCors
        $env:ETH_RPC_URL = $oldEthRpc
    }

    if ($DockerBuild) {
        Run-Step "Docker image build" {
            docker compose -f docker-compose.devnet.yml build
        }
    }
}

Write-Host "`nOK: FULL BLOCKCHAIN TEST PASSED" -ForegroundColor Green
Write-Host "Reports:"
Write-Host "  data/full_audit_report.json"
Write-Host "  data/final_audit_report.json"
