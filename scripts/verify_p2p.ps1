# P2P smoke test: two nodes must see each other and sync heights
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

Write-Host "=== Two-node P2P check ===" -ForegroundColor Cyan

function Get-NodeInfo($Url, $Name) {
    try {
        $peers = Invoke-RestMethod -Uri "$Url/peers" -TimeoutSec 10
        $status = Invoke-RestMethod -Uri "$Url/status" -TimeoutSec 10
        $height = [int]($status.height)
        Write-Host (
            "{0}: peers={1} solo={2} height={3}" -f $Name, $peers.count, $peers.solo_mode, $height
        ) -ForegroundColor $(if ($peers.count -gt 0) { "Green" } else { "Yellow" })
        return @{ peers = $peers.count; height = $height; ok = $true }
    }
    catch {
        Write-Host ("{0}: FAIL {1}" -f $Name, $_.Exception.Message) -ForegroundColor Red
        return @{ peers = -1; height = -1; ok = $false }
    }
}

$n1 = Get-NodeInfo "http://127.0.0.1:8080" "node1"
$n2 = Get-NodeInfo "http://127.0.0.1:8081" "node2"

if (-not $n1.ok -or -not $n2.ok) {
    Write-Host "Start nodes first: .\scripts\start_two_nodes.ps1" -ForegroundColor Yellow
    exit 1
}

if ($n1.peers -eq 0 -and $n2.peers -eq 0) {
    Write-Host "No P2P link yet. Wait ~30s and retry, or check firewall." -ForegroundColor Yellow
    exit 2
}

$gap = $n1.height - $n2.height
if ($gap -gt 50) {
    Write-Host "Sync in progress: node2 behind node1 by $gap blocks (wait ~60s)" -ForegroundColor Yellow
    Write-Host "Trigger catch-up: Invoke-RestMethod http://127.0.0.1:8081/sync/fast-sync -Method POST -Body '{}' -ContentType 'application/json'" -ForegroundColor Gray
    exit 3
}

Write-Host "P2P link OK (height gap=$gap)" -ForegroundColor Green
exit 0
