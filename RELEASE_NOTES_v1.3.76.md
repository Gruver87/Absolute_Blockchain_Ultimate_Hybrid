# Release notes — v1.3.76

## Value-transfer CALL ownership (fail-closed)

### What shipped

- Inline **value > 0 CALL** when `bridge_state.balances` is preloaded
- Fail-closed debit: insufficient balance → CALL returns 0, child not executed, balances unchanged
- On child revert/OOG: balance snapshot restored
- Without balances map: fall through to Python hook (no invented balances)

### Honesty

- Not full account DB / satoshi writeback inside the opcode loop
- CALLCODE value transfer and journaled Rocks debit still use the adapter path
- Not public mainnet; bridge OFF on live mesh

### Version

- `node_version`: `1.3.76-industrial`

### Verify

```powershell
python scripts/verify_industrial_waves.py
pytest tests/unit/test_v1376_value_call.py -q
```
