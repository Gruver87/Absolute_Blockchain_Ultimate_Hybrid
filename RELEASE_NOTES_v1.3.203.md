# Release notes — v1.3.203

## Summary

**Industrial mempool unparseable-gas refuse (no simplifications):**

1. **Unparseable gas refuse** — P2P wire txs with Inf/junk `gas` are refused before `validate_transaction` (`gas_unparseable`) instead of raising into the ingest path.
2. Soft DoS honesty — closes OverflowError/ValueError crash gap on `int(gas)`.
3. Sequel to v1.3.187 (negative gas) / v1.3.179 (max gas) refuse-before-validate family.

## Changes

- `network/p2p_node.py` — safe gas parse in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_unparseable_gas_refuse` / `P2P_MEMPOOL_UNPARSEABLE_GAS_REFUSE` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.203-industrial`

## Honesty

- Soft unparseable-gas gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not Rust gas PQ

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13203_mempool_unparseable_gas_refuse.py -q
```
