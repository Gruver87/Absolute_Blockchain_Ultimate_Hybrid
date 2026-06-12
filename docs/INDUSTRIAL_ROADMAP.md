# Industrial Upgrade Roadmap

> Учебный проект → промышленный профиль. Поэтапно.

## Phase 1 — Deploy & trust ✅ (in progress)

- [x] Config from env (`DATA_DIR`, `NODE_ID`, ports)
- [x] `/health/live`, `/health/ready`
- [x] Docker ports aligned (8080, 5000, 8545, 8766)
- [x] Monitor fixed (`/status`, `/network/peers`)
- [x] CI blocking tests
- [x] Prometheus `/metrics`

## Phase 2 — Security

- [x] `DEPLOYMENT_MODE=prod` profile
- [x] CORS allowlist
- [x] JWT enforce on admin POST (optional)
- [ ] TLS termination guide (nginx)
- [ ] API keys for RPC

## Phase 3 — Observability

- [x] Prometheus metrics
- [ ] JSON structured logs
- [ ] Grafana dashboard
- [ ] Alert rules

## Phase 4 — Data durability ✅

- [x] SQLite `synchronous=FULL` in prod
- [x] Atomic block+tx commits (`persist_block_atomic`)
- [x] Backup script (`python scripts/backup_db.py`)
- [x] Graceful HTTP/RPC shutdown

## Phase 5 — Scale & HA

- [ ] ASGI migration (optional)
- [ ] Multi-node K8s manifests
- [ ] Distributed rate limit (Redis)
- [ ] Load tests in CI

## Quick start (prod profile)

```bash
export DEPLOYMENT_MODE=prod
export DATA_DIR=./data/node1
export NODE_ID=node1
export REQUIRE_WALLET_FILE=true
export JWT_ENFORCE_ADMIN=true
export CORS_ORIGINS=http://localhost:8080
python main.py
```

Docker:

```bash
docker compose up --build
```
