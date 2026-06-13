# Quick two-node devnet health check
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

Write-Host "=== Devnet status ===" -ForegroundColor Cyan

function Probe-Node($Base, $Name) {
    try {
        $null = Invoke-RestMethod -Uri "$Base/health/live" -TimeoutSec 5
        Start-Sleep -Milliseconds 200
        $status = Invoke-RestMethod -Uri "$Base/status" -TimeoutSec 5
        $peers = Invoke-RestMethod -Uri "$Base/peers" -TimeoutSec 5
        $sync = Invoke-RestMethod -Uri "$Base/sync/status" -TimeoutSec 5
        Write-Host (
            "{0}: UP height={1} peers={2} chain={3} state_ok={4}" -f `
                $Name, $status.height, $peers.count, $status.chain_id, ($sync.state_consistent -ne $false)
        ) -ForegroundColor Green
        return @{ ok = $true; height = [int]$status.height; peers = $peers.count }
    }
    catch {
        Write-Host "$Name`: DOWN ($($_.Exception.Message))" -ForegroundColor Red
        return @{ ok = $false }
    }
}

$n1 = Probe-Node "http://127.0.0.1:8080" "node1"
$n2 = Probe-Node "http://127.0.0.1:8081" "node2"

if ($n1.ok -and $n2.ok) {
    $gap = [Math]::Abs($n1.height - $n2.height)
    if ($gap -le 5) {
        Write-Host "Sync OK (gap=$gap)" -ForegroundColor Green
        exit 0
    }
    Write-Host "Height gap=$gap" -ForegroundColor Yellow
    exit 2
}

Write-Host "Start: .\scripts\start_two_nodes.ps1" -ForegroundColor Yellow
exit 1
