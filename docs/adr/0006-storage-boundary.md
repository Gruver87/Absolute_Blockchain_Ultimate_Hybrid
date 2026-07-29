# ADR 0006 — Storage Boundary (Ports + Adapter + Unit DoD)

- **Status:** Accepted (A); B adapter implemented; C unit DoD via FakeStorage
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

`storage/adapters/rocks_adapter.py` implements ports over `RocksChainStore`:

- Single commit path maps UoW → `persist_block_atomic` + account writeback + tip fence
- Error map: ENOSPC → `StorageFullError`; decode fail → `StorageCorruptionError`; IO → `StorageUnavailableError`
- Reopen repair: tip must reference an existing body or fail-closed / rewind
- `sync_writes` / WAL remain adapter-owned

### C — Unit DoD

`tests/unit/fakes/fake_storage.py` + `tests/unit/test_storage_ports.py`:
atomicity, abort, crash recover, reorg, disk_full, corruption, CAS conflict,
isolation needles (no Rocks imports in ports/types).

## Honesty

- Ports ≠ aux.db evacuated / 100% Rocks
- Unit green ≠ live disk-fill soak / public mainnet storage audit
- Adapter present ≠ every `blockchain.py` call site cut over (Step D–E later)

## Out of scope (later)

- D: factory returns port façade as primary
- E: `Blockchain._persist_block_locked` / EVM writeback → UoW
- F: aux.db behind MetaStore only
