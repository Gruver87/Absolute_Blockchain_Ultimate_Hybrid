# Release v1.2.0-industrial

**Educational blockchain node** — промышленный учебный профиль.

## Highlights

- Single entry: `python main.py`
- Health: `/health/live`, `/health/ready`
- Prometheus: `/metrics`
- RPC API keys (`X-API-Key`)
- JWT + CORS prod profile
- JSON structured logs (`LOG_JSON`)
- Atomic SQLite block commits
- Redis distributed rate limit (HA)
- K8s manifests (`deploy/k8s/`)
- Grafana dashboard + Prometheus alerts
- Secret scanner in CI

## Quick start

```bash
pip install -r requirements.txt
python main.py
open http://localhost:8080
```

## Prod profile

```bash
DEPLOYMENT_MODE=prod
REQUIRE_WALLET_FILE=true
JWT_ENFORCE_ADMIN=true
RPC_API_KEY_REQUIRED=true
RPC_API_KEYS=<generate via scripts/generate_rpc_key.py>
LOG_JSON=true
python main.py
```

## Observability

```bash
docker compose -f docker-compose.observability.yml up -d
# Grafana: http://localhost:3000 (admin/admin)
```

## Tests

83 tests passing in CI.

---

*Not a production mainnet. Educational use only.*
