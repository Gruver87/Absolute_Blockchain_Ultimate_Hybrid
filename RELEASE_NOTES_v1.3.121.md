# Release notes — v1.3.121

## Summary

**Native `blocks` batch hash ingress:** on the message-loop shell, each block in a sync `blocks` array is canonical-hash checked (reuses `verify_block_announce_semantics_inner`). Parent continuity, import, and fork-choice stay Python.

Also: root **Makefile** for Linux/macOS (`make build` / `test-quick` / `test-gate` / `mesh-up`) wrapping existing scripts. PowerShell remains the Windows path; CI was already Ubuntu-native.

## Changes

- `verify_blocks_batch_semantics_inner` + `check_blocks_batch_semantics` on `read_message_loop_events`
- Strike: `bad_block_hash` per bad entry (shape: `bad_blocks_batch`)
- Status: `native_blocks_batch_semantic_gate` (rejects fold into `block_semantic_rejects_total`)
- Metrics: `abs_p2p_native_blocks_batch_semantic_gate`
- Root `Makefile` + README / COMMANDS_REFERENCE dual entry
- `node_version`: `1.3.121-industrial`

## Honesty

- Still **not** full sync import / fork-choice / message-loop / libp2p
- Makefile ≠ “no Windows” and ≠ public mainnet
- Not adding fake `develop` PR theater or Cargo `crates/` mega-split
- Ceremony pin + external audit remain org blockers

## Verify

```text
make test-quick
# or:
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13121_p2p_native_blocks_batch_semantic_gate.py -q
```
