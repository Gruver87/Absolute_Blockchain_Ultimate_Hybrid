# Перенос старого кода на рабочий стол в "Начало блокчейна"
# Запуск: .\scripts\move_legacy_to_desktop.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$LegacyRoot = Join-Path ([Environment]::GetFolderPath("Desktop")) "Начало блокчейна"

New-Item -ItemType Directory -Force -Path $LegacyRoot | Out-Null
Set-Location $Root

$moves = @(
    @{ Src = "absolute-blockchain-ultimate"; Dst = "absolute-blockchain-ultimate-копия" },
    @{ Src = "_archive"; Dst = "_archive" },
    @{ Src = "rpc_proxy.py"; Dst = "rpc_proxy.py" },
    @{ Src = "extended_api_server.py"; Dst = "extended_api_server.py" }
)

foreach ($m in $moves) {
    $srcPath = Join-Path $Root $m.Src
    if (-not (Test-Path $srcPath)) {
        Write-Host "[SKIP] $($m.Src) not found" -ForegroundColor Yellow
        continue
    }
    $dstPath = Join-Path $LegacyRoot $m.Dst
    if (Test-Path $dstPath) {
        $stamp = Get-Date -Format "yyyyMMdd_HHmmss"
        $dstPath = "$dstPath`_$stamp"
    }
    Write-Host "[MOVE] $($m.Src) -> $dstPath" -ForegroundColor Cyan
    Move-Item -Path $srcPath -Destination $dstPath -Force
}

$readme = @"
# Начало блокчейна - архив старых версий

Локальная папка на рабочем столе. **Не часть GitHub-релиза v1.0-educational.**

Содержит:
- Старые скрипты и дубликаты (level12_node, indexers, auto_heal и т.д.)
- Копию nested-папки absolute-blockchain-ultimate
- Legacy: rpc_proxy.py, extended_api_server.py

Актуальный учебный проект:
  C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate
  python main.py

Дата переноса: $(Get-Date -Format "yyyy-MM-dd HH:mm")
"@

Set-Content -Path (Join-Path $LegacyRoot "README.txt") -Value $readme -Encoding UTF8
Write-Host ""
Write-Host "Done. Legacy folder: $LegacyRoot" -ForegroundColor Green
