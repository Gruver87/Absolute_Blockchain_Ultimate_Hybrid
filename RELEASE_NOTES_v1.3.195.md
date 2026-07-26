# Release notes — v1.3.195

## Summary

**Industrial mempool empty-to refuse (no simplifications):**

1. **Empty to refuse** — P2P wire txs with empty/whitespace `to` / `to_addr` are refused before `validate_transaction` (`to_empty`).
2. Soft DoS honesty — mirrors `from_empty`; chain already rejects via `missing_address`, this fails cheaper.
3. Sequel to v1.3.188 (empty from) refuse-before-validate family.

## Changes

- `network/p2p_node.py` — empty-to check in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_empty_to_refuse` / `P2P_MEMPOOL_EMPTY_TO_REFUSE` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.195-industrial`

## Honesty

- Soft empty-to gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not contract-create semantics / address checksum

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13195_mempool_empty_to_refuse.py -q
```
