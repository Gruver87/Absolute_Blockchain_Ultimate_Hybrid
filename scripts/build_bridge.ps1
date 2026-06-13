# Build Rust cross-chain bridge CLI (bridge/abs_bridge_bin)
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location (Join-Path $ProjectRoot "bridge\rust_bridge")

cargo build --release
if ($LASTEXITCODE -ne 0) {
    Write-Host "cargo build failed - install Rust from https://rustup.rs" -ForegroundColor Red
    exit 1
}

$meta = cargo metadata --format-version 1 --no-deps | ConvertFrom-Json
$bin = Join-Path $meta.target_directory "release\abs_bridge_bin.exe"
if (-not (Test-Path $bin)) {
    Write-Host "Binary not found at $bin" -ForegroundColor Red
    exit 1
}
$out = Join-Path $ProjectRoot "bridge\abs_bridge_bin.exe"
Copy-Item $bin $out -Force
Write-Host "Built: $out" -ForegroundColor Green
