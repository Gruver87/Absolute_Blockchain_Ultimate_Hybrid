# Start two local ABS nodes for P2P testing (Windows PowerShell)
param(
    [switch]$NoCloneDb,
    [switch]$RustBridge,
    [switch]$Fresh,
    [switch]$Industrial
)

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

# UTF-8 for hidden node processes (avoids UnicodeEncodeError on emoji in logs)
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

$node1Config = if ($Industrial) { "node.industrial.json" } else { "node.example.json" }
$node2Config = if ($Industrial) { "node2.industrial.json" } else { "node2.example.json" }
if ($Industrial) {
    $env:ABS_REQUIRE_NATIVE_CRYPTO = "true"
    Write-Host "Industrial devnet: native crypto required, L2/demo features off, rust bridge" -ForegroundColor Cyan
}
$bin = Join-Path $ProjectRoot "bridge\abs_bridge_bin.exe"
if (-not (Test-Path $bin)) {
    Write-Host "Rust bridge binary missing - running build_bridge.ps1" -ForegroundColor Yellow
    & (Join-Path $ProjectRoot "scripts\build_bridge.ps1")
    if ($LASTEXITCODE -ne 0) { exit 1 }
}
if ($RustBridge) {
    Write-Host "-RustBridge is now the default path; using $node1Config" -ForegroundColor DarkGray
}
Write-Host "Local nodes bridge_mode=rust ($node1Config + $node2Config)" -ForegroundColor Cyan

function Stop-DockerDevnetIfRunning {
    foreach ($file in @(
        "docker-compose.devnet-rust.yml",
        "docker-compose.devnet.yml",
        "docker-compose.devnet-3node.yml",
        "docker-compose.devnet-5validator.yml"
    )) {
        $compose = Join-Path $ProjectRoot $file
        if (-not (Test-Path $compose)) { continue }
        Write-Host "Ensuring Docker devnet is down ($file)..." -ForegroundColor Gray
        docker compose -f $compose down --remove-orphans 2>$null | Out-Null
    }
    try {
        $names = docker ps --format "{{.Names}}" 2>$null
        foreach ($name in @($names)) {
            if ($name -match "(?i)(absolute_blockchain|devnet).*(node|relayer)") {
                Write-Host "Stopping leftover container $name..." -ForegroundColor Yellow
                docker stop $name 2>$null | Out-Null
            }
        }
    }
    catch { }
    Start-Sleep -Seconds 3
    foreach ($port in @(8080, 8081, 5000, 5001)) {
        for ($i = 0; $i -lt 10; $i++) {
            $listeners = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
            if ($listeners.Count -eq 0) { break }
            if ($i -eq 0) {
                Write-Host "Waiting for port :$port to clear..." -ForegroundColor Gray
            }
            Start-Sleep -Seconds 1
        }
    }
    try {
        $st = Invoke-RestMethod -Uri "http://127.0.0.1:8080/status" -TimeoutSec 2
        if ($st.node_id -like "docker-node-*") {
            Write-Host "FAIL: Docker still owns :8080 ($($st.node_id)). Run:" -ForegroundColor Red
            Write-Host "  docker stop absolute_blockchain_ultimate-node1-1" -ForegroundColor Gray
            Write-Host "  docker compose -f docker-compose.devnet-3node.yml down --remove-orphans" -ForegroundColor Gray
            exit 1
        }
    }
    catch { }
}

function Assert-LocalDevnetNode {
    param(
        [string]$Url,
        [string]$ExpectedNodeId
    )
    try {
        $st = Invoke-RestMethod -Uri "$Url/status" -TimeoutSec 5
    }
    catch {
        Write-Host "FAIL: cannot read $Url/status" -ForegroundColor Red
        exit 1
    }
    if ($st.node_id -like "docker-node-*") {
        Write-Host "FAIL: $Url is Docker ($($st.node_id)), not local devnet" -ForegroundColor Red
        Write-Host "  docker compose -f docker-compose.devnet-rust.yml down" -ForegroundColor Gray
        Write-Host "  .\scripts\stop_node.ps1" -ForegroundColor Gray
        exit 1
    }
    if ($ExpectedNodeId -and $st.node_id -ne $ExpectedNodeId) {
        Write-Host "WARN: $Url node_id=$($st.node_id) (expected $ExpectedNodeId)" -ForegroundColor Yellow
    }
    return $st
}

function Wait-Node1MiningHead {
    param(
        [string]$Url = "http://127.0.0.1:8080",
        [int]$MinHeight = 2,
        [int]$MaxSec = 60
    )
    Write-Host "Waiting for node1 height >= $MinHeight before seeding node2..." -ForegroundColor Gray
    for ($elapsed = 0; $elapsed -lt $MaxSec; $elapsed += 2) {
        try {
            $st = Invoke-RestMethod -Uri "$Url/status" -TimeoutSec 5
            if ([int]$st.height -ge $MinHeight) {
                Write-Host "node1 at height $($st.height) - cloning DB to node2" -ForegroundColor Green
                return [int]$st.height
            }
        }
        catch { }
        Start-Sleep -Seconds 2
    }
    Write-Host "WARN: node1 still below height $MinHeight - seeding current snapshot anyway" -ForegroundColor Yellow
    try {
        return [int](Invoke-RestMethod -Uri "$Url/status" -TimeoutSec 5).height
    }
    catch {
        return 0
    }
}

function Clear-NodeLogs {
    foreach ($rel in @(
        "data\node_stdout.log", "data\node_stderr.log",
        "data\node2\node_stdout.log", "data\node2\node_stderr.log"
    )) {
        $path = Join-Path $ProjectRoot $rel
        if (Test-Path $path) {
            Clear-Content $path
        }
    }
}

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

function Sync-Node2DatabaseFromNode1 {
    param(
        [string]$SourceRel = "data\blockchain.db",
        [string]$DestRel = "data\node2\blockchain.db"
    )
    $src = Join-Path $ProjectRoot $SourceRel
    $dst = Join-Path $ProjectRoot $DestRel
    if (-not (Test-Path $src)) {
        Write-Host "WARN: node1 DB missing at $SourceRel - node2 will bootstrap via P2P" -ForegroundColor Yellow
        return $false
    }
    python (Join-Path $ProjectRoot "scripts\clone_node_db.py") --source $src --dest $dst
    if ($LASTEXITCODE -ne 0) {
        Write-Host "FAIL: could not clone node1 DB for node2" -ForegroundColor Red
        return $false
    }
    $srcDir = Split-Path $src -Parent
    $dstDir = Split-Path $dst -Parent
    if ($dstDir -and -not (Test-Path $dstDir)) {
        New-Item -ItemType Directory -Path $dstDir -Force | Out-Null
    }
    foreach ($extra in @("dev_signer.json", "wallet.json")) {
        $from = Join-Path $srcDir $extra
        if (Test-Path $from) {
            Copy-Item $from (Join-Path $dstDir $extra) -Force
        }
    }
    Write-Host "Node2 DB seeded from node1 (SQLite backup, WAL-safe)" -ForegroundColor Gray
    return $true
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

Stop-DockerDevnetIfRunning
& (Join-Path $ProjectRoot "scripts\stop_node.ps1") 2>$null

if ($Fresh) {
    Write-Host "Fresh: removing local chain DBs..." -ForegroundColor Yellow
    Clear-NodeLogs
    foreach ($base in @("data\blockchain.db", "data\node2\blockchain.db")) {
        foreach ($suffix in @("", "-shm", "-wal")) {
            $p = Join-Path $ProjectRoot ($base + $suffix)
            if (Test-Path $p) { Remove-Item $p -Force -ErrorAction SilentlyContinue }
        }
    }
}

$node1Db = Join-Path $ProjectRoot "data\blockchain.db"
$node2Db = Join-Path $ProjectRoot "data\node2\blockchain.db"
if ($NoCloneDb) {
    Write-Host "Node2 fresh DB (-NoCloneDb: P2P catch-up sync test)" -ForegroundColor Yellow
} elseif (-not $Fresh) {
    Sync-Node2DatabaseFromNode1 | Out-Null
} else {
    Write-Host "Node2 will seed from node1 after genesis (-Fresh)" -ForegroundColor Gray
}

foreach ($dir in @("data", "data\node2")) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
}

$node1 = Start-AbsNode -ConfigFile $node1Config `
    -StdoutLog "data\node_stdout.log" -StderrLog "data\node_stderr.log"

if (-not (Wait-NodeReady -Url "http://127.0.0.1:8080" -Name "node1" -MaxSec 90)) {
    Write-Host "Node 1 failed. Tail: Get-Content data\node_stderr.log -Tail 30" -ForegroundColor Red
    exit 1
}
$null = Assert-LocalDevnetNode -Url "http://127.0.0.1:8080" -ExpectedNodeId "node-1"

# After node1 is up, seed node2 from node1 so genesis + tip match (required for -Fresh)
if (-not $NoCloneDb) {
    $null = Wait-Node1MiningHead -MinHeight 2 -MaxSec 60
    if (-not (Sync-Node2DatabaseFromNode1)) {
        Write-Host "WARN: node2 DB seed failed - P2P catch-up may diverge" -ForegroundColor Yellow
    }
}

$node2 = Start-AbsNode -ConfigFile $node2Config `
    -StdoutLog "data\node2\node_stdout.log" -StderrLog "data\node2\node_stderr.log"

if (-not (Wait-NodeReady -Url "http://127.0.0.1:8081" -Name "node2" -MaxSec 60)) {
    Write-Host "Node 2 failed. Tail: Get-Content data\node2\node_stderr.log -Tail 30" -ForegroundColor Red
    exit 1
}
$null = Assert-LocalDevnetNode -Url "http://127.0.0.1:8081" -ExpectedNodeId "node-2"

Write-Host "Waiting for P2P link (up to 45s)..." -ForegroundColor Gray
$p2pOk = $false
for ($i = 0; $i -lt 15; $i++) {
    try {
        $p1 = (Invoke-RestMethod -Uri "http://127.0.0.1:8080/peers" -TimeoutSec 5).count
        $p2 = (Invoke-RestMethod -Uri "http://127.0.0.1:8081/peers" -TimeoutSec 5).count
        $s1 = Invoke-RestMethod -Uri "http://127.0.0.1:8080/status" -TimeoutSec 5
        $s2 = Invoke-RestMethod -Uri "http://127.0.0.1:8081/status" -TimeoutSec 5
        if ($s1.node_id -like "docker-node-*" -or $s2.node_id -like "docker-node-*") {
            Write-Host "FAIL: Docker nodes still on devnet ports - run docker compose down first" -ForegroundColor Red
            exit 1
        }
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
                $body = @{ timeout = [Math]::Min(600, [Math]::Max(120, $gap * 8)) } | ConvertTo-Json
                Invoke-RestMethod -Uri "http://127.0.0.1:8081/sync/fast-sync" -Method POST -Body $body -ContentType 'application/json' -TimeoutSec 620 | Out-Null
                Invoke-RestMethod -Uri "http://127.0.0.1:8081/sync/reconcile" -Method POST -Body $body -ContentType 'application/json' -TimeoutSec 620 | Out-Null
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
    node1 = @{ pid = $node1.Id; http = 8080; config = $node1Config }
    node2 = @{ pid = $node2.Id; http = 8081; config = $node2Config }
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
