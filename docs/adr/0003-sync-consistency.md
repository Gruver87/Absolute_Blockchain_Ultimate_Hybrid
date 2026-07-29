# ADR 0003 — Sync Consistency Boundary (Stages A–D)

- **Status:** Accepted (A–D)
- **Date:** 2026-07-29
- **Deciders:** Absolute Blockchain maintainers

## Context

Sync policy lived inside `P2PNode` / `SyncEngine` with scattered `_state_consistent`
writes, dual catch-up paths (tip-safety gap on AbsoluteNode `fast_sync` import),
and a large solicit-waiter block inside `_handle_message`.

## Decision

### A — Ports + domain

Package layout:

| Path | Role |
|------|------|
| `sync/ports.py` | Protocols: PeerView, Chain, BlockFetch, WireProbe, ConsistencyStore, CatchUpPolicy, **Solicit** |
| `sync/consistency/` | Types, fail-closed state machine, ConsistencyService |
| `sync/catchup/policy.py` | Pure catch-up refuse/bind helpers |
| `sync/solicit.py` | SyncSolicitHub (waiter table + solicit-only + stale timeout) |

Sync domain **must not** import the P2P node module.

### B — Fail-closed machine

States: `Unknown` → `Probing` → `Consistent` | `BehindOpen` | `LockedDown`.

- Incomplete-ahead → `BehindOpen` (never green / never `sync_state()==True` as success).
- Single writer: `ConsistencyService` via `SyncConsistencyStorePort`.
- `SyncChainPort.import_block` must be tip-safety aware.

### C — Solicit evacuation

Pipeline: allowlist → shape gates → **SyncSolicitHub** → `P2PDispatcher`.

P2P keeps TCP send/timeout; hub owns waiter semantics.

### D — Thin dispatcher handoff (final solicit debt)

- `_handle_message` only **forwards** to `solicit_hub.fulfill_or_reject` — no inline
  waiter match / fulfill / clear / kind loops.
- `_wait_peer_response` arms/clears exclusively via the hub; transport timeouts
  call `hub.timeout` (Future shielded from `wait_for` cancel).
- `SyncSolicitPort` in `sync/ports.py`; hub implements arm / clear / timeout /
  `expire_stale` / `fulfill_or_reject`.
- Stale waiter sweep (`expire_stale`) is hub-owned cleanup, independent of TCP.

## Honesty

- Consistency ≠ tip proof / Long-Range / BFT
- Wire state_root probe ≠ global state proof
- Solicit-only ≠ libp2p
- Gate green ≠ public mainnet

## Definition of Done

- Unit tests for machine transitions + solicit hub kinds + timeout/stale sweep
- Live SyncEngine/P2P use ConsistencyService; waiters not inlined in `_handle_message`
- Evidence matrix updated honestly
