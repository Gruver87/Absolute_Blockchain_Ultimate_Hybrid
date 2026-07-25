# Release notes — v1.3.123

## Summary

**Native `state_root_response` digest ingress:** on the message-loop shell, `state_root` and `head_hash` must be 32-byte hex digests (64 hex chars, optional `0x`) before Python dispatch. Request correlation and “root belongs to head” stay Python.

## Changes

- `verify_state_root_response_semantics_inner` + `check_state_root_response_semantics`
- Strike: `bad_state_root_digest` (shape still `bad_state_root_response`)
- Status: `native_state_root_response_semantic_gate`, `state_root_semantic_rejects_total`
- Metrics: `abs_p2p_native_state_root_response_semantic_gate`, `abs_p2p_state_root_semantic_rejects_total`
- `node_version`: `1.3.123-industrial`

## Honesty

- Still **not** sync ownership / proof verification / full message-loop / libp2p
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
make test-quick
python -m pytest tests/unit/test_v13123_p2p_native_state_root_response_semantic_gate.py -q
```
