#!/bin/sh
# Clone node1 blockchain.db into node2 volume before node2 starts (devnet parity with start_two_nodes.ps1)
set -eu

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
for suffix in -shm -wal; do
  if [ -f "$FROM/blockchain.db$suffix" ]; then
    cp "$FROM/blockchain.db$suffix" "$TO/blockchain.db$suffix"
  fi
done
echo "node2 DB seeded from node1 ($(wc -c < "$TO/blockchain.db") bytes)"
