# Release notes — v1.3.185

## Summary

**Industrial mempool negative-nonce refuse (no simplifications):**

1. **Negative nonce refuse** — P2P wire txs with `nonce < 0` are refused before `validate_transaction` (`nonce_negative`).
2. Soft DoS honesty — cheap sign gate; not account-nonce window / full mempool scheduler / Rust gas PQ.
3. Sequel to v1.3.184 (negative value) refuse-before-validate family.

## Changes

- `network/p2p_node.py` — negative-nonce check in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_negative_nonce_refuse` / `P2P_MEMPOOL_NEGATIVE_NONCE_REFUSE` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.185-industrial`

## Honesty

- Soft negative-nonce gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not Rust gas PQ

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13185_mempool_negative_nonce_refuse.py -q
```
