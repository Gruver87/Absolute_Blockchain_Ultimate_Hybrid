# Release notes — v1.3.193

## Summary

**Industrial mempool non-finite value refuse (no simplifications):**

1. **NaN/Inf value refuse** — P2P wire txs with non-finite `value` are refused before `validate_transaction` (`value_non_finite`).
2. Soft DoS honesty — `value_negative` does not catch NaN/Inf; this closes that gap.
3. Sequel to v1.3.184 (negative value) refuse-before-validate family.

## Changes

- `network/p2p_node.py` — `math.isfinite` check in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_nonfinite_value_refuse` / `P2P_MEMPOOL_NONFINITE_VALUE_REFUSE` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.193-industrial`

## Honesty

- Soft non-finite gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not Rust gas PQ

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13193_mempool_nonfinite_value_refuse.py -q
```
