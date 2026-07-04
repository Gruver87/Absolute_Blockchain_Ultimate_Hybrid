#!/usr/bin/env python3
"""Apply generated ceremony material to local prod data/ (never commit keys)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, Tuple

from runtime.genesis_ceremony import build_from_paths
from runtime.ceremony_keygen import verify_ceremony_directory, verify_wallet_file


def deploy_ceremony_files(
    ceremony_dir: str,
    *,
    root: str | Path,
    data_dir: str | Path = "data",
    validator_index: int = 1,
    node_config: str = "node.prod.mainnet-v1.example.json",
) -> Tuple[Dict[str, Any], list[str]]:
    """Copy manifest + validator wallet into data/ for prod/docker deploy."""
    base = Path(root).resolve()
    cdir = Path(ceremony_dir)
    if not cdir.is_absolute():
        cdir = base / cdir
    data = Path(data_dir)
    if not data.is_absolute():
        data = base / data
    data.mkdir(parents=True, exist_ok=True)

    errors: list[str] = []
    verify_errors, _ = verify_ceremony_directory(str(cdir))
    errors.extend(verify_errors)
    if errors:
        return {}, errors

    src_manifest = cdir / "validators.manifest.json"
    dst_manifest = data / "validators.manifest.json"
    shutil.copy2(src_manifest, dst_manifest)

    wallet_src = cdir / "wallets" / f"validator-{int(validator_index)}.wallet.json"
    dst_wallet = data / "wallet.json"
    if not wallet_src.is_file():
        errors.append(f"wallet_missing:{wallet_src}")
        return {}, errors
    shutil.copy2(wallet_src, dst_wallet)

    ok, reason = verify_wallet_file(str(dst_wallet), str(dst_manifest), int(validator_index))
    if not ok:
        errors.append(f"wallet_manifest_binding:{reason}")

    cfg_path = base / node_config
    artifact, ceremony_errors = build_from_paths(
        str(cfg_path),
        str(dst_manifest),
        strict_addresses=True,
    )
    errors.extend([f"genesis_ceremony:{e}" for e in ceremony_errors])

    result = {
        "ceremony_dir": str(cdir),
        "manifest_path": str(dst_manifest),
        "wallet_path": str(dst_wallet),
        "validator_index": int(validator_index),
        "ceremony_hash": artifact.get("ceremony_hash"),
        "validator_set_hash": artifact.get("validator_set_hash"),
        "ready": artifact.get("ready"),
    }
    meta_path = data / "ceremony_deploy.json"
    meta_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    return result, errors
