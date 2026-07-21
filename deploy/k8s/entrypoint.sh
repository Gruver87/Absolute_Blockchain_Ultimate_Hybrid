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

TLS_SRC="/app/p2p_tls_secrets"
TLS_DST="/app/p2p_tls"
if [ -d "${TLS_SRC}" ]; then
  mkdir -p "${TLS_DST}"
  if [ -f "${TLS_SRC}/ca.pem" ]; then
    cp "${TLS_SRC}/ca.pem" "${TLS_DST}/ca.pem"
  fi
  NODE_CERT="${TLS_SRC}/node-${ORDINAL}.pem"
  NODE_KEY="${TLS_SRC}/node-${ORDINAL}.key"
  if [ -f "${NODE_CERT}" ] && [ -f "${NODE_KEY}" ]; then
    cp "${NODE_CERT}" "${TLS_DST}/node.pem"
    cp "${NODE_KEY}" "${TLS_DST}/node.key"
  elif [ -f "${TLS_SRC}/tls.crt" ] && [ -f "${TLS_SRC}/tls.key" ]; then
    cp "${TLS_SRC}/tls.crt" "${TLS_DST}/node.pem"
    cp "${TLS_SRC}/tls.key" "${TLS_DST}/node.key"
  else
    echo "[entrypoint] WARN: missing P2P TLS material for ordinal ${ORDINAL}" >&2
  fi
fi

exec python main.py --config /app/config/node.prod.k8s.json
