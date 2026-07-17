# Release Notes — v1.2.80

## Balance satoshi dual-write (soak-safe)

Continue core hardening without new features. Canonical money math uses integer satoshi; storage dual-writes `balance_satoshi` + derived float `balance`.

### What changed

| Layer | Behavior |
|-------|----------|
| SQLite `accounts` | Column `balance_satoshi`; backfill on migrate; writes update both |
| Rocks account JSON | Field `balance_satoshi`; deltas applied in satoshi |
| HybridDatabase / Blockchain | `get_balance_satoshi()` |
| industrial_gate | Fails if amount dual-write helpers missing |

### Compatibility

- Existing float balances still readable (backfill on read/write)
- API `get_balance` still returns float ABS derived from satoshi
- **Do not** restart the running 48h soak for this release

### Verify

```powershell
pytest tests/unit/test_balance_satoshi_dual_write.py tests/unit/test_amount_units.py -q
python scripts/industrial_gate.py
.\scripts\soak_status.ps1
```

### Still open

- Drop float `balance` column after full fleet upgrade
- Unify StateEngine int units with satoshi ledger → done in **v1.2.81**
- 48h soak PASS
