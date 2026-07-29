# ADR 0005 — Same-Height Fork Reconcile Thin Adapter

- **Status:** Accepted (A) — fail-closed Evidence hardened
- **Date:** 2026-07-29
- **Deciders:** Absolute Blockchain maintainers

## Context

Same-height fork reconcile mixed wire probes, hash/parent/tip binds, ancestor
lookup, and reorg+import inside the P2P control plane. Hostile peers can spam
fake same-height bodies; soft refuse without strike/evidence is insufficient.

## Decision

### Ports → domain → thin wire

| Path | Role |
|------|------|
| `sync/ports.py` | `ForkReconcileChain/Fetch/Probe/SideEffectPort` (+ Evidence hooks) |
| `sync/fork/policy.py` | Pure refuse predicates |
| `sync/fork/evidence.py` | `ForkSecurityEvidence`, `ForkReconcileMaliciousError` |
| `sync/fork/service.py` | `ForkReconcileService` — fail-closed on malicious refuses |
| `network/fork_adapters.py` | P2P façades; `bus.emit("security.fork_refuse", …)` + `strike_peer` |

Domain is synchronous; no P2P node imports under `sync/fork/`.

### Fail-closed malicious path

On malicious refuse codes (hash/parent/probe/tip-evidence/spam):

1. `note_malicious_attempt` (spam escalate at ≥3 → `fork_same_height_spam`)
2. `emit_security_evidence` → EventBus `security.fork_refuse` + node status
3. `strike_malicious_peer`
4. raise `ForkReconcileMaliciousError` (thin wire catches → `False`)

### Honesty

- Soft binds ≠ tip proof / Long-Range
- Evidence event ≠ audited SIEM
- Unit green ≠ mesh soak

## Definition of Done

- Unit tests: happy path, malicious hash/parent, spam escalate, tip-evidence,
  Evidence payload, strike, thin-wire needles
- `_reconcile_fork_at_peer` is thin wire only
