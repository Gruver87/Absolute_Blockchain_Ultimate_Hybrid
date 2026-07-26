# Release notes — v1.3.161

## Summary

**Industrial STATUS tip-meta honesty (no simplifications):**

1. **Head requires height** — STATUS with `head_hash` but `height<=0` is refused when local tip `> 0` (`status_head_without_height`); tip meta is not installed.
2. Head-only at genesis (`local tip == 0`) still allowed for bootstrap.
3. Sequel to v1.3.155 (known-head height bind) + v1.3.159 (cap clears head).

## Changes

- `network/p2p_node.py` — refuse head-only STATUS when local tip > 0
- Config: `p2p_status_head_requires_height` / `P2P_STATUS_HEAD_REQUIRES_HEIGHT` (default on)
- Metrics / security status gauge + counter
- `node_version`: `1.3.161-industrial`

## Honesty

- Soft tip-meta ownership — **not** tip existence proof, not Long-Range / weak-subjectivity, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13161_status_head_requires_height.py -q
```
