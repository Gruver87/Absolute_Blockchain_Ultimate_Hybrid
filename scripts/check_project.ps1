# Quick local verification for Absolute Blockchain Ultimate.
# Usage:
#   .\scripts\check_project.ps1
#   .\scripts\check_project.ps1 -Live
#   .\scripts\check_project.ps1 -SkipUnit
#   .\scripts\check_project.ps1 -ProdGate

param(
    [switch]$Live,
    [switch]$SkipUnit,
    [switch]$ProdGate
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

Run-Step "Secrets scan" {
    python scripts/check_secrets.py
}

Run-Step "Quick project audit" {
    python scripts/full_audit.py --quick
}

if ($ProdGate) {
    Run-Step "Production gate" {
        python scripts/prod_gate.py
    }
}

if (-not $SkipUnit) {
    Run-Step "Unit tests" {
        pytest tests/unit -q
    }
}

if ($Live) {
    Write-Host "`n=== Live node checks ===" -ForegroundColor Cyan
    $baseUrl = "http://127.0.0.1:8080"

    foreach ($path in @("/health/live", "/status", "/p2p/topology", "/sync/status")) {
        $url = "$baseUrl$path"
        Write-Host "GET $url"
        Invoke-RestMethod $url -UseBasicParsing | Out-Null
    }

    Run-Step "Live audit" {
        python scripts/full_audit.py --live
    }
}

Write-Host "`nOK: project checks passed" -ForegroundColor Green
