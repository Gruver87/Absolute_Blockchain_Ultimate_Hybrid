#!/usr/bin/env bash
# Bootstrap public testnet seed on Linux VPS (chain 77777).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=== Absolute public testnet VPS bootstrap ==="
echo "  chain_id=77777  ports: HTTP 9080 RPC 9085 P2P 9500"

if ! command -v docker >/dev/null 2>&1; then
  echo "FAIL: docker not installed" >&2
  exit 1
fi

if [[ ! -f .env.testnet ]]; then
  if [[ -f .env.testnet.example ]]; then
    cp .env.testnet.example .env.testnet
    echo "WARN: created .env.testnet — rotate JWT_SECRET and RPC_API_KEYS before public DNS"
  else
    echo "FAIL: missing .env.testnet.example" >&2
    exit 1
  fi
fi

python3 scripts/public_testnet_gate.py || true

docker compose -f docker-compose.testnet.yml -p abs-testnet build testnet-seed
docker compose -f docker-compose.testnet.yml -p abs-testnet up -d testnet-seed

HTTP_PORT="${TESTNET_HTTP_PORT:-9080}"
deadline=$((SECONDS + 180))
until curl -sf "http://127.0.0.1:${HTTP_PORT}/health/ready" >/dev/null 2>&1; do
  if (( SECONDS > deadline )); then
    echo "FAIL: seed not ready within 3 minutes" >&2
    exit 1
  fi
  sleep 3
done

python3 scripts/public_testnet_gate.py --live --base-url "http://127.0.0.1:${HTTP_PORT}"
echo "OK: testnet seed live on :${HTTP_PORT}"
  echo "  TLS: deploy/nginx/testnet.example.conf + certbot"
echo "  gate: python3 scripts/public_testnet_gate.py --live --require-soak-hours 48"
