# Release notes — v1.2.98

**Date:** 2026-07-21  
**Theme:** AI/MEV/PQ probes, security-audit bridge gate, main fail-loud

## Features / API

- `OPTIONAL_MODULE_PROBES` extended: **ai_agents**, **mev**, **pq**
- `/ai-agent/stats`, `/mev/stats`, `/pq/status` → `import_error` when module not loaded

## CI / ops

- `security-audit.yml`: dedicated `bridge-off-gate` job (`bridge_off_audit_gate.py`)
- `industrial_gate.py`: registry checks for ai_agents/mev/pq

## Node boot

- `main.py`: fail-loud messages for validator key provider, monitor, and RPC proxy startup failures
