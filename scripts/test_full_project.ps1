# =============================================================================
# ПОЛНЫЙ ТЕСТ ПРОЕКТА — Absolute Blockchain Ultimate Hybrid
# =============================================================================
#
# Запуск из корня репозитория (PowerShell):
#
#   БЫСТРО (без пересборки native, ~2–5 мин):
#     .\scripts\test_full_project.ps1 -SkipNativeBuild
#
#   СТАНДАРТ (рекомендуется перед push, ~5–15 мин):
#     .\scripts\test_full_project.ps1
#
#   МАКСИМУМ (нода должна быть запущена для -Live):
#     .\scripts\test_full_project.ps1 -Live -P2P
#
#   + Docker compose + сборка образов (~30+ мин):
#     .\scripts\test_full_project.ps1 -Docker -DockerBuild -Live -P2P
#
# Что проверяется:
#   - сборка abs_native (Rust/PyO3), self-test крипты
#   - secrets scan, prod_gate, pre_mainnet_audit
#   - rust bridge binary
#   - verify_prod_stack
#   - full_audit.py + ВСЕ pytest (tests/)
#   - критичные hybrid/native/EVM/bridge/sharding тесты
#   - опционально: live HTTP, P2P mesh, Docker compose
#
# Отчёты:
#   data/full_audit_report.json
#   data/final_audit_report.json
#
# Перед -Live запустите ноду (в другом терминале):
#   python main.py --config node.example.json
#   или: .\scripts\start_industrial_devnet.ps1 -Fresh
#
# Не запускайте два devnet на одних портах (8080/8545) одновременно.
# =============================================================================

param(
    [switch]$Live,
    [switch]$P2P,
    [switch]$Docker,
    [switch]$DockerBuild,
    [switch]$BuildRust,
    [switch]$SkipNativeBuild,
    [switch]$NoClean,
    [string]$BaseUrl = "http://127.0.0.1:8080",
    [int]$PytestTimeout = 900,
    [int]$P2PWait = 300,
    [int]$AuditRetries = 1
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $ScriptDir "test_blockchain_full.ps1") @PSBoundParameters
exit $LASTEXITCODE
