# Release notes — v1.3.146

## Summary

**Industrial catch-up ownership honesty (no simplifications):**

1. **Head↔height local bind** — if `peer.head` is already known locally, claimed `peer.height` must match that header (`catch_up_head_height_mismatch`).
2. **Local-tip wire probe** — before `get_blocks` ahead catch-up, solicit `state_root` at local tip; fail/timeout/height mismatch refuses (`p2p_catch_up_tip_probe`, default on).
3. Sequel to v1.3.139 (require head) + wire-only state consistency waves.

## Changes

- `network/p2p_node.py` — refuse reasons + tip probe before sync download
- Config: `p2p_catch_up_tip_probe` / `P2P_CATCH_UP_TIP_PROBE`
- Metrics / security status gauges + refuse counters
- `node_version`: `1.3.146-industrial`

## Honesty

- Soft scheduling / wire bind — **not** tip existence proof, not root-belongs-to-head merkle, not Long-Range / weak-subjectivity checkpoint, not libp2p / public mainnet

## Verify

```text
.\scripts\check_all.ps1
python -m pytest tests/unit/test_v13146_catch_up_tip_probe.py tests/unit/test_v13139_p2p_catch_up_require_head.py -q
```
