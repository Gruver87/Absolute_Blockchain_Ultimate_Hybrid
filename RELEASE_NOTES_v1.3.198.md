# Release notes — v1.3.198

## Summary

**Industrial mempool max-from refuse (no simplifications):**

1. **Oversized from refuse** — P2P wire txs with `from` / `from_addr` longer than the cap are refused before `validate_transaction` (`from_too_large`).
2. Soft DoS honesty — Python defense-in-depth aligned with Rust `MAX_P2P_ADDR_LEN` (default 128 chars).
3. Sequel to v1.3.188 (empty from) / max-hash refuse-before-validate family.

## Changes

- `network/p2p_node.py` — max-from check in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_max_from_refuse` / `p2p_mempool_max_addr_chars` (default on / 128)
- Env: `P2P_MEMPOOL_MAX_FROM_REFUSE` / `P2P_MEMPOOL_MAX_ADDR_CHARS`
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.198-industrial`

## Honesty

- Soft max-from gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not address checksum / anti-Sybil

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13198_mempool_max_from_refuse.py -q
```
