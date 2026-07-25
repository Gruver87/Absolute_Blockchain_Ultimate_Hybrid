# Contributing — Absolute Blockchain Ultimate

Спасибо за интерес! Это **production-hardened R&D / devnet** проект (локальный prod-mesh evidence, **не** launched public mainnet) — вклад в код, тесты и честную документацию приветствуется.

## Перед началом

1. **30 секунд:** [docs/AT_A_GLANCE.md](docs/AT_A_GLANCE.md) — что proven / что нет.
2. [DISCLAIMER.md](DISCLAIMER.md) — это **не** launched public audited mainnet.
3. Запуск: `python main.py` (не `_archive/`).

## 60-second setup

```bash
git clone https://github.com/Gruver87/Absolute_Blockchain_Ultimate_Hybrid.git
cd Absolute_Blockchain_Ultimate_Hybrid
pip install -r requirements.txt && cp .env.example .env
# Linux/macOS:  make build && make test-quick && python main.py
# Windows:      .\scripts\build_native.ps1 ; .\scripts\check_all.ps1 ; python main.py
```

http://localhost:8080

## Как помочь

| Действие | Зачем |
|----------|-------|
| Star / Watch Releases | Видимость репо |
| Issues + evidence | Баги с `data/check_all.json` / soak |
| Docs / PR | Фиксы, тесты — в **`master`** |

## Ветки

| Ветка | Назначение |
|-------|------------|
| **`master`** | Default development |
| **`main`** | Mirror of `master` (CI sync) |

PR → **`master`**. Мы **не** ведём фейковую историю «командных» PR ради hiring optics.

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

- Issues: https://github.com/Gruver87/Absolute_Blockchain_Ultimate_Hybrid/issues
- Автор: [@Gruver87](https://github.com/Gruver87)

**Спасибо за развитие Absolute Blockchain Ultimate вместе с сообществом!**
