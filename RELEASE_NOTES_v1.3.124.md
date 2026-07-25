# Release notes — v1.3.124

## Summary

**Native `status.head_hash` digest ingress:** on the message-loop shell, a non-empty advertised `head_hash` must be a 32-byte hex digest (optional `0x`). Empty / null / non-object status keepalives stay OK (genesis may advertise `""`).

## Changes

- `verify_status_head_hash_semantics_inner` + `check_status_head_hash_semantics`
- Strike: `bad_status_head_digest` (shape still `bad_status_payload`)
- Status: `native_status_head_hash_semantic_gate`, `status_semantic_rejects_total`
- Metrics: `abs_p2p_native_status_head_hash_semantic_gate`, `abs_p2p_status_semantic_rejects_total`
- `node_version`: `1.3.124-industrial`

## Honesty

- Still **not** height↔hash binding, peer auth, handshake head_hash semantic, full message-loop, or libp2p
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
make test-quick
python -m pytest tests/unit/test_v13124_p2p_native_status_semantic_gate.py -q
```
