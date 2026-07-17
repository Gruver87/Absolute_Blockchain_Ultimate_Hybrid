# Release Notes — v1.2.79

## Core industrial hardening (no new features)

Soak-safe code/docs hardening for a serious L1 path. Does **not** restart prod mesh or claim 48h soak PASS.

### Wave checklist (done in this release)

| Wave | Item | Status |
|------|------|--------|
| 79 | Honest NFT/aux Rocks vs SQLite docs | Done |
| 79 | Fail-loud ImmutableState apply in prod | Done |
| 79 | Scrub remaining PS1 em-dashes | Done |
| 80 | Prod refuse tip `state_root` rewrite | Done |
| 80 | Prod skip parallel consensus engines | Done |
| 81 | Shared `runtime.amount` satoshi helpers | Done (foundation) |
| 81 | Deterministic CREATE address (no wall-clock) | Done |

### Still open (later)

- Full SQLite/Rocks **INTEGER** balance column migration (ledger truth)
- Full unify Database / StateEngine / IMS as single write path
- 48h soak PASS + external audit (organizational)

### Operator notes

```powershell
python scripts/industrial_gate.py
pytest tests/unit/test_amount_units.py tests/unit/test_state_root_rewrite_guard.py tests/unit/test_evm_create_address.py -q
.\scripts\soak_status.ps1   # do not stop soak
```

Prod configs must keep `ALLOW_STATE_ROOT_REWRITE=false` (default in prod apply_env).
