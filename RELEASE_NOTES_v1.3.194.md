# Release notes — v1.3.194

## Summary

**Industrial mempool non-finite fee refuse (no simplifications):**

1. **NaN/Inf fee refuse** — P2P wire txs with non-finite `fee` are refused before `validate_transaction` (`fee_non_finite`).
2. Soft DoS honesty — `fee_negative` does not catch NaN/Inf; this closes that gap.
3. Sequel to v1.3.186 (negative fee) / v1.3.193 (non-finite value) refuse-before-validate family.

## Changes

- `network/p2p_node.py` — `math.isfinite` check on fee in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_nonfinite_fee_refuse` / `P2P_MEMPOOL_NONFINITE_FEE_REFUSE` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.194-industrial`

## Honesty

- Soft non-finite gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not Rust fee PQ

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13194_mempool_nonfinite_fee_refuse.py -q
```
