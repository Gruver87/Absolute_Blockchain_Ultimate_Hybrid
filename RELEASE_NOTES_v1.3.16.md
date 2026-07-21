# Release notes — v1.3.16

**Date:** 2026-07-21  
**Theme:** Shared SyncEngine + unsolicited state_root honesty + probe/sqlite alerts

## Sync / P2P honesty

- Node shares one `SyncEngine` with P2P (`p2p.sync_engine = self.sync_engine`) so HTTP repair and mesh use the same probe path
- P2P boots `_state_consistent=False`; unsolicited `MSG_STATE_ROOT_RESPONSE` never flips consistent=True on match (only SyncEngine.sync_state may)
- Unsolicited mismatch clears consistency and logs a warning
- Fork-recovery drill defaults `state_consistent` to False when absent

## Metrics / alerts

- `abs_sync_wire_probe_probed` (already) + alert **AbsoluteSyncWireProbeNeverProbed** (peers up, probe still unknown)
- Alert **AbsoluteProdSqliteEngine** when `abs_db_engine{engine="sqlite"}==1`

## Gates / tests

- industrial_gate needles for shared SyncEngine + unsolicited honesty + new alerts
- `test_silent_except_honesty` covers shared SyncEngine / unsolicited path

## Explicit non-goals (unchanged)

- External pen-test / third-party L1 audit
- Ceremony pin without operator `--ceremony-dir`
- Bridge ON / public mainnet launch
