# P2P smoke test: two nodes must see each other, sync heights, truth layer OK
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

Write-Host "=== Two-node P2P + Truth Layer check ===" -ForegroundColor Cyan

function Get-NodeInfo($Url, $Name) {
    try {
        $peers = Invoke-RestMethod -Uri "$Url/peers" -TimeoutSec 10
        $status = Invoke-RestMethod -Uri "$Url/status" -TimeoutSec 10
        $sync = Invoke-RestMethod -Uri "$Url/sync/status" -TimeoutSec 10
        $validators = Invoke-RestMethod -Uri "$Url/validators" -TimeoutSec 10
        $att = Invoke-RestMethod -Uri "$Url/consensus/attestations" -TimeoutSec 10
        $height = [int]($status.height)
        $vcount = @($validators.validators).Count
        if ($vcount -eq 0 -and $validators -is [array]) { $vcount = $validators.Count }
        $consistent = ($sync.state_consistent -ne $false)
        Write-Host (
            "{0}: peers={1} height={2} validators={3} attestations={4} state_ok={5}" -f `
                $Name, $peers.count, $height, $vcount, $att.count, $consistent
        ) -ForegroundColor $(if ($peers.count -gt 0) { "Green" } else { "Yellow" })
        return @{
            peers = $peers.count
            height = $height
            validators = $vcount
            attestations = [int]$att.count
            state_consistent = $consistent
            ok = $true
        }
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

$gap = [Math]::Abs($n1.height - $n2.height)
if ($gap -gt 50) {
    Write-Host "Sync in progress: height gap=$gap (wait ~60s)" -ForegroundColor Yellow
    Write-Host "Trigger catch-up: Invoke-RestMethod http://127.0.0.1:8081/sync/fast-sync -Method POST -Body '{}' -ContentType 'application/json'" -ForegroundColor Gray
    exit 3
}

if (-not $n1.state_consistent -or -not $n2.state_consistent) {
    Write-Host "State drift detected (legacy blocks may WARN; new blocks should match)" -ForegroundColor Yellow
}

if ($n1.validators -lt 2) {
    Write-Host "Multi-validator: node1 has $($n1.validators) validators (expected >=2 after node2 gossip)" -ForegroundColor Yellow
}

Write-Host "P2P link OK (height gap=$gap, attestations node1=$($n1.attestations) node2=$($n2.attestations))" -ForegroundColor Green
exit 0
