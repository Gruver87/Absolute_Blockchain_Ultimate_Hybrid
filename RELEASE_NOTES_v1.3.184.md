# Release notes — v1.3.184

## Summary

**Industrial mempool negative-value refuse (no simplifications):**

1. **Negative value refuse** — P2P wire txs with `value < 0` are refused before `validate_transaction` (`value_negative`).
2. Soft DoS honesty — cheap sign gate; not amount-cap economics / full tokenomics port / Rust fee scheduler.
3. Sequel to v1.3.177 (min-fee) / v1.3.179 (max-gas) / v1.3.183 (max-calldata) refuse-before-validate family.

## Changes

- `network/p2p_node.py` — negative-value check in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_negative_value_refuse` / `P2P_MEMPOOL_NEGATIVE_VALUE_REFUSE` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.184-industrial`

## Honesty

- Soft negative-value gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not Rust gas PQ

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13184_mempool_negative_value_refuse.py -q
```
