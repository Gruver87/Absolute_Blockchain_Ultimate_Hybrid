# Release notes — v1.3.197

## Summary

**Industrial mempool max-hash refuse (no simplifications):**

1. **Oversized hash refuse** — P2P wire txs with `hash` / `tx_hash` longer than the cap are refused before `validate_transaction` (`hash_too_large`).
2. Soft DoS honesty — Python defense-in-depth aligned with Rust `MAX_P2P_HASH_LEN` (default 128 chars).
3. Sequel to v1.3.196 (empty hash) / max-sig / max-pubkey refuse-before-validate family.

## Changes

- `network/p2p_node.py` — max-hash check in `_build_mempool_tx_from_wire` before dup lookup
- Config: `p2p_mempool_max_hash_refuse` / `p2p_mempool_max_hash_chars` (default on / 128)
- Env: `P2P_MEMPOOL_MAX_HASH_REFUSE` / `P2P_MEMPOOL_MAX_HASH_CHARS`
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.197-industrial`

## Honesty

- Soft max-hash gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not hash↔body binding

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13197_mempool_max_hash_refuse.py -q
```
