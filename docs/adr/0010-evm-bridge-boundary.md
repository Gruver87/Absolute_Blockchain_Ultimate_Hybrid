# ADR 0010 — EVM Bridge Layer (Ports + Isolation)

- **Status:** Accepted
- **Date:** 2026-07-30
- **Deciders:** Absolute Blockchain maintainers

## Context

L1 cross-chain bridge (`RustBridge`) was a NodeOrchestrator/HTTP sidecar on
raw `db`, outside `StoragePort` and the Blockchain facade. Replay keys and
atomic debit/credit already existed on Rocks/SQLite, but validation (receipt /
ZK) was not a separate port. `EvmHostBridge` (execution CALL host) is a
different module and must not be confused with L1 bridging.

## Decision

1. **`BridgePort`** — domain API: `lock_and_bridge`, `confirm_incoming(InboundEnvelope)`,
   `confirm_lock`, `refund`, `get_stats`.
2. **`InboundMessageValidatorPort`** — pure validation (replay key, receipt,
   confirmations, optional ZK). Never mutates balances.
3. **`L1RpcPort`** — receipt / confirmation reads (real RPC or `FakeEvmBridge`).
4. **`BridgeStorePort`** — `debit_and_create_bridge_lock`, `claim_and_credit_bridge_event`,
   `refund_pending_bridge_lock`, lock/credit lookups; each transition one `atomic()`.
5. **DI:** `Blockchain.attach_bridge(BridgePort)`; NodeOrchestrator owns lifecycle;
   HTTP uses the same port instance.
6. **Inbound flow:** validate → then claim/credit. ZK/receipt failure never credits.
7. **Tip UoW untouched** — bridge does not call `begin_block_commit`.

## Honesty

- Bridge OFF remains a valid production profile until audited L1 contracts ship.
- Inbound ZK is fail-closed only when `bridge_require_inbound_zk` (and feature ZK)
  is enabled; otherwise receipt + replay gates still apply.
- Cross-shard P2P gossip is out of scope.

## Definition of Done

- This ADR present; industrial_gate needles for ADR + `BridgePort`
- Ports + `NullBridgePort` + `FakeEvmBridge` + ≥20 automated scenarios
- Facade `attach_bridge`; inbound validate-before-credit
