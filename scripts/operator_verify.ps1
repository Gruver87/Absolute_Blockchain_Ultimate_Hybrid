# Operator full-verify helper for Absolute Blockchain Ultimate Hybrid.
# Usage (from repo root):
#   .\scripts\operator_verify.ps1              # Quick (waves + gate)
#   .\scripts\operator_verify.ps1 -Mode Standard
#   .\scripts\operator_verify.ps1 -Mode Full
# Honesty: green gate != public mainnet / ceremony pin / external audit complete.

param(
    [ValidateSet("Quick", "Standard", "Full", "Live", "Max")]
    [string]$Mode = "Quick",
    [switch]$SkipNativeBuild
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host ""
Write-Host "========================================================================"
Write-Host " OPERATOR VERIFY  mode=$Mode"
Write-Host " Repo: $Root"
Write-Host " Honesty: PASS != public mainnet"
Write-Host "========================================================================"
Write-Host ""

Write-Host ">>> node_version"
python -c "from runtime.config import Config; print(Config().node_version)"
if ($LASTEXITCODE -ne 0) { throw "node_version failed" }

if (-not $SkipNativeBuild) {
    Write-Host ""
    Write-Host ">>> build_native (recommended before Standard/Full)"
    & (Join-Path $Root "scripts\build_native.ps1")
    if ($LASTEXITCODE -ne 0) { throw "build_native failed rc=$LASTEXITCODE" }
}

Write-Host ""
Write-Host ">>> check_all -Mode $Mode"
& (Join-Path $Root "scripts\check_all.ps1") -Mode $Mode
if ($LASTEXITCODE -ne 0) { throw "check_all failed rc=$LASTEXITCODE" }

Write-Host ""
Write-Host "OK: operator_verify mode=$Mode"
Write-Host "Reports:"
Write-Host "  data/check_all.json"
Write-Host "  data/verify_industrial_waves.json  (Quick+)"
Write-Host "  data/full_audit_report.json        (Standard+)"
Write-Host "  data/industrial_gate.json"
Write-Host ""
