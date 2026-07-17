# Release Notes — v1.2.83

## IMS honesty + satoshi read leftovers (soak-safe)

Shadow ImmutableState now mirrors DB satoshi after each block. Remaining float read bypasses prefer satoshi. Tip state-root float `"b"` encoding is frozen in industrial_gate.

### What changed

| Path | Fix |
|------|-----|
| `ImmutableStateManager.reconcile_from_store` | Mirror DB/Rocks satoshi (+ nonce) into IMS |
| `main.py` post-block IMS sync | Reconcile touched addrs (not flawed fee apply) |
| `/state/balance`, `/state/supply`, … | DB cross-check + `canonical` flag |
| `/state/credit` | Explicit prod 403 (IMS shadow only) |
| `get_address_activity` / total supply | Prefer `balance_satoshi` |
| `Blockchain` insufficient-funds | Satoshi compare |
| `industrial_gate` | Tip float `"b"` soak contract + IMS reconcile |

### Compatibility

- Tip consensus root still hashes float `"b"` (unchanged soak contract)
- Float `balance` column retained
- **Do not** restart the running 48h soak for this release

### Verify

```powershell
pytest tests/unit/test_ims_reconcile_honesty.py tests/unit/test_balance_write_path_unify.py tests/unit/test_state_engine_satoshi.py -q
python scripts/industrial_gate.py
.\scripts\soak_status.ps1
```

### Still open

- Tip state-root payload → satoshi (coordinated rebuild / fork)
- Drop float `balance` column after full fleet upgrade
- 48h soak PASS
