# State-root encoding migration (v1 → v2)

**Status:** planning scaffold — **v2 is not active** on mainnet-v1 (`chain_id` 778888).

## Current (v1) — `float_b_round12`

- Consensus tip `state_root` uses native encoding with float `round(balance, 12)` in field `"b"`.
- Enforced by `industrial_gate` (soak contract).
- Reads prefer `balance_satoshi` dual-write where available (`runtime/state_truth.py`).

Runtime snapshot: `GET /status` → `state_root_policy.encoding`.

## Planned (v2) — `satoshi_b`

- Tip commits use integer satoshi in field `"b_satoshi"`.
- Requires **chain halt**, state export, ceremony rebuild, and coordinated node upgrade.
- `state_root_encoding_version >= 2` in config is **blocked** until migration completes.

## Migration checklist (high level)

1. **Freeze** mining and publish halt block height `H_halt`.
2. **Export** canonical account set at `H_halt` (satoshi + nonce + code/storage hashes).
3. **Ceremony** recompute genesis/tip roots under v2 encoding; publish manifest hash.
4. **Deploy** nodes with `state_root_encoding_version=2` only after all validators sign manifest.
5. **Soak** 48h+ on staging mesh with v2 before any production cutover.
6. **Rollback** plan: keep v1 snapshot + DB backup until v2 mesh proven.

## Code references

| Area | Path |
|------|------|
| Encoding contract | `runtime/state_root_encoding.py` |
| Live tip root | `execution/state_root.py` → `compute_db_state_root` |
| Policy API | `Blockchain.get_state_root_policy()` |
| Auditor note | `docs/STORAGE_ROCKSDB.md` |

## Non-goals

- Silent in-place switch from float tip to satoshi tip without ceremony.
- Claiming “satoshi tip roots” while v1 encoding is active.
