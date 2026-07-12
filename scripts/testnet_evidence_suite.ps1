# Live evidence for public testnet seed (chain 77777 on :19080).
param(
    [string]$BaseUrl = "http://127.0.0.1:19080",
    [switch]$SkipReadiness
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

function Step([string]$Name, [scriptblock]$Action) {
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL: $Name" -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "OK: $Name" -ForegroundColor Green
}

Step "docker_testnet_seed" {
    & (Join-Path $ScriptDir "docker_testnet_seed.ps1") -SkipBuild
}

Step "public_testnet_gate_live" {
    python (Join-Path $ScriptDir "public_testnet_gate.py") --live --base-url $BaseUrl
}

if (-not $SkipReadiness) {
    $port = ([uri]$BaseUrl).Port
    if (-not $port) { $port = 19080 }
    Step "testnet_readiness_seed" {
        & (Join-Path $ScriptDir "testnet_readiness.ps1") -Ports $port -SkipIndustrialGate -MinSoakHours 0
    }
}

python (Join-Path $ScriptDir "record_evidence_run.py") `
    --name public_testnet_seed_live `
    --result PASS `
    --command ".\scripts\testnet_evidence_suite.ps1" `
    --artifact "data/public_testnet_gate.json" `
    --git-tag v1.2.37 `
    2>$null | Out-Null

Write-Host "`nOK: testnet evidence suite passed" -ForegroundColor Green
exit 0
