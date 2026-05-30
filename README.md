# Absolute Blockchain Ultimate

> **Экспериментальный блокчейн-клиент | PoS консенсус | Учебный проект**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-experimental-red.svg)](https://github.com/Gruver87/absolute-blockchain-ultimate)

---

## ⚠️ ВАЖНОЕ ПРЕДУПРЕЖДЕНИЕ

**Это экспериментальный учебный проект. НЕ ИСПОЛЬЗУЙТЕ В PRODUCTION!**

- 🧪 Проект в стадии активной разработки (Alpha)
- 🔄 Данные могут быть сброшены в любой момент
- 🐛 Баги и нестабильная работа — норма
- 🔒 Безопасность не гарантируется

---

## 📌 Что это такое?

Это мой учебный проект по созданию блокчейн-клиента с нуля. Я изучаю:

- Как работают Ethereum-клиенты изнутри
- LMD-GHOST консенсус
- PoS (Proof of Stake) механизмы
- Casper FFG финализацию
- P2P сети и gossip протоколы
- Слэшинг и экономическую защиту

**Проект не претендует на production-качество. Это песочница для экспериментов.**

---

## ✅ Что уже реализовано

### Консенсус (v43-v49)
| Компонент | Статус | Описание |
|-----------|--------|----------|
| LMD-GHOST | 🟡 90% | Выбор головы цепочки |
| Casper FFG | 🟡 85% | Финализация эпох |
| Slashing | ✅ 85% | Наказание валидаторов |
| RANDAO | ✅ 90% | Случайный выбор proposer'а |
| Reorg Engine | ✅ 90% | Безопасные реорганизации |
| Sync Engine | ✅ 85% | Синхронизация с сетью |
| State Engine | ✅ 85% | Управление состоянием |

### Сеть
| Компонент | Статус | Описание |
|-----------|--------|----------|
| P2P | ✅ 80% | Peer-to-peer коммуникация |
| Gossip | ✅ 80% | Распространение сообщений |
| Adversarial | ✅ 85% | Симуляция атак и задержек |

### API
| Компонент | Статус | Описание |
|-----------|--------|----------|
| JSON-RPC | 🟡 70% | MetaMask совместимый API |
| REST API | ✅ 80% | Оригинальный API |

---

## 🏗️ Архитектура
┌─────────────────────────────────────────────────────────────┐
│ JSON-RPC API (8545) │
├─────────────────────────────────────────────────────────────┤
│ SYNC ENGINE │
│ (Fast catch-up) │
├─────────────────────────────────────────────────────────────┤
│ STATE ENGINE │
│ (Balances + execution) │
├─────────────────────────────────────────────────────────────┤
│ REORG ENGINE │
│ (Finality-safe reorgs) │
├─────────────────────────────────────────────────────────────┤
│ RANDAO │
│ (Random proposer selection) │
├─────────────────────────────────────────────────────────────┤
│ SLASHING │
│ (Economic punishment for cheating) │
├─────────────────────────────────────────────────────────────┤
│ CASPER FFG │
│ (Epoch-based finality) │
├─────────────────────────────────────────────────────────────┤
│ LMD-GHOST │
│ (Fork choice) │
├─────────────────────────────────────────────────────────────┤
│ P2P + GOSSIP │
│ (Network layer) │
└─────────────────────────────────────────────────────────────┘

text

---

## 🚀 Быстрый старт

```bash
# Клонирование
git clone https://github.com/Gruver87/absolute-blockchain-ultimate.git
cd absolute-blockchain-ultimate

# Установка
pip install -r requirements.txt

# Запуск ноды
python run_node.py --node-id node1 --rpc-port 8545 --p2p-port 30303

# Запуск devnet из 3 нод
python run_devnet.py
🧪 Запуск тестов
bash
# Тест консенсуса
python test_finality.py

# Тест слэшинга
python test_slashing_integration.py

# Тест sync engine
python test_sync_engine_v2.py

# Тест state engine
python test_state_engine.py

# Тест reorg engine
python test_reorg_engine.py

# Тест RANDAO
python test_validator_selection.py

# Тест adversarial network
python test_adversarial_network.py
📊 Статус компонентов (честно)
КомпонентСтатусПримечание
LMD-GHOST🟡 90%Работает, но edge cases не все
Casper FFG🟡 85%Упрощённая модель
Slashing✅ 85%Double vote detection работает
RANDAO✅ 90%Случайность из блоков
Reorg Engine✅ 90%Финализация защищает
State Engine✅ 85%Без Merkle trie
Sync Engine✅ 85%Fast sync работает
Adversarial Net✅ 85%Задержки, потери, partition
JSON-RPC🟡 70%Базовые методы
Production-ready🔴 0%Не для продакшена
📁 Структура проекта
text
absolute-blockchain-ultimate/
├── consensus/          # LMD-GHOST + Casper + Slashing + RANDAO + Reorg
├── execution/          # State engine + transaction execution
├── sync/               # Sync engine (fast catch-up)
├── network/            # P2P + gossip + adversarial simulation
├── core/               # Блоки, мемпул, импорт
├── rpc/                # JSON-RPC API
├── state/              # Управление состоянием
├── run_node.py         # Запуск одной ноды
├── run_devnet.py       # Запуск 3 нод
└── tests/              # Все тесты
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
