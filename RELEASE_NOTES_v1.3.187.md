# Release notes — v1.3.187

## Summary

**Industrial mempool negative-gas refuse (no simplifications):**

1. **Negative gas refuse** — P2P wire txs with `gas < 0` are refused before `validate_transaction` (`gas_negative`).
2. Soft DoS honesty — complements `gas_too_high`; note `gas = int(...) or 21000` keeps negatives (only 0 defaults).
3. Sequel to v1.3.184–186 sign-gate family (value / nonce / fee).

## Changes

- `network/p2p_node.py` — negative-gas check in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_negative_gas_refuse` / `P2P_MEMPOOL_NEGATIVE_GAS_REFUSE` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.187-industrial`

## Honesty

- Soft negative-gas gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not Rust gas PQ

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13187_mempool_negative_gas_refuse.py -q
```
