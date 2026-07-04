#!/usr/bin/env bash
# Multi-node P2P smoke — two local nodes, state consistency check.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
URL1="${1:-http://127.0.0.1:8080}"
URL2="${2:-http://127.0.0.1:8081}"
WAIT="${3:-120}"
echo "Multi-node P2P smoke (n1=$URL1 n2=$URL2)"
exec python scripts/verify_p2p_ci.py --mode auto --wait "$WAIT" --url1 "$URL1" --url2 "$URL2"
