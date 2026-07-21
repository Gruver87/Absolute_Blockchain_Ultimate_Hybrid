# Release notes — v1.3.39

**Date:** 2026-07-21  
**Theme:** Native Casper FFG + slashing conflict kernels

## Rust / hybrid

- `ffg_threshold` / `ffg_best_checkpoint` / `ffg_accumulate_vote` / `ffg_evaluate_epoch` — classic two-step justify/finalize
- `fe_epoch` / `fe_quorum_reached` / `fe_can_finalize` — FinalityEngine count-quorum path
- `slash_check_double_vote` / `slash_check_double_proposal` — fail-closed conflict checks
- Wired into `finality_casper.py`, `finality_beacon.py`, `finality_engine.py`, `slashing.py` (Python owns callbacks / honesty labels)

## Config

- `node_version`: `1.3.39-industrial`

## Tests / gates

- `tests/unit/test_v1339_ffg_slash.py`
- Industrial gate + post_soak needles for new symbols

## Explicit non-goals

- Surround-vote · claiming standalone node FinalityEngine is consensus-bound · eth_tx decode · public mainnet
