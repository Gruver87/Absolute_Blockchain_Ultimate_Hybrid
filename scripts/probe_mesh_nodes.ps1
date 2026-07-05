# Probe /status, /bridge/status, /features on multiple local HTTP ports.
param(
    [int[]]$Ports = @(8080, 8081, 8082, 8083, 8084),
    [switch]$ProdMesh
)

$ErrorActionPreference = "Continue"
if ($ProdMesh) {
    $Ports = @(18180, 18181, 18182)
}

function Get-Json($Url) {
    try {
        return Invoke-RestMethod -Uri $Url -TimeoutSec 4
    } catch {
        return $null
    }
}

function F($v, $fallback) {
    if ($null -eq $v -or "$v" -eq "") { return $fallback }
    return $v
}

Write-Host "Mesh probe - ports: $($Ports -join ', ')" -ForegroundColor Cyan
Write-Host ("{0,-6} {1,-18} {2,-8} {3,-6} {4,-22} {5,-12} {6}" -f `
    "Port", "node_id", "chain", "height", "p2p_sync", "bridge", "features") -ForegroundColor DarkGray

$alive = 0
foreach ($p in $Ports) {
    $st = Get-Json "http://127.0.0.1:$p/status"
    if (-not $st) {
        Write-Host ("{0,-6} {1}" -f $p, "(not reachable)") -ForegroundColor DarkGray
        continue
    }
    $alive++
    $br = Get-Json "http://127.0.0.1:$p/bridge/status"
    $fe = Get-Json "http://127.0.0.1:$p/features"
    $bridgeLabel = if ($st.bridge_enabled) { F $st.bridge_mode "on" } else { "off" }
    $featOn = @()
    if ($fe -and $fe.flags) {
        foreach ($k in $fe.flags.PSObject.Properties.Name) {
            if ($fe.flags.$k -eq $true) { $featOn += $k }
        }
    }
    $featJoined = $featOn -join ","
    if ($featJoined.Length -gt 24) { $featJoined = $featJoined.Substring(0, 24) }
    if (-not $featJoined) { $featJoined = "-" }
    Write-Host ("{0,-6} {1,-18} {2,-8} {3,-6} {4,-22} {5,-12} {6}" -f `
        $p,
        (F $st.node_id "-"),
        (F $st.chain_id "-"),
        (F $st.height "-"),
        (F $st.p2p_sync_status "-"),
        $bridgeLabel,
        $featJoined)
    if (-not $st.bridge_enabled -and $st.bridge_disabled_reason) {
        Write-Host ("       bridge: $($st.bridge_disabled_reason)") -ForegroundColor DarkGray
    }
    if ($br -and $br.locks) {
        Write-Host ("       /bridge/status tier=$(F $br.tier '-') locks=$($br.locks.total)") -ForegroundColor DarkGray
    }
}

Write-Host ""
if ($alive -eq 0) {
    Write-Host "No nodes reachable. Start mesh:" -ForegroundColor Yellow
    Write-Host "  .\scripts\docker_devnet_5validator.ps1" -ForegroundColor White
    Write-Host "  .\scripts\docker_prod_3node.ps1" -ForegroundColor White
    exit 1
}
Write-Host "Reachable: $alive / $($Ports.Count)" -ForegroundColor Green
exit 0
