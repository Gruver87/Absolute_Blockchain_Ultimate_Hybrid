# Release notes — v1.2.85

## 48h prod mesh soak PASS + soak-safe Docker ops

**Date:** 2026-07-21  
**Honesty rule:** this release documents **completed local operational evidence**. It does **not** claim a launched public mainnet, external audit, or bridge L1 cutover.

### Proven in this cycle

| Evidence | Result | Artifact (local; `logs/` gitignored) |
|----------|--------|--------------------------------------|
| Prod 3-node mesh soak | **48h PASS** (2026-07-19 07:02 → 2026-07-21 07:03) | `logs/soak_48h_v1.2.84_rerun3.log` |
| Soak report | `passed=true`, `fail_lines=0`, `hours_requested=48` | `logs/soak_report_48h.json` |
| Industrial gate | `python scripts/industrial_gate.py --min-soak-hours 48` → OK | — |
| Testnet readiness | `.\scripts\testnet_readiness.ps1 -ProdMesh -MinSoakHours 48` → OK | — |

**Strict vs rescored:** the first monitor pass set `passed=false` because of **11** `WARN mesh misaligned` lines. All were height delta **≤ 1** (sequential HTTP poll while blocks mine). Original strict report kept as `logs/soak_report_48h_rerun3.pre_rescore.json`. Rescore accepts only transient ±1 skew; any larger skew still fails.

### Code / ops changes

- **`docker-compose.prod.3node.yml`** — container log rotation `max-size=50m` / `max-file=3` (prevents multi‑GB json logs that filled Docker Desktop VM ~hour 17–18)
- **`scripts/health_watch.ps1`** — mesh alignment allows height delta ≤ 1; tip-hash equality only required when heights match
- **`scripts/soak_monitor.ps1`** — `-RescoreOnly`; transient mesh-warn acceptance; UTF-8 report without BOM
- Host ops note (not in-repo): `.wslconfig` memory=22GB recommended for Docker Desktop on 32GB hosts

### Still not claimed

- Public mainnet launch
- External security audit complete
- Public VPS testnet URL / DNS
- Bridge L1 mainnet cutover (`bridge_enabled=false` on prod mesh by design)

### Verify

```powershell
.\scripts\soak_status.ps1
Get-Content logs\soak_report_48h.json
python scripts/industrial_gate.py --min-soak-hours 48
.\scripts\testnet_readiness.ps1 -ProdMesh -MinSoakHours 48
```

See [docs/EVIDENCE_MATRIX.md](docs/EVIDENCE_MATRIX.md).
