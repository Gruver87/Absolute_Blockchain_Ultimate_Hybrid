#!/usr/bin/env bash
# Bootstrap 3-node public testnet mesh on Linux VPS (chain 77777).
set -euo pipefail
export MESH3=1
exec "$(cd "$(dirname "$0")" && pwd)/vps_testnet_bootstrap.sh" --mesh3
