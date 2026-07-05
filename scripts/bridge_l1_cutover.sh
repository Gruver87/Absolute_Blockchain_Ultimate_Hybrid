#!/usr/bin/env bash
# Bridge L1 cutover gate — static + optional live checks.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CONFIG="node.prod.mainnet-v1.bridge.example.json"
LIVE=0
PROBE_L1=0
BASE_URL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --live) LIVE=1; shift ;;
    --probe-l1) PROBE_L1=1; shift ;;
    --config) CONFIG="$2"; shift 2 ;;
    --base-url) BASE_URL="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [[ -f .env ]]; then set -a; source .env; set +a; fi

args=(scripts/bridge_l1_cutover.py --config "$CONFIG")
[[ "$LIVE" -eq 1 ]] && args+=(--live)
[[ "$PROBE_L1" -eq 1 ]] && args+=(--probe-l1)
[[ -n "$BASE_URL" ]] && args+=(--base-url "$BASE_URL")

python "${args[@]}"
