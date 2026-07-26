# Release notes — v1.3.201

## Summary

**Industrial mempool max-fee refuse (no simplifications):**

1. **Oversized fee refuse** — P2P wire txs with `fee` above the cap are refused before `validate_transaction` (`fee_too_high`).
2. Soft DoS honesty — complements `fee_too_low`; default ceiling `1_000_000_000` ABS.
3. Sequel to v1.3.177 (min fee) / v1.3.186 (negative fee) refuse-before-validate family.

## Changes

- `network/p2p_node.py` — max-fee check in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_max_fee_refuse` / `p2p_mempool_max_fee` (default on / 1e9)
- Env: `P2P_MEMPOOL_MAX_FEE_REFUSE` / `P2P_MEMPOOL_MAX_FEE`
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.201-industrial`

## Honesty

- Soft max-fee gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not fee-market / Rust fee PQ

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13201_mempool_max_fee_refuse.py -q
```
