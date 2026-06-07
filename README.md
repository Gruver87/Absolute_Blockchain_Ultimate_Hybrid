# Absolute Blockchain Ultimate 🚀

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-stable-green.svg)]()

> **Полноценный учебный блокчейн-клиент | PoS консенсус | JSON-RPC | Python**

---

## ⚠️ **ВАЖНОЕ ПРЕДУПРЕЖДЕНИЕ**

**Это учебный/экспериментальный проект. НЕ ИСПОЛЬЗУЙТЕ В PRODUCTION!**

- 🧪 Проект в стадии активной разработки
- 🔄 Данные могут быть сброшены в любой момент
- 🔒 Безопасность не гарантируется

---

## 📌 **Что это такое?**

Учебный проект по созданию блокчейн-клиента с нуля на Python. Реализует:

- ✅ LMD-GHOST консенсус
- ✅ PoS (Proof of Stake) механизмы
- ✅ Casper FFG финализацию
- ✅ JSON-RPC API (совместим с Ethereum)
- ✅ Persistent storage (SQLite)
- ✅ Mempool с приоритетом по gas price
- ✅ Автоматический майнинг
- ✅ Восстановление после перезапуска

---

## ✅ **Что РАБОТАЕТ (проверено тестами)**

### Core Components
| Компонент | Статус | Описание |
|-----------|--------|----------|
| Blockchain Storage | ✅ | SQLite, сохранение блоков |
| Block Production | ✅ | Автомайнинг каждые 15 секунд |
| Wallets | ✅ | Создание, импорт, экспорт |
| ECDSA Signatures | ✅ | secp256k1 подписи |
| Chain Recovery | ✅ | Восстановление после перезапуска |

### Transaction System
| Компонент | Статус | Описание |
|-----------|--------|----------|
| Mempool | ✅ | Пул транзакций с приоритетом |
| Transaction Processing | ✅ | Полный цикл: подпись → мемпул → блок |
| Nonce Protection | ✅ | Защита от повторных транзакций |

### Virtual Machine (Mini-EVM)
| Компонент | Статус | Описание |
|-----------|--------|----------|
| Arithmetic (ADD/SUB/MUL/DIV) | ✅ | Базовые арифметические операции |
| Storage (SSTORE/SLOAD) | ✅ | Постоянное хранилище |
| Comparisons (LT/GT/EQ) | ✅ | Операции сравнения |
| Gas Metering | ✅ | Лимиты газа |
| Stack Operations | ✅ | PUSH, POP |
| Persistence | ✅ | Состояние между вызовами |

### RPC API (JSON-RPC 2.0)
| Метод | Статус | Описание |
|-------|--------|----------|
| `eth_blockNumber` | ✅ | Текущая высота блока |
| `eth_chainId` | ✅ | ID сети (1337) |
| `eth_getBalance` | ✅ | Баланс кошелька |
| `eth_gasPrice` | ✅ | Текущая цена газа |
| `eth_sendTransaction` | ✅ | Отправка транзакции |
| `eth_getMempoolSize` | ✅ | Размер мемпула |
| `net_version` | ✅ | Версия сети |
| `web3_clientVersion` | ✅ | Версия клиента |

### Storage
| Компонент | Статус | Описание |
|-----------|--------|----------|
| SQLite Database | ✅ | Персистентное хранение |
| Crash Recovery | ✅ | Восстановление после сбоя |
| Snapshots | ✅ | Снимки состояния |

---

## 🏗️ **Архитектура**
┌─────────────────────────────────────────────────────────────┐
│ JSON-RPC API (8545) │
├─────────────────────────────────────────────────────────────┤
│ Transaction Mempool │
├─────────────────────────────────────────────────────────────┤
│ Block Pipeline │
├─────────────────────────────────────────────────────────────┤
│ Mini-EVM (VM) │
├─────────────────────────────────────────────────────────────┤
│ Consensus Layer │
├─────────────────────────────────────────────────────────────┤
│ Storage Layer (SQLite) │
├─────────────────────────────────────────────────────────────┤
│ Crypto Layer (ECDSA) │
└─────────────────────────────────────────────────────────────┘

text

---

## 🚀 **Быстрый старт**

### Установка

```bash
git clone https://github.com/Gruver87/absolute-blockchain-ultimate.git
cd absolute-blockchain-ultimate
pip install -r requirements.txt
Запуск ноды
bash
python node_persistent.py
Проверка RPC
bash
curl -X POST http://localhost:8545 -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'
Отправка транзакции
bash
curl -X POST http://localhost:8545 -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_sendTransaction","params":[{"from":"0x...","to":"0x...","value":"0x64"}],"id":1}'
📊 Тестирование
bash
# VM тесты
python test_vm_complete.py

# Транзакции
python quick_test.py

# Полный тест
python test_final.py
📁 Структура проекта
text
absolute-blockchain-ultimate/
├── core/               # Основные компоненты (блоки, транзакции, кошельки)
├── execution/          # Исполнение (mempool, VM)
├── consensus/          # Консенсус (GHOST, Casper, Slashing)
├── rpc/                # JSON-RPC сервер
├── storage/            # Хранение (SQLite)
├── crypto/             # Криптография (ECDSA, ключи)
├── network/            # P2P сеть
├── data/               # Данные (кошельки, блокчейн)
├── logs/               # Логи работы
├── node_persistent.py  # Главный файл запуска
├── requirements.txt    # Зависимости
└── test_*.py          # Тесты
🛠️ Команды для работы
Запуск
bash
python node_persistent.py          # Запуск ноды
python quick_test.py               # Быстрый тест
python test_final.py               # Полный тест
RPC запросы
bash
# Высота блока
curl -X POST http://localhost:8545 -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Размер мемпула
curl -X POST http://localhost:8545 -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_getMempoolSize","params":[],"id":1}'

# Отправка транзакции
curl -X POST http://localhost:8545 -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_sendTransaction","params":[{"from":"0x...","to":"0x...","value":"0x64"}],"id":1}'
Очистка данных
bash
rm -rf data/*          # Удалить все данные
rm data/wallet.json    # Удалить только кошелёк
📈 Текущий статус проекта
ПодсистемаСтатусПроцент
Blockchain Core✅100%
Wallets & Signatures✅100%
Persistent Storage✅100%
Mempool✅100%
Transactions✅100%
JSON-RPC✅85%
Mini-EVM✅80%
P2P Network⚠️50%
Smart Contracts⚠️40%
🤝 Как помочь проекту
⭐ Поставьте звезду на GitHub

🐛 Сообщайте об ошибках

💡 Предлагайте улучшения

📝 Улучшайте документацию

📄 Лицензия
MIT License — свободно для изучения и экспериментов

👤 Автор
Uladzimir Dabranski (Gruver87)

GitHub: @Gruver87

Email: gruverpetrov@gmail.com

⚠️ ЕЩЁ РАЗ: ЭТО УЧЕБНЫЙ ПРОЕКТ, НЕ PRODUCTION!
Проект создан для изучения принципов работы блокчейна. Не используйте в реальных финансовых операциях.

Спасибо за внимание! 🎉
