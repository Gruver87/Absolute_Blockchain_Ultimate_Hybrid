#!/usr/bin/env bash
# Three-node production mesh (ceremony manifest + per-validator wallets)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CEREMONY_DIR="${CEREMONY_DIR:-data/ceremony_keys}"
NO_CLONE_DB=0
SKIP_BUILD=0
KEEP_VOLUMES=0
PULL_LATEST=0
PROD_IMAGE="${PROD_IMAGE:-ghcr.io/gruver87/abs-blockchain-node:latest}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --ceremony-dir) CEREMONY_DIR="$2"; shift 2 ;;
    --no-clone-db) NO_CLONE_DB=1; shift ;;
    --skip-build) SKIP_BUILD=1; shift ;;
    --keep-volumes) KEEP_VOLUMES=1; shift ;;
    --pull-latest) PULL_LATEST=1; shift ;;
    --prod-image) PROD_IMAGE="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  echo "Loaded .env"
fi

python scripts/deploy_ceremony_prod.py --ceremony-dir "$CEREMONY_DIR" --mesh

META_PATH="data/ceremony_deploy.json"
export VALIDATORS_MANIFEST_PATH="data/validators.manifest.json"
export GENESIS_CEREMONY_HASH="$(python -c "import json; print(json.load(open('$META_PATH'))['ceremony_hash'])")"
export BRIDGE_ENABLED=false
export BRIDGE_PROBE_L1_RPC=false

for key in JWT_SECRET RPC_API_KEYS BRIDGE_ORACLE_SECRET CORS_ORIGINS ETH_RPC_URL; do
  if [[ -z "${!key:-}" ]]; then
    echo "Missing required prod env: $key" >&2
    exit 1
  fi
done

for wallet in \
  data/prod_mesh/wallets/validator-1.wallet.json \
  data/prod_mesh/wallets/validator-2.wallet.json \
  data/prod_mesh/wallets/validator-3.wallet.json \
  data/validators.manifest.json
do
  [[ -f "$wallet" ]] || { echo "FAIL: missing $wallet" >&2; exit 1; }
done

echo "Running production gate..."
python scripts/prod_gate.py

COMPOSE_FILE="docker-compose.prod.3node.yml"
COMPOSE_PROJECT="abs-prod-mesh3"
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

if [[ "$PULL_LATEST" -eq 1 ]]; then
  echo "PullLatest: pulling $PROD_IMAGE"
  docker pull "$PROD_IMAGE" || {
    echo "FAIL: could not pull $PROD_IMAGE" >&2
    echo "  Image is published after CI workflow 'Docker prod image' succeeds on master." >&2
    exit 1
  }
  export ABS_PROD_IMAGE="$PROD_IMAGE"
  SKIP_BUILD=1
fi

if [[ "$NO_CLONE_DB" -eq 1 ]]; then
  export SKIP_DB_SEED=1
else
  unset SKIP_DB_SEED || true
fi

echo "Recreating prod 3-node mesh (18180/18181/18182)..."
[[ "$SKIP_BUILD" -eq 1 ]] && echo "SkipBuild: using existing Docker image"
[[ "$KEEP_VOLUMES" -eq 1 ]] && echo "KeepVolumes: docker down without -v"
if [[ "$KEEP_VOLUMES" -eq 1 ]]; then
  docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" down --remove-orphans || true
else
  docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" down -v --remove-orphans || true
fi
if [[ "$SKIP_BUILD" -eq 0 ]]; then
  docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" build node1 node2 node3
fi
docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" up -d --force-recreate node1

echo "Waiting for node1..."
deadline=$((SECONDS + 180))
until curl -sf "http://127.0.0.1:18180/health/ready" >/dev/null; do
  [[ "$SECONDS" -lt "$deadline" ]] || { docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" logs node1 --tail 40; exit 1; }
  sleep 5
done

if [[ "$NO_CLONE_DB" -eq 0 ]]; then
  pre_h="$(curl -sf "http://127.0.0.1:18180/status" | python -c "import sys,json; print(int(json.load(sys.stdin).get('height',0)))" 2>/dev/null || echo "")"
  if [[ -n "$pre_h" && "$pre_h" -gt 1 ]]; then
    echo "FAIL: node1 height=$pre_h before seed (expected <=1). Mining ran before mesh peers." >&2
    exit 1
  fi
  [[ -n "$pre_h" ]] && echo "OK: node1 height=$pre_h before seed"
  echo "Stopping node1 for consistent RocksDB seed..."
  docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" stop node1
  docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" --profile seed run --rm node2-db-seed
  docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" --profile seed run --rm node3-db-seed
fi

echo "Starting 3-node mesh together (avoid solo mining before followers)..."
docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" up -d --force-recreate node1 node2 node3

echo "Waiting for node1..."
deadline=$((SECONDS + 180))
until curl -sf "http://127.0.0.1:18180/health/ready" >/dev/null; do
  [[ "$SECONDS" -lt "$deadline" ]] || { docker compose -p "$COMPOSE_PROJECT" -f "$COMPOSE_FILE" logs node1 --tail 40; exit 1; }
  sleep 3
done

for port in 18181 18182; do
  deadline=$((SECONDS + 120))
  until curl -sf "http://127.0.0.1:${port}/health/live" >/dev/null; do
    [[ "$SECONDS" -lt "$deadline" ]] || { echo "FAIL: node not reachable on :$port" >&2; exit 1; }
    sleep 3
  done
done

echo "Waiting for 3-node mesh sync..."
python scripts/verify_p2p_ci.py --mode prod-mesh3-live \
  --url1 http://127.0.0.1:18180 \
  --url2 http://127.0.0.1:18181 \
  --url3 http://127.0.0.1:18182 \
  --wait 360

python scripts/prod_smoke.py http://127.0.0.1:18180

echo "OK: prod 3-node mesh"
echo "  node1 http://127.0.0.1:18180"
echo "  node2 http://127.0.0.1:18181"
echo "  node3 http://127.0.0.1:18182"
