# Absolute Blockchain Ultimate Hybrid — Справочник команд

> **Полный список команд (без секретов):** [`ALL_COMMANDS.txt`](ALL_COMMANDS.txt)  
> **Секреты:** только `.env` (gitignore) — см. [`secrets/README.md`](../secrets/README.md)  
> **Личная копия с секретами (Desktop, не в git):** `Absolute_Blockchain_All_Commands_FIXED.txt`

| | |
|---|---|
| **Версия** | `1.3.117-industrial` |
| **API Wave** | `61` |
| **Обновлено** | 2026-07-25 |
| **Entry** | `python main.py` / `.\scripts\start_node.ps1` |
| **Статус** | production-hardened R&D / prod-profile mesh — **не** public audited mainnet |

---

## Честно

- Gate green ≠ public mainnet
- Prod mesh `778888` = profile, не запущенный публичный mainnet
- Bridge на live mesh: **OFF** (пока нет audited L1 cutover)
- Ceremony pin + external audit = org blockers
- ABS = in-repo tokenomics (221M), не листинг

Доказательства: [EVIDENCE_MATRIX.md](EVIDENCE_MATRIX.md) · gaps: [MAINNET_GAP_ANALYSIS.md](MAINNET_GAP_ANALYSIS.md)

---

## Единая проверка работоспособности

```powershell
cd C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate_Hybrid

.\scripts\check_all.ps1                 # Quick — волны + industrial gate (~20–40 с)
.\scripts\check_all.ps1 -Mode Standard  # полный offline (pytest/audit)
.\scripts\check_all.ps1 -Mode Full      # Standard + rebuild abs_native
.\scripts\check_all.ps1 -Mode Live      # Quick + живой узел (:8080)
.\scripts\check_all.ps1 -Mode Max       # Full + Live + P2P
.\scripts\check_all.ps1 -Help
```

Отчёт: `data/check_all.json`. Перед `-Mode Live` / `Max`: `python main.py` (или `.\scripts\start_node.ps1`).

Алиасы того же полного gate: `.\scripts\test_all.ps1`, `.\scripts\check_everything.ps1`.

---

## Порты (шпаргалка)

| Что | Порт / URL |
|-----|------------|
| Explorer + REST | `http://localhost:8080` |
| Node2 / Node3 | `:8081` / `:8082` |
| JSON-RPC | `:8545` (prod docker alt `:18545`) |
| P2P | `:5000+` |
| WebSocket | `:8766` |
| Prod mesh 3 nodes | `:18180`–`:18182` |
| Chain ID devnet | `77777` |
| Chain ID mainnet-v1 profile | `778888` |

```powershell
(Invoke-RestMethod http://localhost:8080/status).api_wave
(Invoke-RestMethod http://localhost:8080/status).node_version
```

---

## Быстрый старт

```powershell
cd C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate_Hybrid
pip install -r requirements.txt
.\scripts\build_native.ps1
.\scripts\init_env.ps1
# заполнить .env (не коммитить)
python scripts/apply_local_secrets.py
.\scripts\start_node.ps1
```

Открыть: http://localhost:8080

---

## Оглавление полного справочника (`ALL_COMMANDS.txt`)

| Часть | Тема |
|------:|------|
| 0 | Быстрый старт |
| 1 | Первичная настройка |
| 2 | Одна нода |
| 3 | Два узла локально |
| 4–6 | Docker 2 / 3 / 5-validator |
| 7 | P2P sync / verify / heal |
| 8 | REST API L1 |
| 9 | Bridge |
| 10–11 | Кошелёк / TX · JSON-RPC |
| 12–14 | EVM · Explorer · Telegram |
| 15 | Production / mainnet-v1 Docker |
| 16 | Тесты · industrial gate · waves |
| 17 | Soak · evidence · resilience |
| 18 | RocksDB · backup · DR |
| 19 | P2P TLS mesh |
| 20 | Ceremony · validators · KMS |
| 21 | Public testnet / VPS |
| 22 | Observability · HA · K8s |
| 23 | Диагностика |
| 24 | Секреты → **только `.env`** (в репо — placeholders) |
| 25–26 | Git / пути · сценарии дня |
| 27 | Устаревшее |
| 28 | Industrial waves map **v1.3.65–86** |

---

## Самые частые команды

```powershell
# Devnet 2 nodes
.\scripts\stop_node.ps1
.\scripts\start_two_nodes.ps1 -RustBridge -Fresh
python scripts/verify_p2p_ci.py --mode devnet --wait 240

# Industrial waves (v1.3.65–91)
python scripts/verify_industrial_waves.py

# Native P2P fuzz smoke (Windows-friendly; cargo-fuzz on Linux CI)
.\scripts\fuzz_native.ps1 -Mode smoke
python scripts/industrial_gate.py

# Full local gate
.\scripts\test_full_project.ps1 -SkipNativeBuild -Live -P2P

# Prod-profile 3-node mesh
.\scripts\docker_prod_3node.ps1 -CeremonyDir data\ceremony_keys

# Перед push
python scripts/check_secrets.py
```

---

## Industrial waves (кратко)

Последние P2P/EVM срезы: **v1.3.77–86** (ingress, bandwidth, egress, NDJSON framer; CREATE/writeback journal).  
Полная таблица — **Часть 28** в [`ALL_COMMANDS.txt`](ALL_COMMANDS.txt) и [`PORTING_ROADMAP.md`](PORTING_ROADMAP.md).

**Не claimed:** full Rust P2P message-loop / libp2p (native I/O pumps+handshake+CN/SAN+auto-pong), public mainnet, external audit complete.

---

## Архитектура (коротко)

| Сервис | Порт | Статус |
|--------|------|--------|
| REST + Explorer | `:8080` | единый `main.py` |
| JSON-RPC | `:8545` | eth_* подмножество |
| P2P | `:5000` | 2/3/5-node + prod mesh proven |
| WebSocket | `:8766` | live feed |
| Storage | SQLite / RocksDB | Rocks — prod path |

Hybrid: Python orchestrates · Rust `abs_native` — crypto / EVM kernels / P2P wire+rate+frame.

---

PowerShell: всегда `.\scripts\...` (не без пути).  
Команды вводить без хвостов из отчётов (`→ OK`, `→ 99 passed`).
