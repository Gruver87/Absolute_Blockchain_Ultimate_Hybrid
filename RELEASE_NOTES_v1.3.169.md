# Release notes — v1.3.169

## Summary

**Industrial GHOST parent ownership honesty (no simplifications):**

1. **GHOST head parent bind** — after canonical-head wire probe, require probed `parent_hash` to match expected tip-height parent (`ghost_head_parent_mismatch`).
2. Sequel to v1.3.164 (GHOST head probe) + v1.3.168 (fork peer-head parent bind).

## Changes

- `network/p2p_node.py` — parent check in `_ghost_head_probe_refuse_reason`
- Config: `p2p_ghost_head_parent_bind` / `P2P_GHOST_HEAD_PARENT_BIND` (default on)
- Metrics / security status gauge; refuse counted via ghost probe counter
- `node_version`: `1.3.169-industrial`

## Honesty

- Soft same-height GHOST sibling parent bind — **not** tip existence proof, not Long-Range / weak-subjectivity, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13169_ghost_head_parent_bind.py -q
```
