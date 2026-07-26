# Release notes — v1.3.177

## Summary

**Industrial mempool min-fee cheap refuse (no simplifications):**

1. **P2P min-fee refuse** — wire txs with `fee < mempool.min_fee` are refused **before** `validate_transaction` (ECDSA/state) (`fee_too_low`).
2. Soft DoS honesty under spam — **not** a Rust gas priority queue / EIP-1559 lanes.
3. Sequel to v1.3.143 (dup cheap refuse) + solicit-armed mempool shell.

## Changes

- `network/p2p_node.py` — min-fee gate in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_min_fee_refuse` / `P2P_MEMPOOL_MIN_FEE_REFUSE` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.177-industrial`

## Honesty

- Cheap ingress refuse — **not** tip proof, not Long-Range, not libp2p / public mainnet, not Rust fee scheduler

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13177_mempool_min_fee_refuse.py -q
```
