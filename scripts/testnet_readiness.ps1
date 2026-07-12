# Automated checks from docs/PUBLIC_TESTNET.md (local prod mesh prerequisites).
param(
    [switch]$ProdMesh,
    [switch]$TestnetSeed,
    [int[]]$Ports = @(8080, 8081, 8082),
    [string]$SoakReport = "",
    [int]$MinSoakHours = 10,
    [switch]$SkipIndustrialGate,
    [switch]$RunPublicGate
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

if ($ProdMesh) { $Ports = @(18180, 18181, 18182) }
if ($TestnetSeed) { $Ports = @(19080) }

if (-not $SoakReport) {
    if ($MinSoakHours -ge 48 -and (Test-Path (Join-Path $Root "logs/soak_report_48h.json"))) {
        $SoakReport = "logs/soak_report_48h.json"
    } else {
        $SoakReport = "logs/soak_report.json"
    }
}

$failures = @()
$checks = @()

function Add-Check([string]$Name, [bool]$Ok, [string]$Detail = "") {
    $script:checks += [PSCustomObject]@{ name = $Name; ok = $Ok; detail = $Detail }
    if (-not $Ok) { $script:failures += "$Name${Detail}" }
}

Write-Host "Testnet readiness (local automated)" -ForegroundColor Cyan
Write-Host "  ports=$($Ports -join ',') soak_report=$SoakReport min_hours=$MinSoakHours" -ForegroundColor DarkGray

if (-not $SkipIndustrialGate) {
    Write-Host "`n=== industrial_gate ===" -ForegroundColor Cyan
    python (Join-Path $ScriptDir "industrial_gate.py")
    Add-Check "industrial_gate" ($LASTEXITCODE -eq 0)
} else {
    Add-Check "industrial_gate" $true " (skipped)"
}

Write-Host "`n=== mesh health + harness ===" -ForegroundColor Cyan
$readySec = if ($ProdMesh) { 15 } else { 5 }
$statusSec = if ($ProdMesh) { 12 } else { 5 }
$harnessSec = if ($ProdMesh) { 20 } else { 15 }
$heights = @()
foreach ($p in $Ports) {
    try {
        $ready = Invoke-RestMethod -Uri "http://127.0.0.1:$p/health/ready" -TimeoutSec $readySec
        $st = Invoke-RestMethod -Uri "http://127.0.0.1:$p/status" -TimeoutSec $statusSec
        $cs = Invoke-RestMethod -Uri "http://127.0.0.1:$p/chain/consistency/harness?quick=1&peer_timeout=5" -TimeoutSec $harnessSec
        $ok = ($ready.status -eq "ready") -and ($cs.harness_healthy -eq $true) -and ($cs.tip_state_aligned -eq $true)
        $heights += [int]$st.height
        Add-Check "node:$p" $ok " height=$($st.height) peers=$($st.peers)"
    } catch {
        Add-Check "node:$p" $false " $($_.Exception.Message)"
    }
}
if ($heights.Count -gt 1) {
    $uniq = ($heights | Select-Object -Unique).Count
    Add-Check "mesh_height_aligned" ($uniq -le 1) " heights=$($heights -join '/')"
}

if ($RunPublicGate -or $TestnetSeed) {
    Write-Host "`n=== public_testnet_gate ===" -ForegroundColor Cyan
    $base = "http://127.0.0.1:$($Ports[0])"
    python (Join-Path $ScriptDir "public_testnet_gate.py") --live --base-url $base
    Add-Check "public_testnet_gate_live" ($LASTEXITCODE -eq 0)
}

if ($MinSoakHours -gt 0) {
if (Test-Path $SoakReport) {
    try {
        $soak = Get-Content $SoakReport -Raw -Encoding UTF8 | ConvertFrom-Json
        $hrs = [double]($soak.hours_requested)
        $elapsedOk = $soak.passed -eq $true
        $hoursOk = $hrs -ge $MinSoakHours
        Add-Check "soak_passed" $elapsedOk " passed=$($soak.passed)"
        Add-Check "soak_duration" $hoursOk " requested=${hrs}h (min $MinSoakHours)"
    } catch {
        Add-Check "soak_report" $false " parse error"
    }
} else {
    Add-Check "soak_report" $false " missing $SoakReport"
}
} else {
    Add-Check "soak_report" $true " (skipped min_hours=0)"
}

Write-Host "`n=== summary ===" -ForegroundColor Cyan
foreach ($c in $checks) {
    $color = if ($c.ok) { "Green" } else { "Yellow" }
    $mark = if ($c.ok) { "OK" } else { "WARN" }
    $detail = if ($c.detail) { " $($c.detail)" } else { "" }
    Write-Host "$mark $($c.name)$detail" -ForegroundColor $color
}

$manual = @(
    "TLS / public DNS",
    "VPS seed + validators",
    "Rate limits + RPC keys on public endpoints",
    "48h+ soak for public testnet (use -MinSoakHours 48)",
    "Third-party security audit (mainnet)"
)
Write-Host "`nManual / not automated:" -ForegroundColor DarkGray
foreach ($m in $manual) { Write-Host "  - $m" -ForegroundColor DarkGray }

if ($failures.Count -gt 0) {
    Write-Host "`nWARN: testnet readiness gaps ($($failures.Count))" -ForegroundColor Yellow
    exit 1
}
Write-Host "`nOK: automated testnet prerequisites passed" -ForegroundColor Green
exit 0
