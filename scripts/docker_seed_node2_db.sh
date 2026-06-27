#!/bin/sh
# Reference copy of node2-db-seed logic (compose uses inline command to avoid Windows CRLF mounts).
set -e

FROM="${SEED_FROM:-/seed-from}"
TO="${SEED_TO:-/seed-to}"

if [ "${SKIP_DB_SEED:-0}" = "1" ]; then
  echo "node2 DB seed skipped (SKIP_DB_SEED=1)"
  exit 0
fi

if [ ! -f "$FROM/blockchain.db" ]; then
  echo "node1 DB not found at $FROM/blockchain.db — node2 starts fresh"
  exit 0
fi

rm -f "$TO/blockchain.db" "$TO/blockchain.db-shm" "$TO/blockchain.db-wal"
cp "$FROM/blockchain.db" "$TO/blockchain.db"
echo "node2 DB seeded from node1 (main file only, node1 stopped)"
