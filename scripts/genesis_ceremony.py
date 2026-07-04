#!/usr/bin/env python3
"""Build and verify mainnet genesis ceremony artifact."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.genesis_ceremony import build_from_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Mainnet genesis ceremony builder")
    parser.add_argument("--config", default="node.prod.example.json", help="Node config JSON")
    parser.add_argument("--manifest", default="validators.manifest.example.json", help="Validator manifest")
    parser.add_argument("--founder", default="", help="Optional founder address override")
    parser.add_argument("--write", default="", help="Write artifact JSON to path")
    parser.add_argument("--json", action="store_true", help="Print artifact JSON to stdout")
    args = parser.parse_args()

    config_path = str(ROOT / args.config) if not Path(args.config).is_absolute() else args.config
    manifest_path = str(ROOT / args.manifest) if not Path(args.manifest).is_absolute() else args.manifest

    artifact, errors = build_from_paths(config_path, manifest_path, args.founder)
    out_path = args.write
    if out_path:
        target = Path(out_path)
        if not target.is_absolute():
            target = ROOT / target
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {target}")

    if args.json:
        print(json.dumps(artifact, indent=2, ensure_ascii=False))
    elif not out_path:
        print("Genesis ceremony")
        print("================")
        print(f"  chain_id          : {artifact['chain_id']}")
        print(f"  validators        : {artifact['validators_count']}")
        print(f"  validator_set_hash: {artifact['validator_set_hash'][:16]}…")
        print(f"  ceremony_hash     : {artifact['ceremony_hash'][:16]}…")
        print(f"  ready             : {artifact['ready']}")
        if errors:
            print("  errors:")
            for err in errors:
                print(f"    - {err}")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
