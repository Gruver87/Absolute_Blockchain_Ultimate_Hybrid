#!/usr/bin/env pwsh
# Быстрый запуск unified node (замена start_all_services.bat v57)
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ProjectRoot

Write-Host "=== Absolute Blockchain Ultimate ===" -ForegroundColor Cyan
Write-Host "Entry: python main.py (unified node)" -ForegroundColor Gray
Write-Host "Web:   http://localhost:8080" -ForegroundColor Gray
Write-Host "RPC:   http://localhost:8545" -ForegroundColor Gray
Write-Host ""

if (-not (Test-Path "data")) { New-Item -ItemType Directory -Path "data" | Out-Null }

Start-Process "http://localhost:8080"
python main.py
