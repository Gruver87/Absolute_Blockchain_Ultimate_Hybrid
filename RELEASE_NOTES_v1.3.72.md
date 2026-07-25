# Release notes — v1.3.72

## P2P sync admission + outbound honesty

Closes half-done v1.3.66 mesh load/DoS debt with real admission control and observability.

### What shipped

- **Sync admission:** `p2p_max_sync_inflight` (default 2) — caps concurrent peer sync tasks so catch-up cannot flood the serial apply queue
- **Outbound max_peers:** `connect_peer` refuses new dials when at capacity (inbound already did)
- **Outbound drops:** per-peer `_send_drops` roll up to `_outbound_drops` + Prometheus + `/p2p` security status
- **Config:** `p2p_send_queue_max`, `p2p_drain_timeout_sec`, `p2p_exempt_messages_per_sec` (default 2000)
- **Exempt flood ceiling:** sync/tx types stay primary-exempt for catch-up, but still bound by secondary budget
- **Fail-closed RL table** when `require_native_crypto` / prod and native table init fails

### Honesty

- Not a claim of complete P2P DoS resistance or bandwidth QoS
- Not a public mainnet claim; bridge stays OFF on live mesh
- Priority 38 (multi-depth Rust CALL) remains next on the EVM porting track

### Version

- `node_version`: `1.3.72-industrial`

### Verify

```powershell
python scripts/verify_industrial_waves.py
pytest tests/unit/test_v1372_p2p_admission.py -q
```
