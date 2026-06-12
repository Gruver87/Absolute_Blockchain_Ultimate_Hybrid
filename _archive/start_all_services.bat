@echo off
chcp 65001 > nul
title ABSOLUTE BLOCKCHAIN ULTIMATE - FULL NODE

echo.
echo ÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛ
echo ÛÛ     ABSOLUTE BLOCKCHAIN ULTIMATE - Ž‹›‰ ‡€“‘Š           ÛÛ
echo ÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛÛ
echo.

set PROJECT_DIR=C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate
cd /d "%PROJECT_DIR%"

echo ?? à®¥ªâ: %PROJECT_DIR%
echo.

:: à®¢¥àª  Python
python --version > nul 2>&1
if errorlevel 1 (
    echo ? Python ­¥ ­ ©¤¥­! “áâ ­®¢¨â¥ Python 3.11+
    pause
    exit /b 1
)

echo ? Python ­ ©¤¥­
echo.

:: ‡ ¯ãáª ¢ ®â¤¥«ì­ëå ®ª­ å
start "Blockchain Node" cmd /k "cd /d %PROJECT_DIR% && python node_persistent.py"
timeout /t 2 /nobreak > nul

start "RPC Proxy" cmd /k "cd /d %PROJECT_DIR% && python rpc_proxy.py"
timeout /t 1 /nobreak > nul

start "Extended API" cmd /k "cd /d %PROJECT_DIR% && python extended_api_server.py"
timeout /t 1 /nobreak > nul

start "WebSocket" cmd /k "cd /d %PROJECT_DIR% && python websocket_server.py"
timeout /t 1 /nobreak > nul

echo.
echo ÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍ
echo ?? ‚‘… ‘…‚ˆ‘› ‡€“™…›
echo ÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍ
echo.
echo ?? ‚¥¡-¨­â¥àä¥©á:    http://localhost:8080
echo ?? RPC API:          http://localhost:8545
echo ?? Swagger Docs:     http://localhost:8081/docs
echo ?? WebSocket:        ws://localhost:8546
echo.
echo ÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍÍ
echo.
echo  ¦¬¨â¥ «î¡ãî ª« ¢¨èã ¤«ï ®áâ ­®¢ª¨ ¢á¥å á¥à¢¨á®¢...
pause > nul

:: ‡ ªàë¢ ¥¬ ¢á¥ ®ª­  Python
taskkill /f /im python.exe > nul 2>&1
echo.
echo ?? ‚á¥ á¥à¢¨áë ®áâ ­®¢«¥­ë
timeout /t 2 /nobreak > nul
