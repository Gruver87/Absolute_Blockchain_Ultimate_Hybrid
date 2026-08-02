# Fuzz abs_native P2P kernels (v1.3.88)
#
# Windows / local: deterministic smoke (cargo test) — no libFuzzer required.
# Linux CI: short cargo-fuzz runs (see .github/workflows/fuzz-native.yml).
#
# Honesty: smoke/fuzz ≠ full audit; ≠ public mainnet; ≠ full Rust P2P transport.
param(
    [ValidateSet("smoke", "fuzz")]
    [string]$Mode = "smoke",
    [int]$Seconds = 60,
    [ValidateSet("p2p_frame", "p2p_wire", "p2p_rate_limit", "all")]
    [string]$Target = "all"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Manifest = Join-Path $Root "native\abs_native\Cargo.toml"
$FuzzDir = Join-Path $Root "native\abs_native\fuzz"

Set-Location $Root

if ($Mode -eq "smoke") {
    Write-Host "=== abs_native P2P fuzz smoke (cargo test) ===" -ForegroundColor Cyan
    cargo test --manifest-path $Manifest --no-default-features fuzz_p2p_ -- --nocapture
    if ($LASTEXITCODE -ne 0) {
        throw "fuzz smoke failed rc=$LASTEXITCODE"
    }
    Write-Host "OK: fuzz smoke passed" -ForegroundColor Green
    exit 0
}

# Mode = fuzz (libFuzzer via cargo-fuzz; primarily Linux)
if ($IsWindows -or $env:OS -match "Windows") {
    Write-Warning "cargo-fuzz / libFuzzer is not the primary path on Windows. Use -Mode smoke."
    Write-Warning "Continuing only if cargo-fuzz is installed and a nightly+clang toolchain exists."
}

Write-Host "=== cargo-fuzz ($Target, ${Seconds}s) ===" -ForegroundColor Cyan
Push-Location $FuzzDir
try {
    cargo install cargo-fuzz --locked 2>$null
    $targets = if ($Target -eq "all") {
        @("p2p_frame", "p2p_wire", "p2p_rate_limit")
    } else {
        @($Target)
    }
    foreach ($t in $targets) {
        Write-Host "--- fuzz $t ---" -ForegroundColor Yellow
        cargo fuzz run $t -- -max_total_time=$Seconds
        if ($LASTEXITCODE -ne 0) {
            throw "cargo fuzz run $t failed rc=$LASTEXITCODE"
        }
    }
} finally {
    Pop-Location
}
Write-Host "OK: cargo-fuzz finished" -ForegroundColor Green
