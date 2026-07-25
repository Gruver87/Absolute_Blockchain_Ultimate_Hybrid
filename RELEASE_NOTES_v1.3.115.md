# Release notes — v1.3.115

## Summary

**Native handshake policy fuse + Max-gate fixes:** `handshake_roundtrip` can enforce `chain_id` and TLS identity bind in Rust before Python dual policy. Also fixes Max live `/health/ready` 503 under prod-mandatory native transport (listener is `_native_listener`, not asyncio `_server`), plus k8s/smoke JSON drift from v1.3.114.

## Changes

- Rust `check_handshake_policy` on `handshake_roundtrip` (`chain_id_mismatch` / `tls_missing` / `tls_identity_mismatch` / `handshake_rejected`)
- Python passes local chain_id + TLS flags; skips dual chain/identity checks when native policy applied (fingerprint allowlist stays Python)
- `/health/ready` prod `p2p_running` accepts `_native_listener`
- `deploy/k8s/configmap.yaml` + `prod_smoke_profile` sync `p2p_native_transport`
- Status `native_handshake_policy_gate`; metric `abs_p2p_native_handshake_policy_gate`
- `node_version`: `1.3.115-industrial`

## Honesty

- Still **not** full Rust message-loop ownership / libp2p
- Fingerprint allowlist + asyncio handshake path remain Python
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13115_p2p_native_handshake_policy.py tests/unit/test_bind_ready_status_honesty.py -q
python scripts/k8s_prod_gate.py
```
