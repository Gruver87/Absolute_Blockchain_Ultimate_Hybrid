# Start two local ABS nodes for P2P testing (Windows PowerShell)
param(
    [switch]$NoCloneDb
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

# UTF-8 for hidden node processes (avoids UnicodeEncodeError on emoji in logs)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

function Wait-NodeReady {
    param(
        [string]$Url,
        [string]$Name,
        [int]$MaxSec = 90
    )
    Write-Host "Waiting for $Name at $Url ..." -ForegroundColor Gray
    for ($elapsed = 0; $elapsed -lt $MaxSec; $elapsed += 3) {
        try {
            $null = Invoke-RestMethod -Uri "$Url/health/live" -TimeoutSec 5
            Write-Host "$Name ready" -ForegroundColor Green
            return $true
        }
        catch {
            Start-Sleep -Seconds 3
        }
    }
    Write-Host "$Name not ready after ${MaxSec}s" -ForegroundColor Red
    return $false
}

function Start-AbsNode {
    param(
        [string]$ConfigFile,
        [string]$StdoutLog,
        [string]$StderrLog
    )
    $out = Join-Path $ProjectRoot $StdoutLog
    $err = Join-Path $ProjectRoot $StderrLog
    foreach ($f in @($out, $err)) {
        $dir = Split-Path $f -Parent
        if ($dir -and -not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
    }
    return Start-Process -FilePath "python" `
        -ArgumentList "main.py", "--config", $ConfigFile `
        -WorkingDirectory $ProjectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $out `
        -RedirectStandardError $err `
        -PassThru
}

function Test-NodeAlive {
    param([int]$ProcessId, [string]$Name, [string]$LogHint)
    if (Get-Process -Id $ProcessId -ErrorAction SilentlyContinue) {
        return $true
    }
    Write-Host "WARN: $Name (PID $ProcessId) exited - see $LogHint" -ForegroundColor Red
    return $false
}

Write-Host "=== Absolute Blockchain - two-node devnet ===" -ForegroundColor Cyan
Write-Host "Node 1: P2P :5000  REST :8080  Monitor :8092" -ForegroundColor Gray
Write-Host "Node 2: P2P :5001  REST :8081  Monitor :8093  (bootstrap -> 127.0.0.1:5000)" -ForegroundColor Gray
Write-Host "Logs: data/node_stdout.log, data/node2/node_stdout.log" -ForegroundColor Gray
Write-Host ""

& (Join-Path $ProjectRoot "scripts\stop_node.ps1") 2>$null

$node1Db = Join-Path $ProjectRoot "data\blockchain.db"
$node2Db = Join-Path $ProjectRoot "data\node2\blockchain.db"
if ($NoCloneDb) {
    Write-Host "Node2 fresh DB (-NoCloneDb: P2P catch-up sync test)" -ForegroundColor Yellow
} else {
    foreach ($suffix in @("", "-shm", "-wal")) {
        $dst = "$node2Db$suffix"
        if (Test-Path $dst) { Remove-Item $dst -Force -ErrorAction SilentlyContinue }
    }
    if (Test-Path $node1Db) {
        foreach ($suffix in @("", "-shm", "-wal")) {
            $src = "$node1Db$suffix"
            if (Test-Path $src) {
                Copy-Item $src "$node2Db$suffix" -Force
            }
        }
        Write-Host "Node2 DB cloned from node1 (same chain snapshot)" -ForegroundColor Gray
    } else {
        Write-Host "Node2 fresh DB (node1 chain not found yet)" -ForegroundColor Gray
    }
}

foreach ($dir in @("data", "data\node2")) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
}

$node1 = Start-AbsNode -ConfigFile "node.example.json" `
    -StdoutLog "data\node_stdout.log" -StderrLog "data\node_stderr.log"

if (-not (Wait-NodeReady -Url "http://127.0.0.1:8080" -Name "node1" -MaxSec 90)) {
    Write-Host "Node 1 failed. Tail: Get-Content data\node_stderr.log -Tail 30" -ForegroundColor Red
    exit 1
}

$node2 = Start-AbsNode -ConfigFile "node2.example.json" `
    -StdoutLog "data\node2\node_stdout.log" -StderrLog "data\node2\node_stderr.log"

if (-not (Wait-NodeReady -Url "http://127.0.0.1:8081" -Name "node2" -MaxSec 60)) {
    Write-Host "Node 2 failed. Tail: Get-Content data\node2\node_stderr.log -Tail 30" -ForegroundColor Red
    exit 1
}

Write-Host "Waiting for P2P link (up to 45s)..." -ForegroundColor Gray
$p2pOk = $false
for ($i = 0; $i -lt 15; $i++) {
    try {
        $p1 = (Invoke-RestMethod -Uri "http://127.0.0.1:8080/peers" -TimeoutSec 5).count
        $p2 = (Invoke-RestMethod -Uri "http://127.0.0.1:8081/peers" -TimeoutSec 5).count
        $s1 = Invoke-RestMethod -Uri "http://127.0.0.1:8080/status" -TimeoutSec 5
        $s2 = Invoke-RestMethod -Uri "http://127.0.0.1:8081/status" -TimeoutSec 5
        if ($s1.chain_id -ne $s2.chain_id) {
            Write-Host "FAIL: chain_id mismatch node1=$($s1.chain_id) node2=$($s2.chain_id)" -ForegroundColor Red
            exit 1
        }
        if ($p1 -gt 0 -or $p2 -gt 0) {
            $p2pOk = $true
            Write-Host "P2P connected (node1 peers=$p1 node2 peers=$p2 chain_id=$($s1.chain_id))" -ForegroundColor Green
            break
        }
    }
    catch { }
    Start-Sleep -Seconds 3
}

if ($p2pOk) {
    Write-Host "Waiting for height sync (up to 120s)..." -ForegroundColor Gray
    for ($i = 0; $i -lt 40; $i++) {
        try {
            $s1 = Invoke-RestMethod -Uri "http://127.0.0.1:8080/status" -TimeoutSec 5
            $s2 = Invoke-RestMethod -Uri "http://127.0.0.1:8081/status" -TimeoutSec 5
            $gap = [Math]::Abs([int]$s1.height - [int]$s2.height)
            if ($gap -le 5) {
                Write-Host "Heights synced: node1=$($s1.height) node2=$($s2.height)" -ForegroundColor Green
                break
            }
            if ($i % 5 -eq 4 -and [int]$s2.height -lt [int]$s1.height) {
                Invoke-RestMethod -Uri "http://127.0.0.1:8081/sync/fast-sync" -Method POST -Body '{}' -ContentType 'application/json' -TimeoutSec 10 | Out-Null
            }
        }
        catch { }
        Start-Sleep -Seconds 3
    }
}

if (-not $p2pOk) {
    Write-Host "WARN: P2P not linked yet - wait 30s then: .\scripts\verify_p2p.ps1" -ForegroundColor Yellow
}

@{
    node1 = @{ pid = $node1.Id; http = 8080; config = "node.example.json" }
    node2 = @{ pid = $node2.Id; http = 8081; config = "node2.example.json" }
    started_at = (Get-Date).ToString("o")
} | ConvertTo-Json | Set-Content (Join-Path $ProjectRoot "data\node_pids.json") -Encoding UTF8

Start-Sleep -Seconds 2
$alive1 = Test-NodeAlive -ProcessId $node1.Id -Name "node1" -LogHint "data\node_stderr.log"
$alive2 = Test-NodeAlive -ProcessId $node2.Id -Name "node2" -LogHint "data\node2\node_stderr.log"

Write-Host ""
Write-Host "Node 1 PID: $($node1.Id)  |  Node 2 PID: $($node2.Id)" -ForegroundColor Green
Write-Host "Explorer:     http://localhost:8080  (Ctrl+F5 after restart)" -ForegroundColor Yellow
Write-Host "Stop:         .\scripts\stop_node.ps1" -ForegroundColor Yellow
Write-Host "Status:       .\scripts\devnet_status.ps1" -ForegroundColor Yellow

if ($alive1 -and $alive2) {
    Write-Host "Running P2P verify..." -ForegroundColor Gray
    $verifyOk = $false
    for ($v = 0; $v -lt 3; $v++) {
        if ($v -gt 0) { Start-Sleep -Seconds 5 }
        python scripts/verify_p2p_ci.py --mode devnet
        if ($LASTEXITCODE -eq 0) {
            $verifyOk = $true
            Write-Host "Devnet OK" -ForegroundColor Green
            break
        }
    }
    if (-not $verifyOk) {
        Write-Host "Verify failed after 3 tries (exit $LASTEXITCODE) - nodes may still be up" -ForegroundColor Yellow
        Write-Host "Retry: python scripts/verify_p2p_ci.py --mode devnet" -ForegroundColor Gray
    }
}
