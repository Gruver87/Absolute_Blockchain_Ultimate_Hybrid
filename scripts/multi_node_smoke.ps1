# Multi-node P2P smoke - two local nodes, state consistency check.
# Requires: nodes started separately (see start_two_nodes.ps1).
#
# Usage:
#   .\scripts\start_two_nodes.ps1 -RustBridge -Fresh
#   .\scripts\multi_node_smoke.ps1
#
# Or auto-spawn via CI helper:
#   python scripts/verify_p2p_ci.py --mode auto --wait 120

param(
    [string]$Url1 = "http://127.0.0.1:8080",
    [string]$Url2 = "http://127.0.0.1:8081",
    [int]$WaitSec = 120
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Multi-node P2P smoke (n1=$Url1 n2=$Url2)" -ForegroundColor Cyan
python scripts/verify_p2p_ci.py --mode auto --wait $WaitSec --url1 $Url1 --url2 $Url2
exit $LASTEXITCODE
