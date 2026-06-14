# Build Rust cross-chain bridge CLI (bridge/abs_bridge_bin)
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location (Join-Path $ProjectRoot "bridge\rust_bridge")

$Cargo = "cargo"
if ($IsWindows -or $env:OS -eq "Windows_NT") {
    $msvc = "stable-x86_64-pc-windows-msvc"
    $active = (rustup show active-toolchain 2>$null) -join ""
    if ($active -notmatch "windows-msvc") {
        Write-Host "Using MSVC toolchain for bridge build (no MinGW/gcc required)..." -ForegroundColor Cyan
        rustup toolchain install $msvc 2>$null | Out-Null
        $Cargo = "cargo +$msvc"
    }
}

Invoke-Expression "$Cargo build --release"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Bridge build failed. Install MSVC Build Tools or use Python L1 relayer." -ForegroundColor Red
    exit 1
}

$meta = Invoke-Expression "$Cargo metadata --format-version 1 --no-deps" | ConvertFrom-Json
$bin = Join-Path $meta.target_directory "release\abs_bridge_bin.exe"
if (-not (Test-Path $bin)) {
    Write-Host "Binary not found at $bin" -ForegroundColor Red
    exit 1
}

$out = Join-Path $ProjectRoot "bridge\abs_bridge_bin.exe"
Copy-Item $bin $out -Force
Set-Location $ProjectRoot
Write-Host "Built: $out (from $($meta.target_directory))" -ForegroundColor Green
$test = '{"command":"status","args":{}}'
$test | & $out | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "CLI smoke test: OK" -ForegroundColor Green
}
