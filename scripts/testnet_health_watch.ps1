# Poll public testnet mesh health (:19080 seed, optional :19081/:19082 validators).
param(
    [int[]]$Ports = @(19080, 19081, 19082),
    [switch]$Mesh2,
    [switch]$Mesh3,
    [int]$IntervalSec = 120,
    [int]$DurationMin = 0,
    [string]$LogFile = "logs/testnet_health_watch.log"
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if ($Mesh2) { $Ports = @(19080, 19081) }
if ($Mesh3) { $Ports = @(19080, 19081, 19082) }

$logDir = Split-Path -Parent $LogFile
if ($logDir -and -not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
}

function Write-Log([string]$Msg, [string]$Color = "Gray") {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Msg"
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
    Write-Host $line -ForegroundColor $Color
}

function Test-TestnetNode([int]$Port) {
    try {
        $ready = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health/ready" -TimeoutSec 8
        $st = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/status" -TimeoutSec 8
        if ($ready.status -ne "ready") {
            return @{ Ok = $false; Port = $Port; Error = "not ready" }
        }
        if ([int]$st.chain_id -ne 77777) {
            return @{ Ok = $false; Port = $Port; Error = "chain_id=$($st.chain_id)" }
        }
        return @{
            Ok = $true
            Port = $Port
            Height = $st.height
            Peers = $st.peers
            Head = $st.head_hash
        }
    } catch {
        return @{ Ok = $false; Port = $Port; Error = $_.Exception.Message }
    }
}

$end = if ($DurationMin -gt 0) { (Get-Date).AddMinutes($DurationMin) } else { $null }
$cycle = 0
do {
    $cycle++
    $ok = $true
    $rows = @()
    foreach ($p in $Ports) {
        $r = Test-TestnetNode -Port $p
        $rows += $r
        if (-not $r.Ok) { $ok = $false }
    }
    if ($ok) {
        $summary = ($rows | ForEach-Object { ":$($_.Port) h=$($_.Height) p=$($_.Peers)" }) -join " | "
        Write-Log "OK cycle=$cycle $summary" "Green"
        if ($Ports -contains 19080 -and $Ports.Count -ge 2) {
            try {
                $mesh = Invoke-RestMethod -Uri "http://127.0.0.1:19080/testnet/mesh" -TimeoutSec 12
                Write-Log "  mesh_healthy=$($mesh.mesh_healthy) peer_count=$($mesh.peer_count)" "DarkGray"
            } catch { }
        }
    } else {
        foreach ($r in $rows | Where-Object { -not $_.Ok }) {
            Write-Log "FAIL :$($r.Port) $($r.Error)" "Red"
        }
    }
    if ($end -and (Get-Date) -ge $end) { break }
    if ($DurationMin -gt 0) { Start-Sleep -Seconds $IntervalSec }
} while ($DurationMin -gt 0)

if ($DurationMin -eq 0) {
    if (-not $ok) { exit 1 }
    Write-Log "OK: testnet health snapshot" "Green"
}
exit 0
