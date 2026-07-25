# Release notes — v1.3.126

## Summary

**Industrial sync hardening (no simplifications):**

1. **Request-bound singular `block` response gate** — before fulfilling `_sync_waiters` for `get_block_by_hash`, the payload must be null (not-found) or a canonically hashed block whose claimed hash matches the requested digest. Mismatched well-formed blocks never steer fork reconcile / reorg.

## Changes

- `verify_block_response_semantics_inner` / `verify_p2p_block_response_semantics`
- Waiter `request_ctx` on `_request_block_by_hash` (`kind=block`, `expected_hash`)
- Strike reasons: `bad_block_response_hash` / `bad_block_response_expected` / `empty_block_response` (+ existing announce/hash reasons)
- Status/metrics: `native_block_response_semantic_gate`, `block_response_semantic_rejects_total`
- `node_version`: `1.3.126-industrial`

## Honesty

- Still **not** tip existence proof / fork-choice ownership / full Rust sync / libp2p / public mainnet
- Import validation remains defense-in-depth
- Ceremony pin + external audit remain org blockers

## Verify

```text
make test-quick
python -m pytest tests/unit/test_v13126_p2p_block_response_semantic_gate.py -q
```
