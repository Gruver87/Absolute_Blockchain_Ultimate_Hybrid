#!/usr/bin/env python3
"""Load public validator manifests (prod) — addresses only, no derived dev keys."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional


def load_manifest(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("validator_manifest_must_be_object")
    return data


def manifest_founder_address(path: str = "", manifest: Dict[str, Any] | None = None) -> str:
    """Founder pool address for genesis/replay — validator index 1 in public manifests."""
    data = manifest
    if data is None:
        if not path or not os.path.isfile(path):
            return ""
        data = load_manifest(path)
    for row in manifest_entries(data):
        if int(row.get("index", 0) or 0) == 1:
            addr = str(row.get("address", "") or "").strip()
            if addr.startswith("0x") and len(addr) == 42:
                return addr
    rows = manifest_entries(data)
    if rows:
        addr = str(rows[0].get("address", "") or "").strip()
        if addr.startswith("0x") and len(addr) == 42:
            return addr
    return ""


def manifest_entries(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    for row in manifest.get("validators") or []:
        if not isinstance(row, dict):
            continue
        rows.append(dict(row))
    return rows


def manifest_requires_runtime_key_derivation(manifest: Dict[str, Any]) -> bool:
    """Devnet manifests omit addresses and derive keys at runtime."""
    for row in manifest_entries(manifest):
        addr = str(row.get("address", "") or "").strip()
        if not addr or not addr.startswith("0x") or len(addr) != 42:
            return True
    return False


def snapshot_public_set(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Public validator set for APIs (no secrets)."""
    out = []
    for row in manifest_entries(manifest):
        addr = str(row.get("address", "") or "").strip()
        if not addr:
            continue
        out.append({
            "index": int(row.get("index", 0) or 0),
            "node_id": row.get("node_id", ""),
            "address": addr,
            "stake": float(row.get("stake", 0) or 0),
            "mines": bool(row.get("mines", True)),
            "public_key": str(row.get("public_key", "") or ""),
            "shard_id": row.get("shard_id"),
            "source": "manifest",
        })
    return out


def apply_public_manifest(node, path: str) -> int:
    """Register validators from a public manifest into DB + consensus + registry."""
    if not path or not os.path.isfile(path):
        return 0
    manifest = load_manifest(path)
    if node.config.is_production and manifest_requires_runtime_key_derivation(manifest):
        raise RuntimeError(
            "production validator manifest must list explicit 0x addresses "
            "(devnet key derivation is blocked)"
        )

    existing = {v["address"].lower() for v in (node.db.get_validators(active_only=False) or [])}
    added = 0
    for row in manifest_entries(manifest):
        addr = str(row.get("address", "") or "").strip()
        if not addr:
            continue
        stake = float(row.get("stake", getattr(node.config, "min_stake", 1000)))
        key = addr.lower()
        if key in existing:
            continue
        node.consensus.add_validator(addr, stake)
        if hasattr(node.db, "save_validator"):
            node.db.save_validator(addr, stake)
        existing.add(key)
        added += 1
        if getattr(node, "validator_registry", None) and hasattr(
            node.validator_registry, "register_validator"
        ):
            node.validator_registry.register_validator(addr, int(stake))
    node._public_validator_manifest = path  # noqa: SLF001
    node._public_validator_set = snapshot_public_set(manifest)  # noqa: SLF001
    if added:
        print(f"[Node] Public validator manifest: registered {added} validators from {path}")
    return added


def merged_registry_view_from_parts(
    db,
    validator_registry=None,
    manifest_rows: Optional[List[Dict[str, Any]]] = None,
    manifest_path: str = "",
) -> Dict[str, Any]:
    """Combine DB validators, optional manifest rows, and registry scores."""
    db_rows = db.get_validators(active_only=False) if db else []
    by_addr = {r["address"].lower(): dict(r) for r in db_rows}
    for row in manifest_rows or []:
        key = row["address"].lower()
        by_addr.setdefault(key, {})
        by_addr[key].update({
            "address": row["address"],
            "stake": row.get("stake", by_addr[key].get("stake", 0)),
            "node_id": row.get("node_id", ""),
            "mines": row.get("mines", True),
            "public_key": row.get("public_key", ""),
            "manifest": True,
        })
    if validator_registry and hasattr(validator_registry, "validators"):
        for addr, state in validator_registry.validators.items():
            key = addr.lower()
            entry = by_addr.setdefault(key, {"address": addr})
            if hasattr(state, "to_dict"):
                entry.update(state.to_dict())
            entry["registry"] = True
    validators = list(by_addr.values())
    validators.sort(key=lambda v: float(v.get("stake", 0) or 0), reverse=True)
    return {
        "enabled": True,
        "count": len(validators),
        "manifest_path": manifest_path or "",
        "validators": validators,
    }


def merged_registry_view(node) -> Dict[str, Any]:
    return merged_registry_view_from_parts(
        node.db,
        getattr(node, "validator_registry", None),
        getattr(node, "_public_validator_set", None),
        getattr(node, "_public_validator_manifest", "") or "",
    )
