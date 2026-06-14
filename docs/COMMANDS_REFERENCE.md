# Absolute Blockchain Ultimate — Справочник команд

> **Версия:** `1.2.0-industrial` (unified node)  
> **Автор:** Uladzimir Dabranski (Gruver87)  
> **Обновлено:** 2026-06-12  
> **Статус:** учебный проект, не production mainnet  
> **Заменяет:** справочник v57 (2026-06-08)

---

## Миграция v57 → v1.2.0 (полная таблица)

| v57 (Часть) | Старый способ | Сейчас (unified) |
|-------------|---------------|------------------|
| 1 Нода | `python node_persistent.py` | `python main.py` или `.\scripts\start_node.ps1` |
| 2 Extended API :8081 | `python extended_api_server.py` | REST на **:8080** (встроено в `main.py`) |
| 3 RPC proxy :8080 | `python rpc_proxy.py` | RPC **:8545**, REST **:8080**, dev CORS **:8082/rpc** |
| 4 Оракулы отдельно | `python real_world_oracles.py` | `/oracles/*` на :8080, ключи в `.env` |
| 5 Шардинг отдельно | `python dynamic_sharding.py` | `/sharding/*` на :8080 |
| 6 NFT отдельно | `python nft_core.py` | `/nft/*` на :8080 + `features/nft.py` |
| 7 P2P отдельно | `python global_p2p_network.py` | P2P **:5000** в `main.py` |
| 8 Telegram отдельно | `python telegram_super_bot.py` | Автостарт из `.env` `TELEGRAM_BOT_TOKEN` |
| 9 HTTP картинок :8081 | `python -m http.server 8081` | Explorer :8080, NFT в `/nft` |
| 10 Тесты | `test_vm_complete.py`, `quick_test.py` | `pytest tests/ -q` |
| 11 Транзакции | `/api/balance`, `/api/transaction/send` | `/wallet/balance/`, `/transactions` POST |
| 12 Майнинг POST | `/api/mine` | Автоматический цикл в `main.py` (~15 сек) |
| 13 Web UI | много URL на :8080/:8081 | **Один** SPA: http://localhost:8080 |
| 14 Блоки | RPC + `/api/stats` | `/blocks`, `/status`, RPC `eth_*` |
| 15 Слэшинг | скрипт Python | `/slashing/status`, встроено в консенсус |
| 16 Запуск всего стека | `start_all_services.bat` (3 окна) | **Одна** команда `start_node.ps1` |
| 17 Остановка | `Stop-Process python` | `.\scripts\stop_node.ps1` |
| 18 Очистка data | `Remove-Item data\*` | то же (осторожно: потеряете цепочку) |
| 19 Логи `logs/` | `logs/blockchain.log` | `data/node.log` |
| 20 Диагностика | netstat 8545/8080/8081/5000 | + 8766 WS, 8092 monitor, 8082 proxy |
| 21–22 Git / бэкап | git + zip | `scripts/backup_db.py`, `backup_scheduled.ps1` |
| 23 Секреты в .txt | **ОПАСНО** | Только локальный `.env` (см. ниже) |
| 24–26 Пути / ссылки | v57 пути | см. Часть 15 ниже |

**Секреты из v57 Части 23 никогда не копируйте в git, чаты и markdown.**  
Локально: скопируйте `.env.example` → `.env` или выполните `python scripts/apply_local_secrets.py` (читает Desktop-файл команд, если он есть).

---

## Часть 1: Запуск узла

```powershell
cd C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate
pip install -r requirements.txt
.\scripts\start_node.ps1
```

Или напрямую:

```powershell
python main.py
```

Deprecated (перенаправляет на `main.py`):

```powershell
python node_persistent.py
```

### Опции CLI

```powershell
python main.py --mode rpc-only      # без майнинга
python main.py --http-port 8080
python main.py --rpc-port 8545
python main.py --port 5001          # P2P порт
python main.py --data-dir ./data/node2
python main.py --config node.json
python main.py --config node2.example.json   # порты из JSON перекрывают .env
python main.py --log-level DEBUG
```

Порядок конфигурации: **`.env` → JSON-файл узла → CLI`**.  
Для второго узла используйте `node2.example.json` (P2P `:5001`, REST `:8081`).

### Prod-профиль

Скопируйте `node.prod.example.json`, соберите Rust-мост и задайте секреты:

```powershell
.\scripts\build_bridge.ps1
copy node.prod.example.json node.prod.json
# data\wallet.json — обязателен; RPC_API_KEYS и JWT_SECRET в .env
$env:JWT_SECRET = "your-secret"
$env:RPC_API_KEYS = "your-rpc-key"
$env:BRIDGE_MODE = "rust"
$env:RUST_BRIDGE_PATH = "bridge\abs_bridge_bin.exe"
python main.py --config node.prod.json
```

Минимальный prod через env:

```powershell
$env:DEPLOYMENT_MODE = "prod"
$env:DATA_DIR = ".\data\node1"
$env:REQUIRE_WALLET_FILE = "true"
$env:JWT_ENFORCE_ADMIN = "true"
$env:CORS_ORIGINS = "http://localhost:8080"
python main.py
```

### Сброс данных (v57 Часть 18)

```powershell
.\scripts\stop_node.ps1
Remove-Item -Recurse -Force data\* -ErrorAction SilentlyContinue
python main.py
```

### Остановка (v57 Части 1.2, 17)

```powershell
.\scripts\stop_node.ps1
```

- `Ctrl+C` в окне ноды (graceful shutdown)
- Перед повторным запуском — `stop_node.ps1` (иначе WinError 10048 на P2P/WS)

---

## Часть 2: Порты и URL

| Сервис | v57 | v1.2.0 |
|--------|-----|--------|
| Web Explorer + REST | :8080 (proxy) | **:8080** |
| Extended API | :8081 | объединён в :8080 |
| JSON-RPC | :8545 | **:8545** |
| P2P | :5000 / :4567 | **:5000** |
| WebSocket | — | **:8766** |
| Monitor | — | **:8092** |
| CORS RPC proxy (dev) | — | **:8082/rpc** |

---

## Часть 3: Health и метрики

```powershell
Invoke-RestMethod http://localhost:8080/health/live
Invoke-RestMethod http://localhost:8080/health/ready
Invoke-RestMethod http://localhost:8080/metrics
Invoke-RestMethod http://localhost:8080/status
```

---

## Часть 4: REST API

### Статус и токеномика (221M, D.U.P. 17.4%)

```powershell
Invoke-RestMethod http://localhost:8080/status
Invoke-RestMethod http://localhost:8080/tokenomics
Invoke-RestMethod http://localhost:8080/founder
Invoke-RestMethod http://localhost:8080/stats
Invoke-RestMethod http://localhost:8080/allocation
```

### Блоки и мемпул (v57 Часть 14)

```powershell
Invoke-RestMethod http://localhost:8080/blocks
Invoke-RestMethod http://localhost:8080/mempool
Invoke-RestMethod http://localhost:8080/burn-stats
```

### Баланс (v57 Часть 11.1)

```powershell
# Founder D.U.P. (текущая токеномика v1.2)
$founder = "0xbeb0962327d6f0ad8de263bd883bb184e88744a2"
Invoke-RestMethod "http://localhost:8080/wallet/balance/$founder"

# Любой адрес
$addr = "0xYOUR_ADDRESS"
Invoke-RestMethod "http://localhost:8080/state/balance/$addr"
```

### Транзакция POST (v57 Часть 11.2)

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

# Алиас + авто-подпись (если в .env задан WALLET_PRIVATE_KEY):
$body = @{
    auto_sign = $true
    to        = "0xRECIPIENT_ADDRESS"
    value     = 1.0
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8080/tx/send" `
    -Method POST -Body $body -ContentType "application/json"

Invoke-RestMethod http://localhost:8080/wallet/status
```

### P2P (v57 Часть 7)

```powershell
Invoke-RestMethod http://localhost:8080/peers
Invoke-RestMethod http://localhost:8080/network/peers
Invoke-RestMethod http://localhost:8080/network/stats
Invoke-RestMethod http://localhost:8080/sync/status
```

Два узла (devnet):

```powershell
.\scripts\stop_node.ps1
.\scripts\start_two_nodes.ps1
.\scripts\start_two_nodes.ps1 -RustBridge
```

`-RustBridge` — node1 с `node.rust.example.json` (`bridge_mode=rust`), при отсутствии бинарника вызывает `scripts/build_bridge.ps1`.

Скрипт:
- клонирует `data/blockchain.db` в `data/node2/` (одинаковая высота, без replay 4000+ блоков);
- поднимает node1 (`node.example.json` :8080) и node2 (`node2.example.json` :8081) в фоне;
- ждёт P2P и синхронизацию высот;
- запускает `python scripts/verify_p2p_ci.py --mode devnet`.

Проверка вручную:

```powershell
.\scripts\verify_p2p.ps1
python scripts/verify_p2p_ci.py
python scripts/verify_p2p_ci.py --mode devnet
```

Логи: `data/node_stdout.log`, `data/node2/node_stdout.log`, PID-файл `data/node_pids.json`.

Остановка: `.\scripts\stop_node.ps1`

### Мост и документация API

```powershell
Invoke-RestMethod http://localhost:8080/bridge
Invoke-RestMethod http://localhost:8080/bridge/locks
Invoke-RestMethod http://localhost:8080/openapi.json
# Браузер: http://localhost:8080/docs
```

### Валидаторы и слэшинг (v57 Часть 15)

```powershell
Invoke-RestMethod http://localhost:8080/validators
Invoke-RestMethod http://localhost:8080/consensus/stats
Invoke-RestMethod http://localhost:8080/slashing/status
```

### Pool locks

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
curl.exe -X POST http://localhost:8545 -H "Content-Type: application/json" `
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

curl.exe -X POST http://localhost:8545 -H "Content-Type: application/json" `
  -d '{"jsonrpc":"2.0","method":"eth_getBalance","params":["0xADDRESS","latest"],"id":1}'

curl.exe -X POST http://localhost:8545 -H "Content-Type: application/json" `
  -d '{"jsonrpc":"2.0","method":"eth_getBlockByNumber","params":["latest",true],"id":1}'
```

### RPC API Key (prod)

```powershell
python scripts/generate_rpc_key.py
# .env: RPC_API_KEY_REQUIRED=true, RPC_API_KEYS=<key>
```

Dev CORS (v57 proxy :8080/rpc → сейчас :8082/rpc):

```powershell
curl.exe -X POST http://localhost:8082/rpc -H "Content-Type: application/json" `
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

### Несколько транзакций подряд (v57 Часть 11.3)

```powershell
python -c @"
import requests, time
for i in range(3):
    tx = {'from':'0xFROM','to':f'0x{i+1:040x}','value':'0x64','gas':'0x5208','gasPrice':'0x1'}
    r = requests.post('http://localhost:8545', json={'jsonrpc':'2.0','method':'eth_sendTransaction','params':[tx],'id':i+1})
    print(f'Tx {i+1}:', r.json())
    time.sleep(0.5)
"@
```

---

## Часть 6: NFT (v57 Часть 6)

```powershell
Invoke-RestMethod http://localhost:8080/nft
Invoke-RestMethod http://localhost:8080/nft/listings
Invoke-RestMethod http://localhost:8080/nft/marketplace
Invoke-RestMethod http://localhost:8080/nft/auctions
```

```powershell
python -c "from features.nft import NFTMarketplace; m=NFTMarketplace(); print(m.get_stats())"
```

```powershell
start http://localhost:8080
```

---

## Часть 7: Оракулы (v57 Часть 4)

```powershell
Invoke-RestMethod http://localhost:8080/oracles/prices
Invoke-RestMethod "http://localhost:8080/oracles/weather?city=Moscow"
Invoke-RestMethod "http://localhost:8080/oracles/weather?city=London"
Invoke-RestMethod http://localhost:8080/oracles/stats
```

Ключи в `.env`: `OPENWEATHER_API_KEY`, `WEATHERAPI_KEY` (без ключей — demo).

---

## Часть 8: Шардинг (v57 Часть 5)

```powershell
Invoke-RestMethod http://localhost:8080/sharding/stats
Invoke-RestMethod http://localhost:8080/sharding/shards
Invoke-RestMethod "http://localhost:8080/sharding/route?address=0xABC"
```

---

## Часть 9: Telegram (v57 Часть 8)

Токен только в локальном `.env`:

```powershell
# .env: TELEGRAM_BOT_TOKEN=<from BotFather>
python main.py
```

Команды в чате: `/start`, `/balance`, `/block`, `/price`, `/weather`, `/nft`, `/help`

---

## Часть 10: Майнинг (v57 Часть 12)

Автоматически в `main.py` каждые ~15 сек. Ручной POST `/api/mine` больше не нужен.

```powershell
Invoke-RestMethod http://localhost:8080/status | Select-Object height
```

Отключить: `python main.py --mode rpc-only`

---

## Часть 11: Web UI (v57 Часть 13)

```powershell
start http://localhost:8080
```

31 вкладка SPA: Explorer, Wallet, NFT, Staking, EVM, WASM, Lightning, Plasma, ZK, Bridge, AI, MEV и др.

---

## Часть 12: Тестирование (v57 Часть 10)

```powershell
pytest tests/ -q
python tests/smoke/merkle_light.py
python scripts/load_test.py --spawn-local
python scripts/final_audit.py
```

Примеры из v57 (если файлы есть):

```powershell
python -c "from consensus.slashing import SlashingEngine; e=SlashingEngine(); print(e.get_stats())"
```

---

## Часть 13: Docker, HA, observability

```powershell
docker compose up --build
docker compose -f docker-compose.ha.yml up --build
docker compose -f docker-compose.observability.yml up
kubectl apply -k deploy/k8s/
```

```powershell
$env:LOG_JSON = "true"
python main.py
```

- Metrics: http://localhost:8080/metrics  
- Grafana: `deploy/grafana/dashboard.json`

---

## Часть 14: Бэкап (v57 Часть 22)

```powershell
python scripts/backup_db.py
.\scripts\backup_scheduled.ps1

$ts = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item data\blockchain.db "C:\Users\vovun\Desktop\blockchain_backup_$ts.db"
```

---

## Часть 15: Диагностика (v57 Части 19–20)

```powershell
netstat -an | findstr "8545 8080 5000 8766 8082 8092"
Get-Process python -ErrorAction SilentlyContinue

Get-Content data\node.log -Tail 50
Invoke-RestMethod http://localhost:8092/api/monitor/metrics -ErrorAction SilentlyContinue

curl.exe -X POST http://localhost:8545 -H "Content-Type: application/json" `
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
```

---

## Часть 16: Секреты и кошельки (v57 Часть 23 — БЕЗОПАСНО)

**Не храните ключи в `.txt`, чатах и git.** Только локальный `.env`:

```powershell
Copy-Item .env.example .env
# Заполните вручную или:
python scripts/apply_local_secrets.py
```

| Переменная | Назначение |
|------------|------------|
| `TELEGRAM_BOT_TOKEN` | Telegram бот |
| `OPENWEATHER_API_KEY` | Оракул погоды |
| `WEATHERAPI_KEY` | Оракул погоды (запасной) |
| `WALLET_PRIVATE_KEY` | ECDSA 64 hex (подпись TX) |
| `JWT_SECRET` | Admin API (prod) |
| `RPC_API_KEYS` | RPC auth (prod) |

### Кошельки v1.2 vs v57

| Роль | v57 | v1.2.0-industrial |
|------|-----|-------------------|
| Founder D.U.P. (221M, 17.4%) | `0x40e908...` (старая модель) | `0xbeb0962327d6f0ad8de263bd883bb184e88744a2` |
| Файл | `data/wallet.json` | то же |
| Подпись | нужен `private_key` в json или `WALLET_PRIVATE_KEY` в `.env` | то же |

Если в `wallet.json` только `address` + `public_key` — добавьте `WALLET_PRIVATE_KEY` в `.env` или поле `private_key` в json (локально).

**Срочно:** если v57 Часть 23 когда-либо попадала в git/чат — перевыпустите Telegram, API погоды, Ngrok, SSH.

---

## Часть 17: Git (v57 Часть 21)

```powershell
cd C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate
git status
git pull origin master
git push origin master
```

Перед push: `python scripts/check_secrets.py`

---

## Часть 18: Полезные пути (v57 Часть 24)

| Что | Путь |
|-----|------|
| Точка входа | `main.py` |
| REST API | `api/http.py` |
| Web UI | `web/explorer/index.html` |
| База данных | `data/blockchain.db` |
| Кошелёк | `data/wallet.json` (gitignore) |
| Секреты | `.env` (gitignore) |
| Лог | `data/node.log` |
| Справочник | `docs/COMMANDS_REFERENCE.md` |
| Legacy v57 | `Desktop/Начало блокчейна` |

---

## Часть 19: Параметры сети (v57 Часть 26)

| Параметр | v57 | v1.2.0 |
|----------|-----|--------|
| Chain ID | 1337 | 1337 |
| RPC | 8545 | 8545 |
| Web | 8080 | 8080 |
| Extended API | 8081 | объединён в 8080 |
| P2P | 5000, 4567 | 5000 |
| Block time | ~15 сек | ~15 сек |
| Max supply | — | **221 000 000 ABS** |
| Founder D.U.P. | — | **17.4%** (38 454 000 ABS) |
| Burn | — | 2% комиссии |

---

## Ссылки (v57 Часть 25)

- GitHub: https://github.com/Gruver87/absolute-blockchain-ultimate
- Releases: https://github.com/Gruver87/absolute-blockchain-ultimate/releases
- Actions: https://github.com/Gruver87/absolute-blockchain-ultimate/actions

---

*Конец справочника — unified industrial edition (замена v57)*
