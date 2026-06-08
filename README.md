# 🌐 Absolute Blockchain Ultimate

> **Учебно-экспериментальный блокчейн-клиент | Python | JSON-RPC | Демонстрационный проект**

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Experimental-yellow.svg)]()

## ⚠️ **ВАЖНОЕ ПРЕДУПРЕЖДЕНИЕ**
╔═══════════════════════════════════════════════════════════════════════════╗
║ ЭТО УЧЕБНЫЙ/ЭКСПЕРИМЕНТАЛЬНЫЙ ПРОЕКТ ║
║ ║
║ ❌ НЕ ИСПОЛЬЗУЙТЕ В PRODUCTION! ║
║ ❌ НЕ ХРАНИТЕ РЕАЛЬНЫЕ ЦЕННОСТИ ║
║ ❌ БЕЗОПАСНОСТЬ НЕ ГАРАНТИРУЕТСЯ ║
║ ║
║ ✅ Для изучения принципов работы блокчейна ║
║ ✅ Для экспериментов и тестирования ║
║ ✅ Для демонстрации инженерных навыков ║
╚═══════════════════════════════════════════════════════════════════════════╝

text

## 📌 О проекте

**Absolute Blockchain Ultimate** — это учебный блокчейн-клиент, созданный для:
- 🎓 Изучения принципов работы блокчейна
- 🧪 Экспериментов с консенсусами и криптографией
- 📊 Демонстрации инженерных компетенций

## ✅ Что РАБОТАЕТ (проверено)

| Компонент | Статус | Примечание |
|-----------|--------|------------|
| Блокчейн ядро | ✅ | 150+ блоков, автомайнинг |
| JSON-RPC API | ✅ | Порт 8545, основные методы |
| Mini-EVM | ✅ | 50+ опкодов, тесты 12/12 |
| NFT Marketplace | ✅ | 5 тестовых NFT |
| Шардинг | ✅ | 4 шарда (демо) |
| Оракулы | ✅ | Цены ETH/BTC |
| NFT галерея | ✅ | http://localhost:8081 |

## ❌ Что НЕ РАБОТАЕТ (честно)

| Проблема | Статус |
|----------|--------|
| P2P сеть | ⚠️ Заглушка, требует доработки |
| Веб-интерфейс | ⚠️ Ошибки подключения |
| Безопасность | ❌ Не реализована |
| Production-ready | ❌ Нет |

## 🚀 Быстрый старт

### Установка
```bash
git clone https://github.com/Gruver87/absolute-blockchain-ultimate.git
cd absolute-blockchain-ultimate
pip install -r requirements.txt
Запуск ноды
bash
python node_persistent.py
Проверка работы
bash
# Запрос к RPC
curl -X POST http://localhost:8545 -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Ожидаемый ответ: {"jsonrpc":"2.0","result":"0x...","id":1}
NFT галерея (отдельное окно)
bash
cd nft_images
python -m http.server 8081
# Открыть http://localhost:8081
🛠️ Тестирование
bash
# Тест Mini-EVM
python test_vm.py

# Проверка компонентов
python -c "from nft_core import nft_marketplace; print('NFT OK')"
python -c "from dynamic_sharding import sharding_manager; print('Sharding OK')"
python -c "from real_world_oracles import oracles; print('Oracles OK')"
📁 Структура проекта
text
absolute-blockchain-ultimate/
├── node_persistent.py       # Основная нода (RPC сервер)
├── nft_core.py              # NFT Marketplace
├── dynamic_sharding.py      # Шардинг (демо)
├── real_world_oracles.py    # Оракулы цен
├── test_vm.py               # Тесты Mini-EVM
├── execution/vm.py          # Mini-EVM (50+ опкодов)
├── nft_images/              # SVG изображения NFT
├── data/                    # Данные (wallet, chain)
└── logs/                    # Логи работы
📊 Текущий статус (локальный тест)
ПоказательЗначение
Блоков намайнено150+
Баланс кошелька~30,000,000 ABS
NFT токенов5
Активных шардов4
Тесты VM12/12 ✅
🗺️ Roadmap (планы)
v55 (в разработке)
Исправление ошибок ConnectionAbortedError

Полноценный веб-интерфейс

JWT авторизация

v56 (планы)
Реальное P2P

Полноценный EVM

Децентрализованные оракулы

v57 (долгосрочно)
ZK-Rollups

Поддержка смарт-контрактов WASM

Графический интерфейс

🤝 Как помочь проекту
⭐ Поставьте звезду на GitHub
🐛 Сообщайте об ошибках через Issues
💡 Предлагайте улучшения
🔧 Присылайте Pull Requests

📄 Лицензия
MIT License — свободно для изучения и экспериментов

👤 Автор
Uladzimir Dabranski (Gruver87)

GitHub: @Gruver87

Email: gruverpetrov@gmail.com

⚠️ ЕЩЁ РАЗ: ЭТО УЧЕБНЫЙ ПРОЕКТ, НЕ PRODUCTION!
text
╔═══════════════════════════════════════════════════════════════════════════╗
║                                                                           ║
║   🎓 ДЛЯ ОБУЧЕНИЯ И ЭКСПЕРИМЕНТОВ — ОТЛИЧНО!                             ║
║   🚀 ДЛЯ PRODUCTION И РЕАЛЬНЫХ ДЕНЕГ — НЕТ!                              ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝
⭐ Если проект полезен для изучения — поставьте звезду!
