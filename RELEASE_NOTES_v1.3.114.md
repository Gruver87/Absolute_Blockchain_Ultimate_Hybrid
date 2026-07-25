# Release notes — v1.3.114

## Summary

**Native P2P transport is mandatory in prod:** `deployment_mode=prod` defaults `p2p_native_transport=true`, `prod_gate` / config validation fail-closed without it, and `P2PNode` no longer silently falls back to asyncio when native crypto/prod requires the data plane. On the native path, Python dual shape re-validation is skipped (Rust `check_ingress_shape_gates` already ran).

## Changes

- Config: prod default + validate `p2p_native_transport`; require abs_native transport when enabled under `require_native_crypto`
- `prod_gate.py`: `p2p_native_transport` in `REQUIRED_TRUE`; prod JSON profiles updated
- `P2PNode`: fail-closed when transport required but unavailable; skip dual shape gates when `_use_native_transport`
- Status: `native_transport_prod_required`, `native_shape_revalidate`; metric `abs_p2p_native_shape_revalidate`
- `node_version`: `1.3.114-industrial`

## Honesty

- Still **not** full Rust message-loop ownership / libp2p
- Enabling native transport ≠ semantic gossip / dispatch in Rust
- Asyncio remains available for **dev** when `p2p_native_transport=false`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/prod_gate.py
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13114_p2p_native_transport_prod.py -q
```
