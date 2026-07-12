#!/usr/bin/env python3
"""Preflight checks before prod deploy: ceremony dir, hash pin, deploy meta."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def run_ceremony_preflight(
    ceremony_dir: str,
    *,
    config_path: str = "node.prod.mainnet-v1.example.json",
    strict_mainnet: bool = False,
    require_env_pin: bool = False,
) -> Tuple[List[str], List[str], dict]:
    from runtime.ceremony_keygen import verify_ceremony_directory
    from runtime.genesis_ceremony import build_from_paths

    cdir = Path(ceremony_dir)
    if not cdir.is_absolute():
        cdir = ROOT / cdir
    errors: List[str] = []
    warnings: List[str] = []
    meta: dict = {"ceremony_dir": str(cdir)}

    if not cdir.is_dir():
        return [f"ceremony_dir_missing:{cdir}"], warnings, meta

    c_errors, c_warnings = verify_ceremony_directory(str(cdir))
    errors.extend(c_errors)
    warnings.extend(c_warnings)

    manifest = cdir / "validators.manifest.json"
    cfg = Path(config_path)
    if not cfg.is_absolute():
        cfg = ROOT / cfg
    if not manifest.is_file():
        errors.append(f"ceremony_manifest_missing:{manifest}")
        return errors, warnings, meta

    artifact, build_errors = build_from_paths(
        str(cfg),
        str(manifest),
        strict_addresses=strict_mainnet,
    )
    errors.extend(build_errors)
    computed = str(artifact.get("ceremony_hash") or "")
    meta["ceremony_hash"] = computed
    meta["ready"] = bool(artifact.get("ready"))

    pinned = (os.environ.get("GENESIS_CEREMONY_HASH") or "").strip()
    meta["env_pinned_hash"] = pinned
    if require_env_pin and not pinned:
        errors.append("GENESIS_CEREMONY_HASH not set (run scripts/pin_ceremony_hash.ps1)")
    elif pinned and computed and pinned != computed:
        errors.append("GENESIS_CEREMONY_HASH mismatch: env vs ceremony manifest")

    deploy_meta_path = ROOT / "data" / "ceremony_deploy.json"
    if deploy_meta_path.is_file():
        try:
            deploy_meta = json.loads(deploy_meta_path.read_text(encoding="utf-8"))
            deployed = str(deploy_meta.get("ceremony_hash") or "")
            meta["deploy_meta_hash"] = deployed
            deployed_dir = str(deploy_meta.get("ceremony_dir") or "")
            same_ceremony = bool(deployed_dir) and Path(deployed_dir).resolve() == cdir.resolve()
            meta["deploy_meta_same_ceremony"] = same_ceremony
            if same_ceremony:
                if deployed and computed and deployed != computed:
                    errors.append("ceremony_deploy.json hash mismatch vs live ceremony dir")
                if pinned and deployed and pinned != deployed:
                    warnings.append("GENESIS_CEREMONY_HASH differs from data/ceremony_deploy.json")
            elif deployed and computed and pinned and pinned == deployed:
                warnings.append(
                    "ceremony_deploy.json refers to a different ceremony_dir than preflight target"
                )
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            warnings.append(f"ceremony_deploy.json unreadable: {exc}")

    if strict_mainnet and not artifact.get("mainnet_addresses_ready"):
        errors.append("ceremony_not_mainnet_ready: placeholder validator addresses remain")

    return errors, warnings, meta


def main() -> int:
    parser = argparse.ArgumentParser(description="Ceremony preflight before prod deploy")
    parser.add_argument(
        "--ceremony-dir",
        default="data/ceremony_keys",
        help="Generated ceremony directory (manifest + wallets/)",
    )
    parser.add_argument(
        "--config",
        default="node.prod.mainnet-v1.example.json",
        help="Node config for ceremony hash computation",
    )
    parser.add_argument(
        "--strict-mainnet",
        action="store_true",
        help="Reject placeholder/template validator addresses",
    )
    parser.add_argument(
        "--require-env-pin",
        action="store_true",
        help="Fail if GENESIS_CEREMONY_HASH is not set or mismatched",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    errors, warnings, meta = run_ceremony_preflight(
        args.ceremony_dir,
        config_path=args.config,
        strict_mainnet=args.strict_mainnet,
        require_env_pin=args.require_env_pin,
    )
    payload = {"ok": not errors, "errors": errors, "warnings": warnings, **meta}
    out = ROOT / "data" / "ceremony_preflight.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(payload, indent=2))
    elif errors:
        print("FAIL: ceremony preflight")
        for err in errors:
            print(f"  - {err}")
    else:
        print("OK: ceremony preflight")
        if meta.get("ceremony_hash"):
            print(f"  ceremony_hash: {meta['ceremony_hash']}")
    for warn in warnings:
        print(f"  WARN: {warn}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
