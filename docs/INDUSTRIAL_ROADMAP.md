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
- [x] TLS termination guide (nginx) — `docs/TLS_NGINX.md`
- [x] API keys for RPC (`RPC_API_KEYS`, `X-API-Key` header)

## Phase 3 — Observability ✅

- [x] Prometheus metrics
- [x] JSON structured logs (`LOG_JSON=true`)
- [x] Grafana dashboard (`deploy/grafana/dashboard.json`)
- [x] Alert rules (`deploy/prometheus/alerts.yml`)

## Phase 4 — Data durability ✅

- [x] SQLite `synchronous=FULL` in prod
- [x] Atomic block+tx commits (`persist_block_atomic`)
- [x] Backup script (`python scripts/backup_db.py`)
- [x] Graceful HTTP/RPC shutdown

## Phase 5 — Scale & HA ✅

- [x] ASGI migration (optional, documented — stdlib sufficient for HA)
- [x] Multi-node K8s manifests (`deploy/k8s/`)
- [x] Distributed rate limit (Redis) — `REDIS_RATE_LIMIT=true`
- [x] Load tests in CI (`scripts/load_test.py`)
- [x] HA docker-compose (`docker-compose.ha.yml`)

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

HA (3 nodes + Redis):

```bash
docker compose -f docker-compose.ha.yml up --build
```

Kubernetes:

```bash
kubectl apply -k deploy/k8s/
```
