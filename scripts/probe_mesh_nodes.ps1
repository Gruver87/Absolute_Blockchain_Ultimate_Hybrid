# Probe /status, /bridge/status, /features on multiple local HTTP ports.
param(
    [int[]]$Ports = @(8080, 8081, 8082, 8083, 8084),
    [switch]$ProdMesh,
    [switch]$Deep
)

$ErrorActionPreference = "Continue"
if ($ProdMesh) {
    $Ports = @(18180, 18181, 18182)
    if (-not $PSBoundParameters.ContainsKey("Deep")) {
        $Deep = $true
    }
}

function Get-Json($Url, [int]$TimeoutSec = 4) {
    try {
        return Invoke-RestMethod -Uri $Url -TimeoutSec $TimeoutSec
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
$rows = @()
foreach ($p in $Ports) {
    $base = "http://127.0.0.1:$p"
    $st = Get-Json "$base/status"
    if (-not $st) {
        Write-Host ("{0,-6} {1}" -f $p, "(not reachable)") -ForegroundColor DarkGray
        continue
    }
    $alive++
    $br = Get-Json "$base/bridge/status"
    $fe = Get-Json "$base/features"
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

    $row = [ordered]@{
        Port = $p
        Height = [int](F $st.height 0)
        Head = [string](F $st.head_hash "")
        Peers = [int](F $st.peers (F $st.peer_count 0))
        StateRoot = ""
        TopologyHealthy = $null
        ConsistencyOk = $null
    }

    if ($Deep) {
        $topo = Get-Json "$base/p2p/topology" 12
        if ($topo) {
            $row.TopologyHealthy = [bool]$topo.topology_healthy
            $scoreAvg = F $topo.peer_score_avg "-"
            $peerCount = F $topo.peer_count 0
            Write-Host ("       p2p: peers=$peerCount healthy=$($topo.topology_healthy) score_avg=$scoreAvg") -ForegroundColor DarkGray
            if ($topo.security) {
                $sec = $topo.security
                Write-Host ("       security: bans=$($sec.active_bans) rate=$($sec.rate_limit_per_sec)/s strikes=$($sec.strikes_before_ban)") -ForegroundColor DarkGray
            }
        }
        $harness = Get-Json "$base/chain/consistency/harness" 20
        if ($harness) {
            $row.ConsistencyOk = [bool]$harness.harness_healthy
            $row.StateRoot = [string](F $harness.live_state_root "")
            $rootsMatch = F $harness.peer_roots_aligned $true
            Write-Host ("       harness: healthy=$($harness.harness_healthy) peer_roots=$rootsMatch") -ForegroundColor DarkGray
        }
    }
    $rows += [pscustomobject]$row
}

Write-Host ""
if ($alive -eq 0) {
    Write-Host "No nodes reachable. Start mesh:" -ForegroundColor Yellow
    Write-Host "  .\scripts\docker_devnet_5validator.ps1" -ForegroundColor White
    Write-Host "  .\scripts\docker_prod_3node.ps1" -ForegroundColor White
    exit 1
}

if ($Deep -and $rows.Count -ge 2) {
    $heights = $rows | ForEach-Object { $_.Height }
    $spread = ($heights | Measure-Object -Maximum).Maximum - ($heights | Measure-Object -Minimum).Minimum
    $heads = @($rows | ForEach-Object { $_.Head } | Where-Object { $_ })
    $uniqueHeads = ($heads | Select-Object -Unique).Count
    $roots = @($rows | ForEach-Object { $_.StateRoot } | Where-Object { $_ })
    $uniqueRoots = ($roots | Select-Object -Unique).Count

    Write-Host "Deep summary:" -ForegroundColor Cyan
    Write-Host "  height spread: $spread (max-min)"
    Write-Host "  unique head hashes: $uniqueHeads"
    if ($roots.Count -gt 0) {
        Write-Host "  unique state roots: $uniqueRoots"
    }
    if ($spread -gt 1) {
        Write-Host "WARN: height spread > 1 — mesh may still be syncing" -ForegroundColor Yellow
    }
    if ($uniqueHeads -gt 1) {
        Write-Host "FAIL: head hash mismatch across reachable nodes" -ForegroundColor Red
        exit 1
    }
    if ($roots.Count -ge 2 -and $uniqueRoots -gt 1) {
        Write-Host "FAIL: state root mismatch across reachable nodes" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Reachable: $alive / $($Ports.Count)" -ForegroundColor Green
exit 0
