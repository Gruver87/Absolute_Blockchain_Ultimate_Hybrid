# Release notes — v1.3.205

## Summary

**Industrial mempool unparseable-nonce refuse (no simplifications):**

1. **Unparseable nonce refuse** — P2P wire txs with junk / Inf `nonce` are refused before `validate_transaction` (`nonce_unparseable`) instead of raising into the ingest path.
2. Soft DoS honesty — closes TypeError/ValueError/OverflowError crash gap on `int(nonce)`.
3. Sequel to v1.3.204 (unparseable value) / nonce_negative / nonce_too_high family.

## Changes

- `network/p2p_node.py` — safe nonce parse in `_build_mempool_tx_from_wire`
- Config: `p2p_mempool_unparseable_nonce_refuse` / `P2P_MEMPOOL_UNPARSEABLE_NONCE_REFUSE` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.205-industrial`

## Honesty

- Soft unparseable-nonce gate — **not** tip proof, not Long-Range, not libp2p / public mainnet, not account-nonce sequencing

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13205_mempool_unparseable_nonce_refuse.py -q
```
