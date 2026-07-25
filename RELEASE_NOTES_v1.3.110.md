# Release notes — v1.3.110

## Summary

**Native peer discovery shape gates:** on the native read path, `peers` frames that fail `validate_peers_list_inner` are rejected with `bad_peers_list`, and `validator_register` frames that fail `validate_validator_register_inner` are rejected with `bad_validator_register`, before Python dispatch.

## Changes

- `check_peers_list_payload` / `check_validator_register_payload` in `p2p_transport.rs`
- Status `native_peer_discovery_gate`; metric `abs_p2p_native_peer_discovery_gate`
- `node_version`: `1.3.110-industrial`

## Honesty

- Still **not** full Rust message-loop ownership / libp2p
- Shape-only; peer dial / validator stake policy stay Python
- Default transport remains asyncio unless `p2p_native_transport=true`
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13110_p2p_native_peer_discovery_gate.py -q
```
