# Quick probe of public testnet ports (:19080 seed, :19081 validator).
param(
    [switch]$Deep,
    [int[]]$Ports = @(19080, 19081)
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Split-Path -Parent $ScriptDir
Set-Location $Root

$fail = 0
foreach ($port in $Ports) {
    $label = if ($port -eq 19080) { "seed" } else { "validator" }
    Write-Host "[$label] :$port" -ForegroundColor Cyan
    try {
        $ready = Invoke-RestMethod -Uri "http://127.0.0.1:$port/health/ready" -TimeoutSec 8
        $st = Invoke-RestMethod -Uri "http://127.0.0.1:$port/status" -TimeoutSec 8
        if ($ready.status -ne "ready") {
            Write-Host "  FAIL: not ready" -ForegroundColor Red
            $fail++
            continue
        }
        if ([int]$st.chain_id -ne 77777) {
            Write-Host "  FAIL: chain_id=$($st.chain_id) expected 77777" -ForegroundColor Red
            $fail++
            continue
        }
        Write-Host "  OK height=$($st.height) peers=$($st.peers)" -ForegroundColor Green
        if ($Deep) {
            $mesh = Invoke-RestMethod -Uri "http://127.0.0.1:$port/testnet/mesh" -TimeoutSec 12
            Write-Host "  mesh_healthy=$($mesh.mesh_healthy) peer_count=$($mesh.peer_count)" -ForegroundColor DarkGray
            $cs = Invoke-RestMethod -Uri "http://127.0.0.1:$port/chain/consistency/harness?quick=1&peer_timeout=5" -TimeoutSec 25
            Write-Host "  harness=$($cs.harness_healthy) tip_aligned=$($cs.tip_state_aligned)" -ForegroundColor DarkGray
        }
    } catch {
        Write-Host "  FAIL: $($_.Exception.Message)" -ForegroundColor Red
        $fail++
    }
}

if ($Ports -contains 19080 -and $Ports -contains 19081 -and $fail -eq 0) {
    python (Join-Path $ScriptDir "verify_testnet_mesh.py") --mesh --wait 0
    if ($LASTEXITCODE -ne 0) { $fail++ }
}

if ($fail -gt 0) { exit 1 }
Write-Host "OK: testnet mesh probe" -ForegroundColor Green
exit 0
