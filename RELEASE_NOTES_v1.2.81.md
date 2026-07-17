# Release Notes — v1.2.81

## StateEngine satoshi ledger + canonical balance reads (soak-safe)

Continue core hardening. In-memory StateEngine stores balances as integer satoshi; API/Blockchain balance reads prefer the dual-write satoshi path via `runtime.state_truth`.

### What changed

| Layer | Behavior |
|-------|----------|
| `execution/state_engine.py` | Internal balances in satoshi; wire/genesis still ABS |
| `execution/state_root.py` | `compute_state_engine_root` hashes `balance_satoshi` |
| `runtime/state_truth.py` | `canonical_balance_satoshi` / `canonical_balance_abs` |
| `core/blockchain.py` | `get_balance` / `get_balance_satoshi` use state_truth |
| industrial_gate | Fails if StateEngine genesis is not satoshi |

### Compatibility

- Tip consensus root remains DB/Rocks (unchanged)
- Float `balance` column still dual-written (not dropped)
- **Do not** restart the running 48h soak for this release

### Verify

```powershell
pytest tests/unit/test_state_engine_satoshi.py tests/unit/test_state_root_native.py tests/test_integration.py::TestSystemC_StateEngine -q
python scripts/industrial_gate.py
.\scripts\soak_status.ps1
```

### Still open

- Drop float `balance` column after full fleet upgrade
- Unify Database / StateEngine / IMS as a single write path
- 48h soak PASS
