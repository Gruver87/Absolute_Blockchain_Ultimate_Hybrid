# Release v1.2.15 — CI fix + health watch

**Date:** 2026-07-05

## Summary

Fix red GitHub Actions on master; sync mainnet gap docs; add local health watch for prod mesh.

## Changes

- Remove unused numpy import (postquantum tests collect on CI)
- Docker workflow: push to GHCR only, smoke via `ghcr.io/...:latest`
- Fix publish-wheel workflow YAML
- `scripts/health_watch.ps1` — poll `/health/ready` + consistency harness; optional webhook
- Updated MAINNET_GAP, INCIDENT_RESPONSE, REPO_PROFILE

## Test plan

- [x] Docker prod image CI green on master
- [x] Security audit CI green on master
- [ ] Blockchain Tests (long prod-mesh spawn job; check Actions)
- [ ] `.\scripts\health_watch.ps1 -ProdMesh -DurationMin 1`
