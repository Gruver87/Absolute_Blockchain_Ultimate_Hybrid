# Release notes — v1.3.141

## Summary

**Industrial sync honesty (no simplifications):**

1. **`sync_state` same-height match is wire-only** — no longer invents consistency from the local block at `peer.height` when wire roots lack a same-height match.
2. Sequel to v1.3.140 (no invent of `peer.head` in `request_heads`).

## Changes

- `sync/sync_engine.py` — remove local `get_block(peer_height)` invent loop in `sync_state`
- Status / metrics: `native_sync_state_wire_only`
- `node_version`: `1.3.141-industrial`

## Honesty

- Soft wire-probe honesty — **not** tip existence proof, not fork-choice finality, not libp2p, not ceremony pin / public mainnet

## Verify

```text
.\scripts\check_all.ps1
python -m pytest tests/unit/test_v13141_sync_state_wire_only.py -q
```
