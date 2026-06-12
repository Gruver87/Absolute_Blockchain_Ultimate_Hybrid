@echo off
title Blockchain Launcher
cd /d "C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate"

echo ========================================
echo STARTING BLOCKCHAIN SERVICES
echo ========================================
echo.

echo [1/4] Starting Node...
start "Blockchain Node" cmd /k "python node_persistent.py"
timeout /t 2 /nobreak > nul

echo [2/4] Starting RPC Proxy...
start "RPC Proxy" cmd /k "python rpc_proxy.py"
timeout /t 1 /nobreak > nul

echo [3/4] Starting Extended API...
start "Extended API" cmd /k "python extended_api_server.py"
timeout /t 1 /nobreak > nul

echo [4/4] Starting WebSocket...
start "WebSocket" cmd /k "python websocket_server.py"

echo.
echo ========================================
echo ALL SERVICES RUNNING
echo ========================================
echo.
echo Web Interface:  http://localhost:8080
echo RPC API:        http://localhost:8545
echo Swagger Docs:   http://localhost:8081/docs
echo WebSocket:      ws://localhost:8546
echo.
echo ========================================
echo Press any key to STOP all services...
pause > nul

echo Stopping all services...
taskkill /f /im python.exe > nul 2>&1
echo Done.
timeout /t 2 /nobreak > nul