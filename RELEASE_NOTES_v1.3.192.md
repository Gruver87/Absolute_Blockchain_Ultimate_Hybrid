# Release notes — v1.3.192

## Summary

**Industrial mempool max-pubkey refuse (no simplifications):**

1. **Oversized public_key refuse** — P2P wire txs with `public_key` larger than `p2p_mempool_max_pubkey_bytes` (default 2048) are refused before `validate_transaction` (`pubkey_too_large`).
2. Soft DoS honesty — cheap size gate before ECDSA; complements `pubkey_empty` (v1.3.190) and `signature_too_large` (v1.3.191).
3. Sequel to identity/size refuse-before-validate family.

## Changes

- `network/p2p_node.py` — size check via `_wire_calldata_byte_len` on public_key
- Config: `p2p_mempool_max_pubkey_refuse` / `P2P_MEMPOOL_MAX_PUBKEY_REFUSE` (default on)
- Config: `p2p_mempool_max_pubkey_bytes` / `P2P_MEMPOOL_MAX_PUBKEY_BYTES` (default 2048)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.192-industrial`

## Honesty

- Soft pubkey-size gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not Rust gas PQ

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13192_mempool_max_pubkey_refuse.py -q
```
