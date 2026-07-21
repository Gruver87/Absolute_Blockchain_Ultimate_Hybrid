# Release notes — v1.2.99

**Date:** 2026-07-21  
**Theme:** State-root encoding honesty API, harness check, evidence stamp

## Features / API

- `GET /chain/state-root/encoding` — dedicated auditor endpoint for v1/v2 encoding contract
- Harness check `state_root_encoding_honest` — asserts v1 float tip active, satoshi tip not claimed
- `/block/{n}` and `/chain/block/{n}` — fail-loud `Invalid block number: {exc}` (no silent `except`)

## Evidence / gates

- `stamp_release_evidence.py` — records `state_root_encoding_v1` stamp (with `--skip-encoding`)
- `industrial_gate` — encoding endpoint, harness check, fail-loud block handlers

## Docs

- `STATE_ROOT_ENCODING_MIGRATION.md` — links new encoding endpoint
