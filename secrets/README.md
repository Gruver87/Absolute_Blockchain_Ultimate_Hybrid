# Локальные секреты — только `.env`

## Правило

| Что | Где хранить | В git? |
|-----|-------------|--------|
| API keys, tokens, private keys | **`.env`** в корне проекта | **Нет** (`.gitignore`) |
| Публичный адрес founder | `data/wallet.json`, справочники | Адрес — да; **private_key — нет** |
| Команды и URL | `docs/ALL_COMMANDS.txt` | Да (без секретов) |

**Никогда** не пишите токены и приватные ключи в `.txt`, чаты, скриншоты и markdown.

## Первый запуск

```powershell
.\scripts\init_env.ps1
# Откройте .env в редакторе и вставьте свои ключи
python scripts/apply_local_secrets.py   # синхронизирует WALLET_PRIVATE_KEY → wallet.json
```

## Перед git push

```powershell
python scripts/check_secrets.py
```

## Если ключи светились раньше

Перевыпустите: GitHub PAT, Telegram bot token, OpenWeather/WeatherAPI, Ngrok, SSH пароль.
