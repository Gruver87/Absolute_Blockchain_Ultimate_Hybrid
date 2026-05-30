[![Docs](https://img.shields.io/badge/docs-github%20pages-blue.svg)](https://gruver87.github.io/absolute-blockchain-ultimate/)
# Absolute Blockchain Ultimate

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://github.com/Gruver87/absolute-blockchain-ultimate/actions/workflows/test.yml/badge.svg)](https://github.com/Gruver87/absolute-blockchain-ultimate/actions)
[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://hub.docker.com/r/gruver87/absolute-blockchain)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![GitHub release](https://img.shields.io/github/v/release/Gruver87/absolute-blockchain-ultimate)](https://github.com/Gruver87/absolute-blockchain-ultimate/releases)

> **Учебный блокчейн-клиент | PoS консенсус | Multi-node sync | Python + Docker**

---

## ⚠️ ВАЖНОЕ ПРЕДУПРЕЖДЕНИЕ

**Это учебный/экспериментальный проект. НЕ ИСПОЛЬЗУЙТЕ В PRODUCTION!**

- 🧪 Проект в стадии активной разработки (Beta)
- 🔄 Данные могут быть сброшены в любой момент
- 🔒 Безопасность не гарантируется

---

## 📌 Что это такое?

Учебный проект по созданию блокчейн-клиента с нуля на Python. Реализует:

- LMD-GHOST консенсус
- PoS (Proof of Stake) механизмы
- Casper FFG финализацию
- P2P сети и gossip протоколы
- **Multi-node синхронизацию (v50)**

---

## ✅ Что РЕАЛЬНО работает (v44-v51)

### Core Components (Проверено тестами)
| Компонент | Статус | Тесты |
|-----------|--------|-------|
| State Engine | ✅ | 19/19 |
| Mempool | ✅ | Gas priority |
| Block Builder | ✅ | Сборка блоков |
| Block Validator | ✅ | Подписи, балансы, nonce |
| Block Importer | ✅ | Импорт + реорг |

### Cryptography (Проверено)
| Компонент | Статус |
|-----------|--------|
| secp256k1 Keys | ✅ |
| ECDSA Signatures | ✅ |
| Wallet (create/export/import) | ✅ |
| Nonce Protection | ✅ |
| Chain ID Protection | ✅ |

### Storage (Проверено)
| Компонент | Статус |
|-----------|--------|
| SQLite Database | ✅ |
| Crash Recovery | ✅ |
| Snapshots | ✅ |
| Backup | ✅ |



### 🔥 v51: Fast Sync (State Root Sync) (НОВОЕ!)
| Компонент | Статус | Описание |
|-----------|--------|----------|
| Fast Sync Manager | ✅ | Управление быстрой синхронизацией |
| Snapshot Protocol | ✅ | SNAPSHOT_REQUEST/RESPONSE |
| State Root Verification | ✅ | STATE_ROOT_REQUEST/RESPONSE |
| Auto Trigger | ✅ | Запуск при отставании >20 блоков |
| Near-instant Bootstrap | ✅ | Состояние восстанавливается мгновенно |
| Компонент | Статус |
|-----------|--------|
| Peer Manager | ✅ |
| Peer Discovery | ✅ |
| Message Protocol | ✅ |
| Peer Scoring | ✅ |
| Ban System | ✅ |
| Rate Limiting | ✅ |

### 🔥 v50: Block Sync (НОВОЕ!)
| Компонент | Статус |
|-----------|--------|
| Sync Manager | ✅ |
| Block Propagation | ✅ |
| Chain Sync | ✅ |
| Peer Height Tracking | ✅ |
| Fork Detection | ✅ |
| Reorg Support | ✅ |

### API
| Компонент | Статус |
|-----------|--------|
| JSON-RPC 2.0 | ✅ |
| CORS Support | ✅ |

---

## ❌ Что НЕ реализовано (честно)

- Полноценный EVM / Смарт-контракты (в планах)
- Доказательства с нулевым разглашением (ZK)
- Шардинг
- Механизмы slashing для валидаторов
- NFT (только базовая структура)

---

## 🏗️ Архитектура
┌─────────────────────────────────────────────────────────────┐
│ JSON-RPC API (8545) │
├─────────────────────────────────────────────────────────────┤
│ BLOCK SYNC ENGINE (v50) │
├─────────────────────────────────────────────────────────────┤
│ STATE ENGINE │
├─────────────────────────────────────────────────────────────┤
│ MEMPOOL │
├─────────────────────────────────────────────────────────────┤
│ BLOCK PIPELINE │
├─────────────────────────────────────────────────────────────┤
│ CRYPTO LAYER │
├─────────────────────────────────────────────────────────────┤
│ P2P + GOSSIP NETWORK │
└─────────────────────────────────────────────────────────────┘

text

---

## 🚀 Быстрый старт

### Установка

```bash
git clone https://github.com/Gruver87/absolute-blockchain-ultimate.git
cd absolute-blockchain-ultimate
pip install -r requirements.txt
Запуск ноды
bash
python node_persistent.py
Или через Docker
bash
docker-compose up --build
Проверка RPC
bash
curl -X POST http://localhost:8545 -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
Запуск тестов
bash
python -X utf8 test_state_engine.py
python -X utf8 test_v44.py
python -X utf8 test_v46.py
python -X utf8 test_v47.py
python -X utf8 test_v48.py
python -X utf8 test_v49.py
python -X utf8 test_v50.py
📊 Результаты тестов (актуальные)
text
test_state_engine.py   → [OK] 19/19
test_v44.py            → [OK] 7/7
test_v46.py            → [OK] 25/25
test_p2p.py            → [OK] 4/4
test_v47.py            → [OK] 24/24
test_v48.py            → [OK] 8/8
test_v49.py            → [OK] 11/11
test_v50.py            → [OK] 10/10

[WIN] ALL 8 TESTS PASSED!
📁 Структура проекта
text
absolute-blockchain-ultimate/
├── crypto/           # Криптография (ключи, подписи, кошельки)
├── execution/        # Исполнение (state engine, mempool, блоки)
├── storage/          # Хранение (SQLite, snapshots)
├── network/          # P2P сеть (peer manager, discovery, sync)
│   ├── p2p/          # Peer-to-peer протокол
│   └── sync/         # Block sync engine (v50)
├── rpc/              # JSON-RPC API
├── consensus/        # Консенсус (GHOST, Casper)
├── data/             # Данные (блоки, состояние)
├── node_persistent.py # Главный файл запуска
├── Dockerfile
├── docker-compose.yml
└── test_*.py         # Тесты (v44-v51)
🤝 Как помочь
⭐ Поставьте звезду

🐛 Сообщайте об ошибках

💡 Предлагайте улучшения

📄 Лицензия
MIT License — свободно для изучения и экспериментов

👤 Автор
Uladzimir Dabranski (Gruver87)

GitHub: @Gruver87

Email: gruverpetrov@gmail.com

⚠️ ЕЩЁ РАЗ: ЭТО УЧЕБНЫЙ ПРОЕКТ, НЕ PRODUCTION!


