# Ceremony pin + secret rotation (industrial core)

Phase-1 ops spine (ADR 0016 Profile A) — no FEATURE_* sprouts.

## Ceremony pin

1. Generate / load ceremony keys under `data/ceremony_keys` (or operator path).
2. `python scripts/deploy_ceremony_prod.py --ceremony-dir=... --mesh`
3. Confirm `GENESIS_CEREMONY_HASH` in `.env` matches `data/ceremony_deploy.json`.
4. Confirm `data/validators.manifest.json` + per-validator wallets exist.
5. Prod gate refuses start without manifest when `deployment_mode=prod`.

## Secret rotation (preserve pin)

```powershell
.\scripts\rotate_prod_secrets.ps1          # dry-run
.\scripts\rotate_prod_secrets.ps1 -Force   # rotate JWT / RPC / bridge oracle
```

Preserves `CHAIN_ID`, `GENESIS_CEREMONY_HASH`, `VALIDATORS_MANIFEST_PATH`, and
bridge policy flags. Restart mesh after rotation.

## Honesty

Ceremony pin + rotated secrets ≠ external audit. See MAINNET_GAP_ANALYSIS P0.
