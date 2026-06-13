# Absolute Blockchain Ultimate

> **Учебно-экспериментальный блокчейн-клиент на Python** — единая нода, REST/RPC API, веб-эксплорер, PoS-консенсус, токеномика ABS.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Educational%20Only-orange.svg)]()
[![Industrial](https://img.shields.io/badge/Profile-Industrial%20Educational-blue.svg)](docs/INDUSTRIAL_ROADMAP.md)
[![Release](https://img.shields.io/badge/Release-v1.2.0--industrial-blue.svg)](https://github.com/Gruver87/absolute-blockchain-ultimate/releases/tag/v1.2.0-industrial)

**Репозиторий:** [github.com/Gruver87/absolute-blockchain-ultimate](https://github.com/Gruver87/absolute-blockchain-ultimate)

**Версия:** 1.2.0-industrial

| Документация | Ссылка |
|--------------|--------|
| Roadmap | [docs/INDUSTRIAL_ROADMAP.md](docs/INDUSTRIAL_ROADMAP.md) |
| Команды | [docs/COMMANDS_REFERENCE.md](docs/COMMANDS_REFERENCE.md) |
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

**Если проект полезен для обучения — поставьте ⭐, форкните и продвигайте дальше.**  
Любой может развивать код: улучшать консенсус, безопасность, P2P, документацию, тесты.

---

## О проекте

**Absolute Blockchain Ultimate** — монорепозиторий с **одной точкой входа** `main.py`, который поднимает полный учебный узел:

| Компонент | Описание |
|-----------|----------|
| **Ядро** | Блоки, транзакции, burn 2%, genesis, SQLite |
| **Токеномика** | Max supply **221 000 000 ABS**, основатель **D.U.P.** (17.4%) |
| **Консенсус** | PoS-адаптер, эпохи, slashing, beacon/Casper-модули |
| **API** | **~100+** REST handlers в `api/http.py`; **16** документированы в `/openapi.json` и `/docs` |
| **Web UI** | SPA-эксплорер **31 вкладка** — `http://localhost:8080` |
| **Light Client** | SPV / Merkle proofs |
| **Pool Locks** | Блокировка ecosystem/treasury, staking release по эпохам |
| **Features** | NFT, ZK, Lightning, Plasma, WASM VM, bridge, oracles и др. |

Это **Mini-Ethereum-стиль** для обучения, а не конкурент Ethereum или Bitcoin.

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

### Установка

```bash
git clone https://github.com/Gruver87/absolute-blockchain-ultimate.git
cd absolute-blockchain-ultimate
pip install -r requirements.txt
cp .env.example .env   # опционально
cp wallet.example.json data/wallet.json   # опционально, локальный кошелёк (не коммитить ключи)
```

### Запуск (одна команда)

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
| **JSON-RPC** | http://localhost:8545 |
| **WebSocket** | ws://localhost:8766 |
| **P2P** | `:5000` |

### Проверка

```bash
curl http://localhost:8080/health/live
curl http://localhost:8080/status
curl http://localhost:8080/tokenomics
curl http://localhost:8080/peers
curl http://localhost:8080/bridge
curl http://localhost:8080/docs
pytest tests/ -q
```

Два узла локально (P2P): `.\scripts\start_two_nodes.ps1` — см. `node.example.json` / `node2.example.json`.

### Мониторинг (Grafana + Prometheus)

```bash
docker compose -f docker-compose.observability.yml up -d
# Grafana: http://localhost:3000 (admin/admin)
```

См. [docs/OBSERVABILITY.md](docs/OBSERVABILITY.md)

---

## Структура проекта

```
absolute-blockchain-ultimate/
├── main.py                 # Единственная точка входа узла
├── api/http.py             # REST + RPC handlers (~100+ routes, см. /docs)
├── web/explorer/index.html # Браузерный SPA (31 вкладка)
├── core/blockchain.py      # Блоки, транзакции, genesis
├── runtime/
│   ├── config.py           # Конфигурация узла
│   ├── tokenomics.py       # 221M ABS, D.U.P. 17.4%
│   └── pool_locks.py       # Блокировки пулов
├── light/light_client.py   # SPV light client
├── consensus/              # PoS, эпохи, slashing, finality
├── execution/              # VM, state engine, contracts
├── features/               # NFT, ZK, Lightning, AI и др.
├── storage/database.py     # SQLite + meta
├── bridge/                 # Cross-chain (simulator)
├── scripts/                # start/stop node, audits, release
├── tests/                  # pytest (unit + integration)
│   ├── smoke/              # merkle_light.py
│   └── legacy/             # старые test_v*.py (не CI)
├── requirements.txt
└── README.md
```

Подробная архитектура: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)  
**Справочник команд (PowerShell/curl):** [docs/COMMANDS_REFERENCE.md](docs/COMMANDS_REFERENCE.md)

**Старые версии (локально):** папка на рабочем столе `Desktop/Начало блокчейна/` — архив скриптов v54–v57 и legacy API. Не входит в GitHub-релиз.

---

## Что реально работает (локально)

| Компонент | Статус |
|-----------|--------|
| Core blockchain + SQLite | 🟢 |
| Mining (15s) + эмиссия ABS | 🟢 |
| REST API `:8080` | 🟢 (~100+ handlers, `/docs` + `verify_endpoints.ps1`) |
| JSON-RPC `:8545` | 🟢 |
| WebSocket `:8766` + Explorer live feed | 🟢 |
| Wallet + auto-sign TX | 🟢 |
| Signed TX enforcement (`require_signatures`) | 🟢 |
| State root verify on P2P import | 🟢 |
| Fork reorg (common ancestor + replay) | 🟢 |
| Proposer slashing (`double_proposal`) | 🟢 |
| Validators + PoS-модули | 🟢 |
| NFT, Oracles, State Engine | 🟢 |
| P2P (интернет) | 🟡 solo по умолчанию; 2 узла — `start_two_nodes.ps1` |
| Bridge / Sharding / Lightning / Plasma | 🟡 demo / simulator |
| Production mainnet | 🔴 не цель проекта |

Проверка ключевых маршрутов:

```powershell
.\scripts\verify_endpoints.ps1   # /tokenomics, /bridge, /founder, /allocation, …
```

## Устранение проблем

### Два узла / порты заняты

```
[P2P] Could not bind port 5000
[WebSocket] port 8766 already in use
```

Остановите старый процесс:

```powershell
.\scripts\stop_node.ps1
# или вручную:
netstat -ano | findstr :5000
taskkill /PID <pid> /F
```

`start_node.ps1` теперь **автоматически** останавливает предыдущий узел (флаг `-NoAutoStop` — отключить).

### Ложный slashing `double_vote`

Исправлено: slashing считает конфликт **по slot**, а не по epoch (32 блока). Solo-валидатор при майнинге больше не режется за каждый новый блок.

## Честные ограничения

| Ограничение | Пояснение |
|-------------|-----------|
| Production | ❌ Не готов |
| Реальная сеть / mainnet | ❌ Это локальный учебный узел |
| Полный EVM | ⚠️ Упрощённый / частичный |
| P2P в интернете | ⚠️ Требует настройки, не «боевая» сеть |
| Крипто-аудит | ❌ Не проводился |

---

## API (примеры)

```bash
# Статус узла
GET /status

# Токеномика
GET /tokenomics
GET /founder
GET /allocation

# Pool locks
GET /pools/locks
POST /pools/dao/vote  {"pool_id":"ecosystem","voter":"0x..."}

# Light client
GET /light/stats
GET /merkle/root/1
POST /light/spv/verify
```

Полный список — в `api/http.py` и вкладках веб-эксплорера.

---

## Тестирование

```bash
pytest tests/ -q
python tests/smoke/merkle_light.py
python scripts/mega_audit.py      # интеграционный аудит
python scripts/final_audit.py     # финальная проверка
```

Старые скрипты `test_v*.py` перенесены в `tests/legacy/` (не CI).

---

## Как помочь и продвинуть проект

Мы **приветствуем** любое развитие:

1. ⭐ **Star** на GitHub — помогает другим найти проект  
2. 🍴 **Fork** — экспериментируйте в своей ветке  
3. 🐛 **Issues** — баги и идеи  
4. 🔧 **Pull Requests** — код, тесты, документация  
5. 📢 **Расскажите** — блог, курс, видео, портфолио  

См. [CONTRIBUTING.md](CONTRIBUTING.md)

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

*Последнее обновление документации: июнь 2026 — chain integrity (signatures, state_root, reorg), ~100+ API, токеномика 221M ABS.*
