# v1.2.30 — Consensus hardening, ceremony native hash, 48h soak started

## Summary

Prod uses unified consensus only (parallel Casper/Beacon disabled on block events). Genesis ceremony digests route through `abs_native`. Industrial gate can require completed soak report. **Live prod mesh evidence re-run** after v1.2.29.

## Changed

- `consensus/adapter.py` — unified path skips parallel fork engines on `_on_new_block`
- `runtime/genesis_ceremony.py` — ceremony/validator/allocation hashes via native `hash_text` / `sha256_hex`
- `scripts/industrial_gate.py` — optional `--min-soak-hours` (reads `logs/soak_report.json`)

## Live evidence (2026-07-12 evening, Docker prod mesh :18180–18182)

| Check | Result |
|-------|--------|
| `prod_evm_smoke.py` (docker exec node1) | **PASS** — block #7, storage slot0=1 on all 3 RPC |
| `soak_monitor.ps1 -ProdMesh -Hours 48` | **STARTED** — `logs/soak_48h_v1.2.30.log` |
| `prod_signed_tx_smoke.py` | in progress / topology WARN (mesh mining resumed after EVM) |

Re-verify after soak completes:

```powershell
.\scripts\testnet_readiness.ps1 -ProdMesh -MinSoakHours 48
python scripts/industrial_gate.py --min-soak-hours 48
```
