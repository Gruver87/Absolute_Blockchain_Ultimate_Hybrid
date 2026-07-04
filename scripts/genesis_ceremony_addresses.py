#!/usr/bin/env python3
"""Print deterministic mainnet-v1 ceremony validator addresses for operator keygen."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.mainnet_constants import MAINNET_V1_CHAIN_ID, ceremony_validator_address
from runtime.validator_loader import manifest_entries


def main() -> int:
    parser = argparse.ArgumentParser(description="Mainnet v1 ceremony address helper")
    parser.add_argument(
        "--manifest",
        default="validators.manifest.mainnet-v1.example.json",
        help="Validator manifest (node_id + index rows)",
    )
    parser.add_argument("--chain-id", type=int, default=MAINNET_V1_CHAIN_ID)
    parser.add_argument("--json", action="store_true", help="Emit JSON array")
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = ROOT / manifest_path
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = []
    for row in manifest_entries(manifest):
        index = int(row.get("index", 0) or 0)
        node_id = str(row.get("node_id", "") or f"validator-{index}")
        addr = ceremony_validator_address(args.chain_id, index, node_id)
        rows.append(
            {
                "index": index,
                "node_id": node_id,
                "ceremony_address": addr,
                "manifest_address": str(row.get("address", "") or "").lower(),
                "matches_manifest": str(row.get("address", "") or "").lower() == addr.lower(),
            }
        )

    if args.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return 0

    print(f"Mainnet v1 ceremony addresses (chain_id={args.chain_id})")
    print("=" * 60)
    for row in rows:
        match = "OK" if row["matches_manifest"] else "MISMATCH"
        print(
            f"  [{row['index']}] {row['node_id']}\n"
            f"       ceremony : {row['ceremony_address']}\n"
            f"       manifest : {row['manifest_address']} ({match})"
        )
    print("\nGenerate operator keys for these addresses before public cutover.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
