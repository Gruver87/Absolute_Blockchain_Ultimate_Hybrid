# ⚡ ABSOLUTE BLOCKCHAIN ULTIMATE

**Modular experimental Layer-1 blockchain framework | UTXO | P2P | PoW | NFT | Sharding | Oracles**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Code size](https://img.shields.io/github/languages/code-size/Gruver87/absolute-blockchain-ultimate)](https://github.com/Gruver87/absolute-blockchain-ultimate)
[![Lines of Code](https://img.shields.io/tokei/lines/github/Gruver87/absolute-blockchain-ultimate)](https://github.com/Gruver87/absolute-blockchain-ultimate)

**Полноценный модульный блокчейн с UTXO, P2P сетью, NFT, шардингом, оракулами и веб-интерфейсом**

🚀 **GitHub** • 📖 **Документация** • 💡 **API** • 🔧 **Установка**

---

## 📋 Оглавление

- [О проекте](#-о-проекте)
- [Возможности](#-возможности)
- [Архитектура](#-архитектура)
- [Установка и запуск](#-установка-и-запуск)
- [API Эндпоинты](#-api-эндпоинты)
- [Структура проекта](#-структура-проекта)
- [Технологии](#-технологии)
- [Контакты](#-контакты)
- [Лицензия](#-лицензия)

---

## 📖 О проекте

**Absolute Blockchain Ultimate** — это полноценный, работающий модульный блокчейн с нуля, написанный на Python. Проект включает в себя:

- 🔗 **UTXO модель** транзакций (как в Bitcoin)
- 🌐 **P2P сеть** для децентрализованного общения узлов
- 🖥️ **REST API** с полной документацией
- 💼 **Веб-кошелёк** для управления средствами
- 🔍 **Блокчейн эксплорер** для просмотра транзакций
- 🦋 **NFT система** с маркетплейсом и 60 героями
- 📡 **Оракулы** для реальных цен криптовалют и погоды
- 🗺️ **Шардинг** (64 шарда) для масштабирования
- 🧠 **AI Autonomous Core** для самообучения сети
- 🔧 **Self-Healing** для автоматического восстановления

**150,000+ строк кода | 120+ модулей | Полностью рабочий продукт**

---

## ✨ Возможности

### 🎯 Ядро блокчейна

| Функция | Статус |
|---------|--------|
| UTXO модель транзакций | ✅ |
| Merkle Tree верификация | ✅ |
| Mempool (пул транзакций) | ✅ |
| Proof-of-Work консенсус | ✅ |
| Динамическая сложность | ✅ |
| Fork resolution (heaviest chain) | ✅ |

### 🔐 Криптография

| Функция | Статус |
|---------|--------|
| ECDSA secp256k1 подписи | ✅ |
| SPHINCS+ (пост-квантовая) | ✅ |
| Quantum Hash (SHA3-512 + BLAKE2b) | ✅ |
| BIP39 мнемоника | ✅ |
| Bitcoin-style адреса (Base58) | ✅ |

### 🌐 Сеть и P2P

| Функция | Статус |
|---------|--------|
| P2P gossip протокол | ✅ |
| Peer discovery | ✅ |
| Block propagation | ✅ |
| Header-first sync | ✅ |
| 3 узла (5000,5001,5002) | ✅ |

### 🦋 NFT система

| Функция | Статус |
|---------|--------|
| Создание коллекций | ✅ |
| Майнтинг NFT | ✅ |
| Маркетплейс | ✅ |
| Листинг на продажу | ✅ |
| Покупка NFT | ✅ |
| 60 AI героев | ✅ |

### 📡 Оракулы

| Функция | Статус |
|---------|--------|
| Цены BTC/ETH/SOL | ✅ |
| Погода (OpenWeatherMap) | ✅ |
| Новости | ✅ |

### 🗺️ Шардинг

| Функция | Статус |
|---------|--------|
| 64 шарда | ✅ |
| Динамический ребаланс | ✅ |
| Распределение транзакций | ✅ |

### 💼 Веб-интерфейс

| Функция | Статус |
|---------|--------|
| Главная панель | ✅ |
| Создание кошелька | ✅ |
| Проверка баланса | ✅ |
| Отправка транзакций | ✅ |
| Блокчейн эксплорер | ✅ |
| NFT галерея | ✅ |

### 🔒 Безопасность

| Функция | Статус |
|---------|--------|
| ECDSA secp256k1 подписи | ✅ |
| Защита от 51% атаки | ✅ |
| Защита от Sybil атаки | ✅ |
| Защита от Replay атаки | ✅ |
| Rate limiting (DDoS защита) | ✅ |

---

## 🏗️ Архитектура
┌─────────────────────────────────────────────────────────────┐
│ ABSOLUTE BLOCKCHAIN │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │ CORE │ │ UTXO │ │ MERKLE │ │
│ │ Engine │ │ Model │ │ Tree │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │ P2P │ │ Consensus │ │ Storage │ │
│ │ Network │ │ (PoW) │ │ (RocksDB) │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │ NFT │ │ Oracles │ │ Sharding │ │
│ │ System │ │ (Real API)│ │ (64) │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│ │ API │ │ Explorer │ │ GUI │ │
│ │ (REST) │ │ (Web) │ │ (Web) │ │
│ └─────────────┘ └─────────────┘ └─────────────┘ │
└─────────────────────────────────────────────────────────────┘

text

---

## 
## 📋 ПЛАН ЗАПУСКА (ДЛЯ НОВИЧКОВ)

1. **Клонируй репозиторий**  
   `git clone https://github.com/Gruver87/absolute-blockchain-ultimate.git`

2. **Перейди в папку**  
   `cd absolute-blockchain-ultimate`

3. **Установи зависимости**  
   `pip install -r requirements.txt`

4. **Запусти основной блокчейн**  
   `python ABSOLUTE_FINAL_FIXED.py`

5. **Открой браузер** → `http://localhost:8080`

### 🎯 ЧТО ДЕЛАТЬ ДАЛЬШЕ?

| Действие | Команда |
|----------|---------|
| Создать кошелёк | `curl -X POST http://localhost:8080/api/wallet/create` |
| Проверить баланс | `curl "http://localhost:8080/api/balance?address=foundation"` |
| Отправить транзакцию | `curl -X POST http://localhost:8080/api/transaction/send -H "Content-Type: application/json" -d '{"from":"foundation","to":"test","amount":100}'` |
| Замайнить блок | `curl -X POST http://localhost:8080/api/mine -H "Content-Type: application/json" -d '{"miner":"foundation"}'` |
| Открыть веб-интерфейс | `http://localhost:8080` |
| Посмотреть NFT | `http://localhost:8080/nft` |




### Требования

- Python 3.11+
- Git

### Быстрый старт

```bash
# 1. Клонировать репозиторий
git clone https://github.com/Gruver87/absolute-blockchain-ultimate.git
cd absolute-blockchain-ultimate

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Запустить блокчейн
python ABSOLUTE_FINAL_FIXED.py
Запуск всех модулей
ОкноКомандаПорт
1python ABSOLUTE_FINAL_FIXED.py8080
2python extended_api_server.py8081
3python testnet.py8088
4python explorer.py8090
5python gui.py8091
Docker (опционально)
bash
docker-compose up --build
🔌 API Эндпоинты
GET эндпоинты
ЭндпоинтОписание
/api/statsСтатистика блокчейна
/api/healthHealth check
/api/balance?address=xxxБаланс адреса
/api/peersСписок пиров
/api/nft/tokensСписок NFT
/api/nft/statsСтатистика NFT
/api/oracle/price?symbol=bitcoinКурс BTC
POST эндпоинты
ЭндпоинтОписаниеТело
/api/wallet/createСоздать кошелёк-
/api/transaction/sendОтправить транзакцию{"from":"foundation","to":"test","amount":100}
/api/mineЗамайнить блок{"miner":"foundation"}
/api/nft/collection/createСоздать NFT коллекцию{"name":"Heroes","creator":"foundation","royalty":5}
/api/nft/mintСоздать NFT{"collection_id":"xxx","name":"Hero #1","owner":"foundation"}
📁 Структура проекта
text
absolute-blockchain-ultimate/
├── core/              # Ядро блокчейна (UTXO, Merkle, Mempool)
├── p2p/               # P2P сеть (gossip, sync)
├── consensus/         # Консенсус (heaviest chain)
├── api/               # REST API
├── modules/           # NFT, оракулы, шардинг
├── storage/           # Хранилище (RocksDB)
├── tests/             # Тесты
├── nft_images/        # 60 NFT изображений
├── .github/workflows/ # CI/CD
├── ABSOLUTE_FINAL_FIXED.py  # Главный файл
├── extended_api_server.py   # Extended API
├── testnet.py               # Тестнет + Faucet
├── explorer.py              # Блокчейн эксплорер
├── gui.py                   # Графический интерфейс
├── telegram_super_bot.py    # Telegram бот
├── requirements.txt         # Зависимости
├── Dockerfile               # Docker
├── docker-compose.yml       # Docker Compose
└── README.md                # Документация
🔧 Порты
СервисПорт
Основной API8080
Документация API8080/docs
Extended API (оракулы)8081
Тестнет + Faucet8088
Блокчейн-эксплорер8090
Графический интерфейс (GUI)8091
Мониторинг8092
Mobile API8093
Prometheus метрики9090
P2P сеть5000
🧪 Быстрый тест API
bash
# Статистика блокчейна
curl http://localhost:8080/api/stats

# Создать кошелёк
curl -X POST http://localhost:8080/api/wallet/create

# Проверить баланс
curl "http://localhost:8080/api/balance?address=foundation"

# Отправить транзакцию
curl -X POST http://localhost:8080/api/transaction/send \
  -H "Content-Type: application/json" \
  -d '{"from":"foundation","to":"test","amount":100}'

# Замайнить блок
curl -X POST http://localhost:8080/api/mine \
  -H "Content-Type: application/json" \
  -d '{"miner":"foundation"}'

# Получить курс BTC (оракул)
curl http://localhost:8081/api/oracle/price?symbol=bitcoin
🌐 Контакты
💻 GitHub

🔗 LinkedIn

💬 Telegram

🐦 Twitter (X)

📄 Лицензия
MIT © 2026 Uladzimir Dabranski (Gruver87)

⭐ Если вам нравится этот проект
Поставьте звезду на GitHub — это поможет проекту расти!




