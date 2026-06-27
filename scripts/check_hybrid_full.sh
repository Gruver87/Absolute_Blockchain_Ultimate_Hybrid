#!/usr/bin/env bash
# Full verification for Absolute Blockchain Ultimate Hybrid on Linux/macOS CI.
# Usage:
#   bash scripts/check_hybrid_full.sh
#   bash scripts/check_hybrid_full.sh --docker
#   bash scripts/check_hybrid_full.sh --live --p2p --base-url http://127.0.0.1:8080

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LIVE=0
P2P=0
DOCKER=0
BASE_URL="http://127.0.0.1:8080"
PYTEST_TIMEOUT=900

while [[ $# -gt 0 ]]; do
  case "$1" in
    --live)
      LIVE=1
      shift
      ;;
    --p2p)
      P2P=1
      shift
      ;;
    --docker)
      DOCKER=1
      shift
      ;;
    --base-url)
      BASE_URL="${2:?missing value for --base-url}"
      shift 2
      ;;
    --pytest-timeout)
      PYTEST_TIMEOUT="${2:?missing value for --pytest-timeout}"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

run_step() {
  local name="$1"
  shift
  echo
  echo "=== ${name} ==="
  "$@"
}

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Required command not found: $1" >&2
    exit 1
  fi
}

echo "Absolute Blockchain Ultimate Hybrid - full verification"
echo "Project: $ROOT"

require_command python
require_command cargo

run_step "Python version" python --version
run_step "Build Rust/PyO3 native crypto" bash scripts/build_native.sh
run_step "Build Rust bridge CLI" bash scripts/build_bridge.sh

run_step "Native crypto self-test" python -c "from crypto import native; s=native.native_crypto_status(required=True); assert s['available'] and s['self_test'], s; print('OK native:', s)"
run_step "Production gate" python scripts/prod_gate.py

run_step "Secrets scan" python scripts/check_secrets.py
run_step "Full audit with tests" python scripts/full_audit.py --pytest-timeout "$PYTEST_TIMEOUT"

if [[ "$LIVE" == "1" ]]; then
  live_args=(scripts/full_audit.py --live --no-tests --base-url "$BASE_URL")
  if [[ "$P2P" == "1" ]]; then
    live_args+=(--p2p)
  fi
  run_step "Live node audit" python "${live_args[@]}"
elif [[ "$P2P" == "1" ]]; then
  run_step "P2P verification" python scripts/verify_p2p_ci.py --mode auto --wait 120
fi

if [[ "$DOCKER" == "1" ]]; then
  require_command docker
  run_step "Docker devnet compose config" docker compose -f docker-compose.devnet.yml config --quiet
  run_step "Docker 3-node devnet compose config" docker compose -f docker-compose.devnet-3node.yml config --quiet
  run_step "Docker 5-validator devnet compose config" docker compose -f docker-compose.devnet-5validator.yml config --quiet

  export JWT_SECRET="${JWT_SECRET:-composeconfigplaceholder}"
  export RPC_API_KEYS="${RPC_API_KEYS:-composeconfigplaceholder}"
  export BRIDGE_ORACLE_SECRET="${BRIDGE_ORACLE_SECRET:-composeconfigplaceholder}"
  export CORS_ORIGINS="${CORS_ORIGINS:-https://explorer.example.com}"
  export ETH_RPC_URL="${ETH_RPC_URL:-https://rpc.example.com}"
  run_step "Docker production compose config" docker compose -f docker-compose.prod.yml config --quiet
fi

run_step "Hybrid critical tests" python -m pytest \
  tests/unit/test_native_crypto.py \
  tests/unit/test_state_root_native.py \
  tests/unit/test_secp256k1.py \
  tests/unit/test_chain_integrity.py \
  tests/unit/test_api.py \
  tests/unit/test_prod_config.py \
  tests/unit/test_bridge_health.py \
  tests/unit/test_rust_bridge_cli.py \
  tests/unit/test_rust_bridge_e2e.py \
  -q

echo
echo "OK: HYBRID BLOCKCHAIN FULL CHECK PASSED"
