# Release notes — v1.3.125

## Summary

**Industrial sync hardening (no simplifications):**

1. **Request-bound `blocks` response gate** — before fulfilling `_sync_waiters`, each `blocks` batch must match the active `get_blocks` context: first height, consecutive heights, parent linkage, and canonical hashes (Rust kernel). Rejected batches never deliver attacker data to import.
2. **Prod native shell fail-closed** — `p2p_native_transport` under prod / `require_native_crypto` requires `read_message_loop_events` (stale wheels raise). `/health/ready` surfaces `p2p_native_message_loop_shell`.

## Changes

- `verify_blocks_response_semantics_inner` / `verify_p2p_blocks_response_semantics`
- Waiter `request_ctx` on `_wait_peer_response` for sync batches
- Strike reasons: `bad_blocks_response_range` / `bad_blocks_response_continuity` / `bad_blocks_response_parent` / `empty_blocks_response` (+ existing `bad_block_hash`)
- Status/metrics: `native_blocks_response_semantic_gate`, `blocks_response_semantic_rejects_total`
- `node_version`: `1.3.125-industrial`

## Honesty

- Still **not** full Rust sync ownership / tip existence proof / fork-choice / state_root ownership / libp2p / public mainnet
- Import validation remains defense-in-depth
- Ceremony pin + external audit remain org blockers

## Verify

```text
make test-quick
python -m pytest tests/unit/test_v13125_p2p_blocks_response_semantic_gate.py -q
```
