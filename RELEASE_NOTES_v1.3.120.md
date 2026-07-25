# Release notes — v1.3.120

## Summary

**Native `new_block` canonical-hash ingress:** on the message-loop shell, announced blocks whose claimed `hash` does not match the canonical recompute (parity with `import_block` / `Block._compute_hash`) are struck before Python dispatch. Parent/height continuity, proposer, and state_root validity stay Python.

## Changes

- `recomputed_canonical_block_hash` + `verify_block_announce_semantics_inner`
- `check_block_announce_semantics` on `read_message_loop_events`
- Strike reason: `bad_block_hash` (shape failures stay `bad_block_announce`)
- Status: `native_block_semantic_gate`, `block_semantic_rejects_total`
- Metrics: `abs_p2p_native_block_semantic_gate`, `abs_p2p_block_semantic_rejects_total`
- `node_version`: `1.3.120-industrial`

## Honesty

- Still **not** full block validation / fork-choice / Rust import ownership
- Still **not** full message-loop / libp2p
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13120_p2p_native_block_semantic_gate.py -q
```
