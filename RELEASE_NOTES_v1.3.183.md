# Release notes — v1.3.183

## Summary

**Industrial mempool max-calldata refuse (no simplifications):**

1. **Calldata size refuse** — P2P wire txs with calldata larger than `p2p_mempool_max_calldata_bytes` (default 128 KiB) are refused before `validate_transaction` (`calldata_too_large`).
2. Soft DoS honesty — cheap size gate; not full RLP tx-size budget / Rust mempool.
3. Sequel to v1.3.177 (min-fee) / v1.3.179 (max-gas) refuse-before-validate family.

## Changes

- `network/p2p_node.py` — `_wire_calldata_byte_len` + refuse in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_max_calldata_refuse` / `P2P_MEMPOOL_MAX_CALLDATA_REFUSE` (default on)
- Config: `p2p_mempool_max_calldata_bytes` / `P2P_MEMPOOL_MAX_CALLDATA_BYTES` (default 131072)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.183-industrial`

## Honesty

- Soft calldata size gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not Rust gas PQ

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13183_mempool_max_calldata_refuse.py -q
```
