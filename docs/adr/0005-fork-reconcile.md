# ADR 0005 — Same-Height Fork Reconcile Thin Adapter

- **Status:** Accepted (A)
- **Date:** 2026-07-29
- **Deciders:** Absolute Blockchain maintainers

## Context

Same-height fork reconcile (`P2PNode._reconcile_fork_at_peer` →
`_reconcile_to_head_hash`) mixed wire probes, hash/parent/tip binds, ancestor
lookup, and reorg+import inside the network control plane.

ADR 0004 extracted Path A ahead catch-up. Same-height reconcile remained on P2P.

## Decision

### A — Ports + domain + thin wire (this stage)

| Path | Role |
|------|------|
| `sync/ports.py` | `ForkReconcileChainPort`, `FetchPort`, `ProbePort`, `SideEffectPort` |
| `sync/fork/policy.py` | Pure refuse predicates (hash / parent / tip binds) |
| `sync/fork/service.py` | `ForkReconcileService.run_same_height` / `run_to_head` |
| `network/fork_adapters.py` | P2P blocking façades over solicit / reorg |

- Domain is **synchronous** over ports (no `asyncio`, no `PeerConnection`).
- Sync domain **must not** import the P2P node module.
- Scheduling / NEW_BLOCK callers stay on P2P; they call the thin wire.

### Honesty

- Fork reconcile ≠ tip proof / Long-Range / BFT
- Soft parent/hash binds ≠ ancestry DAG store
- Unit green ≠ mesh soak

## Definition of Done

- Unit tests: ok sibling reorg, malicious hash mismatch, same-height parent
  mismatch, probe refuse, no ancestor, tip-head post-import refuse
- `_reconcile_fork_at_peer` / `_reconcile_to_head_hash` thin-wired
- Evidence: unit-proven + integration-wired; live mesh **not** claimed
