#!/usr/bin/env bash
# Full blockchain verification — single entry point (delegates to test_blockchain_full.sh).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$ROOT/scripts/test_blockchain_full.sh" "$@"
