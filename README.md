# Absolute Blockchain Ultimate

> **Экспериментальный блокчейн-клиент | Учебный проект | Не для production**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Status](https://img.shields.io/badge/status-experimental-red.svg)](https://github.com/Gruver87/absolute-blockchain-ultimate)

---

## ⚠️ ЧЕСТНОЕ ПРЕДУПРЕЖДЕНИЕ

**Это экспериментальный учебный проект. НЕ ИСПОЛЬЗУЙТЕ В PRODUCTION!**

- 🧪 Проект в стадии активной разработки (Alpha)
- 🔄 Данные могут быть сброшены в любой момент
- 🐛 Баги и нестабильная работа — норма
- 🔒 Безопасность не гарантируется
- 📡 API может меняться без предупреждения

---

## 📌 Что это такое?

Это мой учебный проект по созданию блокчейн-клиента с нуля. Я изучаю:

- Как работают Ethereum-клиенты изнутри
- LMD-GHOST консенсус
- P2P сети и gossip протоколы
- Casper FFG финализацию
- JSON-RPC API

**Проект не претендует на production-качество. Это песочница для экспериментов.**

---

## ✅ Что уже реализовано (на данный момент)

### Базовые компоненты
- 🔗 Блокчейн ядро (блоки, транзакции)
- 🌐 P2P сеть (peer discovery, gossip)
- 💰 Integer экономика (сатоши вместо float)
- 🔐 JWT аутентификация
- 🦋 NFT система (маркетплейс, коллекции)

### Консенсус (v43)
- 🧠 LMD-GHOST fork choice
- 🗳️ Validator attestations
- 🔒 Casper FFG finality (checkpoint-based)
- 📊 Epoch management (3 блока на эпоху)

### Сеть
- 📡 Gossip протокол (hash-first propagation)
- 🔄 Sync engine (header-first sync)
- 👥 Peer scoring

### API
- 📡 JSON-RPC (частичная совместимость с Ethereum)
- 🔌 REST API (оригинальный)

---

## 🚀 Быстрый старт

```bash
git clone https://github.com/Gruver87/absolute-blockchain-ultimate.git
cd absolute-blockchain-ultimate
pip install -r requirements.txt

# Запуск ноды
python run_node.py --node-id node1 --rpc-port 8545 --p2p-port 30303

# Запуск devnet из 3 нод
python run_devnet.py
🧪 Запуск тестов
bash
# Тест консенсуса (LMD-GHOST + финализация)
python test_finality.py

# Тест gossip протокола
python test_gossip_protocol.py

# Тест sync engine
python test_sync_engine.py
📊 Статус компонентов (честно)
КомпонентСтатусЧто работает
LMD-GHOST🟡 90%Выбор head работает, но не идеально
Casper FFG🟡 85%Финализация работает, но модель упрощённая
P2P gossip🟢 80%Базовое распространение работает
Sync engine🟢 85%Header-first sync работает
JSON-RPC🟡 70%Базовые методы работают
Production-ready🔴 0%Не пытайтесь использовать в проде
📁 Структура
text
absolute-blockchain-ultimate/
├── consensus/          # LMD-GHOST + Casper FFG
├── network/            # P2P + gossip + sync
├── core/               # Блоки, мемпул, импорт
├── rpc/                # JSON-RPC API
├── run_node.py         # Запуск одной ноды
├── run_devnet.py       # Запуск 3 нод
└── tests/              # Тесты
🤝 Как помочь
Если вы тоже учитесь и хотите поэкспериментировать:

⭐ Поставьте звезду (если полезно)

🐛 Сообщайте об ошибках

💡 Предлагайте улучшения

📄 Лицензия
MIT License — свободно для изучения и экспериментов

👤 Автор
Uladzimir Dabranski (Gruver87)

GitHub: @Gruver87

Email: gruverpetrov@gmail.com

⚠️ ЕЩЁ РАЗ: ЭТО УЧЕБНЫЙ ПРОЕКТ, НЕ PRODUCTION!
