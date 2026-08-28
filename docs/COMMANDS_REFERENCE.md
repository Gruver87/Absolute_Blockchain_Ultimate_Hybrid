# Absolute Blockchain — Справочник команд

> **Полный список (без секретов):** [`ALL_COMMANDS.txt`](ALL_COMMANDS.txt)  
> **Личная копия (Desktop):** `Absolute_Blockchain_All_Commands_FIXED.txt`  
> **Бэкап Desktop:** `Absolute_Blockchain_All_Commands_FIXED.bak_20260828.txt`  
> **Секреты:** только `.env` — [`secrets/README.md`](../secrets/README.md)

| | |
|---|---|
| **Обновлено** | 2026-08-28 |
| **Репозитории** | [Hybrid](https://github.com/Gruver87/Absolute_Blockchain_Ultimate_Hybrid) (audit pin) · [Experimental](https://github.com/Gruver87/experimental) (R&D) |
| **Entry** | `python main.py` / `.\scripts\start_node.ps1` |
| **Статус** | audit-freeze / prod-profile mesh — **не** public audited mainnet |

---

## Честно

- Gate green ≠ public mainnet
- Prod mesh `778888` = industrial profile, не публичный mainnet
- Bridge на live mesh: **OFF**
- Council 87 NFT — только Experimental staging `778889` (ADR 0022), **не** в audit-pin mesh

Доказательства: [`EVIDENCE_MATRIX.md`](EVIDENCE_MATRIX.md) · [`AT_A_GLANCE.md`](AT_A_GLANCE.md) · [`MAINNET_GAP_ANALYSIS.md`](MAINNET_GAP_ANALYSIS.md)

---

## L1 Integration Gate [обязательно после core/P2P/sync]

```powershell
cd C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate_Hybrid
.\scripts\build_native.ps1
.\scripts\docker_prod_3node.ps1 -SkipBuild -KeepVolumes
.\scripts\probe_prod_mesh.ps1 -Quick
python scripts/industrial_gate.py
```

---

## Быстрый старт (Hybrid, audit pin)

```powershell
cd C:\Users\vovun\Desktop\Absolute_Blockchain_Ultimate_Hybrid
.\scripts\build_native.ps1
.\scripts\start_all.ps1 -SkipBuild -KeepVolumes
```

R&D (libp2p, council NFT, Long-Range lab): репозиторий **Experimental**.

---

## Порты

| Что | Порт / URL |
|-----|------------|
| Solo REST | `http://localhost:8080` |
| Prod mesh | `:18180`–`:18182` |
| Chain ID prod mesh | `778888` |

---

## Оглавление `ALL_COMMANDS.txt`

| Часть | Тема |
|------:|------|
| 0–23 | Старт, devnet, API, bridge, prod mesh, gate, soak, DR, ceremony |
| 24 | Секреты — **только имена** (значения в `.env`) |
| 25–27 | Git, сценарии дня, устаревшее |
| 28 | ADR 0016 profiles |
| 29 | Hybrid vs Experimental |
| 30 | **L1 Integration Gate** |
| 31–32 | Experimental R&D labs и council NFT (см. Experimental repo) |

---

## Перед git push

```powershell
python scripts/check_secrets.py
```

PowerShell: всегда `.\scripts\...` — не без пути.
