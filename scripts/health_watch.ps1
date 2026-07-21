# Poll prod/dev mesh health and optionally POST to a webhook on failure.
param(
    [int[]]$Ports = @(18180, 18181, 18182),
    [switch]$ProdMesh,
    [int]$IntervalSec = 300,
    [int]$DurationMin = 0,
    [int]$FullHarnessEvery = 6,
    [switch]$AlwaysFullHarness,
    [string]$LogFile = "logs/health_watch.log",
    [string]$WebhookUrl = $env:HEALTH_WEBHOOK_URL
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if ($ProdMesh) {
    $Ports = @(18180, 18181, 18182)
}

# Short runs: default 300s interval means only one poll before DurationMin ends.
if ($DurationMin -gt 0 -and -not $PSBoundParameters.ContainsKey("IntervalSec")) {
    $IntervalSec = [Math]::Max(10, [Math]::Min(60, [int](($DurationMin * 60) / 3)))
}

$logDir = Split-Path -Parent $LogFile
if ($logDir -and -not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
}

function Write-Log([string]$Msg, [string]$Color = "Gray") {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $Msg"
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
    Write-Host $line -ForegroundColor $Color
}

function Test-NodeHealth([int]$Port, [bool]$FullHarness) {
    $readySec = if ($ProdMesh) { 15 } else { 5 }
    $statusSec = if ($ProdMesh) { 12 } else { 5 }
    $harnessSec = if ($FullHarness) { if ($ProdMesh) { 30 } else { 20 } } else { if ($ProdMesh) { 15 } else { 10 } }
    try {
        $null = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health/ready" -TimeoutSec $readySec
        $st = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/status" -TimeoutSec $statusSec
        $harnessUri = if ($FullHarness) {
            "http://127.0.0.1:$Port/chain/consistency/harness?peer_timeout=8"
        } else {
            "http://127.0.0.1:$Port/chain/consistency/harness?quick=1&peer_timeout=3"
        }
        $cs = Invoke-RestMethod -Uri $harnessUri -TimeoutSec $harnessSec
        $failed = @($cs.failed_checks)
        return @{
            Ok = $true
            Port = $Port
            Height = $st.height
            Head = $st.head_hash
            Peers = $st.peers
            P2P = $st.p2p_sync_status
            Aligned = $cs.tip_state_aligned
            HarnessHealthy = $cs.harness_healthy
            Failed = $failed
            FullHarness = $FullHarness
        }
    } catch {
        return @{ Ok = $false; Port = $Port; Error = $_.Exception.Message }
    }
}

function Test-MeshAlignment([int[]]$PortList) {
    $rows = @()
    foreach ($p in $PortList) {
        try {
            $st = Invoke-RestMethod -Uri "http://127.0.0.1:$p/status" -TimeoutSec $(if ($ProdMesh) { 12 } else { 5 })
            $rows += [PSCustomObject]@{
                Port = $p
                Height = [int]$st.height
                Head = [string]$st.head_hash
                Peers = [int]$st.peers
            }
        } catch {
            return @{ Ok = $false; Error = "port $p status: $($_.Exception.Message)" }
        }
    }
    $heights = @($rows | ForEach-Object { $_.Height })
    $heads = @(($rows | ForEach-Object { $_.Head }) | Where-Object { $_ })
    # Allow ±1 height skew: status is polled sequentially while blocks mine.
    $maxH = ($heights | Measure-Object -Maximum).Maximum
    $minH = ($heights | Measure-Object -Minimum).Minimum
    $heightOk = ($maxH - $minH) -le 1
    # Same tip hash only required when all heights match; otherwise heads differ by design.
    if (($heights | Select-Object -Unique).Count -le 1) {
        $headOk = ($heads.Count -eq 0) -or (($heads | Select-Object -Unique).Count -le 1)
    } else {
        $headOk = $true
    }
    return @{
        Ok = $heightOk -and $headOk
        Rows = $rows
        HeightOk = $heightOk
        HeadOk = $headOk
    }
}

function Send-Webhook([string]$Text) {
    if (-not $WebhookUrl) { return }
    try {
        $body = @{ text = $Text } | ConvertTo-Json -Compress
        Invoke-RestMethod -Uri $WebhookUrl -Method Post -Body $body -ContentType "application/json" -TimeoutSec 10 | Out-Null
    } catch {
        Write-Log "webhook failed: $($_.Exception.Message)" "Yellow"
    }
}

$end = if ($DurationMin -gt 0) { (Get-Date).AddMinutes($DurationMin) } else { $null }
$cycle = 0
$totalHardFails = 0
Write-Log "health_watch start ports=$($Ports -join ',') interval=${IntervalSec}s full_every=$FullHarnessEvery log=$LogFile" "Cyan"

while ($true) {
    $cycle++
    $fullHarness = $AlwaysFullHarness -or ($FullHarnessEvery -le 1) -or ($cycle % $FullHarnessEvery -eq 0)
    $modeLabel = if ($fullHarness) { "full" } else { "quick" }
    $failures = @()

    foreach ($p in $Ports) {
        $r = Test-NodeHealth $p $fullHarness
        if (-not $r.Ok) {
            $failures += "port $p unreachable: $($r.Error)"
            $totalHardFails++
            Write-Log "FAIL port $p $($r.Error)" "Red"
            continue
        }
        $failedTxt = if ($r.Failed.Count -gt 0) { $r.Failed -join "," } else { "" }
        $line = "OK port $($r.Port) [$modeLabel] height=$($r.Height) peers=$($r.Peers) p2p=$($r.P2P) aligned=$($r.Aligned) failed=$failedTxt"
        $p2pWarn = ($r.P2P -in @("solo", "under_mesh", "stale"))
        $harnessBad = ($r.Aligned -eq $false) -or ($r.Failed.Count -gt 0) -or ($r.HarnessHealthy -eq $false)
        if ($harnessBad) {
            $failures += $line
            Write-Log "WARN $line" "Yellow"
        } elseif ($p2pWarn) {
            Write-Log "$line (p2p not full mesh; chain OK)" "Yellow"
        } else {
            Write-Log $line "Green"
        }
    }

    if ($Ports.Count -gt 1) {
        $mesh = Test-MeshAlignment $Ports
        if (-not $mesh.Ok) {
            $detail = ($mesh.Rows | ForEach-Object { "h$($_.Port)=$($_.Height)" }) -join " "
            $failures += "mesh misaligned: $detail"
            Write-Log "WARN mesh misaligned $detail" "Yellow"
        } else {
            $detail = ($mesh.Rows | ForEach-Object { "$($_.Port):h$($_.Height)/p$($_.Peers)" }) -join " "
            Write-Log "OK mesh aligned $detail" "DarkGray"
        }
    }

    if ($failures.Count -gt 0) {
        Send-Webhook ("Absolute mesh alert (cycle $cycle):`n" + ($failures -join "`n"))
    }

    if ($end -and (Get-Date) -ge $end) {
        Write-Log "health_watch done (duration ${DurationMin}m cycles=$cycle hard_fails=$totalHardFails)" "Cyan"
        break
    }
    $sleepFor = $IntervalSec
    if ($end) {
        $remaining = [int](($end - (Get-Date)).TotalSeconds)
        if ($remaining -le 0) {
            Write-Log "health_watch done (duration ${DurationMin}m cycles=$cycle hard_fails=$totalHardFails)" "Cyan"
            break
        }
        if ($remaining -lt $sleepFor) { $sleepFor = $remaining }
    }
    Start-Sleep -Seconds $sleepFor
}

# Hard FAIL lines (unreachable ports) must fail the process for soak honesty.
if ($totalHardFails -gt 0) {
    Write-Log "health_watch exit=1 hard_fails=$totalHardFails" "Red"
    exit 1
}
exit 0
