# Operator prep before mainnet cutover: ceremony verify, pin check, secret rotation preview.
param(
    [string]$CeremonyDir = "data/ceremony_keys",
    [switch]$StrictMainnet,
    [switch]$RequirePin,
    [switch]$SkipCeremonyPreflight
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

function Step([string]$Name, [scriptblock]$Action) {
    Write-Host ""
    Write-Host "=== $Name ===" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL: $Name" -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "OK: $Name" -ForegroundColor Green
}

$envPath = Join-Path $ProjectRoot ".env"
if (Test-Path $envPath) {
    Get-Content $envPath | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { return }
        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        $val = $parts[1].Trim().Trim([char]34).Trim([char]39)
        if ($key) { [Environment]::SetEnvironmentVariable($key, $val, "Process") }
    }
}

if (-not $SkipCeremonyPreflight) {
    Step "ceremony_preflight" {
        $argsList = @("scripts/ceremony_preflight.py", "--ceremony-dir", $CeremonyDir)
        if ($StrictMainnet) { $argsList += "--strict-mainnet" }
        if ($RequirePin) { $argsList += "--require-env-pin" }
        python @argsList
    }
}

if (-not $env:GENESIS_CEREMONY_HASH) {
    Write-Host ""
    Write-Host "WARN: GENESIS_CEREMONY_HASH not set in .env or session" -ForegroundColor Yellow
    Write-Host "  Run: .\scripts\pin_ceremony_hash.ps1 -CeremonyDir $CeremonyDir -StrictMainnet" -ForegroundColor DarkGray
    if ($RequirePin) { exit 1 }
} else {
    Write-Host ""
    Write-Host "OK: GENESIS_CEREMONY_HASH present in environment" -ForegroundColor Green
}

Step "secret_rotation_preview" {
    & (Join-Path $ProjectRoot "scripts\rotate_prod_secrets.ps1")
}

Step "bridge_decision_off" {
    python scripts/bridge_l1_preflight.py --config node.prod.mainnet-v1.example.json
}

Write-Host ""
Write-Host "Operator cutover prep passed (automation only)." -ForegroundColor Green
Write-Host "Before public cutover:" -ForegroundColor Cyan
Write-Host "  1. .\scripts\pin_ceremony_hash.ps1 -CeremonyDir $CeremonyDir -StrictMainnet" -ForegroundColor DarkGray
Write-Host "  2. .\scripts\rotate_prod_secrets.ps1 -Force" -ForegroundColor DarkGray
Write-Host "  3. .\scripts\docker_prod_3node.ps1 -CeremonyDir $CeremonyDir" -ForegroundColor DarkGray
Write-Host "  4. .\scripts\prod_evidence_suite.ps1 -RecordEvidence" -ForegroundColor DarkGray
Write-Host "  5. Wait for 48h soak -> industrial_gate --min-soak-hours 48" -ForegroundColor DarkGray
exit 0
