# ADR 0002 — P2P Transport Boundary (Steps A–D)

- **Status:** Accepted (A–D)
- **Date:** 2026-07-29
- **Deciders:** Absolute Blockchain maintainers

## Context

`network/p2p_node.py` mixed TCP/TLS I/O, rate/ban policy, wire gates, sync
waiters, and a large application `if/elif` type switch. Native kernels and the
A–C transport adapter exist; application routing still lived inside the node.

## Decision

### A–B (domain)

`network/transport/` — ports, reject taxonomy, `NativeTransportAdapter`.

### C (live wiring)

Transport adapter owns live ingress admit + egress prepare; counters merge into
`get_p2p_security_status`.

### D (application dispatcher)

Introduce `network/p2p_dispatch/` (sibling of `p2p_node`, **not** under
`network.p2p` package — avoids `__init__` cycle with `P2PNode`):

| Module | Role |
|--------|------|
| `constants.py` | Wire type strings (parity-tested vs `p2p_node`) |
| `registry.py` | `HandlerRegistry` — msg_type → async handler |
| `handlers.py` | Default handlers; depend on `DispatchHost` only |
| `dispatcher.py` | `P2PDispatcher.dispatch` |
| `tip_evidence.py` | `TipSafetyEvidenceBridge` (`TipEvidencePort`) |
| `ports.py` | `DispatchHost`, `TipEvidencePort` Protocols |

Pipeline retained on the node:

```text
_message_loop → _handle_message
  → allowlist / mid-session refuse
  → shape gates
  → sync waiters / solicit-only
  → P2PDispatcher.dispatch (Handler Registry)
```

Tip-safety is injected via `TipSafetyEvidenceBridge(shadow_provider=...)`.
Enforce refuse on `NEW_BLOCK` happens **before** domain `_handle_new_block`.
Shadow observe counters remain on the import path (no double-count).

**Still out of scope:** replacing native shell `read_message_loop_events`,
libp2p, tip proof / Long-Range / BFT quorum.

## Consequences

### Positive

- New wire types register on the registry without editing the message loop.
- Transport stays free of application type switches.
- Tip-evidence port avoids `p2p_node` ↔ `tip_safety` import cycles.

### Limits (honest)

- Shape gates + sync waiters remain on `P2PNode` (pipeline stages).
- Dispatcher tip gate ≠ ancestry store / Long-Range proof.
- Domain handlers (`_handle_new_block`, …) still live on the node; routing is isolated.

## Definition of Done (D)

- `_handle_message` application switch replaced by `dispatcher.dispatch`
- Unit tests for registry, ping/mempool/new_block, tip enforce refuse, node wiring
- ADR + Evidence updated; no libp2p / tip-proof claims
