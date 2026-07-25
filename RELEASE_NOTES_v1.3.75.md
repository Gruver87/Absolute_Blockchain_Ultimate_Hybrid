# Release notes — v1.3.75

## Multi-depth value=0 CALL frames

### What shipped

- `bytecode_is_inline_call_frame_eligible` — allows CALL*/LOG; rejects CREATE/SELFDESTRUCT
- Nested value=0 CALL chains (A→B→C) run fully in Rust when codes/storages are preloaded
- Depth cap: `MAX_INLINE_CALL_DEPTH = 4` via `_abs_inline_depth` on host_context
- CREATE-containing children still use the Python hook (fail-closed)

### Honesty

- Not value-transfer CALL ownership
- Not unbounded recursion / Cancun-complete EVM
- Not public mainnet; bridge OFF on live mesh

### Version

- `node_version`: `1.3.75-industrial`

### Verify

```powershell
python scripts/verify_industrial_waves.py
pytest tests/unit/test_v1375_multidepth_call.py -q
```
