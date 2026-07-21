# Absolute Blockchain - disk / Docker cleanup (Windows)
#
# Safe defaults: unused Docker data, Cargo debug builds, pip/maturin caches,
# Python __pycache__, local temp logs. Does NOT delete source, .git, wallets,
# or data/*.db unless you pass -Aggressive.
#
# Usage:
#   .\scripts\cleanup_disk.ps1
#   .\scripts\cleanup_disk.ps1 -WhatIf
#   .\scripts\cleanup_disk.ps1 -Aggressive
#   .\scripts\cleanup_disk.ps1 -StopDockerDesktop
#   .\scripts\cleanup_disk.ps1 -StopDockerDesktop -CompactDockerVhdx   # needs Admin UAC; reclaim host GB after prune
#
# Tip: keep Rust builds off C: when disk is tight:
#   $env:CARGO_TARGET_DIR = "D:\cargo-target\abs_native"

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$Aggressive,
    [switch]$StopDockerDesktop,
    [switch]$CompactDockerVhdx,
    [switch]$SkipDocker,
    [switch]$SkipCargo,
    [switch]$SkipCaches
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "main.py"))) {
    $Root = (Get-Location).Path
}

function Get-FreeBytes([string]$DriveLetter) {
    $d = Get-PSDrive -Name $DriveLetter -ErrorAction SilentlyContinue
    if ($d) { return [int64]$d.Free }
    return 0
}

function Format-Bytes([int64]$n) {
    if ($n -ge 1GB) { return ("{0:N2} GB" -f ($n / 1GB)) }
    if ($n -ge 1MB) { return ("{0:N2} MB" -f ($n / 1MB)) }
    if ($n -ge 1KB) { return ("{0:N2} KB" -f ($n / 1KB)) }
    return "$n B"
}

function Remove-PathSafe([string]$Path, [string]$Label) {
    if (-not (Test-Path -LiteralPath $Path)) { return [int64]0 }
    $size = [int64]0
    try {
        $sum = (Get-ChildItem -LiteralPath $Path -Recurse -Force -ErrorAction SilentlyContinue |
            Measure-Object -Property Length -Sum).Sum
        if ($sum) { $size = [int64]$sum }
    } catch {
        $size = [int64]0
    }

    if ($PSCmdlet.ShouldProcess($Path, "Remove $Label")) {
        try {
            Remove-Item -LiteralPath $Path -Recurse -Force -ErrorAction Stop
            Write-Host ("  OK  {0}: freed ~{1}" -f $Label, (Format-Bytes $size)) -ForegroundColor Green
            return $size
        } catch {
            Write-Host ("  WARN {0}: {1}" -f $Label, $_.Exception.Message) -ForegroundColor Yellow
            return [int64]0
        }
    }
    Write-Host ("  dry-run {0}: ~{1}" -f $Label, (Format-Bytes $size)) -ForegroundColor Cyan
    return $size
}

$beforeC = Get-FreeBytes "C"
$beforeD = Get-FreeBytes "D"
$freed = [int64]0

Write-Host ""
Write-Host "=== ABS disk cleanup ===" -ForegroundColor Cyan
Write-Host ("ROOT = {0}" -f $Root)
Write-Host ("C: free before = {0}" -f (Format-Bytes $beforeC))
if ($beforeD -gt 0) {
    Write-Host ("D: free before = {0}" -f (Format-Bytes $beforeD))
}
Write-Host ""

# 1) Docker
if (-not $SkipDocker) {
    Write-Host "[1/4] Docker prune" -ForegroundColor Cyan
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($docker) {
        try {
            Write-Host "  docker system df (before):"
            docker system df 2>&1 | ForEach-Object { Write-Host ("    {0}" -f $_) }

            if ($PSCmdlet.ShouldProcess("docker", "system prune / volume prune")) {
                docker system prune -af 2>&1 | ForEach-Object { Write-Host ("    {0}" -f $_) }
                docker volume prune -af 2>&1 | ForEach-Object { Write-Host ("    {0}" -f $_) }
                if ($Aggressive) {
                    docker builder prune -af 2>&1 | ForEach-Object { Write-Host ("    {0}" -f $_) }
                }
                Write-Host "  docker system df (after):"
                docker system df 2>&1 | ForEach-Object { Write-Host ("    {0}" -f $_) }
            }
        } catch {
            Write-Host ("  WARN docker: {0}" -f $_.Exception.Message) -ForegroundColor Yellow
        }
    } else {
        Write-Host "  skip: docker not in PATH" -ForegroundColor DarkYellow
    }

    if ($StopDockerDesktop) {
        Write-Host "  Stopping Docker Desktop (frees RAM)..." -ForegroundColor Cyan
        if ($PSCmdlet.ShouldProcess("Docker Desktop", "Stop-Process")) {
            Get-Process "Docker Desktop","com.docker.backend","com.docker.build","docker-sandbox" -ErrorAction SilentlyContinue |
                Stop-Process -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
            Write-Host "  OK  Docker Desktop processes signaled to stop" -ForegroundColor Green
        }
    }

    if ($CompactDockerVhdx) {
        Write-Host "  Compacting Docker WSL VHDX (needs Admin; reclaims host disk after prune)..." -ForegroundColor Cyan
        $vhdx = Join-Path $env:LOCALAPPDATA "Docker\wsl\disk\docker_data.vhdx"
        if (-not (Test-Path -LiteralPath $vhdx)) {
            Write-Host "  skip: VHDX not found at $vhdx" -ForegroundColor DarkYellow
        } elseif ($PSCmdlet.ShouldProcess($vhdx, "diskpart compact vdisk")) {
            try {
                wsl --shutdown 2>$null
                Start-Sleep -Seconds 3
                $beforeV = (Get-Item -LiteralPath $vhdx).Length
                $dpScript = Join-Path $env:TEMP "abs_compact_docker.txt"
                @(
                    ("select vdisk file=`"{0}`"" -f $vhdx),
                    "attach vdisk readonly",
                    "compact vdisk",
                    "detach vdisk",
                    "exit"
                ) | Set-Content -Path $dpScript -Encoding ASCII
                $proc = Start-Process -FilePath "diskpart.exe" -ArgumentList @("/s", $dpScript) -Verb RunAs -Wait -PassThru -WindowStyle Hidden
                $afterV = (Get-Item -LiteralPath $vhdx).Length
                Write-Host ("  OK  VHDX {0} -> {1} (diskpart exit {2})" -f (Format-Bytes $beforeV), (Format-Bytes $afterV), $proc.ExitCode) -ForegroundColor Green
            } catch {
                Write-Host ("  WARN compact VHDX: {0}" -f $_.Exception.Message) -ForegroundColor Yellow
                Write-Host "  Run PowerShell as Administrator and re-run with -CompactDockerVhdx" -ForegroundColor DarkYellow
            }
        }
    }
} else {
    Write-Host "[1/4] Docker skipped" -ForegroundColor DarkYellow
}

# 2) Cargo
if (-not $SkipCargo) {
    Write-Host "[2/4] Cargo / Rust build artifacts" -ForegroundColor Cyan
    $cargoPaths = @(
        (Join-Path $Root "native\abs_native\target\debug"),
        (Join-Path $Root "bridge\rust_bridge\target\debug"),
        (Join-Path $Root "rust_blockchain\target")
    )
    foreach ($p in $cargoPaths) {
        $rel = $p
        if ($p.StartsWith($Root)) { $rel = $p.Substring($Root.Length).TrimStart("\") }
        $freed += Remove-PathSafe $p ("cargo debug: " + $rel)
    }
    if ($Aggressive) {
        $fullTargets = @(
            (Join-Path $Root "native\abs_native\target"),
            (Join-Path $Root "bridge\rust_bridge\target")
        )
        foreach ($p in $fullTargets) {
            $rel = $p
            if ($p.StartsWith($Root)) { $rel = $p.Substring($Root.Length).TrimStart("\") }
            $freed += Remove-PathSafe $p ("cargo FULL target: " + $rel)
        }
    } else {
        Write-Host "  tip: keep release/ for faster rebuilds; use -Aggressive to wipe all targets" -ForegroundColor DarkGray
    }

    $cargoHome = if ($env:CARGO_HOME) { $env:CARGO_HOME } else { Join-Path $env:USERPROFILE ".cargo" }
    if ($Aggressive) {
        $freed += Remove-PathSafe (Join-Path $cargoHome "git\checkouts") "cargo git checkouts"
    }
} else {
    Write-Host "[2/4] Cargo skipped" -ForegroundColor DarkYellow
}

# 3) Caches
if (-not $SkipCaches) {
    Write-Host "[3/4] Python / pip / maturin caches" -ForegroundColor Cyan
    $cachePaths = @(
        (Join-Path $env:LOCALAPPDATA "pip\Cache"),
        (Join-Path $env:LOCALAPPDATA "pypa\maturin"),
        (Join-Path $env:LOCALAPPDATA "cargo-maturin")
    )
    foreach ($p in $cachePaths) {
        if (Test-Path -LiteralPath $p) {
            $freed += Remove-PathSafe $p ("cache: " + (Split-Path $p -Leaf))
        }
    }

    Get-ChildItem -Path $env:TEMP -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like "maturin*" -or $_.Name -like "pip-build-env-*" } |
        ForEach-Object {
            $freed += Remove-PathSafe $_.FullName ("temp cache: " + $_.Name)
        }

    if ($PSCmdlet.ShouldProcess($Root, "Remove __pycache__ / *.pyc")) {
        $pyc = Get-ChildItem -Path $Root -Recurse -Force -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch "\\\.git\\" }
        $pycSize = [int64]0
        foreach ($d in $pyc) {
            try {
                $sum = (Get-ChildItem $d.FullName -Recurse -Force -ErrorAction SilentlyContinue |
                    Measure-Object Length -Sum).Sum
                if ($sum) { $pycSize += [int64]$sum }
                Remove-Item $d.FullName -Recurse -Force -ErrorAction SilentlyContinue
            } catch {}
        }
        $freed += $pycSize
        Write-Host ("  OK  __pycache__: ~{0}" -f (Format-Bytes $pycSize)) -ForegroundColor Green
    }

    $tmpNames = @(
        "_maturin_build.log",
        "_maturin.txt",
        "_rust_test.txt",
        "_v1337_pytest.txt",
        "_v1337_post_soak.txt",
        "_v1338_pytest.txt",
        "_v1338_post_soak.txt",
        "_commit_msg_v1337.txt",
        "_commit_msg_v1338.txt"
    )
    $dataDir = Join-Path $Root "data"
    foreach ($name in $tmpNames) {
        $p = Join-Path $dataDir $name
        if (Test-Path -LiteralPath $p) {
            $freed += Remove-PathSafe $p ("tmp log: " + $name)
        }
    }

    if ($Aggressive) {
        $dist = Join-Path $Root "dist"
        if (Test-Path -LiteralPath $dist) {
            $freed += Remove-PathSafe $dist "dist/ wheels (rebuild via maturin)"
        }
    }
} else {
    Write-Host "[3/4] Caches skipped" -ForegroundColor DarkYellow
}

# 4) Temp leftovers
Write-Host "[4/4] Temp leftovers" -ForegroundColor Cyan
$tempHits = Get-ChildItem $env:TEMP -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -match "^(maturin|pip-|cargo-|abs_|rocksdb|librocksdb)" -or
        $_.Name -match "maturin|abs_native"
    }
foreach ($item in $tempHits) {
    $freed += Remove-PathSafe $item.FullName ("temp: " + $item.Name)
}

$afterC = Get-FreeBytes "C"
$afterD = Get-FreeBytes "D"
$deltaC = $afterC - $beforeC

Write-Host ""
Write-Host "=== Summary ===" -ForegroundColor Cyan
Write-Host ("Tracked removals (approx): {0}" -f (Format-Bytes $freed))
Write-Host ("C: free after  = {0}  (delta {1}{2})" -f (Format-Bytes $afterC), $(if ($deltaC -ge 0) { "+" } else { "" }), (Format-Bytes $deltaC))
if ($beforeD -gt 0) {
    Write-Host ("D: free after  = {0}" -f (Format-Bytes $afterD))
}
Write-Host ""
Write-Host "RAM tip: Docker Desktop idle often uses 2-6+ GB. Use -StopDockerDesktop when not running mesh." -ForegroundColor DarkGray
Write-Host "Disk tip: set CARGO_TARGET_DIR=D:\cargo-target\abs to keep Rust builds off C:." -ForegroundColor DarkGray
Write-Host "Done." -ForegroundColor Green
