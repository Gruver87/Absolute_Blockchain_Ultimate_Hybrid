# Absolute Blockchain Ultimate

> **Учебно-экспериментальный блокчейн-клиент на Python** — единая нода, REST/RPC API, веб-эксплорер, PoS-консенсус, токеномика ABS.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Educational%20Only-orange.svg)]()
[![API Wave](https://img.shields.io/badge/API%20Wave-45-blue.svg)](CHANGELOG.md)
[![Tests](https://img.shields.io/badge/Unit%20Tests-195%20passed-brightgreen.svg)](tests/unit/)
[![Release](https://img.shields.io/badge/Release-v1.2.0--industrial-blue.svg)](https://github.com/Gruver87/absolute-blockchain-ultimate/releases/tag/v1.2.0-industrial)

**Репозиторий:** [github.com/Gruver87/absolute-blockchain-ultimate](https://github.com/Gruver87/absolute-blockchain-ultimate)

**Версия:** `1.2.0-industrial` · **API Wave:** `45` · **Проверка:** `GET /status` → поле `api_wave`

| Документация | Ссылка |
|--------------|--------|
| Changelog (Wave 37–45) | [CHANGELOG.md](CHANGELOG.md) |
| Все команды (честно) | [docs/ALL_COMMANDS.txt](docs/ALL_COMMANDS.txt) |
| Roadmap | [docs/INDUSTRIAL_ROADMAP.md](docs/INDUSTRIAL_ROADMAP.md) |
| Команды (кратко) | [docs/COMMANDS_REFERENCE.md](docs/COMMANDS_REFERENCE.md) |
| Observability | [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md) |

---

## ⚠️ Это НЕ реальная блокчейн-сеть

```
╔══════════════════════════════════════════════════════════════════════╗
║  УЧЕБНЫЙ / ЭКСПЕРИМЕНТАЛЬНЫЙ ПРОЕКТ — НЕ PRODUCTION                  ║
║                                                                      ║
║  ❌ Не используйте для реальных денег или ценных активов             ║
║  ❌ Безопасность, аудит и консенсус не гарантируются                 ║
║  ❌ Токен ABS здесь — учебная модель, не листинг и не криптовалюта   ║
║                                                                      ║
║  ✅ Изучение архитектуры блокчейна, API, консенсуса, состояния      ║
║  ✅ Локальные эксперименты, демо, портфолио, форки                 ║
║  ✅ Доработка сообществом — приветствуются PR и идеи               ║
╚══════════════════════════════════════════════════════════════════════╝
```

Подробнее: [DISCLAIMER.md](DISCLAIMER.md)

---

## О проекте

**Absolute Blockchain Ultimate** — монорепозиторий с **одной точкой входа** `main.py`, который поднимает полный учебный узел:

| Компонент | Описание |
|-----------|----------|
| **Ядро L1** | Блоки, транзакции, burn 2%, genesis, SQLite persistence |
| **Токеномика** | Max supply **221 000 000 ABS**, основатель **D.U.P.** (17.4%) |
| **Консенсус** | PoS-адаптер, эпохи, slashing, beacon/Casper-модули |
| **API** | **256** REST handlers в `api/http.py`; OpenAPI в `/docs` |
| **Web UI** | SPA-эксплорер **32 вкладки** — `http://localhost:8080` |
| **P2P** | TCP gossip, fast-sync, reorg, state_root verify |
| **L2 / demo** | Lightning, Plasma, WASM, Crypto Will, AI agents, MEV — с SQLite где указано |

Полный честный список возможностей — **Часть 0** в [`docs/ALL_COMMANDS.txt`](docs/ALL_COMMANDS.txt).

Это **Mini-Ethereum-стиль** для обучения, а не конкурент Ethereum или Bitcoin.

---

## Что нового (Wave 37–45)

Краткая сводка последних волн разработки. Подробности — в [CHANGELOG.md](CHANGELOG.md).

| Wave | Суть |
|------|------|
| **37–38** | EVM hardening (LOG, EXTCODE, SELFDESTRUCT…), bytecode validator, EVM logs в SQLite |
| **39** | Oracle feed registry (HMAC), bridge L1 queue, `GET /oracles/feeds` |
| **40** | Lightning + Plasma: SQLite persistence, open/deposit/exit влияют на L1 ABS |
| **41** | Crypto Will: завещания в SQLite, execute/cancel с L1-эффектами |
| **42** | WASM VM persistence, deploy fee, `GET /bridge/relayer/status` |
| **43** | AI agents в SQLite, plasma submit hints |
| **44** | `GET /l2/status` (единый дашборд), MEV history в SQLite |
| **45** | Reorg predictor в SQLite, исправлены `/reorg/*`, dev bridge confirm |

Проверка версии после старта узла:

```powershell
(Invoke-RestMethod http://localhost:8080/status -UseBasicParsing).api_wave
# ожидается: 45
```

---

## Токеномика (учебная модель)

| Параметр | Значение |
|----------|----------|
| Символ | **ABS** |
| Max supply | **221 000 000** |
| Основатель | **Uladzimir Dabranski** (инициалы **D.U.P.**, alias Gruver87) |
| Доля основателя | **17.4%** = **38 454 000 ABS** |
| Ecosystem | 10% (DAO unlock) |
| Treasury | 10% (DAO unlock) |
| Staking pool | 12.6% (release по эпохам, 32 блока) |
| Mining emission | 50% (block rewards до cap) |

Конфиг: `runtime/tokenomics.py`, `runtime/config.py`

---

## Быстрый старт

### Требования

- Python **3.10+** (проверено на 3.11–3.13)
- Windows / Linux / macOS
- **Docker Desktop** — только для `docker_devnet.ps1` (опционально)

### Установка

```bash
git clone https://github.com/Gruver87/absolute-blockchain-ultimate.git
cd absolute-blockchain-ultimate
pip install -r requirements.txt
cp .env.example .env          # секреты только здесь, не в git
cp wallet.example.json data/wallet.json   # локальный кошелёк (не коммитить ключи)
```

### Запуск одного узла

```bash
python main.py
```

Опции:

```bash
python main.py --mode rpc-only    # без майнинга
python main.py --port 5001        # другой P2P-порт
python main.py --config node.json # свой конфиг
```

### Интерфейсы после старта

| Сервис | URL |
|--------|-----|
| **Web Explorer** | http://localhost:8080 |
| **REST API** | http://localhost:8080/status |
| **L2 dashboard** | http://localhost:8080/l2/status |
| **JSON-RPC** | http://localhost:8545 |
| **WebSocket** | ws://localhost:8766 |
| **P2P** | `:5000` |

### Два узла (рекомендуется для P2P)

**Локально (без Docker):**

```powershell
.\scripts\stop_node.ps1
.\scripts\start_two_nodes.ps1 -RustBridge   # node1 :8080, node2 :8081, rust bridge на node1
```

**Docker devnet (2 контейнера):**

```powershell
# 1. Запустите Docker Desktop и дождитесь статуса "Running"
.\scripts\docker_devnet.ps1 -RustBridge
```

| Режим | Команда | `bridge_mode` на node1 |
|-------|---------|------------------------|
| Simulator | `.\scripts\docker_devnet.ps1` | `simulator` |
| Rust bridge | `.\scripts\docker_devnet.ps1 -RustBridge` | `rust` |

После успешного старта скрипт выводит:

```
OK: peers n1=1 n2=1 heights ... / ... state_roots_match=True
```

> **Важно:** сразу после `docker compose up` API может быть недоступен 10–30 с.  
> Скрипт `docker_devnet.ps1` ждёт готовности; при ручных запросах сначала проверьте `/health/live`.

### Проверка API

```powershell
curl.exe http://localhost:8080/health/live
curl.exe http://localhost:8080/status
curl.exe http://localhost:8080/l2/status
curl.exe http://localhost:8080/oracles/feeds
curl.exe "http://localhost:8080/reorg/depth?network_hashrate=100&attacker_hashrate=10"
```

```bash
pytest tests/unit -q    # 195 passed, 1 skipped (июнь 2026)
```

### Devnet helpers

```powershell
# Faucet
Invoke-RestMethod -Method POST http://localhost:8080/devnet/faucet `
  -ContentType "application/json" `
  -Body '{"address":"0x...","amount":100}'

# Подтвердить pending bridge locks без HMAC (только dev)
Invoke-RestMethod -Method POST http://localhost:8080/bridge/dev-confirm-pending -UseBasicParsing
```

Секреты (`BRIDGE_ORACLE_SECRET`, `TELEGRAM_BOT_TOKEN`, RPC keys) — **только в `.env`**, см. `.env.example`.

---

## Что реально работает (проверено локально, июнь 2026)

| Компонент | Статус | Примечание |
|-----------|--------|------------|
| Core blockchain + SQLite | 🟢 | Блоки, балансы, validators |
| Mining (~15s) + эмиссия ABS | 🟢 | До cap 221M |
| REST API `:8080` | 🟢 | 256 routes, `/docs` |
| JSON-RPC `:8545` | 🟢 | eth_* подмножество |
| WebSocket + Explorer | 🟢 | Live feed |
| P2P 2-node sync | 🟢 | `start_two_nodes.ps1` или Docker |
| Fork reorg + state_root verify | 🟢 | |
| Oracle registry (Wave 39) | 🟢 | SQLite feeds |
| Lightning / Plasma L2 (Wave 40) | 🟡 | Demo + SQLite + L1 effects |
| Crypto Will (Wave 41) | 🟡 | SQLite + L1 lock/transfer |
| WASM VM (Wave 42) | 🟡 | SQLite, deploy fee |
| AI agents (Wave 43) | 🟡 | SQLite |
| MEV simulator (Wave 44) | 🟡 | SQLite history |
| Reorg predictor (Wave 45) | 🟡 | SQLite assessments |
| Bridge rust mode | 🟡 | `-RustBridge`; L1 RPC опционален |
| Production mainnet | 🔴 | Не цель проекта |

🟡 = учебный / demo-модуль с реальным поведением там, где описано в docs; не аудирован для prod.

---

## Структура проекта

```
absolute-blockchain-ultimate/
├── main.py                 # Единственная точка входа узла
├── api/http.py             # REST + RPC (256 handlers)
├── web/explorer/index.html # Браузерный SPA (32 вкладки)
├── core/blockchain.py      # Блоки, транзакции, genesis
├── runtime/                # config, tokenomics, pool_locks
├── consensus/              # PoS, эпохи, slashing, finality
├── execution/              # VM, state engine, contracts
├── features/               # L2, NFT, ZK, oracles, reorg, MEV…
├── storage/database.py     # SQLite (L1 + L2 tables)
├── bridge/                 # Cross-chain (sim + rust binary)
├── scripts/                # docker_devnet, start_two_nodes, audits
├── tests/unit/             # pytest (195 tests)
├── docs/ALL_COMMANDS.txt   # Честный справочник (Часть 0)
└── CHANGELOG.md            # Wave 37–45
```

Подробная архитектура: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)

---

## API (ключевые эндпоинты)

```bash
GET  /status              # api_wave, peers, bridge_mode, l2 flags
GET  /l2/status           # Lightning, Plasma, Will, WASM, AI
GET  /features            # feature flags + persisted modules
GET  /oracles/feeds       # signed oracle registry
GET  /bridge/relayer/status
GET  /reorg/depth         # ?network_hashrate=&attacker_hashrate=
GET  /reorg/fork          # live P2P gaps или chain JSON в query
GET  /reorg/history
GET  /mev/history
GET  /tokenomics
POST /bridge/dev-confirm-pending   # dev only
```

Полный список — `api/http.py`, `/docs`, `docs/ALL_COMMANDS.txt`.

---

## Устранение проблем

### Docker is not running

Запустите **Docker Desktop**, дождитесь **Running**, затем:

```powershell
.\scripts\docker_devnet.ps1 -RustBridge
```

### Соединение закрыто сразу после `docker compose up`

Узел ещё инициализируется. Подождите 10–30 с или используйте `docker_devnet.ps1`.

### `api_wave` меньше 45 в Docker

Образ устарел — пересоберите:

```powershell
docker compose -f docker-compose.devnet-rust.yml build --no-cache node1
docker compose -f docker-compose.devnet-rust.yml up -d --force-recreate node1
```

### Порты заняты

```powershell
.\scripts\stop_node.ps1
```

---

## Тестирование

```bash
pytest tests/unit -q
python scripts/mega_audit.py
.\scripts\verify_endpoints.ps1
```

---

## Как помочь проекту

1. ⭐ **Star** на GitHub  
2. 🍴 **Fork** и эксперименты в своей ветке  
3. 🐛 **Issues** — баги и идеи  
4. 🔧 **Pull Requests** — код, тесты, документация  

См. [CONTRIBUTING.md](CONTRIBUTING.md)

---

## Автопост для комьюнити (каждые 3 дня + при обновлениях)

GitHub Actions публикует посты о проекте в **Telegram-канал** (и опционально Discord).

| Когда | Что публикуется |
|-------|-----------------|
| **Каждые 3 дня** (cron) | Ротация постов: devnet, Wave 45, токеномика, призыв star/fork |
| **Push в `master`** | Пост «обновление» с последними коммитами |
| **Вручную** | Actions → Community Autopost → Run workflow |

### Настройка (один раз)

1. Создайте **Telegram-канал** (или группу) для комьюнити.
2. Добавьте вашего бота **администратором** канала (права на публикацию).
3. Узнайте `chat_id` канала (например через `@userinfobot` или `getUpdates` после сообщения в канал).
4. В GitHub: **Settings → Secrets and variables → Actions** добавьте:

| Secret | Значение |
|--------|----------|
| `TELEGRAM_BOT_TOKEN` | Токен от @BotFather |
| `TELEGRAM_CHANNEL_ID` | ID канала, напр. `-1001234567890` |
| `DISCORD_WEBHOOK_URL` | *(опционально)* webhook Discord |

5. Workflow: [`.github/workflows/community-autopost.yml`](.github/workflows/community-autopost.yml)

Пропустить пост при коммите: добавьте `[skip community]` в сообщение коммита.

### Локальный тест (без отправки)

```powershell
.\scripts\run_community_autopost.ps1 -Mode scheduled
.\scripts\run_community_autopost.ps1 -Mode release -Send   # реальная отправка
```

---

## Автор

**Uladzimir Dabranski** (инициалы **D.U.P.**)

- GitHub: [@Gruver87](https://github.com/Gruver87)
- Репозиторий: [absolute-blockchain-ultimate](https://github.com/Gruver87/absolute-blockchain-ultimate)
- Email: gruverpetrov@gmail.com

---

## Лицензия

[MIT License](LICENSE) — свободно для обучения, форков и экспериментов.  
**Без гарантий.** См. [DISCLAIMER.md](DISCLAIMER.md).

---

*Последнее обновление: июнь 2026 — API Wave 45, Docker 2-node P2P verified, 195 unit tests, честная документация Wave 37–45.*
