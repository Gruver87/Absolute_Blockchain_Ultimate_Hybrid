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

if ($DockerMesh1) {
    Write-Host "Backing up docker prod mesh node1 via exec..." -ForegroundColor Cyan
    $ts = Get-Date -Format "yyyyMMdd-HHmmss"
    $containerDest = "/tmp/chain-backup-$ts"
    docker compose -p $ComposeProject -f docker-compose.prod.3node.yml exec -T node1 `
        python scripts/backup_chainstore.py --data-dir /app/data --dest $containerDest
    if ($LASTEXITCODE -ne 0) { exit 1 }
    $localDest = if ($Dest) { $Dest } else { Join-Path "backups" "prod-mesh1-$ts" }
    New-Item -ItemType Directory -Force -Path $localDest | Out-Null
    $cid = docker compose -p $ComposeProject -f docker-compose.prod.3node.yml ps -q node1
    if (-not $cid) {
        Write-Host "FAIL: node1 container not running" -ForegroundColor Red
        exit 1
    }
    docker cp "${cid}:${containerDest}/." $localDest
    Write-Host "OK: backup copied to $localDest" -ForegroundColor Green
    exit 0
}

$args = @("scripts/backup_chainstore.py", "--data-dir", $DataDir)
if ($Dest) { $args += @("--dest", $Dest) }
python @args
exit $LASTEXITCODE
