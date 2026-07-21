# Release notes — v1.3.08

**Date:** 2026-07-21  
**Theme:** Swiss-watch ops honesty — counters, logs, JSON parity, native EVM fail-closed

## Honesty fixes

- `peer_status_send_fail` now increments when `Peer.send` returns `False` (was dead after send swallowed exceptions)
- Mid-session handshake rejects log a warning every time (not only on ban)
- Invalid attestation sig / bad block dict / local attestation sign → `warning` (not silent debug)
- Prometheus HELP text: handshake rejects cover payload + mid-session; `abs_p2p_attestation_local_fail_total`

## Observability

- Grafana: ops_errors by kind + mid_session_handshake shape rejects
- Alert: `AbsoluteP2POpsErrorsBurst`

## Parity / gates

- industrial_gate scans all prod JSON files for shared industrial keys + rate floor + bridge OFF
- Mesh/k8s/mainnet examples: `state_root_legacy_cutoff_height`; k8s `rust_bridge_path`
- `.env.example`: `MESH_MIN_PEERS_BEFORE_MINE`, `FOLLOWER_GENESIS_SYNC`, `STATE_ROOT_LEGACY_CUTOFF_HEIGHT`
- `post_soak_verify` includes `test_p2p_ops_errors.py` + `test_status_honesty.py`

## Native

- `evm_deploy_address_create` / `evm_deploy_address_create2_legacy` call `_require_native_kernel` under `ABS_REQUIRE_NATIVE_CRYPTO`

## Verify

```powershell
.\scripts\post_soak_verify.ps1
```
