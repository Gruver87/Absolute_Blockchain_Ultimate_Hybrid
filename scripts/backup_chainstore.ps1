# Backup prod mesh or local RocksDB/SQLite chain data.
param(
    [string]$DataDir = "data",
    [string]$Dest = "",
    [switch]$DockerMesh1,
    [switch]$Live,
    [string]$ComposeProject = "abs-prod-mesh3"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Invoke-DockerMesh1Backup {
    param(
        [string]$LocalDest,
        [bool]$TryLive
    )

    $composeFile = "docker-compose.prod.3node.yml"
    $inlineScript = Join-Path $Root "scripts\docker_backup_in_container.py"

    if (-not (Test-Path $inlineScript)) {
        Write-Host "FAIL: missing $inlineScript" -ForegroundColor Red
        exit 1
    }

    $absLocalDest = (New-Item -ItemType Directory -Force -Path $LocalDest).FullName
    $scriptBody = Get-Content -Raw -Path $inlineScript

    if ($TryLive) {
        $cid = docker compose -p $ComposeProject -f $composeFile ps -q node1
        if (-not $cid) {
            Write-Host "FAIL: node1 container not running" -ForegroundColor Red
            exit 1
        }
        Write-Host "Live backup (read-only RocksDB open)..." -ForegroundColor Cyan
        $containerDest = "/tmp/chain-backup-live"
        $scriptBody | docker compose -p $ComposeProject -f $composeFile exec -T `
            -e "BACKUP_DEST=$containerDest" `
            -e "DATA_DIR=/app/data" `
            -e "READ_ONLY=1" `
            node1 python -
        if ($LASTEXITCODE -eq 0) {
            docker cp "${cid}:${containerDest}/." $absLocalDest
            docker compose -p $ComposeProject -f $composeFile exec -T node1 `
                rm -rf $containerDest 2>$null | Out-Null
            return
        }
        Write-Host "Live backup failed; falling back to brief node1 stop..." -ForegroundColor Yellow
    }

    $runningId = docker compose -p $ComposeProject -f $composeFile ps -q node1 --status running
    $wasRunning = [bool]$runningId
    if ($wasRunning) {
        Write-Host "Stopping node1 briefly for consistent RocksDB checkpoint..." -ForegroundColor Yellow
        docker compose -p $ComposeProject -f $composeFile stop node1 | Out-Null
    }

    try {
        Write-Host "One-off checkpoint backup (stdin pipe)..." -ForegroundColor Cyan
        $scriptBody | docker compose -p $ComposeProject -f $composeFile run --rm --no-deps `
            -v "${absLocalDest}:/backup" `
            -e "BACKUP_DEST=/backup" `
            -e "DATA_DIR=/app/data" `
            node1 python -
        if ($LASTEXITCODE -ne 0) {
            Write-Host "FAIL: in-container backup" -ForegroundColor Red
            exit 1
        }
    }
    finally {
        if ($wasRunning) {
            Write-Host "Starting node1..." -ForegroundColor Cyan
            docker compose -p $ComposeProject -f $composeFile start node1 | Out-Null
        }
    }
}

if ($DockerMesh1) {
    Write-Host "Backing up docker prod mesh node1..." -ForegroundColor Cyan
    $ts = Get-Date -Format "yyyyMMdd-HHmmss"
    $localDest = if ($Dest) { $Dest } else { Join-Path "backups" "prod-mesh1-$ts" }
    Invoke-DockerMesh1Backup -LocalDest $localDest -TryLive:$Live
    Write-Host "OK: backup copied to $localDest" -ForegroundColor Green
    exit 0
}

$pyArgs = @("scripts/backup_chainstore.py", "--data-dir", $DataDir)
if ($Dest) { $pyArgs += @("--dest", $Dest) }
python @pyArgs
exit $LASTEXITCODE
