# Release notes — v1.2.93

**Date:** 2026-07-21  
**Theme:** API repair fail-loud, verify_p2p wave skips fail-closed, per-pod cert-manager

## API fail-loud

- `/oracles/all`: `prices_error` / `weather_error` on failure + logs
- State consistency harness: `peer_probe_error` when P2P wire probe fails
- Fork recovery drill: `state_repair_error` when `ensure_state_at_tip` fails
- P2P TLS snapshot errors logged in `/status` `p2p_hardening`

## verify_p2p_ci

- Wave skips (tx propagation, harness, multi-node, adversarial) → **FAIL** unless `VERIFY_P2P_ALLOW_SKIP=1`
- Bridge / relayer skips fail-closed when invoked in dedicated CI modes
- Prod testnet endpoint skips fail-closed (expected prod policy)

## Docs / K8s

- `docs/STATE_ROOT_ENCODING_MIGRATION.md` — v1→v2 migration checklist
- `deploy/k8s/cert-manager-p2p-perpod.example.yaml` — per-ordinal Certificates (0..2)

## Tests

- `test_consistency_harness_probe.py`
- Extended `test_verify_p2p_skip_policy.py`
