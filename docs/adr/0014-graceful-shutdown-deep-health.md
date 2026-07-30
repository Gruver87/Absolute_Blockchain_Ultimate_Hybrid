# docs/adr/0014-graceful-shutdown-deep-health.md
# ADR 0014 — Graceful Shutdown & Deep Healthcheck

- **Status:** Accepted
- **Date:** 2026-07-30
- **Deciders:** Absolute Blockchain maintainers

## Context

Container orchestrators (K8s, Docker) send `SIGTERM` on rolling restart. Partial
shutdown left RocksDB handles dropped without waiting for WriteBatch, and
`/health/ready` did not encode mesh quorum / sync-stall fail-closed signals.

## Decision

1. **Graceful shutdown (NodeOrchestrator.stop)** — ordered drain:
   - set `accepting_requests=False` (RPC/REST → 503 except `/health/live`)
   - shutdown HTTP/RPC servers (wait)
   - stop WebSocket / monitor
   - cancel asyncio tasks; `p2p.stop()` (peer close)
   - stop apply_queue / sync_executor / bridge
   - `storage.close()` / `db.close()` with RocksDB WriteBatch fence + clean close log
2. **Signals** — `SIGINT` / `SIGTERM` invoke `stop()` without skipping storage close.
3. **Deep `/health/ready`** — 200 only when existing checks pass **and**:
   - `sync_not_stalled` (no SyncEngine stall/lockdown)
   - when mesh expected (`bootstrap_peers` or `mesh_min_peers_before_mine>0`):
     `peers_alive` (peer_count > 0) and `quorum_height` (majority peers within gap ≤1)
   - otherwise **503 Service Unavailable** for K8s readiness
4. **`/health/live`** remains liveness-only (always 200 while process is up).

## Definition of Done

- ADR present; industrial_gate needles for shutdown + deep ready symbols
- RocksDB prints `[RocksDB] clean close`
- Signal-initiated `stop(force_process_exit=True)` ends the PID after clean
  close (avoids hang on native P2P `asyncio.to_thread(accept)`)
- E2E `tests/e2e/test_runtime_signals.py` SIGTERM during mining → clean close
