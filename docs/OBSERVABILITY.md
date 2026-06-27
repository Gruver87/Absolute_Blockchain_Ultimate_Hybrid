# Observability Stack

Мониторинг узла: Prometheus + Grafana.

## Быстрый старт

**Терминал 1** — нода:

```bash
python main.py
```

**Терминал 2** — мониторинг:

```bash
docker compose -f docker-compose.observability.yml up -d
```

## URL

| Сервис | URL | Логин |
|--------|-----|-------|
| Grafana | http://localhost:3000 | admin / admin |
| Prometheus | http://localhost:9090 | — |
| Node metrics | http://localhost:8080/metrics | — |

## Метрики

- `abs_uptime_seconds` — uptime
- `abs_chain_height` — высота цепи
- `abs_peers_connected` — P2P пиры
- `abs_mempool_size` — мемпул
- `abs_http_requests_total` — HTTP запросы
- `abs_errors_total` — ошибки API
- `abs_native_crypto_available` / `abs_native_crypto_self_test` — состояние PyO3/Rust crypto
- `abs_rust_bridge_required` / `abs_rust_bridge_ok` — production readiness Rust bridge CLI

## Алерты

Файл: `deploy/prometheus/alerts.yml`

- `AbsoluteNodeDown` — нода недоступна 2m
- `AbsoluteNoPeers` — 0 пиров 10m
- `AbsoluteMempoolBacklog` — mempool > 500
- `AbsoluteHighErrorRate` — рост ошибок
- `AbsoluteRustBridgeDown` — production Rust bridge не прошёл JSON smoke-test

## JSON-логи

```bash
LOG_JSON=true python main.py
# data/node.log — одна JSON-строка на событие
```

Подходит для Loki, ELK, CloudWatch.
