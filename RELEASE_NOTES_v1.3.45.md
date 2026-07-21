# Release notes — v1.3.45

**Date:** 2026-07-21  
**Theme:** Native apply honesty (state_root / receipts / EVM code) + prod example ceremony addresses

## Fixes

- Native account writeback no longer materializes empty burn accounts (state_root parity with Python apply)
- Writeback preserves existing EVM `code`/`storage` (host-in-apply no longer wipes deploys)
- Successful applies set receipt `status=1` (omit → fail-closed `0` unchanged)
- `validators.manifest.example.json` uses ceremony-derived addresses (prod stack verify fail-closed on `0x…0001`)
- Full-audit deterministic-proposer check follows native `abs-proposer:` seed
- Prod smoke clears inherited `FEATURE_*` env; partial sync behind ahead peers stays incomplete (not tip-green)
- Oracle registry: explicit `secret=""` disables HMAC (does not inherit `BRIDGE_ORACLE_SECRET`)

## Config

- `node_version`: `1.3.45-industrial`

## Explicit non-goals

- Public mainnet · external audit · bridge L1 ON without audited contracts · mixed simple+EVM single native apply
