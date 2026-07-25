# Release notes — v1.3.127

## Summary

**Industrial sync hardening (no simplifications):**

1. **Request-bound `state_root_response` height gate** — before fulfilling waiters for `state_root_request`, the response height must match the requested probe height (plus existing 32-byte digest checks). Wrong-height answers never green-path the consistency probe.

## Changes

- `verify_state_root_response_request_semantics_inner` / `verify_p2p_state_root_response_request_semantics`
- Waiter `request_ctx` on `request_peer_state_root` (`kind=state_root`, `height`)
- Strike: `bad_state_root_response_height` (+ existing digest/shape reasons)
- Status/metrics: `native_state_root_response_request_gate`, `state_root_response_request_rejects_total`
- `node_version`: `1.3.127-industrial`

## Honesty

- Still **not** root-belongs-to-head proof / tip proof / fork-choice / full Rust sync / libp2p / public mainnet
- Ceremony pin + external audit remain org blockers

## Verify

```text
make test-quick
python -m pytest tests/unit/test_v13127_p2p_state_root_response_request_gate.py -q
```
