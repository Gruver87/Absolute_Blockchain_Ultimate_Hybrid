#!/bin/sh
set -eu

ORDINAL="${HOSTNAME##*-}"
if [ "${ORDINAL}" = "0" ]; then
  export MINING_ENABLED="${MINING_ENABLED:-true}"
  export FOLLOWER_GENESIS_SYNC="${FOLLOWER_GENESIS_SYNC:-false}"
else
  export MINING_ENABLED="${MINING_ENABLED:-false}"
  export FOLLOWER_GENESIS_SYNC="${FOLLOWER_GENESIS_SYNC:-true}"
fi

exec python main.py --config /app/config/node.prod.k8s.json
