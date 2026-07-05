# Backup prod mesh or local RocksDB/SQLite chain data.
param(
    [string]$DataDir = "data",
    [string]$Dest = "",
    [switch]$DockerMesh1,
    [string]$ComposeProject = "abs-prod-mesh3"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Invoke-DockerMesh1Backup {
    param(
        [string]$LocalDest
    )

    $composeFile = "docker-compose.prod.3node.yml"
    $ts = Get-Date -Format "yyyyMMdd-HHmmss"
    $containerDest = "/tmp/chain-backup-$ts"
    $inlineScript = Join-Path $Root "scripts\docker_backup_in_container.py"

    if (-not (Test-Path $inlineScript)) {
        Write-Host "FAIL: missing $inlineScript" -ForegroundColor Red
        exit 1
    }

    $cid = docker compose -p $ComposeProject -f $composeFile ps -q node1
    if (-not $cid) {
        Write-Host "FAIL: node1 container not running" -ForegroundColor Red
        exit 1
    }

    Write-Host "Checkpoint backup via stdin pipe (works without image rebuild)..." -ForegroundColor Cyan
    $scriptBody = Get-Content -Raw -Path $inlineScript
    $scriptBody | docker compose -p $ComposeProject -f $composeFile exec -T `
        -e "BACKUP_DEST=$containerDest" `
        -e "DATA_DIR=/app/data" `
        node1 python -
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL: in-container backup" -ForegroundColor Red
        exit 1
    }

    New-Item -ItemType Directory -Force -Path $LocalDest | Out-Null
    docker cp "${cid}:${containerDest}/." $LocalDest
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL: docker cp from node1" -ForegroundColor Red
        exit 1
    }

    docker compose -p $ComposeProject -f $composeFile exec -T node1 `
        rm -rf $containerDest 2>$null | Out-Null
}

if ($DockerMesh1) {
    Write-Host "Backing up docker prod mesh node1..." -ForegroundColor Cyan
    $ts = Get-Date -Format "yyyyMMdd-HHmmss"
    $localDest = if ($Dest) { $Dest } else { Join-Path "backups" "prod-mesh1-$ts" }
    Invoke-DockerMesh1Backup -LocalDest $localDest
    Write-Host "OK: backup copied to $localDest" -ForegroundColor Green
    exit 0
}

$pyArgs = @("scripts/backup_chainstore.py", "--data-dir", $DataDir)
if ($Dest) { $pyArgs += @("--dest", $Dest) }
python @pyArgs
exit $LASTEXITCODE
