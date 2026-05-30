# Absolute Blockchain Ultimate

> **Экспериментальный блокчейн-клиент | PoS консенсус | Multi-node sync | Учебный проект**

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

## ✅ Что реализовано (v44-v50)

### Core Components
| Компонент | Статус | Описание |
|-----------|--------|----------|
| State Engine | ✅ | Детерминированные переходы состояний |
| Mempool | ✅ | Пул транзакций с приоритетом по gas price |
| Block Builder | ✅ | Сборка блоков из mempool |
| Block Validator | ✅ | Проверка подписей, балансов, nonce |
| Block Importer | ✅ | Импорт и валидация блоков |

### Cryptography
| Компонент | Статус | Описание |
|-----------|--------|----------|
| secp256k1 Keys | ✅ | Генерация ключей (как в Bitcoin/Ethereum) |
| ECDSA Signatures | ✅ | Подпись транзакций и блоков |
| Wallet | ✅ | Создание/экспорт/импорт кошельков |
| Nonce Protection | ✅ | Защита от replay-атак |
| Chain ID | ✅ | Защита от cross-chain replay |

### Storage
| Компонент | Статус | Описание |
|-----------|--------|----------|
| SQLite Database | ✅ | Сохранение блоков и состояния |
| Crash Recovery | ✅ | Восстановление после сбоев |
| Snapshots | ✅ | Точки восстановления состояния |
| Backup | ✅ | Резервное копирование |

### Network & P2P
| Компонент | Статус | Описание |
|-----------|--------|----------|
| Peer Manager | ✅ | Управление пирами |
| Peer Discovery | ✅ | Обнаружение узлов |
| Message Protocol | ✅ | P2P сообщения (ping/pong/block/tx) |
| Peer Scoring | ✅ | Репутация узлов |
| Ban System | ✅ | Блокировка вредоносных узлов |
| Rate Limiting | ✅ | Защита от спама |

### 🔥 v50: Block Sync & Peer State Sync (НОВОЕ!)
| Компонент | Статус | Описание |
|-----------|--------|----------|
| Sync Manager | ✅ | Управление синхронизацией цепочек |
| Block Propagation | ✅ | BLOCK_ANNOUNCE/REQUEST/RESPONSE |
| Chain Sync | ✅ | SYNC_REQUEST/RESPONSE протокол |
| Peer Height Tracking | ✅ | Отслеживание высоты пиров |
| Fork Detection | ✅ | Обнаружение и обработка форков |
| Reorg Support | ✅ | Переорганизация цепочки |

### API
| Компонент | Статус | Описание |
|-----------|--------|----------|
| JSON-RPC 2.0 | ✅ | eth_blockNumber, eth_getBalance, eth_chainId |
| CORS Support | ✅ | Для подключения MetaMask |

### Tests
| Тест | Статус | Результат |
|------|--------|-----------|
| State Engine | ✅ | 19/19 |
| Block Pipeline (v44) | ✅ | 7/7 |
| Crypto & Wallet (v46) | ✅ | 25/25 |
| P2P Network | ✅ | 4/4 |
| Persistent Storage (v47) | ✅ | 24/24 |
| JSON-RPC (v48) | ✅ | 8/8 |
| Signed Transactions (v49) | ✅ | 11/11 |
| Block Sync (v50) | ✅ | 10/10 |

---

## ❌ Что НЕ реализовано (честно)

- Полноценный EVM / Смарт-контракты (в планах)
- Доказательства с нулевым разглашением (ZK)
- Шардинг
- Механизмы slashing для валидаторов

---

## 🏗️ Архитектура
┌─────────────────────────────────────────────────────────────┐
│ JSON-RPC API (8545) │
├─────────────────────────────────────────────────────────────┤
│ BLOCK SYNC ENGINE (v50) │
│ (Peer tracking + Chain sync) │
├─────────────────────────────────────────────────────────────┤
│ STATE ENGINE │
│ (Balances + execution) │
├─────────────────────────────────────────────────────────────┤
│ MEMPOOL │
│ (Gas priority + validation) │
├─────────────────────────────────────────────────────────────┤
│ BLOCK PIPELINE │
│ (Build → Validate → Import) │
├─────────────────────────────────────────────────────────────┤
│ CRYPTO LAYER │
│ (secp256k1 + ECDSA + Wallet) │
├─────────────────────────────────────────────────────────────┤
│ P2P + GOSSIP NETWORK │
│ (Peer discovery + Messaging) │
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
Проверка RPC (в другом окне)
bash
curl -X POST http://localhost:8545 -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
Запуск всех тестов
bash
python -X utf8 test_state_engine.py
python -X utf8 test_v44.py
python -X utf8 test_v46.py
python -X utf8 test_v47.py
python -X utf8 test_v48.py
python -X utf8 test_v49.py
python -X utf8 test_v50.py
📊 Тест-результат (актуальный)
text
test_state_engine.py   → [OK] 19/19
test_v44.py            → [OK] 7/7
test_v46.py            → [OK] 25/25
test_p2p.py            → [OK] 4/4
test_v47.py            → [OK] 24/24
test_v48.py            → [OK] 8/8
test_v49.py            → [OK] 11/11
test_v50.py            → [OK] 10/10

[WIN][WIN][WIN] ALL 8 TESTS PASSED!
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
└── test_*.py         # Тесты (v44-v50)
🤝 Как помочь
Если вы тоже учитесь и хотите поэкспериментировать:

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
