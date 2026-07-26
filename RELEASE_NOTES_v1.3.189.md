# Release notes — v1.3.189

## Summary

**Industrial mempool empty-signature refuse (no simplifications):**

1. **Empty signature refuse** — P2P wire txs with empty/whitespace `signature` are refused before `validate_transaction` (`signature_empty`).
2. Soft DoS honesty — cheap ECDSA skip; not full signature verify / tip proof.
3. Sequel to v1.3.188 (empty from) refuse-before-validate family.

## Changes

- `network/p2p_node.py` — empty-signature check in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_empty_sig_refuse` / `P2P_MEMPOOL_EMPTY_SIG_REFUSE` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.189-industrial`

## Honesty

- Soft empty-signature gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not Rust gas PQ

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13189_mempool_empty_sig_refuse.py -q
```
