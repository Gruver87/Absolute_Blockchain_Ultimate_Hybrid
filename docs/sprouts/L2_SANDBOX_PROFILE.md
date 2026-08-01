# L2 sandbox profile (Profile D)

Plasma / Lightning / WASM are **aux-DB R&D**. They must not share the prod
Rocks tip or gate industrial `/health/ready`.

## Config

- Example: [`docker/node.sandbox.l2.json`](../../docker/node.sandbox.l2.json)
- Compose lab: [`docker-compose.sandbox.l2.yml`](../../docker-compose.sandbox.l2.yml)
- `feature_plasma` / `feature_lightning` / `feature_wasm`: enabled only here
- `db_engine` may be sqlite for aux; never point `DATA_DIR` at prod mesh volumes

## Health honesty

Sandbox module down ≠ core ready false. Core `/health/ready` sets
`sprout_ready_independent: true` and never gates on plasma/lightning/wasm/oracles
init (ADR 0016). Failures may still appear under `/status` as `feature_degraded`.

## Honesty

Not mainnet L2. Not audited exit games.
