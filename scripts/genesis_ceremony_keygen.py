#!/usr/bin/env python3
"""Generate validator wallets + public manifest for mainnet ceremony (offline)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.ceremony_keygen import generate_validator_set, verify_ceremony_directory
from runtime.genesis_ceremony import build_from_paths
from runtime.mainnet_constants import MAINNET_V1_CHAIN_ID


def main() -> int:
    parser = argparse.ArgumentParser(description="Offline mainnet validator keygen ceremony")
    parser.add_argument(
        "--template",
        default="validators.manifest.mainnet-v1.example.json",
        help="Stake/node_id template (addresses replaced by fresh keys)",
    )
    parser.add_argument(
        "--config",
        default="node.prod.mainnet-v1.example.json",
        help="Node config for ceremony hash",
    )
    parser.add_argument(
        "--out-dir",
        default="data/ceremony_keys",
        help="Output directory (gitignored via data/)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify existing --out-dir instead of generating",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    if args.verify:
        errors, warnings = verify_ceremony_directory(str(out_dir))
        if args.json:
            print(json.dumps({"ok": not errors, "errors": errors, "warnings": warnings}, indent=2))
        else:
            if errors:
                print("FAIL: ceremony directory verification")
                for err in errors:
                    print(f"  - {err}")
            else:
                print(f"OK: ceremony directory verified ({out_dir})")
            for warn in warnings:
                print(f"  WARN: {warn}")
        return 1 if errors else 0

    template = str(ROOT / args.template) if not Path(args.template).is_absolute() else args.template
    _manifest, gen_errors, manifest_path = generate_validator_set(
        template,
        str(out_dir),
        chain_id=MAINNET_V1_CHAIN_ID,
    )
    if gen_errors:
        for err in gen_errors:
            print(f"FAIL: {err}")
        return 1

    config_path = str(ROOT / args.config) if not Path(args.config).is_absolute() else args.config
    artifact, ceremony_errors = build_from_paths(
        config_path,
        str(manifest_path),
        strict_addresses=True,
    )
    verify_errors, _ = verify_ceremony_directory(str(out_dir))
    all_errors = list(ceremony_errors) + list(verify_errors)

    if args.json:
        print(
            json.dumps(
                {
                    "ok": not all_errors,
                    "out_dir": str(out_dir),
                    "manifest_path": str(manifest_path),
                    "ceremony_hash": artifact.get("ceremony_hash"),
                    "validator_set_hash": artifact.get("validator_set_hash"),
                    "errors": all_errors,
                },
                indent=2,
            )
        )
    else:
        print("Mainnet ceremony keygen")
        print("=" * 60)
        print(f"  out_dir           : {out_dir}")
        print(f"  manifest          : {manifest_path}")
        print(f"  ceremony_hash     : {artifact.get('ceremony_hash', '')[:16]}…")
        print(f"  validator_set_hash: {artifact.get('validator_set_hash', '')[:16]}…")
        print(f"  validators        : {artifact.get('validators_count', 0)}")
        if all_errors:
            print("  errors:")
            for err in all_errors:
                print(f"    - {err}")
        else:
            print("  OK: wallets + manifest ready (local only — do not commit)")
            print(f"  Pin: $env:GENESIS_CEREMONY_HASH = \"{artifact.get('ceremony_hash')}\"")

    return 1 if all_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
