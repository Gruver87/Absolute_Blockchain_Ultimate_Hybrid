# ADR 0004 — Path A Catch-Up Thin Adapter

- **Status:** Accepted (A–C)
- **Date:** 2026-07-29
- **Deciders:** Absolute Blockchain maintainers

## Context

Path A ahead catch-up (`P2PNode._sync_with_peer` when peer height > local) mixed
policy gates, `get_blocks` solicit I/O, tip-safety import/reorg, and tip-head
bind inside the network control plane (~230 LOC).

ADR 0003 extracted pure refuse policy (`CatchUpOrchestrator`) and consistency /
solicit hub. The ahead **batch loop** still lived on P2P. SyncEngine.fast_sync
kept a second download→import I/O cycle (parent-walk + private import loop).

## Decision

### A — Ports + domain loop

| Path | Role |
|------|------|
| `sync/ports.py` | `CatchUpChainPort`, `CatchUpFetchPort`, `CatchUpProbePort`, `CatchUpSideEffectPort` |
| `sync/catchup/types.py` | `CatchUpPeerView`, `CatchUpConfig`, `CatchUpOutcome` |
| `sync/catchup/path_a.py` | `CatchUpPathAService.run_ahead` — sync loop over ports only |

- Domain is **synchronous** over blocking port façades (no `asyncio`, no `PeerConnection`).
- Sync domain **must not** import the P2P node module.
- Reuse `CatchUpOrchestrator` for pure gates.

### B — Live thin adapter

`P2PNode._sync_with_peer` ahead branch calls `CatchUpPathAService` via
`network/catchup_adapters.py`. Scheduling stays on P2P.

### C — Shared Path B / fast_sync

`SyncEngine.fast_sync` uses the same `CatchUpPathAService.run_ahead` through
`sync/catchup/engine_io.SyncEngineCatchUpIO` (CatchUp* ports over duck-typed node).
Peer/head selection and `sync_state` remain on SyncEngine; the private
`to_import` import loop is removed.

## Honesty

- Path A service ≠ tip proof / Long-Range / BFT
- Fetch port ≠ libp2p
- Unit green ≠ mesh soak / public mainnet

## Definition of Done

- **A:** Unit tests for refuse / probe / stall / import / reorg / tip-head / complete
- **B:** Integration wiring of `_sync_with_peer` thin adapters
- **C:** `fast_sync` shares Path A service; incremental + Step C wiring tests green;
  evidence claims shared path (not tip proof)
