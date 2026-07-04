#!/usr/bin/env bash
# Absolute Blockchain Ultimate Hybrid — ONE-STOP full verification (Linux/macOS/CI).
#
#   bash scripts/test_blockchain_full.sh
#   bash scripts/test_blockchain_full.sh --live --p2p --base-url http://127.0.0.1:8080
#   bash scripts/test_blockchain_full.sh --docker
#   bash scripts/test_blockchain_full.sh --skip-native-build

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

LIVE=0
P2P=0
DOCKER=0
DOCKER_BUILD=0
BUILD_RUST=0
SKIP_NATIVE_BUILD=0
NO_CLEAN=0
BASE_URL="http://127.0.0.1:8080"
PYTEST_TIMEOUT=900
P2P_WAIT=300
AUDIT_RETRIES=1

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
    --docker-build)
      DOCKER_BUILD=1
      shift
      ;;
    --build-rust)
      BUILD_RUST=1
      shift
      ;;
    --skip-native-build)
      SKIP_NATIVE_BUILD=1
      shift
      ;;
    --no-clean)
      NO_CLEAN=1
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
    --p2p-wait)
      P2P_WAIT="${2:?missing value for --p2p-wait}"
      shift 2
      ;;
    --audit-retries)
      AUDIT_RETRIES="${2:?missing value for --audit-retries}"
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

bridge_binary() {
  if [[ -x "$ROOT/bridge/abs_bridge_bin" ]]; then
    echo "$ROOT/bridge/abs_bridge_bin"
  elif [[ -f "$ROOT/bridge/abs_bridge_bin.exe" ]]; then
    echo "$ROOT/bridge/abs_bridge_bin.exe"
  fi
}

clear_python_cache() {
  find "$ROOT" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
  find "$ROOT" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete 2>/dev/null || true
}

run_full_audit_with_retry() {
  local attempt=0
  local max=$((AUDIT_RETRIES + 1))
  while [[ $attempt -lt $max ]]; do
    attempt=$((attempt + 1))
    echo "Full audit attempt ${attempt}/${max}"
    if python scripts/full_audit.py --pytest-timeout "$PYTEST_TIMEOUT"; then
      return 0
    fi
    if [[ $attempt -gt $AUDIT_RETRIES ]]; then
      return 1
    fi
    echo "Full audit failed once; cleaning caches and retrying..."
    clear_python_cache
    sleep 2
  done
}

echo "Absolute Blockchain Ultimate Hybrid — FULL BLOCKCHAIN TEST"
echo "Project: $ROOT"
echo "BaseUrl: $BASE_URL"

require_command python

run_step "Python version" python --version

if [[ "$SKIP_NATIVE_BUILD" != "1" ]]; then
  require_command cargo
  run_step "Build Rust/PyO3 native crypto (abs_native)" bash scripts/build_native.sh
fi

run_step "Native crypto self-test" python -c "from crypto import native; s=native.native_crypto_status(required=True); assert s['available'] and s['self_test'], s; print('OK native:', s)"
run_step "Secrets scan" python scripts/check_secrets.py
run_step "Static production gate" python scripts/prod_gate.py

bin="$(bridge_binary || true)"
if [[ "$BUILD_RUST" == "1" || -z "$bin" ]]; then
  require_command cargo
  run_step "Build Rust bridge CLI" bash scripts/build_bridge.sh
  bin="$(bridge_binary || true)"
fi
if [[ -z "$bin" ]]; then
  echo "Rust bridge binary missing. Re-run with --build-rust" >&2
  exit 1
fi
run_step "Rust bridge status" bash -c "printf '%s' '{\"command\":\"status\",\"args\":{}}' | '$bin' | python -c \"import json,sys; d=json.load(sys.stdin); assert d.get('status')=='ready', d; print('OK bridge:', d.get('status'), d.get('source'))\""

if [[ "$NO_CLEAN" != "1" ]]; then
  run_step "Clean generated Python cache" clear_python_cache
fi

run_step "Full audit + all pytest (tests/)" run_full_audit_with_retry

run_step "Hybrid critical native/consensus/EVM tests" python -m pytest \
  tests/unit/test_native_crypto.py \
  tests/unit/test_state_root_native.py \
  tests/unit/test_secp256k1.py \
  tests/unit/test_chain_integrity.py \
  tests/unit/test_api.py \
  tests/unit/test_prod_config.py \
  tests/unit/test_bridge_health.py \
  tests/unit/test_native_consensus_hash.py \
  tests/unit/test_native_peer_validation.py \
  tests/unit/test_evm_keccak_native.py \
  tests/unit/test_evm_native_u256.py \
  tests/unit/test_evm_native_cmp_memory.py \
  tests/unit/test_evm_native_arith_extended.py \
  tests/unit/test_evm_native_read_push.py \
  tests/unit/test_evm_native_jumpdest.py \
  tests/unit/test_evm_native_stack.py \
  tests/unit/test_evm_native_scan.py \
  tests/unit/test_native_deploy_address.py \
  tests/unit/test_mempool_batch_signatures.py \
  tests/unit/test_sync_incremental.py \
  tests/unit/test_rust_bridge_cli.py \
  tests/unit/test_rust_bridge_e2e.py \
  -q

if [[ "$LIVE" == "1" ]]; then
  run_step "Live node endpoints" python - <<PY
import urllib.request
base = "${BASE_URL}"
for path in (
    "/health/live", "/status", "/sync/status", "/features",
    "/bridge", "/tokenomics", "/chain/state-root/status",
):
    url = base + path
    print("GET", url)
    with urllib.request.urlopen(url, timeout=10) as resp:
        resp.read()
PY
  live_args=(scripts/full_audit.py --live --no-tests --base-url "$BASE_URL")
  if [[ "$P2P" == "1" ]]; then
    live_args+=(--p2p)
  fi
  run_step "Live audit" python "${live_args[@]}"
elif [[ "$P2P" == "1" ]]; then
  run_step "P2P auto verification" python scripts/verify_p2p_ci.py --mode auto --wait "$P2P_WAIT"
fi

if [[ "$DOCKER" == "1" ]]; then
  require_command docker
  run_step "Docker devnet compose config" docker compose -f docker-compose.devnet.yml config --quiet
  run_step "Docker devnet rust compose config" docker compose -f docker-compose.devnet-rust.yml config --quiet
  run_step "Docker 3-node devnet compose config" docker compose -f docker-compose.devnet-3node.yml config --quiet
  run_step "Docker 5-validator devnet compose config" docker compose -f docker-compose.devnet-5validator.yml config --quiet
  export JWT_SECRET="${JWT_SECRET:-composeconfigplaceholder}"
  export RPC_API_KEYS="${RPC_API_KEYS:-composeconfigplaceholder}"
  export BRIDGE_ORACLE_SECRET="${BRIDGE_ORACLE_SECRET:-composeconfigplaceholder}"
  export CORS_ORIGINS="${CORS_ORIGINS:-https://explorer.example.com}"
  export ETH_RPC_URL="${ETH_RPC_URL:-https://rpc.example.com}"
  run_step "Docker production compose config" docker compose -f docker-compose.prod.yml config --quiet
  if [[ "$DOCKER_BUILD" == "1" ]]; then
    run_step "Docker image build" docker compose -f docker-compose.devnet.yml build
  fi
fi

echo
echo "OK: FULL BLOCKCHAIN TEST PASSED"
echo "Reports:"
echo "  data/full_audit_report.json"
echo "  data/final_audit_report.json"
