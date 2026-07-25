# Release notes — v1.3.117

## Summary

**Native attestation semantic ingress:** on the v1.3.116 message-loop shell, `attestation` frames pass identity bind (pubkey→validator) and secp256k1 signature verify in Rust before `dispatch`. Bad frames become ordered `strike` events (`bad_attestation_identity` / `bad_attestation_sig`). Wire-tx semantic / mempool / consensus apply stay Python.

## Changes

- `verify_attestation_semantics_inner` + `check_attestation_semantics` on `read_message_loop_events`
- Status: `native_attestation_semantic_gate`, `attestation_semantic_rejects_total`
- Metrics: `abs_p2p_native_attestation_semantic_gate`, `abs_p2p_attestation_semantic_rejects_total`
- `node_version`: `1.3.117-industrial`

## Honesty

- Still **not** full Rust message-loop / libp2p / tx semantic ingress
- Consensus apply, relay, ban thresholds, and non-shell paths remain Python
- Not public mainnet; ceremony pin + external audit remain org blockers

## Verify

```text
python scripts/verify_industrial_waves.py
python -m pytest tests/unit/test_v13117_p2p_native_attestation_semantic_gate.py -q
```
