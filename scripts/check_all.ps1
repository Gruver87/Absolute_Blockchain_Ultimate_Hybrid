# Absolute Blockchain Ultimate Hybrid - unified self-check
#
#   .\scripts\check_all.ps1                 # Quick (~20-40s)
#   .\scripts\check_all.ps1 -Mode Standard  # full offline gate
#   .\scripts\check_all.ps1 -Mode Full      # Standard + rebuild abs_native
#   .\scripts\check_all.ps1 -Mode Live      # offline Quick + live HTTP (auto-starts node)
#   .\scripts\check_all.ps1 -Mode Max       # Full + Live + isolated P2P CI
#   .\scripts\check_all.ps1 -Mode Max -NoAutoStart   # require already-running node
#   .\scripts\check_all.ps1 -Help
#
# Report: data\check_all.json
# Honesty: PASS is not public mainnet. Ceremony pin + external audit remain blockers.

param(
    [ValidateSet("Quick", "Standard", "Full", "Live", "Max")]
    [string]$Mode = "Quick",
    [string]$BaseUrl = "http://127.0.0.1:8080",
    [int]$PytestTimeout = 900,
    [int]$P2PWait = 300,
    [int]$LiveBootTimeoutSec = 90,
    [switch]$NoAutoStart,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

if ($Help) {
    Write-Host ""
    Write-Host "check_all.ps1 - unified Absolute Blockchain self-check"
    Write-Host ""
    Write-Host "  Quick     industrial waves + industrial_gate (daily)"
    Write-Host "  Standard  full offline: prod_gate, full_audit, critical pytest"
    Write-Host "  Full      Standard + rebuild abs_native"
    Write-Host "  Live      Quick + HTTP live checks (auto-starts python main.py if needed)"
    Write-Host "  Max       Full + Live + isolated P2P CI spawn"
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\scripts\check_all.ps1"
    Write-Host "  .\scripts\check_all.ps1 -Mode Standard"
    Write-Host "  .\scripts\check_all.ps1 -Mode Live"
    Write-Host "  .\scripts\check_all.ps1 -Mode Max"
    Write-Host "  .\scripts\check_all.ps1 -Mode Max -NoAutoStart"
    Write-Host ""
    Write-Host "Live/Max auto-start a local node on :8080 when /health/live is down."
    Write-Host "Use -NoAutoStart if you already run the node yourself."
    Write-Host ""
    exit 0
}

function Write-Banner {
    param([string]$Text, [ConsoleColor]$Color = [ConsoleColor]::Cyan)
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
        throw ("STEP FAIL: {0} (exit {1})" -f $Name, $rc)
    }
    Write-Host ("OK: " + $Name) -ForegroundColor Green
}

function Test-LiveReachable {
    param([string]$Url)
    try {
        $null = Invoke-RestMethod -Uri ($Url.TrimEnd("/") + "/health/live") -TimeoutSec 5 -UseBasicParsing
        return $true
    }
    catch {
        return $false
    }
}

function Start-CheckAllNode {
    param(
        [string]$Url,
        [int]$TimeoutSec
    )
    $logDir = Join-Path $ProjectRoot "data"
    if (-not (Test-Path $logDir)) {
        New-Item -ItemType Directory -Path $logDir | Out-Null
    }
    $outLog = Join-Path $logDir "check_all_node.out.log"
    $errLog = Join-Path $logDir "check_all_node.err.log"
    Write-Host ("Auto-starting node for live checks (logs: {0})" -f $outLog) -ForegroundColor Cyan
    $proc = Start-Process -FilePath "python" -ArgumentList @("main.py") `
        -WorkingDirectory $ProjectRoot `
        -RedirectStandardOutput $outLog `
        -RedirectStandardError $errLog `
        -PassThru -WindowStyle Hidden
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if ($proc.HasExited) {
            throw ("Auto-started node exited early (pid={0}). See {1}" -f $proc.Id, $errLog)
        }
        if (Test-LiveReachable $Url) {
            Write-Host ("Node ready (pid={0})" -f $proc.Id) -ForegroundColor Green
            return $proc
        }
        Start-Sleep -Seconds 2
    }
    try { Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue } catch {}
    throw ("Timed out waiting for {0}/health/live ({1}s). See {2}" -f $Url, $TimeoutSec, $errLog)
}

function Stop-CheckAllNode {
    param($Proc)
    if ($null -eq $Proc) { return }
    try {
        if (-not $Proc.HasExited) {
            Write-Host ("Stopping auto-started node (pid={0})" -f $Proc.Id) -ForegroundColor DarkGray
            Stop-Process -Id $Proc.Id -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
        }
    }
    catch {}
}

$started = Get-Date
$autoNode = $null
$report = [ordered]@{
    script       = "check_all.ps1"
    mode         = $Mode
    base_url     = $BaseUrl
    started_utc  = $started.ToUniversalTime().ToString("o")
    node_version = $null
    auto_started = $false
    steps        = @()
    ok           = $false
    honesty      = @(
        "PASS is not public mainnet",
        "ceremony pin + external audit remain org blockers",
        "live mesh bridge must stay OFF without audited L1",
        "full Rust P2P transport is not claimed"
    )
}

Write-Banner ("CHECK ALL - mode={0}  base={1}" -f $Mode, $BaseUrl) Green
Write-Host ("Repo: " + $ProjectRoot)
Write-Host "Modes: Quick | Standard | Full | Live | Max   ( -Help for details )"
Write-Host "Honesty: green gate != launched public mainnet" -ForegroundColor DarkYellow

try {
    if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
        throw "python not found in PATH"
    }

    Write-Host ""
    Write-Host ">>> Node version" -ForegroundColor Yellow
    $pyCode = "from runtime.config import Config; print(Config().node_version)"
    $verOut = & python -c $pyCode
    if ($LASTEXITCODE -ne 0) { throw "STEP FAIL: Node version" }
    $report.node_version = ("{0}" -f $verOut).Trim()
    Write-Host ("node_version={0}" -f $report.node_version)
    Write-Host "OK: Node version" -ForegroundColor Green
    $report.steps += "node_version"

    $needQuick = $Mode -in @("Quick", "Live")
    $needFullGate = $Mode -in @("Standard", "Full", "Max")
    $needNative = $Mode -in @("Full", "Max")
    $needLive = $Mode -in @("Live", "Max")
    $needP2P = $Mode -eq "Max"

    if ($needQuick) {
        Invoke-Step "Industrial waves verify (code + unit waves + industrial_gate)" {
            $env:PYTHONPATH = "."
            & python scripts/verify_industrial_waves.py
            if ($LASTEXITCODE -ne 0) {
                throw ("verify_industrial_waves rc={0}" -f $LASTEXITCODE)
            }
        }
        $report.steps += "verify_industrial_waves"
    }

    # v1.3.138: honest ceremony readiness (informational — never invents a pin)
    Invoke-Step "Ceremony status (informational, no fake pin)" {
        $env:PYTHONPATH = "."
        & python scripts/ceremony_status.py --json data/ceremony_status.json
        if ($LASTEXITCODE -ne 0) {
            throw ("ceremony_status rc={0}" -f $LASTEXITCODE)
        }
    }
    $report.steps += "ceremony_status"

    if ($needFullGate) {
        # Hashtable splat (named params). Array splat binds POSITIONALLY and
        # would map "-EvidenceGitTag" onto [int]$P2PWait.
        $fullParams = @{
            PytestTimeout  = [int]$PytestTimeout
            P2PWait        = [int]$P2PWait
            EvidenceGitTag = "v1.3.185"
        }
        if (-not $needNative) {
            $fullParams["SkipNativeBuild"] = $true
        }

        Invoke-Step "Full blockchain gate (test_blockchain_full.ps1)" {
            & (Join-Path $ProjectRoot "scripts\test_blockchain_full.ps1") @fullParams
            if ($LASTEXITCODE -ne 0) {
                throw ("test_blockchain_full rc={0}" -f $LASTEXITCODE)
            }
        }
        $report.steps += "test_blockchain_full"
    }

    if ($needLive) {
        if (-not (Test-LiveReachable $BaseUrl)) {
            if ($NoAutoStart) {
                throw ("Live node not reachable at {0}/health/live - start: python main.py (or omit -NoAutoStart)" -f $BaseUrl)
            }
            $autoNode = Start-CheckAllNode -Url $BaseUrl -TimeoutSec $LiveBootTimeoutSec
            $report.auto_started = $true
            $report.steps += "auto_start_node"
        }

        Invoke-Step "Live health/status" {
            $st = Invoke-RestMethod -Uri ($BaseUrl.TrimEnd("/") + "/status") -TimeoutSec 8
            Write-Host ("version={0} height={1} mode={2}" -f $st.node_version, $st.height, $st.deployment_mode)
            $null = Invoke-RestMethod -Uri ($BaseUrl.TrimEnd("/") + "/health/live") -TimeoutSec 8
            $null = Invoke-RestMethod -Uri ($BaseUrl.TrimEnd("/") + "/health/ready") -TimeoutSec 8
        }
        $report.steps += "live_health"

        $stMode = ""
        try {
            $stMode = [string](Invoke-RestMethod -Uri ($BaseUrl.TrimEnd("/") + "/status") -TimeoutSec 8).deployment_mode
        }
        catch {}
        if ($report.auto_started) {
            Write-Host "NOTE: auto-started single node - skipping prod_smoke (needs peered prod mesh)" -ForegroundColor DarkYellow
            $report.steps += "prod_smoke_skipped_autostart"
        }
        elseif ($stMode -eq "prod") {
            Invoke-Step "Prod smoke (HTTP)" {
                & python scripts/prod_smoke.py $BaseUrl
                if ($LASTEXITCODE -ne 0) {
                    throw ("prod_smoke rc={0}" -f $LASTEXITCODE)
                }
            }
            $report.steps += "prod_smoke"
        }
        else {
            Write-Host ("NOTE: deployment_mode={0} - skipping prod_smoke (needs prod profile)" -f $stMode) -ForegroundColor DarkYellow
            $report.steps += "prod_smoke_skipped_non_prod"
        }
    }

    if ($needP2P) {
        # Isolated CI spawn - does not require your :8080/:8081 mesh.
        Invoke-Step "P2P CI verify (isolated spawn)" {
            & python scripts/verify_p2p_ci.py --mode ci --wait $P2PWait
            if ($LASTEXITCODE -ne 0) {
                throw ("verify_p2p_ci rc={0}" -f $LASTEXITCODE)
            }
        }
        $report.steps += "verify_p2p_ci"
    }

    $report.ok = $true
}
catch {
    Write-Host ""
    Write-Host ("FAIL: {0}" -f $_.Exception.Message) -ForegroundColor Red
    $report.ok = $false
    $report.error = ("{0}" -f $_.Exception.Message)
}
finally {
    Stop-CheckAllNode -Proc $autoNode
}

$ended = Get-Date
$report.ended_utc = $ended.ToUniversalTime().ToString("o")
$report.elapsed_sec = [math]::Round(($ended - $started).TotalSeconds, 1)

$dataDir = Join-Path $ProjectRoot "data"
if (-not (Test-Path $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir | Out-Null
}
$reportPath = Join-Path $dataDir "check_all.json"
($report | ConvertTo-Json -Depth 6) | Set-Content -Path $reportPath -Encoding UTF8

$bannerText = if ($report.ok) {
    ("PASS - mode={0} ({1}s)" -f $Mode, $report.elapsed_sec)
} else {
    ("FAIL - mode={0} ({1}s)" -f $Mode, $report.elapsed_sec)
}
$bannerColor = if ($report.ok) { [ConsoleColor]::Green } else { [ConsoleColor]::Red }
Write-Banner $bannerText $bannerColor

Write-Host ("Steps: {0}" -f ($report.steps -join ", "))
Write-Host ("Report: {0}" -f $reportPath)
Write-Host ""
Write-Host "Chestno / Honesty:" -ForegroundColor DarkYellow
foreach ($h in $report.honesty) {
    Write-Host ("  - {0}" -f $h) -ForegroundColor DarkYellow
}
Write-Host ""
if ($report.ok) {
    Write-Host "Next (optional):" -ForegroundColor Gray
    Write-Host "  .\scripts\check_all.ps1 -Mode Standard"
    Write-Host "  .\scripts\check_all.ps1 -Mode Live"
    Write-Host "  .\scripts\check_all.ps1 -Mode Max"
    exit 0
}
exit 1
