# ADR 0007 — Consensus Boundary (Ports + Fail-Closed Round SM)

- **Status:** Accepted A–C (`ConsensusPort` / round SM / adapter façade)
- **Date:** 2026-07-29
- **Deciders:** Absolute Blockchain maintainers

## Context

`ConsensusAdapter` is a fat façade over `ConsensusEngine`, `FinalityEngine`,
`ConsensusEngineSlashing`, optional Casper/Beacon parallel engines, and
`ValidatorRegistry`. P2P delivers attestation dicts after soft ownership gates;
double-sign is local bookkeeping only. Fork Evidence (ADR 0005) is not wired to
consensus votes. `deployment_mode` + `resolved_consensus_mode()` force **unified**
in prod and forbid `parallel`.

## Decision

### A — Ports and pure domain types

| Path | Role |
|------|------|
| `consensus/ports.py` | `ConsensusPort`, `ValidatorRegistryPort`, Evidence/Lockdown/SideEffect |
| `consensus/bft/types.py` | `Vote`, `Proposal`, `RoundId`, `QuorumCertificate`, outcomes |
| `tests/unit/fakes/fake_consensus.py` | In-memory registry + evidence + lockdown sinks |

Quorum math consumes frozen domain values only. No `network.*`, MSG_*, or
`PeerConnection` under `consensus/bft/` or port protocols.

### B — Fail-closed round state machine

`RoundStateMachine` (Propose → Prevote → Precommit → Finalize / Locked):

1. Stake-weighted ≥⅔ quorum on `ValidatorSetSnapshot`
2. Double-sign / unknown validator / stale round → `ConsensusSecurityEvidence`
3. `note_malicious_attempt`; escalate → `ConsensusLockdownPort.request_lockdown`
4. Raise `ConsensusMaliciousError` (thin wire / façade catches)

Bus topic (wire): `security.consensus_refuse`.

### C — Adapter façade + `deployment_mode`

`ConsensusAdapter` keeps legacy methods (`attest`, `get_stats`, …) as stable
shims. Internally constructs `RoundStateMachine` and implements port queries.
Prod/staging → unified only; parallel Casper/Beacon engines unconstructed.

### Attestation mapping (honesty)

| Today | Domain (A–C) |
|-------|----------------|
| `attest(...)` | Primarily `VoteType.PREVOTE` feeding LMD; SM tracks round votes |
| `process_block_finality` | Local path toward Finalize (not mesh Precommit QC) |
| Double-vote in slashing | Also Evidence + optional lockdown via ports |

A–C **does not** require ⅔ distinct peer Precommits on the wire to Finalize.

## Consequences

### Positive

- Quorum / slash detection testable without P2P or Rocks
- Fail-closed Evidence path aligned with ADR 0005
- Clear prod vs parallel engine construction

### Negative / Honesty limits

- Domain SM ≠ live network BFT quorum
- Local Evidence ≠ audited SIEM / slash gossip
- Unit green ≠ mesh soak-as-BFT
- `finality_quorum_live` remains **False** in API

## Non-goals

- Replacing LMD-GHOST with Tendermint wire
- Economic slash burn / cross-peer evidence gossip
- Claiming `finality_quorum_live: True`
- Evacuating tip_safety (ADR 0001)

## Definition of Done

- Ports + Fake* + RoundStateMachine unit tests (happy QC, double-sign lockdown,
  stale round, unknown validator)
- `ConsensusAdapter` façade stable; industrial needles / evidence matrix updated
- Targeted consensus suites green under explicit `deployment_mode`
