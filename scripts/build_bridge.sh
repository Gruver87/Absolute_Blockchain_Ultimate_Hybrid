#!/usr/bin/env bash
# Build Rust cross-chain bridge CLI (bridge/abs_bridge_bin)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/bridge/rust_bridge"
cargo build --release
OUT="$ROOT/bridge/abs_bridge_bin"
cp target/release/abs_bridge_bin "$OUT"
chmod +x "$OUT"
echo "Built: $OUT"
