# ADR 0006 — Storage Boundary (Ports → Adapter → Cutover → Purge)

- **Status:** Accepted A–F (`blockchain.py` domain on StoragePort)
- **Date:** 2026-07-29
- **Deciders:** Absolute Blockchain maintainers

## Context

Persistence was a duck-typed `Database` / `HybridDatabase` / `RocksChainStore`
surface. Domain code spoke engine verbs (`atomic`, sync flags) and risked
leaking CF / keycodec / bytes into business logic.

## Decision

### A–C — Ports, adapter, unit DoD

Domain ports + `RocksDBStorageAdapter` + `FakeStorage` fault-injection tests.

### D–E — Canonical UoW cutover

`open_storage(db)`; `Blockchain.add_block` persists via CAS-aware UoW joining
open `atomic()` / `_pending_batch`.

### F — Domain purge of `self.db.*`

`Blockchain` holds `self.storage` only for domain logic (blocks/state/meta/UoW/
`atomic()`). Native apply snapshot/writeback goes through the state façade.

Compat: `@property db` → `storage.unwrap()` for API/P2P/tests that still use
`bc.db` (Wave G can evacuate those call sites).

## Honesty

- Domain purge ≠ aux.db gone / SQLite deleted
- Compat `bc.db` ≠ permanent public storage API
- Unit green ≠ live disk-fill soak / mainnet storage audit

## Out of scope (later)

- G: remove `bc.db` from API/P2P
- Evacuate aux.db behind MetaStore only
