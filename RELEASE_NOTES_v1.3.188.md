# Release notes — v1.3.188

## Summary

**Industrial mempool empty-from refuse (no simplifications):**

1. **Empty from refuse** — P2P wire txs with empty/whitespace `from` / `from_addr` are refused before `validate_transaction` (`from_empty`).
2. Soft DoS honesty — cheap identity gate before ECDSA/state; not address checksum / anti-Sybil.
3. Sequel to v1.3.183–187 refuse-before-validate family.

## Changes

- `network/p2p_node.py` — empty-from check in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_empty_from_refuse` / `P2P_MEMPOOL_EMPTY_FROM_REFUSE` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.188-industrial`

## Honesty

- Soft empty-from gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not Rust gas PQ

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13188_mempool_empty_from_refuse.py -q
```
