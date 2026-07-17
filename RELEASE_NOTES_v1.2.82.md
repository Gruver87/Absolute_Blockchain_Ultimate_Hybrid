# Release Notes — v1.2.82

## Balance write-path unify (soak-safe)

Close remaining dual-write bypasses so every SQLite money insert/update sets `balance_satoshi`, and validators read satoshi via `state_truth`.

### What changed

| Path | Fix |
|------|-----|
| SQLite `reset_accounts_from_alloc` | `dual_write_balance` on INSERT |
| SQLite `nonce_increment` | `balance_satoshi=0` on new account |
| `DatabaseStateAdapter` | `canonical_balance_satoshi` (no float×1e6) |
| `migrate_sqlite_to_rocks` | Pass through `balance_satoshi` |
| `PersistentStorage.update_balance` | Delegate to `db.update_balance` |

### Compatibility

- Tip consensus root still hashes float `"b"` (unchanged soak contract)
- Float `balance` column retained
- **Do not** restart the running 48h soak for this release

### Verify

```powershell
pytest tests/unit/test_balance_write_path_unify.py tests/unit/test_balance_satoshi_dual_write.py tests/unit/test_state_engine_satoshi.py -q
python scripts/industrial_gate.py
.\scripts\soak_status.ps1
```

### Still open

- Drop float `balance` column after full fleet upgrade
- Tip state-root payload → satoshi (requires coordinated fork / rebuild)
- IMS shadow honesty → done in **v1.2.83**
- 48h soak PASS
