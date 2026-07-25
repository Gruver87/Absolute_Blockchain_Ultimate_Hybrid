# Release notes — v1.3.132

## Summary

**Industrial mesh discovery honesty (no simplifications):**

1. **Resilient bootstrap redial** — `_bootstrap_retry_loop` no longer stops after the first non-bootstrap peer. Missing configured bootstrap seeds keep being dialed even when `self.peers` is non-empty (stops sticky discovery / eclipse-assist).
2. **Dial-target coverage** — outbound `connect_peer` records `peer.dial_target` (`host:port` as dialed) so hostname seeds still match after DNS resolves to a different IP.

## Changes

- `_missing_bootstrap_addrs` / `_peer_covers_bootstrap` / `_normalize_dial_addr`
- Metrics: `native_bootstrap_resilient`, `bootstrap_redial_total`, `bootstrap_missing_count`
- `node_version`: `1.3.132-industrial`

## Honesty

- Still **not** tip proof / fork-choice / libp2p / anti-Sybil DHT / external audit / public mainnet
- Coverage is host/port dial matching, not authenticated seed identity

## Verify

```text
make test-quick
python -m pytest tests/unit/test_v13132_p2p_bootstrap_resilient.py -q
```
