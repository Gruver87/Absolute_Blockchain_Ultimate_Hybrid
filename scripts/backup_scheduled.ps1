#!/usr/bin/env pwsh
# Плановый бэкап SQLite (Task Scheduler / cron)
# Пример: каждый день в 03:00
#   schtasks /Create /SC DAILY /ST 03:00 /TN "ABS-Backup" /TR "pwsh -File C:\...\scripts\backup_scheduled.ps1"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

$DataDir = if ($env:DATA_DIR) { $env:DATA_DIR } else { "data" }
$env:DATA_DIR = $DataDir

python scripts/backup_db.py --db (Join-Path $DataDir "blockchain.db")
if ($LASTEXITCODE -ne 0) { exit 1 }

# Удалить бэкапы старше 14 дней
$BackupDir = Join-Path $DataDir "backups"
if (Test-Path $BackupDir) {
    Get-ChildItem $BackupDir -Filter "blockchain_*.db" |
        Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-14) } |
        Remove-Item -Force -ErrorAction SilentlyContinue
}
Write-Host "Backup OK: $BackupDir"
