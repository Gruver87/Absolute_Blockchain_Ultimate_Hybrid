# Release notes — v1.3.191

## Summary

**Industrial mempool max-signature refuse (no simplifications):**

1. **Oversized signature refuse** — P2P wire txs with signature larger than `p2p_mempool_max_sig_bytes` (default 2048) are refused before `validate_transaction` (`signature_too_large`).
2. Soft DoS honesty — cheap size gate before ECDSA; complements `signature_empty` (v1.3.189).
3. Sequel to v1.3.183 (max-calldata) / v1.3.188–190 empty identity gates.

## Changes

- `network/p2p_node.py` — size check via `_wire_calldata_byte_len` on signature
- Config: `p2p_mempool_max_sig_refuse` / `P2P_MEMPOOL_MAX_SIG_REFUSE` (default on)
- Config: `p2p_mempool_max_sig_bytes` / `P2P_MEMPOOL_MAX_SIG_BYTES` (default 2048)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.191-industrial`
- README release badges refreshed to current tag (honest presentation)

## Honesty

- Soft signature-size gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not Rust gas PQ

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13191_mempool_max_sig_refuse.py -q
```
