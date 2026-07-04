# Full verification for Absolute Blockchain Ultimate Hybrid.
# Usage:
#   .\scripts\check_hybrid_full.ps1
#   .\scripts\check_hybrid_full.ps1 -Docker
#   .\scripts\check_hybrid_full.ps1 -Live -P2P

param(
    [switch]$Live,
    [switch]$P2P,
    [switch]$Docker,
    [string]$BaseUrl = "http://127.0.0.1:8080",
    [int]$PytestTimeout = 900
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

Write-Host "Absolute Blockchain Ultimate Hybrid - full verification" -ForegroundColor Green
Write-Host "Project: $ProjectRoot"

Require-Command python

Run-Step "Python version" {
    python --version
}

Run-Step "Build Rust/PyO3 native crypto" {
    & (Join-Path $ProjectRoot "scripts\build_native.ps1")
}
Set-Location $ProjectRoot

Run-Step "Build Rust bridge CLI" {
    & (Join-Path $ProjectRoot "scripts\build_bridge.ps1")
}
Set-Location $ProjectRoot

Run-Step "Native crypto self-test" {
    python -c "from crypto import native; s=native.native_crypto_status(required=True); assert s['available'] and s['self_test'], s; print('OK native:', s)"
}

Run-Step "Production gate" {
    python scripts/prod_gate.py
}

$checkArgs = @("scripts\check_everything.ps1", "-PytestTimeout", "$PytestTimeout")
if ($Live) {
    $checkArgs += "-Live"
    $checkArgs += "-BaseUrl"
    $checkArgs += $BaseUrl
}
if ($P2P) {
    $checkArgs += "-P2P"
}
if ($Docker) {
    $checkArgs += "-Docker"
}

Run-Step "Full blockchain audit and tests" {
    powershell -ExecutionPolicy Bypass -File @checkArgs
}

Run-Step "Hybrid critical tests" {
    python -m pytest `
        tests/unit/test_native_crypto.py `
        tests/unit/test_state_root_native.py `
        tests/unit/test_secp256k1.py `
        tests/unit/test_chain_integrity.py `
        tests/unit/test_api.py `
        tests/unit/test_prod_config.py `
        tests/unit/test_bridge_health.py `
        tests/unit/test_native_consensus_hash.py `
        tests/unit/test_native_peer_validation.py `
        tests/unit/test_evm_keccak_native.py `
        tests/unit/test_evm_native_u256.py `
        tests/unit/test_evm_native_cmp_memory.py `
        tests/unit/test_native_deploy_address.py `
        tests/unit/test_sync_incremental.py `
        tests/unit/test_rust_bridge_cli.py `
        tests/unit/test_rust_bridge_e2e.py `
        -q
}

Write-Host "`nOK: HYBRID BLOCKCHAIN FULL CHECK PASSED" -ForegroundColor Green
