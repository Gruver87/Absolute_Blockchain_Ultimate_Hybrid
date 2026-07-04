#!/usr/bin/env bash
# Full hybrid verification — delegates to the unified test script.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec bash "$ROOT/scripts/test_blockchain_full.sh" "$@"
