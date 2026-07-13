# Full local public testnet evidence path (seed + gates + VPS preflight).
param(
    [string]$BaseUrl = "http://127.0.0.1:19080",
    [switch]$SkipReadiness,
    [switch]$WithValidator
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$gitTag = "unknown"
try {
    $desc = git describe --tags --abbrev=0 2>$null
    if ($desc) { $gitTag = $desc.Trim() }
} catch { }

function Step([string]$Name, [scriptblock]$Action) {
    Write-Host "`n=== $Name ===" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL: $Name" -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "OK: $Name" -ForegroundColor Green
}

$seedArgs = @()
if ($WithValidator) { $seedArgs += "-WithValidator" }

Step "docker_testnet_seed" {
    & (Join-Path $ScriptDir "docker_testnet_seed.ps1") -SkipBuild @seedArgs
}

Step "public_testnet_gate_live" {
    python (Join-Path $ScriptDir "public_testnet_gate.py") --live --base-url $BaseUrl
}

Step "vps_testnet_preflight_live" {
    python (Join-Path $ScriptDir "vps_testnet_preflight.py") --live --base-url $BaseUrl
}

Step "testnet_uptime_probe" {
    python (Join-Path $ScriptDir "testnet_uptime_probe.py") --base-url $BaseUrl --append
}

if (-not $SkipReadiness) {
    $port = ([uri]$BaseUrl).Port
    if (-not $port) { $port = 19080 }
    Step "testnet_readiness_seed" {
        & (Join-Path $ScriptDir "testnet_readiness.ps1") -TestnetSeed -SkipIndustrialGate -MinSoakHours 0 -RunPublicGate
    }
}

if ($WithValidator) {
    Step "verify_testnet_mesh" {
        python (Join-Path $ScriptDir "verify_testnet_mesh.py") --mesh --wait 90
    }
}

python (Join-Path $ScriptDir "record_evidence_run.py") `
    --name public_testnet_seed_live `
    --result PASS `
    --command ".\scripts\testnet_evidence_suite.ps1" `
    --artifact "data/public_testnet_gate.json" `
    --git-tag $gitTag `
    2>$null | Out-Null

Write-Host "`nOK: testnet evidence suite passed" -ForegroundColor Green
Write-Host "  VPS deploy: .\scripts\prepare_vps_testnet.ps1 -Live" -ForegroundColor DarkGray
Write-Host "  Cron probe: .\scripts\testnet_uptime_probe.ps1 -Append" -ForegroundColor DarkGray
exit 0
