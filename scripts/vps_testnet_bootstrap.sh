#!/usr/bin/env bash
# Bootstrap public testnet seed on Linux VPS (chain 77777).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MESH3="${MESH3:-0}"
for arg in "$@"; do
  if [[ "$arg" == "--mesh3" ]]; then
    MESH3=1
  fi
done

if [[ "$MESH3" == "1" ]]; then
  echo "=== Absolute public testnet VPS bootstrap (3-node mesh) ==="
  echo "  chain_id=77777  ports: HTTP 19080/19081/19082"
else
  echo "=== Absolute public testnet VPS bootstrap ==="
  echo "  chain_id=77777  ports: HTTP 19080 RPC 19085 P2P 19500"
fi

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

COMPOSE=(docker compose -f docker-compose.testnet.yml -p abs-testnet)
if [[ "$MESH3" == "1" ]]; then
  COMPOSE+=(-f docker-compose.testnet.mesh3.yml --profile validators)
  "${COMPOSE[@]}" build testnet-seed testnet-validator testnet-validator-3
  "${COMPOSE[@]}" up -d testnet-seed testnet-validator testnet-validator-3
else
  "${COMPOSE[@]}" build testnet-seed
  "${COMPOSE[@]}" up -d testnet-seed
fi

HTTP_PORT="${TESTNET_HTTP_PORT:-19080}"
deadline=$((SECONDS + 240))
until curl -sf "http://127.0.0.1:${HTTP_PORT}/health/ready" >/dev/null 2>&1; do
  if (( SECONDS > deadline )); then
    echo "FAIL: seed not ready within 4 minutes" >&2
    exit 1
  fi
  sleep 3
done

python3 scripts/public_testnet_gate.py --live --base-url "http://127.0.0.1:${HTTP_PORT}"
python3 scripts/vps_testnet_preflight.py --live --base-url "http://127.0.0.1:${HTTP_PORT}" || true
python3 scripts/testnet_uptime_probe.py --base-url "http://127.0.0.1:${HTTP_PORT}" --append || true

if [[ "$MESH3" == "1" ]]; then
  python3 scripts/verify_testnet_mesh.py --mesh3 --wait 120 || true
  echo "OK: testnet 3-node mesh live on :19080/:19081/:19082"
else
  echo "OK: testnet seed live on :${HTTP_PORT}"
fi

echo "  TLS: sudo bash deploy/nginx/install_testnet_nginx.sh testnet.yourdomain.com"
echo "  DNS: python3 scripts/testnet_dns_cutover.py --domain testnet.yourdomain.com"
echo "  cron: */5 * * * * cd $ROOT && python3 scripts/testnet_uptime_probe.py --append"
echo "  gate: python3 scripts/public_testnet_gate.py --live --require-soak-hours 48"
