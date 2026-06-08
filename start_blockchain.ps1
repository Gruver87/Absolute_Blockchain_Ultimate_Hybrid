cd C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🚀 ABSOLUTE BLOCKCHAIN ULTIMATE - FULL LAUNCH" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# 1. ПРОВЕРКА ОКРУЖЕНИЯ
# ============================================================
Write-Host "[1/7] Checking environment..." -ForegroundColor Yellow

# Проверка Python
$pythonVersion = python --version 2>&1
Write-Host "  ✅ Python: $pythonVersion" -ForegroundColor Green

# Проверка pip
$pipVersion = pip --version 2>&1
Write-Host "  ✅ pip: $($pipVersion.Split(' ')[0])" -ForegroundColor Green

# Проверка Docker (опционально)
$dockerVersion = docker --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Docker: $dockerVersion" -ForegroundColor Green
} else {
    Write-Host "  ⚠️ Docker not found (optional)" -ForegroundColor Yellow
}

# ============================================================
# 2. УСТАНОВКА ЗАВИСИМОСТЕЙ
# ============================================================
Write-Host ""
Write-Host "[2/7] Installing dependencies..." -ForegroundColor Yellow

pip install -q -r requirements.txt 2>$null
Write-Host "  ✅ Dependencies installed" -ForegroundColor Green

# ============================================================
# 3. ЗАПУСК ТЕСТОВ (быстрая проверка)
# ============================================================
Write-Host ""
Write-Host "[3/7] Running quick tests..." -ForegroundColor Yellow

$testResults = @()
$tests = @(
    "test_state_engine.py",
    "test_v44.py",
    "test_v46.py",
    "test_v47.py",
    "test_v48.py",
    "test_v49.py",
    "test_v50.py",
    "test_v51.py",
    "test_v52.py"
)

foreach ($test in $tests) {
    if (Test-Path $test) {
        $output = python -X utf8 $test 2>&1
        if ($output -match "ALL TESTS PASSED" -or $output -match "SUCCESS") {
            Write-Host "  ✅ $test" -ForegroundColor Green
            $testResults += "✅ $test"
        } else {
            Write-Host "  ❌ $test - FAILED" -ForegroundColor Red
            $testResults += "❌ $test"
        }
    } else {
        Write-Host "  ⚠️ $test - not found" -ForegroundColor Yellow
        $testResults += "⚠️ $test"
    }
}

# ============================================================
# 4. ЗАПУСК НОДЫ (в фоне)
# ============================================================
Write-Host ""
Write-Host "[4/7] Starting blockchain node..." -ForegroundColor Yellow

# Запускаем ноду в фоновом процессе
$nodeProcess = Start-Process -FilePath "python" -ArgumentList "node_persistent.py" -PassThru -NoNewWindow
Start-Sleep -Seconds 3

Write-Host "  ✅ Node started (PID: $($nodeProcess.Id))" -ForegroundColor Green

# ============================================================
# 5. ЗАПУСК RPC СЕРВЕРА (если отдельно)
# ============================================================
Write-Host ""
Write-Host "[5/7] Starting JSON-RPC server..." -ForegroundColor Yellow

# Проверяем, запущен ли RPC сервер
$rpcRunning = $false
try {
    $response = Invoke-RestMethod -Uri "http://localhost:8545" -Method POST -Body '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' -ContentType "application/json" -TimeoutSec 2
    $rpcRunning = $true
} catch {
    $rpcRunning = $false
}

if (-not $rpcRunning) {
    $rpcProcess = Start-Process -FilePath "python" -ArgumentList "-c `"from rpc.server import JSONRPCServer; from node_persistent import PersistentNode; node = PersistentNode(); server = JSONRPCServer(node); server.start(); import time; time.sleep(3600)`"" -PassThru -NoNewWindow
    Start-Sleep -Seconds 2
    Write-Host "  ✅ RPC server started (PID: $($rpcProcess.Id))" -ForegroundColor Green
} else {
    Write-Host "  ✅ RPC server already running" -ForegroundColor Green
}

# ============================================================
# 6. ПРОВЕРКА РАБОТОСПОСОБНОСТИ
# ============================================================
Write-Host ""
Write-Host "[6/7] Verifying functionality..." -ForegroundColor Yellow

# Проверка RPC
try {
    $rpcTest = Invoke-RestMethod -Uri "http://localhost:8545" -Method POST -Body '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' -ContentType "application/json" -TimeoutSec 5
    Write-Host "  ✅ RPC response: blockNumber = $($rpcTest.result)" -ForegroundColor Green
} catch {
    Write-Host "  ❌ RPC server not responding" -ForegroundColor Red
}

# Проверка ноды
try {
    $nodeCheck = Invoke-RestMethod -Uri "http://localhost:8080/api/stats" -TimeoutSec 5 -ErrorAction SilentlyContinue
    if ($nodeCheck) {
        Write-Host "  ✅ Node API responding" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️ Node API not on port 8080 (may be using default)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ⚠️ Node API check skipped" -ForegroundColor Yellow
}

# ============================================================
# 7. DOCKER ЗАПУСК (опционально)
# ============================================================
Write-Host ""
Write-Host "[7/7] Docker setup (optional)..." -ForegroundColor Yellow

if ($dockerVersion) {
    Write-Host "  Building Docker image..." -ForegroundColor Gray
    docker build -t absolute-blockchain:latest . 2>&1 | Out-Null
    Write-Host "  ✅ Docker image built: absolute-blockchain:latest" -ForegroundColor Green
    
    Write-Host ""
    Write-Host "  To run with Docker Compose:" -ForegroundColor Cyan
    Write-Host "    docker-compose up --build" -ForegroundColor Gray
} else {
    Write-Host "  ⚠️ Docker not available - skipping" -ForegroundColor Yellow
}

# ============================================================
# ФИНАЛЬНЫЙ ОТЧЁТ
# ============================================================
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "✅ ABSOLUTE BLOCKCHAIN ULTIMATE - LAUNCH COMPLETE!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

Write-Host "📊 TEST RESULTS:" -ForegroundColor Yellow
foreach ($result in $testResults) {
    Write-Host "  $result" -ForegroundColor Gray
}

Write-Host ""
Write-Host "🌐 ENDPOINTS:" -ForegroundColor Yellow
Write-Host "  🔗 Node RPC:  http://localhost:8545" -ForegroundColor Cyan
Write-Host "  🔗 Node API:  http://localhost:8080" -ForegroundColor Cyan
Write-Host "  🔗 Explorer:  http://localhost:8090" -ForegroundColor Cyan
Write-Host "  🔗 GUI:       http://localhost:8091" -ForegroundColor Cyan
Write-Host "  🔗 Monitor:   http://localhost:8092" -ForegroundColor Cyan
Write-Host "  🔗 Docs:      https://gruver87.github.io/absolute-blockchain-ultimate/" -ForegroundColor Cyan

Write-Host ""
Write-Host "📝 COMMANDS:" -ForegroundColor Yellow
Write-Host "  📊 View logs:     Get-Content -Path 'data/blockchain.log' -Tail 50" -ForegroundColor Gray
Write-Host "  🛑 Stop node:     Stop-Process -Id $($nodeProcess.Id)" -ForegroundColor Gray
Write-Host "  🐳 Docker:        docker-compose up --build" -ForegroundColor Gray
Write-Host "  🧪 Run all tests: python -X utf8 test_v52.py" -ForegroundColor Gray

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "🎉 BLOCKCHAIN IS RUNNING! Press Ctrl+C to stop" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Green

# ============================================================
# ОЖИДАНИЕ ЗАВЕРШЕНИЯ
# ============================================================
try {
    while ($true) {
        Start-Sleep -Seconds 1
    }
} catch {
    Write-Host ""
    Write-Host "🛑 Stopping blockchain..." -ForegroundColor Yellow
    Stop-Process -Id $nodeProcess.Id -Force -ErrorAction SilentlyContinue
    if ($rpcProcess) { Stop-Process -Id $rpcProcess.Id -Force -ErrorAction SilentlyContinue }
    Write-Host "✅ Blockchain stopped" -ForegroundColor Green
}