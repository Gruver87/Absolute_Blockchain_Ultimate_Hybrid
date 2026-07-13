# Backup and optional DR rehearsal for public testnet Docker seed (chain 77777).
param(
    [switch]$DockerTestnetSeed,
    [string]$BackupDir = "",
    [switch]$Rehearsal,
    [switch]$Live,
    [string]$ComposeProject = "abs-testnet"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

function Test-BackupManifest([string]$Dir) {
    $manifest = Join-Path $Dir "backup_manifest.json"
    $chainstore = Join-Path $Dir "chainstore"
    if (-not (Test-Path $manifest)) {
        Write-Host "FAIL: missing backup_manifest.json in $Dir" -ForegroundColor Red
        exit 1
    }
    if (-not (Test-Path $chainstore)) {
        Write-Host "FAIL: missing chainstore/ in $Dir" -ForegroundColor Red
        exit 1
    }
}

function Get-TestnetSeedContext {
    param([string]$ComposeProject)

    $composeArgs = @("-p", $ComposeProject, "-f", "docker-compose.testnet.yml")
    $cid = docker compose @composeArgs ps -aq testnet-seed 2>$null
    if ($cid) { $cid = ($cid | Select-Object -First 1).Trim() }
    if (-not $cid) {
        Write-Host "FAIL: testnet-seed container not found (run docker_testnet_seed.ps1 first)" -ForegroundColor Red
        exit 1
    }

    $image = (docker inspect -f "{{.Config.Image}}" $cid).Trim()
    $volume = "${ComposeProject}_abs-testnet-seed-data"
    $mountJson = docker inspect -f "{{json .Mounts}}" $cid
    if ($mountJson) {
        foreach ($mount in ($mountJson | ConvertFrom-Json)) {
            if ($mount.Destination -eq "/app/data" -and $mount.Name) {
                $volume = $mount.Name
                break
            }
        }
    }

    return @{ ContainerId = $cid; Image = $image; Volume = $volume; ComposeArgs = $composeArgs }
}

if (-not $DockerTestnetSeed) {
    Write-Host "Use -DockerTestnetSeed to backup testnet seed volume" -ForegroundColor Yellow
    python scripts/backup_chainstore.py --data-dir data @(
        if ($BackupDir) { @("--dest", $BackupDir) } else { @() }
    )
    exit $LASTEXITCODE
}

$ts = Get-Date -Format "yyyyMMdd-HHmmss"
$localDest = if ($BackupDir) { $BackupDir } else { Join-Path "backups" "testnet-seed-$ts" }
$absLocalDest = (New-Item -ItemType Directory -Force -Path $localDest).FullName
$inlineScript = Join-Path $Root "scripts\docker_backup_in_container.py"
$ctx = Get-TestnetSeedContext -ComposeProject $ComposeProject

Write-Host "Backing up testnet seed volume $($ctx.Volume)..." -ForegroundColor Cyan

if ($Live) {
    $running = docker compose @($ctx.ComposeArgs) ps -q testnet-seed --status running
    if (-not $running) {
        Write-Host "FAIL: testnet-seed not running (required for -Live)" -ForegroundColor Red
        exit 1
    }
    $scriptInContainer = "/tmp/abs_backup_inline.py"
    $containerDest = "/tmp/chain-backup-live"
    docker cp $inlineScript "$($ctx.ContainerId):${scriptInContainer}"
    docker compose @($ctx.ComposeArgs) exec -T `
        -e "BACKUP_DEST=$containerDest" `
        -e "DATA_DIR=/app/data" `
        -e "READ_ONLY=1" `
        testnet-seed python $scriptInContainer
    if ($LASTEXITCODE -ne 0) { exit 1 }
    docker cp "$($ctx.ContainerId):${containerDest}/." $absLocalDest
    Test-BackupManifest -Dir $absLocalDest
    docker compose @($ctx.ComposeArgs) exec -T testnet-seed rm -rf $containerDest $scriptInContainer 2>$null | Out-Null
} else {
    $wasRunning = [bool](docker compose @($ctx.ComposeArgs) ps -q testnet-seed --status running)
    if ($wasRunning) {
        Write-Host "Stopping testnet-seed briefly for consistent checkpoint..." -ForegroundColor Yellow
        docker compose @($ctx.ComposeArgs) stop testnet-seed | Out-Null
    }
    try {
        docker run --rm -w /app --entrypoint python `
            -v "$($ctx.Volume):/app/data" `
            -v "${absLocalDest}:/backup" `
            -v "${inlineScript}:/tmp/abs_backup_inline.py:ro" `
            -e "BACKUP_DEST=/backup" `
            -e "DATA_DIR=/app/data" `
            -e "READ_ONLY=1" `
            $ctx.Image `
            /tmp/abs_backup_inline.py
        if ($LASTEXITCODE -ne 0) { exit 1 }
        Test-BackupManifest -Dir $absLocalDest
    } finally {
        if ($wasRunning) {
            docker compose @($ctx.ComposeArgs) start testnet-seed | Out-Null
        }
    }
}

Write-Host "OK: testnet backup at $absLocalDest" -ForegroundColor Green

if ($Rehearsal) {
    $rehearsalRoot = Join-Path $env:TEMP "abs-testnet-dr-$ts"
    $restoreTarget = Join-Path $rehearsalRoot "restored"
    New-Item -ItemType Directory -Force -Path $restoreTarget | Out-Null
    Write-Host "DR rehearsal: restore to $restoreTarget ..." -ForegroundColor Cyan
    python scripts/restore_chainstore.py --backup-dir $absLocalDest --data-dir $restoreTarget --force --verify
    if ($LASTEXITCODE -ne 0) { exit 1 }
    Remove-Item -Recurse -Force $rehearsalRoot -ErrorAction SilentlyContinue
    Write-Host "OK: testnet DR rehearsal passed" -ForegroundColor Green
}

exit 0
