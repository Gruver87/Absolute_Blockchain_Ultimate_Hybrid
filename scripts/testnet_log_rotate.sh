#!/usr/bin/env bash
# Rotate public testnet node logs inside Docker (VPS cron weekly).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

COMPOSE=(docker compose -f docker-compose.testnet.yml -p abs-testnet)
SERVICES=(testnet-seed testnet-validator testnet-validator-3)
STAMP="$(date -u +%Y%m%d)"

for svc in "${SERVICES[@]}"; do
  if ! "${COMPOSE[@]}" ps -q "$svc" --status running 2>/dev/null | grep -q .; then
    continue
  fi
  "${COMPOSE[@]}" exec -T "$svc" sh -c "
    if [ -f data/node.log ] && [ -s data/node.log ]; then
      cp data/node.log data/node.log.${STAMP}
      : > data/node.log
      echo rotated data/node.log -> data/node.log.${STAMP}
    fi
  " || true
done

echo "OK: testnet log rotate complete"
