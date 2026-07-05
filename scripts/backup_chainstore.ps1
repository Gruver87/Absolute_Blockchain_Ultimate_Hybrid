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

function Get-MeshNode1Context {
    param([string]$ComposeFile)

    $cid = docker compose -p $ComposeProject -f $ComposeFile ps -aq node1 2>$null
    if ($cid) {
        $cid = ($cid | Select-Object -First 1).Trim()
    }
    if (-not $cid) {
        Write-Host "FAIL: node1 container not found (start prod mesh first)" -ForegroundColor Red
        exit 1
    }

    $image = (docker inspect -f "{{.Config.Image}}" $cid).Trim()
    if (-not $image) {
        $image = (docker inspect -f "{{.Image}}" $cid).Trim()
    }
    if (-not $image) {
        Write-Host "FAIL: cannot resolve node1 image" -ForegroundColor Red
        exit 1
    }

    $volume = ""
    $mountJson = docker inspect -f "{{json .Mounts}}" $cid
    if ($mountJson) {
        $mounts = $mountJson | ConvertFrom-Json
        foreach ($mount in $mounts) {
            if ($mount.Destination -eq "/app/data" -and $mount.Name) {
                $volume = $mount.Name
                break
            }
        }
    }
    if (-not $volume) {
        $volume = "${ComposeProject}_abs-prod-mesh1-data"
    }

    return @{
        ContainerId = $cid
        Image       = $image
        Volume      = $volume
    }
}

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

    $ctx = Get-MeshNode1Context -ComposeFile $composeFile
    $absLocalDest = (New-Item -ItemType Directory -Force -Path $LocalDest).FullName
    $scriptBody = Get-Content -Raw -Path $inlineScript

    if ($TryLive) {
        $runningId = docker compose -p $ComposeProject -f $composeFile ps -q node1 --status running
        if (-not $runningId) {
            Write-Host "FAIL: node1 not running (required for -Live)" -ForegroundColor Red
            exit 1
        }
        Write-Host "Live backup (read-only RocksDB open)..." -ForegroundColor Cyan
        $containerDest = "/tmp/chain-backup-live"
        $scriptBody | docker compose -p $ComposeProject -f $composeFile exec -T `
            --entrypoint python `
            -e "BACKUP_DEST=$containerDest" `
            -e "DATA_DIR=/app/data" `
            -e "READ_ONLY=1" `
            node1 -
        if ($LASTEXITCODE -eq 0) {
            docker cp "$($ctx.ContainerId):${containerDest}/." $absLocalDest
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
        Write-Host ("One-off checkpoint via existing image " + $ctx.Image + " (no rebuild)...") -ForegroundColor Cyan
        $scriptBody | docker run --rm `
            --entrypoint python `
            -v "$($ctx.Volume):/app/data:ro" `
            -v "${absLocalDest}:/backup" `
            -e "BACKUP_DEST=/backup" `
            -e "DATA_DIR=/app/data" `
            $ctx.Image `
            -
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
    Invoke-DockerMesh1Backup -LocalDest $localDest -TryLive:([bool]$Live)
    Write-Host "OK: backup copied to $localDest" -ForegroundColor Green
    exit 0
}

if (-not $DataDir) {
    $DataDir = "data"
}

$pyArgs = @("scripts/backup_chainstore.py", "--data-dir", $DataDir)
if ($Dest) { $pyArgs += @("--dest", $Dest) }
python @pyArgs
exit $LASTEXITCODE
