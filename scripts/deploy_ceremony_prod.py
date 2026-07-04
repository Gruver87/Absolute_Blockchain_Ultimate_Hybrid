#!/usr/bin/env python3
"""Copy ceremony manifest + validator wallet into data/ for prod deploy."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.ceremony_deploy import deploy_ceremony_files


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy ceremony files to data/ for prod")
    parser.add_argument(
        "--ceremony-dir",
        default="data/ceremony_keys",
        help="Generated ceremony directory",
    )
    parser.add_argument("--validator-index", type=int, default=1)
    parser.add_argument(
        "--config",
        default="node.prod.mainnet-v1.example.json",
        help="Node config used for ceremony hash",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    result, errors = deploy_ceremony_files(
        args.ceremony_dir,
        root=ROOT,
        validator_index=args.validator_index,
        node_config=args.config,
    )
    if args.json:
        print(json.dumps({"ok": not errors, "result": result, "errors": errors}, indent=2))
    else:
        if errors:
            print("FAIL: ceremony deploy")
            for err in errors:
                print(f"  - {err}")
        else:
            print("OK: ceremony deployed to data/")
            print(f"  manifest : {result.get('manifest_path')}")
            print(f"  wallet   : {result.get('wallet_path')}")
            print(f"  ceremony_hash: {result.get('ceremony_hash')}")
            print("")
            print("Set for prod node / docker:")
            print('  $env:VALIDATORS_MANIFEST_PATH = "data/validators.manifest.json"')
            print(f'  $env:GENESIS_CEREMONY_HASH = "{result.get("ceremony_hash")}"')
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
