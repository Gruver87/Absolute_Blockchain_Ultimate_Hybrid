# Full local verification for Absolute Blockchain Ultimate.
# Usage:
#   .\scripts\check_everything.ps1
#   .\scripts\check_everything.ps1 -Live
#   .\scripts\check_everything.ps1 -Live -P2P
#   .\scripts\check_everything.ps1 -Docker

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

Write-Host "Absolute Blockchain Ultimate - full verification" -ForegroundColor Green
Write-Host "Project: $ProjectRoot"

Require-Command python

Run-Step "Python version" {
    python --version
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

Run-Step "Production stack verification" {
    python scripts/verify_prod_stack.py
}

Run-Step "Full audit with tests" {
    python scripts/full_audit.py --pytest-timeout $PytestTimeout
}

if ($Live) {
    $liveArgs = @("scripts/full_audit.py", "--live", "--no-tests", "--base-url", $BaseUrl)
    if ($P2P) {
        $liveArgs += "--p2p"
    }

    Run-Step "Live node audit" {
        python @liveArgs
    }
}
elseif ($P2P) {
    Run-Step "P2P verification" {
        python scripts/verify_p2p_ci.py --mode auto --wait 120
    }
}

if ($Docker) {
    Require-Command docker

    Run-Step "Docker devnet compose config" {
        docker compose -f docker-compose.devnet.yml config --quiet
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
}

Write-Host "`nOK: full verification passed" -ForegroundColor Green
