# Release notes — v1.3.167

## Summary

**Industrial attestation tip ownership honesty (no simplifications):**

1. **Attestation target-head bind** — when `target_height` equals local tip height, `target_hash` must match local tip (`attestation_target_head_mismatch`).
2. Sequel to v1.3.137 (known-block height bind) + v1.3.136 (slot/height ahead gate).

## Changes

- `network/p2p_node.py` — `_attestation_target_head_refuse_reason` in `_handle_attestation`
- Config: `p2p_attestation_target_head_bind` / `P2P_ATTESTATION_TARGET_HEAD_BIND` (default on)
- Metrics / security status gauge + refuse counter
- `node_version`: `1.3.167-industrial`

## Honesty

- Soft tip-height ↔ tip-hash LMD ownership — **not** tip existence proof, not Long-Range / weak-subjectivity, not libp2p / public mainnet

## Verify

```text
.\scripts\operator_verify.ps1
.\scripts\operator_verify.ps1 -Mode Standard
python -m pytest tests/unit/test_v13167_attestation_target_head_bind.py -q
```
