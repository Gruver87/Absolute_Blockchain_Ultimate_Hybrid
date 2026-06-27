# Test Docker devnet P2P catch-up WITHOUT cloning node1 DB into node2.
param(
    [int]$WaitSec = 600,
    [switch]$RustBridge
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

Write-Host "=== Docker NoCloneDb sync test (wait up to ${WaitSec}s) ===" -ForegroundColor Cyan
Write-Host "node2 starts with empty DB; must catch up via P2P fast-sync" -ForegroundColor Gray

$args = @("-NoCloneDb")
if ($RustBridge) { $args += "-RustBridge" }

& (Join-Path $ProjectRoot "scripts\docker_devnet.ps1") @args
if ($LASTEXITCODE -ne 0) {
    Write-Host "Docker devnet start failed" -ForegroundColor Red
    exit 1
}

python scripts/verify_p2p_ci.py --mode devnet --wait $WaitSec
exit $LASTEXITCODE
