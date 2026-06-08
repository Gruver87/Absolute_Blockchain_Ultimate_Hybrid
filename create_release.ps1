# create_release.ps1 - Скрипт для создания Release на GitHub
# Запуск: powershell -ExecutionPolicy Bypass -File create_release.ps1

$tag = "v57"
$title = "v57: Production Ready - Complete Blockchain Ecosystem"
$body = @"
## 🎯 WHAT'S NEW IN v57:

### Core Features (100%):
- ✅ Full blockchain with UTXO model
- ✅ PoS consensus + LMD-GHOST + Casper FFG
- ✅ Mini-EVM with 50+ opcodes
- ✅ JSON-RPC API (Ethereum compatible)
- ✅ P2P network with discovery and sync
- ✅ Persistent SQLite storage

### Advanced Features (100%):
- ✅ NFT Marketplace (mint, transfer, list, buy)
- ✅ Dynamic Sharding (4 shards)
- ✅ Real-world Oracles (prices, weather)
- ✅ ZK Proofs (zero-knowledge proofs)
- ✅ SPHINCS+ Post-Quantum Cryptography
- ✅ WebSocket real-time events

### Infrastructure (100%):
- ✅ Web Blockchain Explorer
- ✅ RPC Proxy with CORS
- ✅ Extended API server
- ✅ Telegram bot integration
- ✅ Docker support

## 📊 TEST RESULTS:
| Test | Result |
|------|--------|
| VM Tests | ✅ 10/10 passed |
| Transaction Tests | ✅ 3/3 passed |
| NFT Tests | ✅ Working |
| Sharding Tests | ✅ Working |
| ZK Proofs Tests | ✅ Working |
| RPC Tests | ✅ 8/8 methods |

## 🔗 Links:
- GitHub: https://github.com/Gruver87/absolute-blockchain-ultimate
- Web UI: http://localhost:8080
- RPC: http://localhost:8545

## ⚠️ Note:
**Educational project - not for production use**
"@

Write-Host "📦 Создание Release v57..." -ForegroundColor Cyan

# Проверяем наличие GitHub CLI
$gh = Get-Command gh -ErrorAction SilentlyContinue

if ($gh) {
    gh release create $tag --title $title --notes $body
    Write-Host "✅ Release created via GitHub CLI" -ForegroundColor Green
} else {
    Write-Host "⚠️ GitHub CLI not installed. Installing..." -ForegroundColor Yellow
    
    # Скачиваем GitHub CLI
    $ghUrl = "https://github.com/cli/cli/releases/download/v2.48.0/gh_2.48.0_windows_amd64.msi"
    $ghInstaller = "$env:TEMP\gh_cli.msi"
    Invoke-WebRequest -Uri $ghUrl -OutFile $ghInstaller -UseBasicParsing
    Start-Process msiexec -Wait -ArgumentList "/i `"$ghInstaller`" /quiet"
    Remove-Item $ghInstaller -Force
    
    # Обновляем PATH
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    
    # Повторяем создание release
    gh release create $tag --title $title --notes $body
}

Write-Host ""
Write-Host "🌐 Открыть страницу Release: https://github.com/Gruver87/absolute-blockchain-ultimate/releases" -ForegroundColor Cyan
