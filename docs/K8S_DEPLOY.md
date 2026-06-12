# Kubernetes Deploy (Phase 5)

> Учебный кластер из 3 нод + Redis. Не mainnet production.

## Prerequisites

- Kubernetes 1.28+
- `kubectl`, `kustomize` (или `kubectl apply -k`)
- Docker image: `absolute-blockchain:latest`

## Build image

```bash
docker build -t absolute-blockchain:latest .
# For minikube:
minikube image load absolute-blockchain:latest
```

## Deploy

```bash
kubectl apply -k deploy/k8s/
kubectl -n absolute-chain get pods -w
```

## Services

| Service | Port | Purpose |
|---------|------|---------|
| `abs-http` | 8080 | REST + Explorer |
| `abs-rpc` | 8545 | JSON-RPC |
| `abs-p2p` | 5000 | Headless P2P |
| `abs-redis` | 6379 | Distributed rate limit |

## Port-forward (local access)

```bash
kubectl -n absolute-chain port-forward svc/abs-http 8080:8080
kubectl -n absolute-chain port-forward svc/abs-rpc 8545:8545
```

## Health

```bash
curl http://localhost:8080/health/live
curl http://localhost:8080/health/ready
curl http://localhost:8080/metrics
```

## Multi-node P2P

- Pod `abs-node-0` — seed
- Pods `abs-node-1`, `abs-node-2` — `BOOTSTRAP_PEERS` → `abs-node-0.abs-p2p...:5000`
- Каждый pod: свой PVC `5Gi` в `/app/data`

## Prod wallet (staging→prod)

Для `DEPLOYMENT_MODE=prod` смонтируйте Secret с `wallet.json`:

```yaml
volumes:
  - name: wallet
    secret:
      secretName: abs-wallet
volumeMounts:
  - name: wallet
    mountPath: /app/data/wallet.json
    subPath: wallet.json
```

## ASGI note

Текущий API — `http.server` (stdlib). ASGI-миграция (uvicorn/starlette) — опциональный будущий шаг; для HA достаточно K8s replicas + health probes.
