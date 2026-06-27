# Build Rust cross-chain bridge CLI (bridge/abs_bridge_bin)
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location (Join-Path $ProjectRoot "bridge\rust_bridge")

try {
    $CargoArgs = @()
    if ($IsWindows -or $env:OS -eq "Windows_NT") {
        $msvc = "stable-x86_64-pc-windows-msvc"
        $toolchains = (& rustup toolchain list 2>$null) -join "`n"
        if ($toolchains -notmatch [regex]::Escape($msvc)) {
            Write-Host "Installing MSVC Rust toolchain for bridge build..." -ForegroundColor Cyan
            $oldEap = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            & rustup toolchain install $msvc 2>$null
            $ErrorActionPreference = $oldEap
            if ($LASTEXITCODE -ne 0) {
                Write-Host "Rust MSVC toolchain install failed." -ForegroundColor Red
                exit 1
            }
        }
        Write-Host "Using MSVC toolchain for bridge build (no MinGW/gcc required)..." -ForegroundColor Cyan
        $CargoArgs = @("+$msvc")
    }

    & cargo @CargoArgs build --release
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Bridge build failed. Install MSVC Build Tools or use Python L1 relayer." -ForegroundColor Red
        exit 1
    }

    $metaJson = & cargo @CargoArgs metadata --format-version 1 --no-deps
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Cargo metadata failed." -ForegroundColor Red
        exit 1
    }
    $meta = $metaJson | ConvertFrom-Json
    $bin = Join-Path $meta.target_directory "release\abs_bridge_bin.exe"
    if (-not (Test-Path $bin)) {
        Write-Host "Binary not found at $bin" -ForegroundColor Red
        exit 1
    }

    $out = Join-Path $ProjectRoot "bridge\abs_bridge_bin.exe"
    Copy-Item $bin $out -Force
    Write-Host "Built: $out (from $($meta.target_directory))" -ForegroundColor Green
    $test = '{"command":"status","args":{}}'
    $test | & $out | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "CLI smoke test: OK" -ForegroundColor Green
    }
}
finally {
    Pop-Location
}
