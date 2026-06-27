param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

$crate = Join-Path $ProjectRoot "native\abs_native"
Push-Location $crate
try {
    python -m pip install --upgrade maturin
    $wheelDir = Join-Path $crate "target\wheels"
    python -m maturin build --release --out $wheelDir
    $wheel = Get-ChildItem $wheelDir -Filter "*.whl" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $wheel) {
        throw "abs_native wheel was not produced"
    }
    python -m pip install --force-reinstall $wheel.FullName
    python -c "import abs_native; print('abs_native OK:', abs_native.sha256_hex(b'absolute')[:16])"
}
finally {
    Pop-Location
}
