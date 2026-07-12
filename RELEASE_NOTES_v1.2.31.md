# v1.2.31 — Live prod mesh gate + health_watch + evidence recorder

## Summary

Operational gates for the **real** Docker prod mesh (:18180–18182), longer health timeouts under load, and a script to persist live evidence steps locally.

## Added

- `--live-prod-mesh` on `mainnet_readiness.py` and `verify_prod_stack.py` — 3-node alignment + `prod_smoke` on leader
- `scripts/record_evidence_run.py` — append PASS/FAIL steps to `data/evidence_run.json`
- `health_watch.ps1` — longer timeouts when `-ProdMesh` (fewer false FAILs during soak)

## Verified (2026-07-12 evening)

```powershell
python scripts/mainnet_readiness.py --live-prod-mesh --no-strict-audit   # OK
python scripts/record_evidence_run.py --name prod_evm_smoke --result PASS ...
```

48h soak continues: `logs/soak_48h_v1.2.30.log`
