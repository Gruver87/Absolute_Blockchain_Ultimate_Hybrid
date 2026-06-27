# Contributing — Absolute Blockchain Ultimate

Спасибо за интерес! Это **production-hardened R&D/devnet** проект — любой вклад в код, тесты и документацию приветствуется.

## Перед началом

1. Прочитайте [DISCLAIMER.md](DISCLAIMER.md) — проект **не является запущенным public audited mainnet**.
2. Запуск только через `python main.py` (не `_archive/` и не старые скрипты).

## Как помочь

| Действие | Зачем |
|----------|-------|
| ⭐ Star | Помогает другим найти репозиторий |
| 🍴 Fork | Безопасные эксперименты в своей копии |
| 🐛 Issues | Баги, идеи, вопросы |
| 📝 Docs | README, ARCHITECTURE, комментарии |
| 🔧 PR | Фичи, фиксы, тесты |
| 📢 Share | Курсы, статьи, демо — продвигайте дальше |

## Настройка

```bash
git clone https://github.com/Gruver87/absolute-blockchain-ultimate.git
cd absolute-blockchain-ultimate
pip install -r requirements.txt
cp .env.example .env
python main.py
```

Откройте http://localhost:8080

## Разработка

```bash
git checkout -b feature/my-change
# ... правки ...
pytest tests/ -q
python tests/smoke/merkle_light.py
python scripts/final_audit.py
git commit -m "feat: описание"
git push origin feature/my-change
```

Создайте Pull Request на GitHub.

## Code style

- Минимальный diff — не рефакторить несвязанный код
- Следовать стилю соседних файлов
- Комментарии только для неочевидной логики
- Не коммитить: `.env`, `data/`, ключи, `__pycache__`

## Commit messages

```
feat: add SPV endpoint for block proofs
fix: pool lock check in mempool
docs: update README tokenomics section
test: merkle light client cases
```

## Идеи для контрибьюторов

- Улучшение P2P и синхронизации между узлами
- Больше pytest-тестов вместо script-style tests
- Усиление production-hardening и security gates
- Перевод документации
- CI (GitHub Actions): `pytest tests/`, `tests/smoke/merkle_light.py`, `scripts/final_audit.py`

## Вопросы

- Issues: https://github.com/Gruver87/absolute-blockchain-ultimate/issues
- Автор: [@Gruver87](https://github.com/Gruver87)

**Спасибо за развитие Absolute Blockchain Ultimate вместе с сообществом!**
