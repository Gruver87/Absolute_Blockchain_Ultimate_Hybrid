# ADR 0006 — Storage Boundary (Ports + Adapter + Unit DoD + Cutover)

- **Status:** Accepted A–E (canonical Blockchain UoW cutover wired)
- **Date:** 2026-07-29
- **Deciders:** Absolute Blockchain maintainers

## Context

Persistence was a duck-typed `Database` / `HybridDatabase` / `RocksChainStore`
surface. Domain code spoke engine verbs (`atomic`, sync flags) and risked
leaking CF / keycodec / bytes into business logic. Sync already avoids Rocks
imports; storage had no Protocol ADR.

## Decision

### A — Domain ports

| Path | Role |
|------|------|
| `storage/ports.py` | `BlockStorePort`, `StateStorePort`, `MetaStorePort`, `StorageUnitOfWorkPort`, `StorageHealthPort`, `StoragePort` |
| `storage/types.py` | `BlockRecord`, `AccountRecord`, `TipMeta`, typed `Storage*Error` |

Ports exchange domain values only. Byte packing, JSON, CF names stay in adapters.

Atomic contract:

```text
uow = storage.begin_block_commit(expected_parent=..., expected_tip_height=...)
uow.write_block(...)
uow.write_state_delta(...)
uow.set_tip(TipMeta(...))
uow.commit()  # all-or-nothing
```

### B — RocksDB adapter

`storage/adapters/rocks_adapter.py` implements ports over store façades:

- Prefer join of open `atomic()` / `_pending_batch` (no nested WriteBatch)
- Else single `store.atomic()` + `_persist_block_locked` + writeback + tip fence
- Error map: ENOSPC → `StorageFullError`; decode fail → `StorageCorruptionError`; IO → `StorageUnavailableError`
- Reopen repair: tip must reference an existing body or fail-closed / rewind

### C — Unit DoD

`tests/unit/fakes/fake_storage.py` + `tests/unit/test_storage_ports.py`:
atomicity, abort, crash recover, reorg, disk_full, corruption, CAS conflict,
isolation needles (no Rocks imports in ports/types).

### D — Factory

`storage/factory.open_storage(db)` wraps SQLite/`HybridDatabase` as `StoragePort`.
`main.py` wires `storage=open_storage(self.db)` into `Blockchain`.

### E — Blockchain canonical cutover

`Blockchain(..., storage=...)` DI; `add_block` persist seam is
`_persist_canonical_via_storage` (UoW + CAS). Execution (`balance_delta` /
native apply) stays on legacy `self.db` inside the same outer `atomic()`.
`import_block` unchanged (delegates to `add_block`) — tip_safety / sync order preserved.

Evidence: `tests/unit/test_blockchain_storage_cutover.py`.

## Honesty

- Ports ≠ aux.db evacuated / 100% Rocks
- Canonical UoW cutover ≠ every `self.db.*` call site removed (balance/nonce/reorg still legacy)
- Unit/integration green ≠ live disk-fill soak / public mainnet storage audit

## Out of scope (later)

- F: evacuate aux.db behind `MetaStorePort` or document permanent dual-store
- Expand StateStorePort for balance/nonce and reorg-replay UoW
