# Release notes — v1.3.204

## Summary

**Industrial mempool unparseable-value refuse (no simplifications):**

1. **Unparseable value refuse** — P2P wire txs with junk `value` / `amount` are refused before `validate_transaction` (`value_unparseable`) instead of raising into the ingest path.
2. Soft DoS honesty — closes TypeError/ValueError crash gap on `float(value)`.
3. Sequel to v1.3.203 (unparseable gas) / value_negative / value_non_finite family.

## Changes

- `network/p2p_node.py` — safe value parse in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_unparseable_value_refuse` / `P2P_MEMPOOL_UNPARSEABLE_VALUE_REFUSE` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.204-industrial`

## Honesty

- Soft unparseable-value gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not amount-cap economics

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13204_mempool_unparseable_value_refuse.py -q
```
