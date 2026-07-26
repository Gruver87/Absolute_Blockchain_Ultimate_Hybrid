# Release notes — v1.3.172

## Summary

**Industrial catch-up tip digest ownership honesty (no simplifications):**

1. **Catch-up tip-head bind** — after height catch-up reaches `peer.height`, local tip hash must match `peer.head` (`catch_up_tip_head_mismatch`).
2. Import-loop also refuses a block at `peer.height` whose hash ≠ `peer.head`.
3. Sequel to v1.3.163 (reconcile fetched head hash bind) — height-complete cannot greenwash without tip digest ownership.

## Changes

- `network/p2p_node.py` — `_catch_up_tip_head_refuse_reason` + import-loop tip bind + post-loop clear `reached_target`
- Config: `p2p_catch_up_tip_head_bind` / `P2P_CATCH_UP_TIP_HEAD_BIND` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.172-industrial`

## Honesty

- Soft tip digest bind at catch-up completion — **not** tip existence proof, not Long-Range / weak-subjectivity, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13172_catch_up_tip_head_bind.py -q
```
