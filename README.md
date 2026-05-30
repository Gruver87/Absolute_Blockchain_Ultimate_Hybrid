# Absolute Blockchain

## 🚀 Что это?

**Учебный Ethereum-подобный блокчейн-клиент** на Python. Реализует минимальный набор функций для работы распределённой сети.

⚠️ **Это учебный проект, не для production использования.**

## ✅ Что реализовано (v44-v49)

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

### Network
| Компонент | Статус | Описание |
|-----------|--------|----------|
| Peer Manager | ✅ | Управление пирами |
| Peer Discovery | ✅ | Обнаружение узлов |
| Message Protocol | ✅ | P2P сообщения (ping/pong/block/tx) |
| Peer Scoring | ✅ | Репутация узлов |
| Ban System | ✅ | Блокировка вредоносных узлов |
| Rate Limiting | ✅ | Защита от спама |

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

## ❌ Что НЕ реализовано (честно)

- Полноценный P2P discovery (упрощён)
- EVM/Smart Contracts (в планах)
- Доказательства с нулевым разглашением (ZK)
- Шардинг
- Механизмы slashing для валидаторов

## 🏗️ Архитектура
Transaction → Mempool → Block Builder → State Engine → Validator → Storage → P2P Gossip → JSON-RPC

text

## 🚀 Быстрый старт

### Установка

```bash
git clone https://github.com/yourusername/AbsoluteBlockchain.git
cd AbsoluteBlockchain
pip install -r requirements.txt
Запуск ноды
bash
python node_persistent.py
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
📊 Тест-результат (актуальный)
text
test_state_engine.py   → [OK] 19/19
test_v44.py            → [OK] 7/7
test_v46.py            → [OK] 25/25
test_p2p.py            → [OK] 4/4
test_v47.py            → [OK] 24/24
test_v48.py            → [OK] 8/8
test_v49.py            → [OK] 11/11

[WIN][WIN][WIN] ALL 7 TESTS PASSED!
📁 Структура проекта
text
AbsoluteBlockchain/
├── crypto/           # Криптография (ключи, подписи, кошельки)
├── execution/        # Исполнение (state engine, mempool, блоки)
├── storage/          # Хранение (SQLite, snapshots)
├── network/          # P2P сеть (peer manager, discovery)
├── rpc/              # JSON-RPC API
├── consensus/        # Консенсус (GHOST, Casper)
├── data/             # Данные (блоки, состояние)
├── node_persistent.py # Главный файл запуска
└── test_*.py         # Тесты
📝 Лицензия
MIT

⚠️ Disclaimer
Это учебный проект. Не используйте в production для хранения реальных ценностей. Приватные ключи генерируются локально, но безопасность не гарантируется.
