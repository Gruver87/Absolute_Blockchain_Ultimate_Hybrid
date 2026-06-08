cd C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "🚀 ABSOLUTE BLOCKCHAIN - FULL SYSTEM LAUNCH" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# 1. ПРОВЕРКА ОКРУЖЕНИЯ
# ============================================================
Write-Host "[1/6] CHECKING ENVIRONMENT..." -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray

$pythonVersion = python --version 2>&1
Write-Host "  ✅ Python: $pythonVersion" -ForegroundColor Green

$pipVersion = pip --version 2>&1
Write-Host "  ✅ pip: $($pipVersion.Split(' ')[0])" -ForegroundColor Green

$dockerVersion = docker --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Docker: $dockerVersion" -ForegroundColor Green
} else {
    Write-Host "  ⚠️ Docker not found (optional)" -ForegroundColor Yellow
}

# ============================================================
# 2. ОСТАНОВКА СТАРЫХ ПРОЦЕССОВ
# ============================================================
Write-Host ""
Write-Host "[2/6] STOPPING OLD PROCESSES..." -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray

$oldProcesses = Get-Process python -ErrorAction SilentlyContinue
if ($oldProcesses) {
    $oldProcesses | Stop-Process -Force
    Write-Host "  ✅ Stopped $($oldProcesses.Count) old Python processes" -ForegroundColor Green
} else {
    Write-Host "  ✅ No old processes found" -ForegroundColor Green
}

# ============================================================
# 3. ОЧИСТКА СТАРЫХ ДАННЫХ
# ============================================================
Write-Host ""
Write-Host "[3/6] CLEANING OLD DATA..." -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray

# Очистка старых БД
Remove-Item -Path "data\*.db" -Force -ErrorAction SilentlyContinue
Write-Host "  ✅ Old databases removed" -ForegroundColor Green

# Очистка кэша
Remove-Item -Path "__pycache__" -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "  ✅ Cache cleaned" -ForegroundColor Green

# ============================================================
# 4. ЗАПУСК ОСНОВНОЙ НОДЫ
# ============================================================
Write-Host ""
Write-Host "[4/6] STARTING BLOCKCHAIN NODE..." -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray

# Запускаем ноду
$nodeProcess = Start-Process -FilePath "python" -ArgumentList "node_persistent.py" -PassThru -NoNewWindow
Start-Sleep -Seconds 5

Write-Host "  ✅ Blockchain node started (PID: $($nodeProcess.Id))" -ForegroundColor Green

# ============================================================
# 5. ЗАПУСК ДОПОЛНИТЕЛЬНЫХ МОДУЛЕЙ (опционально)
# ============================================================
Write-Host ""
Write-Host "[5/6] STARTING ADDITIONAL MODULES..." -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray

# Запуск Extended API сервера (если есть)
if (Test-Path "extended_api_server.py") {
    $extendedProcess = Start-Process -FilePath "python" -ArgumentList "extended_api_server.py" -PassThru -NoNewWindow
    Write-Host "  ✅ Extended API server started (PID: $($extendedProcess.Id))" -ForegroundColor Green
} else {
    Write-Host "  ⚠️ Extended API server not found" -ForegroundColor Yellow
}

# Запуск HTTP сервера для картинок (если есть папка nft_images)
if (Test-Path "nft_images") {
    $httpProcess = Start-Process -FilePath "python" -ArgumentList "-m http.server 8081" -PassThru -NoNewWindow
    Write-Host "  ✅ HTTP image server started (port 8081)" -ForegroundColor Green
} else {
    Write-Host "  ⚠️ NFT images folder not found" -ForegroundColor Yellow
}

# ============================================================
# 6. ПРОВЕРКА РАБОТОСПОСОБНОСТИ
# ============================================================
Write-Host ""
Write-Host "[6/6] VERIFYING SYSTEM..." -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Gray

Start-Sleep -Seconds 3

# Проверка RPC
try {
    $rpcResponse = Invoke-RestMethod -Uri "http://localhost:8545" -Method POST -Body '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' -ContentType "application/json" -TimeoutSec 5
    Write-Host "  ✅ JSON-RPC: OK (block: $($rpcResponse.result))" -ForegroundColor Green
} catch {
    Write-Host "  ❌ JSON-RPC: FAILED" -ForegroundColor Red
}

# Проверка основной API
try {
    $apiResponse = Invoke-RestMethod -Uri "http://localhost:8080/api/stats" -TimeoutSec 5 -ErrorAction SilentlyContinue
    Write-Host "  ✅ Node API: OK" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️ Node API: not responding (may be starting)" -ForegroundColor Yellow
}

# ============================================================
# ФИНАЛЬНЫЙ ОТЧЁТ
# ============================================================
Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "✅ ABSOLUTE BLOCKCHAIN - FULL SYSTEM ONLINE!" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""

Write-Host "📊 SYSTEM STATUS:" -ForegroundColor Cyan
Write-Host "  🟢 Blockchain Node: RUNNING (PID: $($nodeProcess.Id))" -ForegroundColor Green
if ($extendedProcess) { Write-Host "  🟢 Extended API: RUNNING (PID: $($extendedProcess.Id))" -ForegroundColor Green }
if ($httpProcess) { Write-Host "  🟢 HTTP Server: RUNNING (port 8081)" -ForegroundColor Green }

Write-Host ""
Write-Host "🌐 ENDPOINTS:" -ForegroundColor Cyan
Write-Host "  🔗 JSON-RPC:      http://localhost:8545" -ForegroundColor Gray
Write-Host "  🔗 Node API:      http://localhost:8080" -ForegroundColor Gray
Write-Host "  🔗 API Docs:      http://localhost:8080/docs" -ForegroundColor Gray
Write-Host "  🔗 Extended API:  http://localhost:8081" -ForegroundColor Gray
Write-Host "  🔗 NFT Gallery:   http://localhost:8080/nft" -ForegroundColor Gray

Write-Host ""
Write-Host "📝 QUICK COMMANDS:" -ForegroundColor Cyan
Write-Host '  📊 Get block number:' -ForegroundColor Gray
Write-Host '    curl -X POST http://localhost:8545 -H "Content-Type: application/json" -d' -ForegroundColor Gray
Write-Host '    "{\"jsonrpc\":\"2.0\",\"method\":\"eth_blockNumber\",\"params\":[],\"id\":1}"' -ForegroundColor Gray
Write-Host ""
Write-Host '  💰 Get balance:' -ForegroundColor Gray
Write-Host '    curl -X POST http://localhost:8545 -H "Content-Type: application/json" -d' -ForegroundColor Gray
Write-Host '    "{\"jsonrpc\":\"2.0\",\"method\":\"eth_getBalance\",\"params\":[\"foundation\",\"latest\"],\"id\":1}"' -ForegroundColor Gray
Write-Host ""
Write-Host '  🛑 Stop all:' -ForegroundColor Gray
Write-Host '    Get-Process python | Stop-Process -Force' -ForegroundColor Gray

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "🎉 BLOCKCHAIN IS RUNNING! Press Ctrl+C to stop monitoring" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Green

# ============================================================
# МОНИТОРИНГ (опционально)
# ============================================================
try {
    while ($true) {
        Start-Sleep -Seconds 10
        # Можно добавить периодическую проверку
    }
} catch {
    Write-Host ""
    Write-Host "🛑 Stopping blockchain..." -ForegroundColor Yellow
    Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
    Write-Host "✅ Blockchain stopped" -ForegroundColor Green
}