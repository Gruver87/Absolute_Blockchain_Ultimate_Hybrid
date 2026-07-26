# Release notes — v1.3.190

## Summary

**Industrial mempool empty-pubkey refuse (no simplifications):**

1. **Empty public_key refuse** — P2P wire txs with empty/whitespace `public_key` are refused before `validate_transaction` (`pubkey_empty`).
2. Soft DoS honesty — cheap ECDSA skip; not key-format validation / tip proof.
3. Sequel to v1.3.188 (empty from) / v1.3.189 (empty signature).

## Changes

- `network/p2p_node.py` — empty-pubkey check in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_empty_pubkey_refuse` / `P2P_MEMPOOL_EMPTY_PUBKEY_REFUSE` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.190-industrial`

## Honesty

- Soft empty-pubkey gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not Rust gas PQ

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13190_mempool_empty_pubkey_refuse.py -q
```
