# Release Notes — v1.2.84

## Prod-critical fail-loud honesty (soak-safe)

Close silent `except: pass` on mesh consistency probes, genesis audit meta, state-root mismatch audit, and IMS nonce mirror. Freeze mesh mining policy in `prod_gate`.

### What changed

| Path | Fix |
|------|-----|
| Mining loop sync probe | Log + `_state_consistent=False` |
| `SyncEngine.sync_state` | Log wire probe failure; `wire_probe_ok` in status |
| Genesis `set_meta` | Fail-loud in prod |
| `record_state_root_mismatch` | Log on failure |
| `/chain/state-root/status` | `peer_probe_error` field |
| IMS `reconcile_from_store` | `fail_loud` for nonce errors |
| `prod_gate` | Mesh peers / follower sync / no tip rewrite |
| `industrial_gate` | Fail-loud surface inspect |

### Compatibility

- Tip consensus root still hashes float `"b"`
- Float `balance` column retained
- **Do not** restart the running 48h soak for this release

### Verify

```powershell
pytest tests/unit/test_silent_except_honesty.py -q
python scripts/industrial_gate.py
python scripts/prod_gate.py
.\scripts\soak_status.ps1
```

### Still open

- Tip state-root payload → satoshi (coordinated rebuild)
- Drop float `balance` column after fleet upgrade
- 48h soak PASS
