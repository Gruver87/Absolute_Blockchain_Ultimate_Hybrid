# P2P smoke test: two nodes must see each other (step 4 checklist)
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

Write-Host "=== Two-node P2P check ===" -ForegroundColor Cyan

function Test-Peers($Url, $Name) {
    try {
        $d = Invoke-RestMethod -Uri "$Url/peers" -TimeoutSec 10
        Write-Host ("{0}: peers={1} solo={2}" -f $Name, $d.count, $d.solo_mode) -ForegroundColor $(if ($d.count -gt 0) { "Green" } else { "Yellow" })
        return $d.count
    }
    catch {
        Write-Host ("{0}: FAIL {1}" -f $Name, $_.Exception.Message) -ForegroundColor Red
        return -1
    }
}

$n1 = Test-Peers "http://127.0.0.1:8080" "node1"
$n2 = Test-Peers "http://127.0.0.1:8081" "node2"

if ($n1 -lt 0 -or $n2 -lt 0) {
    Write-Host "Start nodes first: .\scripts\start_two_nodes.ps1" -ForegroundColor Yellow
    exit 1
}

if ($n1 -eq 0 -and $n2 -eq 0) {
    Write-Host "No P2P link yet. Wait ~30s and retry, or check firewall." -ForegroundColor Yellow
    exit 2
}

Write-Host "P2P link OK" -ForegroundColor Green
exit 0
