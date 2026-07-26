# Release notes — v1.3.199

## Summary

**Industrial mempool max-to refuse (no simplifications):**

1. **Oversized to refuse** — P2P wire txs with `to` / `to_addr` longer than the cap are refused before `validate_transaction` (`to_too_large`).
2. Soft DoS honesty — mirrors `from_too_large`; shares `p2p_mempool_max_addr_chars` (default 128, Rust `MAX_P2P_ADDR_LEN`).
3. Sequel to v1.3.195 (empty to) / v1.3.198 (max from) refuse-before-validate family.

## Changes

- `network/p2p_node.py` — max-to check in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_max_to_refuse` / shared `p2p_mempool_max_addr_chars` (default on / 128)
- Env: `P2P_MEMPOOL_MAX_TO_REFUSE`
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.199-industrial`

## Honesty

- Soft max-to gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not address checksum / contract-create

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13199_mempool_max_to_refuse.py -q
```
