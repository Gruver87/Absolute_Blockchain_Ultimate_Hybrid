# Release notes — v1.3.196

## Summary

**Industrial mempool empty-hash refuse (no simplifications):**

1. **Empty hash refuse** — P2P wire txs with empty/whitespace `hash` / `tx_hash` are refused before `validate_transaction` (`hash_empty`).
2. Soft DoS honesty — empty hash skips the cheap `duplicate_tx` path; this closes that gap.
3. Sequel to v1.3.143 (dup-hash refuse) / empty-field refuse-before-validate family.

## Changes

- `network/p2p_node.py` — empty-hash check in `_build_mempool_tx_from_wire` before dup lookup
- Config: `p2p_mempool_empty_hash_refuse` / `P2P_MEMPOOL_EMPTY_HASH_REFUSE` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.196-industrial`

## Honesty

- Soft empty-hash gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not hash↔body binding / tip proof

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13196_mempool_empty_hash_refuse.py -q
```
