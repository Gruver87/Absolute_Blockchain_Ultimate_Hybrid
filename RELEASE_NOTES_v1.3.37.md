# Release notes — v1.3.37

**Date:** 2026-07-21  
**Theme:** Bridge L1-proof fail-closed + light/PBS/AI honesty

## Honesty / fail-closed

- Prod `BRIDGE_REQUIRE_L1_PROOF` cannot be weakened via env (`apply_env` / `apply_env_secrets` force `True`; validate rejects `false`)
- `bridge_relayer --allow-blind-confirm` hard-fails when target `/status` reports `deployment_mode=prod`
- Light client: peer header import requires trusted local checkpoint (`trusted_local_replay`); rejects unanchored peer bootstrap; `/light/stats` honesty fields
- PBS: labeled fee-bid simulation (`mev_protection=false`, `ordering_applied=false`); mining loop no longer pretends PBS reorders for protection
- AI Validator: gated by `FEATURE_AI_VALIDATOR` (off in prod); `simulation_only` / `consensus_wired=false` / `model_bound=false`; MEV scan no longer invents profit/probability

## Config

- `node_version`: `1.3.37-industrial`
- Prod default: `FEATURE_AI_VALIDATOR=false`

## Tests / gates

- `tests/unit/test_v1337_honesty.py`
- Industrial gate needles for the above paths

## Explicit non-goals

- Ceremony pin · external audit · public mainnet · bridge ON without audited L1 · real MEV extraction / AI consensus wiring
