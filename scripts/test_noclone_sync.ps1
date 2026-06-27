# Test node2 P2P catch-up WITHOUT cloning node1 DB.
# WARNING: on a long chain (4000+ blocks) this can take many minutes or stall.
# For automated short-chain test use: python scripts/verify_p2p_ci.py --mode ci
param(
    [int]$WaitSec = 600
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

Write-Host "=== NoCloneDb sync test (wait up to ${WaitSec}s) ===" -ForegroundColor Cyan
Write-Host "Tip: for fast CI use: python scripts/verify_p2p_ci.py --mode ci" -ForegroundColor Gray

& (Join-Path $ProjectRoot "scripts\stop_node.ps1")
& (Join-Path $ProjectRoot "scripts\start_two_nodes.ps1") -NoCloneDb

if ($LASTEXITCODE -ne 0) {
    Write-Host "Start failed" -ForegroundColor Red
    exit 1
}

python scripts/verify_p2p_ci.py --mode devnet --wait $WaitSec
exit $LASTEXITCODE
