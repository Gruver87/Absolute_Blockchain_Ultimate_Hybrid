# 🤝 Руководство по участию в проекте

Спасибо за интерес к проекту Absolute Blockchain Ultimate! Мы рады любым вкладам.

## 📋 Содержание

- [Как помочь](#как-помочь)
- [Настройка окружения](#настройка-окружения)
- [Процесс разработки](#процесс-разработки)
- [Code Style](#code-style)
- [Тестирование](#тестирование)
- [Создание Pull Request](#создание-pull-request)

---

## 🌟 Как помочь

| Задача | Сложность | Приоритет |
|--------|-----------|-----------|
| 🐛 Сообщать об ошибках | Низкая | Высокий |
| 📝 Улучшать документацию | Низкая | Высокий |
| ⭐ Поставить звезду | Низкая | Высокий |
| 💡 Предлагать идеи | Средняя | Средний |
| 🔧 Исправлять баги | Средняя | Средний |
| 🚀 Добавлять новые функции | Высокая | Низкий |

---

## 🛠️ Настройка окружения

### 1. Клонирование репозитория
```bash
git clone https://github.com/Gruver87/absolute-blockchain-ultimate.git
cd absolute-blockchain-ultimate
2. Установка зависимостей
bash
pip install -r requirements.txt
3. Запуск ноды
bash
python node_persistent.py
4. Запуск тестов
bash
python test_final.py
python quick_test.py
python test_vm_complete.py
📝 Процесс разработки
Создайте Issue с описанием того, что вы хотите сделать

Форкните репозиторий

Создайте ветку для ваших изменений

bash
git checkout -b feature/название-функции
Внесите изменения и закоммитьте

bash
git commit -m "feat: описание изменений"
Запушьте изменения

bash
git push origin feature/название-функции
Создайте Pull Request

🎨 Code Style
Используйте Python 3.11+

Следуйте PEP 8

Используйте типизацию (Type Hints)

Добавляйте докстринги для функций и классов

Пример:
python
def add_transaction(self, tx: dict) -> str:
    """
    Добавить транзакцию в мемпул.

    Args:
        tx: Словарь с данными транзакции

    Returns:
        Хэш транзакции
    """
    pass
🧪 Тестирование
Запуск всех тестов
bash
python test_final.py
Тесты отдельных компонентов
bash
# VM
python test_vm_complete.py

# NFT
python -c "from nft_core import NFTMarketplace; print('OK')"

# Шардинг
python -c "from dynamic_sharding import sharding_manager; print('OK')"
📦 Структура проекта
text
absolute-blockchain-ultimate/
├── core/               # Ядро блокчейна
├── consensus/          # Консенсус
├── execution/          # Исполнение (VM)
├── rpc/                # JSON-RPC API
├── network/            # P2P сеть
├── crypto/             # Криптография
├── storage/            # Хранение
├── web/                # Веб-интерфейс
└── tests/              # Тесты
📄 Лицензия
MIT License — свободно для изучения и экспериментов

💬 Контакты
GitHub: @Gruver87

Email: gruverpetrov@gmail.com

Спасибо за ваш вклад! 🚀
