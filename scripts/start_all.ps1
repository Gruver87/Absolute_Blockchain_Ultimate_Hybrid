# Absolute Blockchain Ultimate - one-shot launcher (Windows PowerShell)
#
# Starts the stack and opens Explorer windows automatically.
#
# Usage:
#   .\scripts\start_all.ps1
#   .\scripts\start_all.ps1 -Mode Mesh -SkipBuild -KeepVolumes
#   .\scripts\start_all.ps1 -Mode Solo
#   .\scripts\start_all.ps1 -Mode OpenOnly
#   .\scripts\start_all.ps1 -NoBrowser
#   .\scripts\start_all.ps1 -OpenLogs
#
# Modes:
#   Mesh     - Docker prod 3-node mesh (:18180-:18182, chain 778888). DEFAULT.
#   Solo     - local python main.py (:8080 / :8545) in a new console window.
#   OpenOnly - only open browser tabs (assumes mesh or solo already running).
#
# Honesty: local / prod-profile mesh R&D - not a public mainnet.

param(
    [ValidateSet("Mesh", "Solo", "OpenOnly")]
    [string]$Mode = "Mesh",

    [switch]$SkipBuild,
    [switch]$KeepVolumes,
    [switch]$NoP2pTls,
    [switch]$NoBrowser,
    [switch]$OpenLogs,
    [switch]$NoProbe,
    [int]$WaitSec = 180,
    [string]$CeremonyDir = "data/ceremony_keys"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

function Write-Banner {
    param([string]$Title)
    Write-Host ""
    Write-Host ("=" * 64) -ForegroundColor Cyan
    Write-Host "  $Title" -ForegroundColor Cyan
    Write-Host ("=" * 64) -ForegroundColor Cyan
}

function Test-UrlReady {
    param([string]$Url, [int]$TimeoutSec = 4)
    try {
        $r = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
        return ($r.StatusCode -ge 200 -and $r.StatusCode -lt 500)
    } catch {
        return $false
    }
}

function Wait-Url {
    param(
        [string]$Url,
        [int]$Seconds = 180,
        [string]$Label = $Url
    )
    $deadline = (Get-Date).AddSeconds($Seconds)
    Write-Host "Waiting for $Label ..." -ForegroundColor DarkGray
    while ((Get-Date) -lt $deadline) {
        if (Test-UrlReady -Url $Url) {
            Write-Host "  OK $Label" -ForegroundColor Green
            return $true
        }
        Start-Sleep -Seconds 3
    }
    Write-Host "  TIMEOUT $Label" -ForegroundColor Red
    return $false
}

function Open-Browsers {
    param([string[]]$Urls)
    if ($NoBrowser) {
        Write-Host "Browsers skipped (-NoBrowser)" -ForegroundColor DarkGray
        return
    }
    foreach ($u in $Urls) {
        Write-Host "Open  $u" -ForegroundColor Gray
        Start-Process -FilePath $u
        Start-Sleep -Milliseconds 400
    }
}

function Open-MeshLogWindows {
    if (-not $OpenLogs) { return }
    $composeCmd = "docker compose -p abs-prod-mesh3 -f docker-compose.prod.3node.yml"
    foreach ($node in @("node1", "node2", "node3")) {
        $cmd = "Set-Location '$Root'; $composeCmd logs -f $node"
        Start-Process -FilePath "powershell.exe" -ArgumentList @("-NoExit", "-Command", $cmd) -WorkingDirectory $Root
    }
    Write-Host "Opened 3 Docker log consoles (-OpenLogs)" -ForegroundColor DarkGray
}

# --- OpenOnly -----------------------------------------------------------------
if ($Mode -eq "OpenOnly") {
    Write-Banner "Open explorers only"
    $mesh = @(
        "http://127.0.0.1:18180",
        "http://127.0.0.1:18181",
        "http://127.0.0.1:18182"
    )
    $solo = @("http://127.0.0.1:8080")
    $open = @()
    foreach ($u in $mesh) {
        if (Test-UrlReady -Url "$u/health/ready") { $open += $u }
    }
    if ($open.Count -eq 0 -and (Test-UrlReady -Url "http://127.0.0.1:8080/health/ready")) {
        $open = $solo
    }
    if ($open.Count -eq 0) {
        Write-Host "Nothing is up on :18180-:18182 or :8080. Start with -Mode Mesh or -Mode Solo first." -ForegroundColor Yellow
        exit 1
    }
    Open-Browsers -Urls $open
    exit 0
}

# --- Solo ---------------------------------------------------------------------
if ($Mode -eq "Solo") {
    Write-Banner "Solo node (python main.py)"
    if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
        Copy-Item ".env.example" ".env"
        Write-Host "Created .env from .env.example" -ForegroundColor Yellow
    }
    if (-not (Test-Path "data")) {
        New-Item -ItemType Directory -Path "data" | Out-Null
    }

    $busy = $false
    foreach ($p in @(8080, 8545)) {
        if (Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue) {
            $busy = $true
            break
        }
    }
    if ($busy -and (Test-Path (Join-Path $ScriptDir "stop_node.ps1"))) {
        Write-Host "Ports busy - stopping previous solo node..." -ForegroundColor Yellow
        & (Join-Path $ScriptDir "stop_node.ps1")
        Start-Sleep -Seconds 2
    }

    $py = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $py) { throw "python not found on PATH" }

    Write-Host "Starting solo node in a new window..." -ForegroundColor Cyan
    # If .env has DEPLOYMENT_MODE=prod, tip-safety enforce is mandatory.
    # Export into the child process so a stale .env without the flag still boots.
    $soloEnvPrefix = ""
    $depMode = $null
    if (Test-Path ".env") {
        Get-Content ".env" | ForEach-Object {
            if ($_ -match '^\s*DEPLOYMENT_MODE\s*=\s*(.+)\s*$') {
                $depMode = $Matches[1].Trim().Trim('"').Trim("'").ToLower()
            }
        }
    }
    if ($depMode -eq "prod") {
        $soloEnvPrefix = "`$env:TIP_SAFETY_ENFORCE='true'; "
        Write-Host "Solo + DEPLOYMENT_MODE=prod: ensuring TIP_SAFETY_ENFORCE=true" -ForegroundColor DarkGray
    }
    $soloCmd = "Set-Location '$Root'; $soloEnvPrefix" +
        "Write-Host 'Absolute Blockchain - solo' -ForegroundColor Cyan; python main.py"
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList @("-NoExit", "-Command", $soloCmd) `
        -WorkingDirectory $Root

    if (-not (Wait-Url -Url "http://127.0.0.1:8080/health/ready" -Seconds $WaitSec -Label "solo :8080")) {
        Write-Host "Solo node did not become ready. Check the console window." -ForegroundColor Red
        exit 1
    }

    Open-Browsers -Urls @(
        "http://127.0.0.1:8080",
        "http://127.0.0.1:8080/health/ready"
    )
    Write-Host ""
    Write-Host "OK: solo running" -ForegroundColor Green
    Write-Host "  Explorer  http://127.0.0.1:8080" -ForegroundColor Gray
    Write-Host "  RPC       http://127.0.0.1:8545" -ForegroundColor Gray
    Write-Host "  Stop:     .\scripts\stop_node.ps1" -ForegroundColor Gray
    exit 0
}

# --- Mesh (default) -----------------------------------------------------------
Write-Banner "Prod 3-node mesh (Docker :18180-:18182)"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker not found. Install Docker Desktop, or use: .\scripts\start_all.ps1 -Mode Solo" -ForegroundColor Red
    exit 1
}

$oldEap = $ErrorActionPreference
$ErrorActionPreference = "Continue"
docker info 2>$null | Out-Null
$dockerInfoExit = $LASTEXITCODE
$ErrorActionPreference = $oldEap
if ($dockerInfoExit -ne 0) {
    Write-Host "Docker daemon not running. Start Docker Desktop, then retry." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path ".env") -and (Test-Path ".env.example")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example - fill JWT/RPC secrets if prod_gate fails." -ForegroundColor Yellow
}

# Hashtable splat = named params. Array splat is positional and breaks -CeremonyDir.
$meshArgs = @{ CeremonyDir = $CeremonyDir }
if ($SkipBuild) { $meshArgs["SkipBuild"] = $true }
if ($KeepVolumes) { $meshArgs["KeepVolumes"] = $true }
if ($NoP2pTls) { $meshArgs["NoP2pTls"] = $true }

$meshArgSummary = ($meshArgs.GetEnumerator() | ForEach-Object {
    if ($_.Value -is [bool] -and $_.Value) { "-$($_.Key)" }
    else { "-$($_.Key) $($_.Value)" }
}) -join " "
Write-Host "Launching docker_prod_3node.ps1 $meshArgSummary" -ForegroundColor Cyan
& (Join-Path $ScriptDir "docker_prod_3node.ps1") @meshArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "Mesh start FAILED (exit $LASTEXITCODE)." -ForegroundColor Red
    Write-Host "Tips:" -ForegroundColor Yellow
    Write-Host "  .\scripts\setup_prod_env.ps1" -ForegroundColor Gray
    Write-Host "  .\scripts\start_all.ps1 -SkipBuild -KeepVolumes" -ForegroundColor Gray
    Write-Host "  .\scripts\start_all.ps1 -Mode Solo" -ForegroundColor Gray
    exit $LASTEXITCODE
}

$meshUrls = @(
    "http://127.0.0.1:18180",
    "http://127.0.0.1:18181",
    "http://127.0.0.1:18182"
)
foreach ($u in $meshUrls) {
    if (-not (Wait-Url -Url "$u/health/ready" -Seconds 60 -Label $u)) {
        exit 1
    }
}

if (-not $NoProbe) {
    Write-Host "Quick probe..." -ForegroundColor Cyan
    & (Join-Path $ScriptDir "probe_prod_mesh.ps1") -Quick
}

Open-Browsers -Urls $meshUrls
Open-MeshLogWindows

Write-Host ""
Write-Host "OK: full mesh is up" -ForegroundColor Green
Write-Host "  mesh-1  http://127.0.0.1:18180" -ForegroundColor Gray
Write-Host "  mesh-2  http://127.0.0.1:18181" -ForegroundColor Gray
Write-Host "  mesh-3  http://127.0.0.1:18182" -ForegroundColor Gray
Write-Host "  Stop:   docker compose -p abs-prod-mesh3 -f docker-compose.prod.3node.yml down" -ForegroundColor Gray
Write-Host "  Reopen: .\scripts\start_all.ps1 -Mode OpenOnly" -ForegroundColor Gray
exit 0
