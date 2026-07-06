# Release v1.2.24 — public testnet Docker seed stack

**Date:** 2026-07-06

## Summary

Shippable starter for PUBLIC_TESTNET (chain 77777): Docker seed, optional validator, nginx template, deploy script.

## Changes

- `docker-compose.testnet.yml` + `docker/node.testnet.seed.json` / `validator.json`
- `scripts/docker_testnet_seed.ps1`, `.env.testnet.example`
- `deploy/nginx/testnet.example.conf`
- Tests: `tests/unit/test_testnet_compose_config.py`

## Test plan

- [x] `pytest tests/unit/test_testnet_compose_config.py`
- [ ] `.\scripts\docker_testnet_seed.ps1` on VPS (rotate secrets first)
