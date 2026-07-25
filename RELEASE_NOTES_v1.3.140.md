# Release notes — v1.3.140

## Summary

**Industrial sync honesty (no simplifications):**

1. **SyncEngine never invents `peer.head`** — `request_heads` no longer fills an empty peer head from the local block at `peer.height`. Peers without a concrete head are skipped (aligns with catch-up-require-head from v1.3.139).
2. **Ops** — `check_all.ps1` Standard/Full/Max `EvidenceGitTag` bumped off the stale `v1.3.114` pin.

## Changes

- `sync/sync_engine.py` `request_heads` + `heads_skipped_no_head` telemetry
- Metrics: `native_sync_heads_no_invent`, `heads_skipped_no_head`
- `node_version`: `1.3.140-industrial`

## Honesty

- Soft head-collection honesty — **not** tip existence proof, not fork-choice finality, not libp2p, not ceremony pin / public mainnet

## Verify

```text
.\scripts\check_all.ps1
python -m pytest tests/unit/test_v13140_sync_heads_no_invent.py -q
```
