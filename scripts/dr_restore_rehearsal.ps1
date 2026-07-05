# DR restore rehearsal — verify backup without touching live data.
param(
    [string]$DataDir = "data",
    [string]$BackupDir = "",
    [switch]$DockerMesh1,
    [string]$ComposeProject = "abs-prod-mesh3"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$rehearsalRoot = Join-Path $env:TEMP "abs-dr-rehearsal-$ts"
New-Item -ItemType Directory -Force -Path $rehearsalRoot | Out-Null

try {
    if ($DockerMesh1) {
        Write-Host "Step 1: backup prod mesh node1..." -ForegroundColor Cyan
        $backupDest = Join-Path "backups" "dr-rehearsal-$ts"
        & "$Root\scripts\backup_chainstore.ps1" -DockerMesh1 -Dest $backupDest
        if ($LASTEXITCODE -ne 0) { exit 1 }
        $BackupDir = $backupDest
    } elseif (-not $BackupDir) {
        Write-Host "Step 1: backup local data dir $DataDir..." -ForegroundColor Cyan
        $BackupDir = Join-Path $rehearsalRoot "snapshot"
        python scripts/backup_chainstore.py --data-dir $DataDir --dest $BackupDir
        if ($LASTEXITCODE -ne 0) { exit 1 }
    }

    $restoreTarget = Join-Path $rehearsalRoot "restored"
    Write-Host "Step 2: restore to temp $restoreTarget (live data untouched)..." -ForegroundColor Cyan
    python scripts/restore_chainstore.py --backup-dir $BackupDir --data-dir $restoreTarget --force --verify
    if ($LASTEXITCODE -ne 0) { exit 1 }

    Write-Host "OK: DR rehearsal passed — backup=$BackupDir restored=$restoreTarget" -ForegroundColor Green
    exit 0
}
finally {
    if (Test-Path $rehearsalRoot) {
        Remove-Item -Recurse -Force $rehearsalRoot -ErrorAction SilentlyContinue
    }
}
