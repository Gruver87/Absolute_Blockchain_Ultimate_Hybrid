#!/usr/bin/env python3
"""Mainnet genesis ceremony — validator set + tokenomics artifact builder."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

from runtime.mainnet_constants import (
    is_ceremony_template_address,
    is_zero_prefix_placeholder_address,
)
from runtime.tokenomics import (
    FOUNDER_AMOUNT_ABS,
    MAX_SUPPLY_ABS,
    genesis_balances,
    get_tokenomics_summary,
)
from runtime.validator_loader import (
    load_manifest,
    manifest_entries,
    manifest_requires_runtime_key_derivation,
    snapshot_public_set,
)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def validator_set_hash(manifest: Dict[str, Any]) -> str:
    rows = []
    for row in snapshot_public_set(manifest):
        rows.append({
            "index": row.get("index", 0),
            "node_id": row.get("node_id", ""),
            "address": row["address"].lower(),
            "stake": float(row.get("stake", 0) or 0),
            "mines": bool(row.get("mines", True)),
            "shard_id": row.get("shard_id"),
        })
    rows.sort(key=lambda r: (int(r.get("index", 0)), r["address"]))
    digest = hashlib.sha256(_canonical_json(rows).encode("utf-8")).hexdigest()
    return digest


def genesis_alloc_hash(founder_address: str = "") -> str:
    alloc = genesis_balances(founder_address or None)
    ordered = {k.lower(): float(v) for k, v in sorted(alloc.items())}
    return hashlib.sha256(_canonical_json(ordered).encode("utf-8")).hexdigest()


def _is_placeholder_validator_address(address: str) -> bool:
    return is_zero_prefix_placeholder_address(address)


def _is_strict_template_address(address: str) -> bool:
    return is_ceremony_template_address(address)


def validate_manifest_for_mainnet(
    manifest: Dict[str, Any],
    *,
    strict_addresses: bool = False,
) -> List[str]:
    errors: List[str] = []
    if manifest_requires_runtime_key_derivation(manifest):
        errors.append("manifest_must_list_explicit_0x_addresses")
    rows = manifest_entries(manifest)
    if not rows:
        errors.append("manifest_empty")
    seen = set()
    total_stake = 0.0
    for row in rows:
        addr = str(row.get("address", "") or "").strip().lower()
        if not addr:
            errors.append("manifest_row_missing_address")
            continue
        if addr in seen:
            errors.append(f"duplicate_validator:{addr}")
        seen.add(addr)
        stake = float(row.get("stake", 0) or 0)
        if stake <= 0:
            errors.append(f"invalid_stake:{addr}")
        if strict_addresses and _is_strict_template_address(addr):
            errors.append(f"placeholder_validator_address:{addr}")
        total_stake += stake
    if total_stake <= 0:
        errors.append("total_stake_zero")
    return errors


def build_ceremony_artifact(
    config: Dict[str, Any],
    manifest: Dict[str, Any],
    manifest_path: str = "",
    founder_address: str = "",
    *,
    strict_addresses: bool = False,
) -> Dict[str, Any]:
    errors = validate_manifest_for_mainnet(manifest, strict_addresses=strict_addresses)
    validators = snapshot_public_set(manifest)
    placeholder_addrs = [
        str(row.get("address", ""))
        for row in manifest_entries(manifest)
        if _is_placeholder_validator_address(str(row.get("address", "")))
    ]
    founder = founder_address or str(config.get("founder_address", "") or "")
    tokenomics = get_tokenomics_summary(founder or None)
    artifact = {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "network_name": str(config.get("network_name", "Absolute")),
        "chain_id": int(config.get("chain_id", 1) or 1),
        "deployment_mode": str(config.get("deployment_mode", "prod")),
        "validators_manifest_path": manifest_path,
        "validators_manifest_sha256": _sha256_file(Path(manifest_path)) if manifest_path and Path(manifest_path).is_file() else "",
        "validators_count": len(validators),
        "total_stake": round(sum(float(v.get("stake", 0) or 0) for v in validators), 6),
        "validator_set_hash": validator_set_hash(manifest),
        "genesis_alloc_hash": genesis_alloc_hash(founder),
        "max_supply_abs": MAX_SUPPLY_ABS,
        "founder_amount_abs": FOUNDER_AMOUNT_ABS,
        "tokenomics": tokenomics,
        "validators": validators,
        "ready": len(errors) == 0,
        "mainnet_addresses_ready": len(placeholder_addrs) == 0,
        "placeholder_validator_count": len(placeholder_addrs),
        "errors": errors,
    }
    artifact["ceremony_hash"] = hashlib.sha256(
        _canonical_json({
            "chain_id": artifact["chain_id"],
            "validator_set_hash": artifact["validator_set_hash"],
            "genesis_alloc_hash": artifact["genesis_alloc_hash"],
            "validators_count": artifact["validators_count"],
        }).encode("utf-8")
    ).hexdigest()
    return artifact


def load_config_dict(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("config_must_be_object")
    return data


def build_from_paths(
    config_path: str,
    manifest_path: str,
    founder_address: str = "",
    *,
    strict_addresses: bool = False,
) -> Tuple[Dict[str, Any], List[str]]:
    cfg = load_config_dict(config_path)
    manifest = load_manifest(manifest_path)
    artifact = build_ceremony_artifact(
        cfg,
        manifest,
        manifest_path,
        founder_address,
        strict_addresses=strict_addresses,
    )
    return artifact, list(artifact.get("errors") or [])


def config_dict_from_config(config: Any) -> Dict[str, Any]:
    return {
        "network_name": getattr(config, "network_name", "Absolute"),
        "chain_id": int(getattr(config, "chain_id", 0) or 0),
        "deployment_mode": getattr(config, "deployment_mode", "dev"),
        "founder_address": getattr(config, "founder_address", ""),
    }


def verify_live_manifest(
    config: Any,
    *,
    strict_addresses: bool = False,
    expected_ceremony_hash: str = "",
) -> Tuple[List[str], Dict[str, Any]]:
    """Validate on-disk manifest for a running node config."""
    import os

    manifest_path = str(getattr(config, "validators_manifest_path", "") or "").strip()
    errors: List[str] = []
    if not manifest_path:
        errors.append("validators_manifest_path_missing")
        return errors, {}
    if not os.path.isfile(manifest_path):
        errors.append(f"validators_manifest_missing:{manifest_path}")
        return errors, {}

    manifest = load_manifest(manifest_path)
    errors.extend(validate_manifest_for_mainnet(manifest, strict_addresses=strict_addresses))
    artifact = build_ceremony_artifact(
        config_dict_from_config(config),
        manifest,
        manifest_path,
        getattr(config, "founder_address", ""),
        strict_addresses=strict_addresses,
    )
    if not artifact.get("mainnet_addresses_ready", True) and strict_addresses:
        errors.append("placeholder_validator_addresses_in_manifest")

    pinned = str(expected_ceremony_hash or os.environ.get("GENESIS_CEREMONY_HASH", "") or "").strip()
    if pinned and artifact.get("ceremony_hash") != pinned:
        errors.append("genesis_ceremony_hash_mismatch")

    return errors, artifact
