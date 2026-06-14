# Build Rust cross-chain bridge CLI (bridge/abs_bridge_bin)
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location (Join-Path $ProjectRoot "bridge\rust_bridge")

# Windows GNU toolchain lacks gcc/dlltool — MSVC + Schannel works out of the box
$Cargo = "cargo"
if ($IsWindows -or $env:OS -eq "Windows_NT") {
    $msvc = "stable-x86_64-pc-windows-msvc"
    $active = (rustup show active-toolchain 2>$null) -join ""
    if ($active -match "windows-gnu") {
        Write-Host "Switching to MSVC toolchain for bridge build (no MinGW/gcc required)..." -ForegroundColor Cyan
        rustup toolchain install $msvc 2>$null | Out-Null
        $Cargo = "cargo +$msvc"
    }
}

Invoke-Expression "$Cargo build --release"
if ($LASTEXITCODE -ne 0) {
    Write-Host @"

Bridge build failed. On Windows install:
  rustup default stable-x86_64-pc-windows-msvc
  Visual Studio Build Tools -> 'Desktop development with C++'

Or skip Rust bridge and use Python L1 relayer:
  python scripts/bridge_relayer.py --watch-l1

"@ -ForegroundColor Red
    exit 1
}

# Resolve output path (MSVC vs GNU target dirs differ)
$bin = Join-Path $ProjectRoot "bridge\rust_bridge\target\release\abs_bridge_bin.exe"
if (-not (Test-Path $bin)) {
    $meta = cargo metadata --format-version 1 --no-deps 2>$null | ConvertFrom-Json
    if ($meta) {
        $bin = Join-Path $meta.target_directory "release\abs_bridge_bin.exe"
    }
}
if (-not (Test-Path $bin)) {
    Write-Host "Binary not found at $bin" -ForegroundColor Red
    exit 1
}

$out = Join-Path $ProjectRoot "bridge\abs_bridge_bin.exe"
Copy-Item $bin $out -Force
Set-Location $ProjectRoot
Write-Host "Built: $out" -ForegroundColor Green
$test = '{"command":"status","args":{}}'
$test | & $out | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "CLI smoke test: OK" -ForegroundColor Green
}
