# Absolute Blockchain Ultimate Hybrid - ONE project self-check
#
# Canonical entry to verify the whole repo. Wraps check_all + industrial
# tip-v2 evidence gates. PASS != public mainnet / firm audit complete.
#
# Usage (from repo root):
#   .\scripts\verify_project.ps1
#   .\scripts\verify_project.ps1 -Mode Standard
#   .\scripts\verify_project.ps1 -Mode Industrial
#   .\scripts\verify_project.ps1 -Mode Max
#   .\scripts\verify_project.ps1 -Help
#
# Cross-platform: python scripts/verify_project.py --mode quick|standard|industrial
# Report: data\verify_project.json

param(
    [ValidateSet("Quick", "Standard", "Industrial", "Max")]
    [string]$Mode = "Quick",
    [string]$BaseUrl = "http://127.0.0.1:8080",
    [double]$MinSoakHours = 48,
    [switch]$SkipNativeBuild,
    [switch]$NoAutoStart,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

if ($Help) {
    Write-Host ""
    Write-Host "verify_project.ps1 - unified project self-check"
    Write-Host ""
    Write-Host "  Quick         waves + industrial_gate (daily)"
    Write-Host "  Standard      full offline gate (prod/pytest)"
    Write-Host "  Industrial    Standard + tip-v2 soak evidence + bridge OFF"
    Write-Host "  Max           Industrial + Live HTTP + isolated P2P CI"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\scripts\verify_project.ps1"
    Write-Host "  .\scripts\verify_project.ps1 -Mode Standard"
    Write-Host "  .\scripts\verify_project.ps1 -Mode Industrial"
    Write-Host "  .\scripts\verify_project.ps1 -Mode Industrial -MinSoakHours 48"
    Write-Host "  .\scripts\verify_project.ps1 -Mode Max"
    Write-Host ""
    Write-Host "Report: data\verify_project.json"
    Write-Host "Honesty: green PASS != public mainnet / external audit PDF."
    Write-Host ""
    exit 0
}

function Write-Banner {
    param(
        [string]$Text,
        [ConsoleColor]$Color = [ConsoleColor]::Cyan
    )
    Write-Host ""
    Write-Host ("=" * 72) -ForegroundColor $Color
    Write-Host (" " + $Text) -ForegroundColor $Color
    Write-Host ("=" * 72) -ForegroundColor $Color
}

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Command
    )
    Write-Host ""
    Write-Host (">>> " + $Name) -ForegroundColor Yellow
    $global:LASTEXITCODE = 0
    & $Command
    $rc = $LASTEXITCODE
    if ($null -eq $rc) { $rc = 0 }
    if ($rc -ne 0) {
        throw ("STEP FAIL: " + $Name + " (exit " + $rc + ")")
    }
    Write-Host ("OK: " + $Name) -ForegroundColor Green
}

$started = Get-Date
$report = [ordered]@{
    script         = "verify_project.ps1"
    mode           = $Mode
    min_soak_hours = $MinSoakHours
    started_utc    = $started.ToUniversalTime().ToString("o")
    steps          = @()
    ok             = $false
    honesty        = @(
        "PASS is not public mainnet"
        "external firm audit PDF still required for audited claim"
        "bridge must stay OFF on live mesh without audited L1 cutover"
        "Industrial mode checks packaged tip-v2 soak evidence (operator-local)"
    )
}

Write-Banner ("VERIFY PROJECT  mode=" + $Mode) Green
Write-Host ("Repo: " + $Root)
Write-Host "Honesty: green != launched public mainnet" -ForegroundColor DarkYellow

try {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        throw "python not found in PATH"
    }

    $checkMode = switch ($Mode) {
        "Quick" { "Quick" }
        "Standard" { "Standard" }
        "Industrial" { "Standard" }
        "Max" { "Max" }
    }

    $checkParams = @{
        Mode    = $checkMode
        BaseUrl = $BaseUrl
    }
    if ($NoAutoStart) {
        $checkParams["NoAutoStart"] = $true
    }

    if ($SkipNativeBuild -and ($Mode -eq "Max")) {
        Write-Host "NOTE: -SkipNativeBuild with Max - native rebuild still runs inside check_all Max" -ForegroundColor DarkYellow
        Write-Host "      Use -Mode Industrial for offline without Max native rebuild." -ForegroundColor DarkYellow
    }

    Invoke-Step ("check_all -Mode " + $checkMode) {
        & (Join-Path $Root "scripts\check_all.ps1") @checkParams
        if ($LASTEXITCODE -ne 0) {
            throw ("check_all rc=" + $LASTEXITCODE)
        }
    }
    $report.steps += ("check_all:" + $checkMode)

    if ($Mode -in @("Industrial", "Max")) {
        Invoke-Step "Secrets scan" {
            & python scripts/check_secrets.py
            if ($LASTEXITCODE -ne 0) {
                throw ("check_secrets rc=" + $LASTEXITCODE)
            }
        }
        $report.steps += "check_secrets"

        Invoke-Step "Prod gate" {
            & python scripts/prod_gate.py
            if ($LASTEXITCODE -ne 0) {
                throw ("prod_gate rc=" + $LASTEXITCODE)
            }
        }
        $report.steps += "prod_gate"

        Invoke-Step "Bridge OFF audit gate" {
            & python scripts/bridge_off_audit_gate.py
            if ($LASTEXITCODE -ne 0) {
                throw ("bridge_off_audit_gate rc=" + $LASTEXITCODE)
            }
        }
        $report.steps += "bridge_off_audit_gate"

        Invoke-Step ("Industrial gate (min soak " + $MinSoakHours + "h)") {
            & python scripts/industrial_gate.py --min-soak-hours $MinSoakHours
            if ($LASTEXITCODE -ne 0) {
                throw ("industrial_gate rc=" + $LASTEXITCODE)
            }
        }
        $report.steps += ("industrial_gate:min_soak=" + $MinSoakHours)

        Invoke-Step "External audit tracker (list)" {
            & python scripts/external_audit_tracker.py --list
            if ($LASTEXITCODE -ne 0) {
                throw ("external_audit_tracker rc=" + $LASTEXITCODE)
            }
        }
        $report.steps += "external_audit_tracker"
    }

    $report.ok = $true
}
catch {
    Write-Host ""
    Write-Host ("FAIL: " + $_.Exception.Message) -ForegroundColor Red
    $report.ok = $false
    $report.error = [string]$_.Exception.Message
}

$ended = Get-Date
$report.ended_utc = $ended.ToUniversalTime().ToString("o")
$report.elapsed_sec = [math]::Round(($ended - $started).TotalSeconds, 1)

$dataDir = Join-Path $Root "data"
if (-not (Test-Path $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir | Out-Null
}
$reportPath = Join-Path $dataDir "verify_project.json"
($report | ConvertTo-Json -Depth 6) | Set-Content -Path $reportPath -Encoding UTF8

$elapsed = [string]$report.elapsed_sec
if ($report.ok) {
    $bannerText = "PASS - mode=" + $Mode + " - " + $elapsed + " sec"
    $bannerColor = [ConsoleColor]::Green
}
else {
    $bannerText = "FAIL - mode=" + $Mode + " - " + $elapsed + " sec"
    $bannerColor = [ConsoleColor]::Red
}
Write-Banner $bannerText $bannerColor

Write-Host ("Steps: " + ($report.steps -join ", "))
Write-Host ("Report: " + $reportPath)
Write-Host "Also:   data\check_all.json"
Write-Host ""
Write-Host "Honesty:" -ForegroundColor DarkYellow
foreach ($h in $report.honesty) {
    Write-Host ("  - " + $h) -ForegroundColor DarkYellow
}
Write-Host ""
if ($report.ok) {
    Write-Host "Next (optional):" -ForegroundColor Gray
    Write-Host "  .\scripts\verify_project.ps1 -Mode Standard"
    Write-Host "  .\scripts\verify_project.ps1 -Mode Industrial"
    Write-Host "  .\scripts\verify_project.ps1 -Mode Max"
    Write-Host "  .\scripts\probe_prod_mesh.ps1 -Quick"
    exit 0
}
exit 1
