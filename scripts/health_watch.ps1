# Poll prod/dev mesh health and optionally POST to a webhook on failure.
param(
    [int[]]$Ports = @(18180, 18181, 18182),
    [switch]$ProdMesh,
    [int]$IntervalSec = 300,
    [int]$DurationMin = 0,
    [string]$LogFile = "logs/health_watch.log",
    [string]$WebhookUrl = $env:HEALTH_WEBHOOK_URL
)

$ErrorActionPreference = "Continue"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

if ($ProdMesh) {
    $Ports = @(18180, 18181, 18182)
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

function Test-NodeHealth([int]$Port) {
    try {
        $h = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health/ready" -TimeoutSec 5
        $st = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/status" -TimeoutSec 5
        $cs = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/chain/consistency/harness" -TimeoutSec 8
        return @{
            Ok = $true
            Port = $Port
            Height = $st.height
            Peers = $st.peers
            P2P = $st.p2p_sync_status
            Aligned = $cs.tip_state_aligned
            Failed = $cs.failed_checks
        }
    } catch {
        return @{ Ok = $false; Port = $Port; Error = $_.Exception.Message }
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
Write-Log "health_watch start ports=$($Ports -join ',') interval=${IntervalSec}s log=$LogFile" "Cyan"

while ($true) {
    $failures = @()
    foreach ($p in $Ports) {
        $r = Test-NodeHealth $p
        if (-not $r.Ok) {
            $failures += "port $p unreachable: $($r.Error)"
            Write-Log "FAIL port $p $($r.Error)" "Red"
            continue
        }
        $line = "OK port $($r.Port) height=$($r.Height) peers=$($r.Peers) p2p=$($r.P2P) aligned=$($r.Aligned) failed=$($r.Failed)"
        if ($r.Aligned -eq $false -or ($r.Failed -and [int]$r.Failed -gt 0)) {
            $failures += $line
            Write-Log "WARN $line" "Yellow"
        } else {
            Write-Log $line "Green"
        }
    }

    if ($failures.Count -gt 0) {
        Send-Webhook ("Absolute mesh alert:`n" + ($failures -join "`n"))
    }

    if ($end -and (Get-Date) -ge $end) {
        Write-Log "health_watch done (duration ${DurationMin}m)" "Cyan"
        break
    }
    Start-Sleep -Seconds $IntervalSec
}
