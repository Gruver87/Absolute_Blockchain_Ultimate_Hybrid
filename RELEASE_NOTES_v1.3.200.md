# Release notes — v1.3.200

## Summary

**Industrial mempool max-nonce refuse (no simplifications):**

1. **Oversized nonce refuse** — P2P wire txs with `nonce` above the cap are refused before `validate_transaction` (`nonce_too_high`).
2. Soft DoS honesty — fantasy nonces fail cheap before DB/ECDSA; default `1_000_000_000_000` (MAX_P2P_HEIGHT-style bound).
3. Sequel to v1.3.185 (negative nonce) refuse-before-validate family.

## Changes

- `network/p2p_node.py` — max-nonce check in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_max_nonce_refuse` / `p2p_mempool_max_nonce` (default on / 1e12)
- Env: `P2P_MEMPOOL_MAX_NONCE_REFUSE` / `P2P_MEMPOOL_MAX_NONCE`
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.200-industrial`

## Honesty

- Soft max-nonce gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not account-nonce window / mempool scheduler

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13200_mempool_max_nonce_refuse.py -q
```
