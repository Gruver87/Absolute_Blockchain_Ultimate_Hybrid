# Release notes — v1.3.186

## Summary

**Industrial mempool negative-fee refuse (no simplifications):**

1. **Negative fee refuse** — P2P wire txs with `fee < 0` are refused before `validate_transaction` (`fee_negative`).
2. Soft DoS honesty — complements `fee_too_low` when `min_fee==0`; not Rust fee priority queue.
3. Sequel to v1.3.184 (value) / v1.3.185 (nonce) sign-gate family.

## Changes

- `network/p2p_node.py` — negative-fee check in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_negative_fee_refuse` / `P2P_MEMPOOL_NEGATIVE_FEE_REFUSE` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.186-industrial`

## Honesty

- Soft negative-fee gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not Rust gas PQ

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13186_mempool_negative_fee_refuse.py -q
```
