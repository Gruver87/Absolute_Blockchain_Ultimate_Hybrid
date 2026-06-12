# Absolute Blockchain Ultimate — Справочник команд

> **Версия:** `1.1.0-industrial` (unified node)  
> **Автор:** Uladzimir Dabranski (Gruver87)  
> **Обновлено:** 2026-06-12  
> **Статус:** учебный проект, не production mainnet

---

## ⚠️ Важно: что изменилось с v57

| Было (v57) | Сейчас (unified) |
|------------|------------------|
| `node_persistent.py` + 3 отдельных сервера | **Один** `python main.py` |
| `extended_api_server.py` :8081 | Всё в REST `:8080` |
| `rpc_proxy.py` :8080 | RPC `:8545`, REST `:8080`, dev CORS proxy `:8082` |
| `global_p2p_network.py` отдельно | P2P встроен в `main.py` :5000 |
| `/api/stats`, `/api/peers` | `/status`, `/network/peers` |
| Логи в `logs/` | `data/node.log` |
| Legacy-файлы | Архив: `Desktop/Начало блокчейна` |

**Секреты (API keys, токены, private keys) — только в `.env` локально. Никогда в git и не в этот файл.**

---

## Часть 1: Запуск узла

```powershell
cd C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate
pip install -r requirements.txt
python main.py
```

Альтернатива (deprecated shim):

```powershell
python node_persistent.py   # перенаправляет на main.py
```

### Опции CLI

```powershell
python main.py --mode rpc-only      # без майнинга
python main.py --http-port 8080
python main.py --rpc-port 8545
python main.py --port 5001          # P2P порт
python main.py --data-dir ./data/node2
python main.py --config node.json
python main.py --log-level DEBUG
```

### Prod-профиль (staging/prod)

```powershell
$env:DEPLOYMENT_MODE = "prod"
$env:DATA_DIR = ".\data\node1"
$env:REQUIRE_WALLET_FILE = "true"
$env:JWT_ENFORCE_ADMIN = "true"
$env:CORS_ORIGINS = "http://localhost:8080"
python main.py
```

### Быстрый старт (скрипт)

```powershell
.\scripts\start_node.ps1
```

### Сброс данных (начать с нуля)

```powershell
Remove-Item -Recurse -Force data\* -ErrorAction SilentlyContinue
python main.py
```

### Остановка

- `Ctrl+C` в окне ноды (graceful shutdown HTTP/RPC)
- Или: `Get-Process python | Stop-Process` (жёстко)

---

## Часть 2: Порты и URL

| Сервис | Порт | URL |
|--------|------|-----|
| Web Explorer + REST | **8080** | http://localhost:8080 |
| JSON-RPC | **8545** | http://localhost:8545 |
| P2P | **5000** | TCP |
| WebSocket | **8766** | ws://localhost:8766 |
| Monitor (опц.) | **8092** | http://localhost:8092 |
| CORS RPC proxy (dev) | **8082** | http://localhost:8082 |

---

## Часть 3: Health & метрики (industrial)

```powershell
Invoke-RestMethod http://localhost:8080/health/live
Invoke-RestMethod http://localhost:8080/health/ready
Invoke-RestMethod http://localhost:8080/metrics
Invoke-RestMethod http://localhost:8080/status
```

---

## Часть 4: REST API — основные команды

### Статус и токеномика

```powershell
Invoke-RestMethod http://localhost:8080/status
Invoke-RestMethod http://localhost:8080/tokenomics
Invoke-RestMethod http://localhost:8080/founder
Invoke-RestMethod http://localhost:8080/stats
```

### Блоки и мемпул

```powershell
Invoke-RestMethod http://localhost:8080/blocks
Invoke-RestMethod http://localhost:8080/mempool
Invoke-RestMethod http://localhost:8080/burn-stats
```

### Баланс

```powershell
# Подставьте реальный адрес из wallet.json или /status
$addr = "0xYOUR_ADDRESS"
Invoke-RestMethod "http://localhost:8080/state/balance/$addr"
Invoke-RestMethod "http://localhost:8080/wallet/balance/$addr"
```

### Транзакция (POST)

```powershell
$body = @{
    from   = "0xYOUR_FROM_ADDRESS"
    to     = "0xRECIPIENT_ADDRESS"
    amount = 1.0
    nonce  = 0
    gas    = 21000
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8080/transactions" `
    -Method POST -Body $body -ContentType "application/json"
```

### P2P

```powershell
Invoke-RestMethod http://localhost:8080/network/peers
Invoke-RestMethod http://localhost:8080/network/stats
```

### Валидаторы и консенсус

```powershell
Invoke-RestMethod http://localhost:8080/validators
Invoke-RestMethod http://localhost:8080/consensus/stats
Invoke-RestMethod http://localhost:8080/slashing/status
```

### Pool locks (D.U.P. токеномика)

```powershell
Invoke-RestMethod http://localhost:8080/pools/locks
Invoke-RestMethod http://localhost:8080/pools/dao/status
```

### Light client (SPV)

```powershell
Invoke-RestMethod http://localhost:8080/light/stats
Invoke-RestMethod http://localhost:8080/light/headers
```

---

## Часть 5: JSON-RPC (:8545)

```powershell
# Высота блока
curl.exe -X POST http://localhost:8545 -H "Content-Type: application/json" `
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Баланс
curl.exe -X POST http://localhost:8545 -H "Content-Type: application/json" `
  -d '{"jsonrpc":"2.0","method":"eth_getBalance","params":["0xADDRESS","latest"],"id":1}'

# Последний блок
curl.exe -X POST http://localhost:8545 -H "Content-Type: application/json" `
  -d '{"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":["latest",true],"id":1}'
```

Dev CORS proxy (если `ENABLE_CORS_RPC_PROXY=true`):

```powershell
curl.exe -X POST http://localhost:8082/rpc -H "Content-Type: application/json" `
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

---

## Часть 6: NFT, оракулы, шардинг

Всё доступно через `:8080` после `python main.py` (не нужен отдельный сервер).

### NFT

```powershell
Invoke-RestMethod http://localhost:8080/nft
Invoke-RestMethod http://localhost:8080/nft/listings
Invoke-RestMethod http://localhost:8080/nft/marketplace
```

```powershell
python -c "from features.nft import NFTMarketplace; m=NFTMarketplace(); print(m.get_stats())"
```

### Оракулы

```powershell
Invoke-RestMethod http://localhost:8080/oracles/prices
Invoke-RestMethod "http://localhost:8080/oracles/weather?city=Moscow"
Invoke-RestMethod http://localhost:8080/oracles/stats
```

Ключи погоды — в `.env`: `OPENWEATHER_API_KEY`, `WEATHERAPI_KEY` (без ключей — demo-режим).

### Шардинг

```powershell
Invoke-RestMethod http://localhost:8080/sharding/stats
Invoke-RestMethod http://localhost:8080/sharding/shards
Invoke-RestMethod "http://localhost:8080/sharding/route?address=0xABC"
```

---

## Часть 7: Telegram бот

```powershell
$env:TELEGRAM_BOT_TOKEN = "your_token_from_botfather"
python main.py
# Бот стартует автоматически если токен в env
```

Команды в чате: `/start`, `/balance`, `/block`, `/price`, `/help`

---

## Часть 8: Майнинг

Майнинг **автоматический** — цикл в `main.py` каждые ~15 сек (`block_time`).

```powershell
# Проверить высоту (растёт = блоки создаются)
Invoke-RestMethod http://localhost:8080/status | Select-Object height, mempool_size
```

Отключить: `python main.py --mode rpc-only` или `$env:MINING_ENABLED="false"`

---

## Часть 9: Web UI

```powershell
start http://localhost:8080
```

31 вкладка в SPA (`web/explorer/index.html`): Explorer, Wallet, NFT, Staking, EVM, ZK, Bridge, Pools, Light Client и др.

---

## Часть 10: Тестирование

```powershell
pytest tests/ -q
python test_merkle_light.py
python scripts/load_test.py --spawn-local
python _final_audit.py
```

---

## Часть 11: Docker & HA

```powershell
# Одна нода
docker compose up --build

# 3 ноды + Redis
docker compose -f docker-compose.ha.yml up --build

# Kubernetes
kubectl apply -k deploy/k8s/
```

---

## Часть 12: Бэкап

```powershell
python scripts/backup_db.py
python scripts/backup_db.py --db data/blockchain.db
```

---

## Часть 13: Диагностика

```powershell
netstat -an | findstr "8545 8080 5000 8766"
Get-Process python -ErrorAction SilentlyContinue

# Лог узла
Get-Content data\node.log -Tail 50

# Монитор (если запущен)
Invoke-RestMethod http://localhost:8092/api/monitor/metrics
```

---

## Часть 14: Git

```powershell
cd C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate
git status
git pull origin master
git push origin master
```

---

## Часть 15: Полезные пути

| Что | Путь |
|-----|------|
| Точка входа | `main.py` |
| REST API | `api/http.py` |
| Web UI | `web/explorer/index.html` |
| База данных | `data/blockchain.db` |
| Кошелёк (локально) | `data/wallet.json` |
| Конфиг env | `.env` (из `.env.example`) |
| Legacy v57 | `Desktop/Начало блокчейна` |
| Roadmap | `docs/INDUSTRIAL_ROADMAP.md` |

---

## Часть 16: Параметры сети

| Параметр | Значение |
|----------|----------|
| Chain ID | 1337 |
| Символ | ABS |
| Max supply | 221 000 000 |
| Founder D.U.P. | 17.4% (38 454 000 ABS) |
| Block time | ~15 сек |
| Epoch | 32 блока |
| Burn | 2% комиссии |

---

## Ссылки

- GitHub: https://github.com/Gruver87/absolute-blockchain-ultimate
- Releases: https://github.com/Gruver87/absolute-blockchain-ultimate/releases
- CI Actions: https://github.com/Gruver87/absolute-blockchain-ultimate/actions

---

*Конец справочника — unified industrial edition*
