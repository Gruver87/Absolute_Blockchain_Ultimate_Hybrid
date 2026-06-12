# Security / Секреты

## Что НЕ должно попадать в Git

- `data/wallet.json` — локальный кошелёк (используйте `wallet.example.json`)
- `.env` — API keys, JWT secret, bot tokens
- `*.db`, `data/` — база блокчейна
- Приватные ключи, seed-фразы, пароли

## Что в репозитории (публично)

- `wallet.example.json` — шаблон без ключей
- `.env.example` — плейсхолдеры
- Адрес основателя в `runtime/tokenomics.py` — **публичный** учебный адрес (не приватный ключ)

## Oracles

Ключи OpenWeather / WeatherAPI берутся только из переменных окружения:
`OPENWEATHER_API_KEY`, `WEATHERAPI_KEY` в `.env`.

## Проверка перед push

```bash
python scripts/check_secrets.py
```

Скрипт запускается в CI — push с ключами в коде будет заблокирован.

## Старый справочник v57 (Часть 23)

Файлы с **API keys, Telegram token, SSH, private keys** — **только локально** на ПК.  
Не добавляйте в git. Используйте актуальный: `docs/COMMANDS_REFERENCE.md` (без секретов).

## Если ключ случайно попал в Git

1. Немедленно **отзовите/ротируйте** ключ на стороне сервиса  
2. Не храните приватные ключи в `data/wallet.json`  
3. Старые коммиты на GitHub могут сохранять историю — при утечке рассмотрите `git filter-repo` или GitHub secret scanning
