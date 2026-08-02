# State-root encoding migration (v1 → v2)

**Status (Wave C tip+apply):** v2 satoshi tip is **ceremony-armed on local prod mesh** (`docker/node.prod.mesh*.json`) for **fresh volumes only**. Default Config remains v1 until operators arm ceremony.

## Live tip encodings

### v1 — `float_b_round12` (legacy)

- Tip leaf field `"b"` = `round(balance, 12)`.
- Used when `state_root_encoding_version < 2` or ceremony not armed.
- Native tip hasher no longer emits float `"b"` (Wave C); v1 hashing is Python-only.

### v2 — `satoshi_b` (Wave C)

- Tip leaf field `"b_satoshi"` = integer satoshi (`SATOSHI_MULTIPLIER = 1_000_000`).
- Activation requires **both**:
  - `state_root_encoding_version=2` (or `ABS_STATE_ROOT_ENCODING_VERSION=2`)
  - `state_root_v2_ceremony_ok=true` (or `ABS_STATE_ROOT_V2_CEREMONY_OK=1`)
- Native `account_payload_row` / Rocks tip accumulator emit integer `b_satoshi`.
- Apply path (StateService fees/gas/reward) uses integer satoshi; ABS float is display-only.

Runtime snapshot: `GET /status` → `state_root_policy.encoding`, or `GET /chain/state-root/encoding`.

## Local prod mesh cutover

1. Arm flags in mesh JSON (already set for staging mesh).
2. **Wipe volumes** — `docker_prod_3node.ps1 -NoCloneDb` (do not KeepVolumes across encoding change).
3. Prove ready×3 + probe + matching tip roots + encoding v2 active.

## Non-goals

- Changing multiplier to 1e8.
- Silent in-place migration of historical float-tip DB without halt/export.
- Claiming 48h public mainnet cutover in this wave.
