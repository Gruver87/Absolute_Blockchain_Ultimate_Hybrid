# Unified mainnet cutover checklist — ceremony, code gates, optional live mesh + bridge.
param(
    [string]$CeremonyDir = "data/ceremony_keys",
    [switch]$RequireCeremonyPin,
    [switch]$StrictMainnet,
    [switch]$LiveProdMesh,
    [switch]$BridgeCutover,
    [switch]$RecordEvidence,
    [string]$GitTag = ""
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
    if ($RecordEvidence) {
        $tagArg = @()
        if ($GitTag) { $tagArg = @("--git-tag", $GitTag) }
        python scripts/record_evidence_run.py --name $Name --result PASS @tagArg | Out-Null
    }
}

$envPath = Join-Path $ProjectRoot ".env"
if (Test-Path $envPath) {
    Get-Content $envPath | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) { return }
        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        $val = $parts[1].Trim().Trim('"').Trim("'")
        if ($key) { [Environment]::SetEnvironmentVariable($key, $val, "Process") }
    }
}

Step "operator_cutover_prep" {
    $argsList = @("-CeremonyDir", $CeremonyDir)
    if ($StrictMainnet) { $argsList += "-StrictMainnet" }
    if ($RequireCeremonyPin) { $argsList += "-RequirePin" }
    & "$ProjectRoot\scripts\operator_cutover_prep.ps1" @argsList
}

Step "mainnet_launch_checklist" {
    $argsList = @(
        "scripts/mainnet_launch_checklist.py",
        "--ceremony-dir", $CeremonyDir
    )
    if ($StrictMainnet) { $argsList += "--strict-mainnet" }
    if ($BridgeCutover) { $argsList += "--bridge-cutover" }
    python @argsList
}

if ($LiveProdMesh) {
    Step "mainnet_readiness_live_mesh" {
        python scripts/mainnet_readiness.py `
            --live-prod-mesh `
            --ceremony-dir $CeremonyDir `
            --no-strict-audit
    }
}

if (-not $BridgeCutover) {
    Write-Host ""
    Write-Host "Bridge: mainnet v1 keeps bridge off (see operator_cutover_prep)" -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "OK: mainnet cutover checklist passed" -ForegroundColor Green
Write-Host "  Next: .\scripts\prod_evidence_suite.ps1 -RecordEvidence" -ForegroundColor DarkGray
Write-Host "  Soak: .\scripts\restart_soak_prod_mesh.ps1 -Hours 48" -ForegroundColor DarkGray
exit 0
