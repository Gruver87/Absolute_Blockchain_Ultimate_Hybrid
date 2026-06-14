#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic 5-validator devnet manifest (Wave 55). No keys stored on disk."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional


def derive_validator_wallet(index: int):
    """Validators 2..N use deterministic dev-only keys."""
    if index <= 1:
        return None
    from crypto.wallet import Wallet

    pk = hashlib.sha256(f"absolute-devnet5-validator-{index}".encode()).hexdigest()
    return Wallet.from_private_key(pk)


def resolve_validator_address(index: int, founder_address: str = "") -> str:
    if index <= 1:
        return founder_address or ""
    w = derive_validator_wallet(index)
    return w.address if w else ""


def load_manifest(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def manifest_entries(manifest: Dict[str, Any], founder_address: str = "") -> List[Dict[str, Any]]:
    rows = []
    for row in manifest.get("validators") or []:
        idx = int(row.get("index", 0) or 0)
        addr = row.get("address") or resolve_validator_address(idx, founder_address)
        rows.append({**row, "index": idx, "address": addr})
    return rows


def mining_validator_addresses(manifest_path: str, founder_address: str = "") -> set:
    """Addresses allowed to propose blocks (manifest mines=true only)."""
    if not manifest_path or not os.path.isfile(manifest_path):
        return set()
    manifest = load_manifest(manifest_path)
    addrs = set()
    for row in manifest_entries(manifest, founder_address):
        if row.get("mines", True):
            addr = row.get("address", "")
            if addr:
                addrs.add(addr.lower())
    return addrs


def resolve_manifest_path(config) -> str:
    path = getattr(config, "testnet_validators_manifest", "") or ""
    if path:
        return path
    ev = int(getattr(config, "testnet_expected_validators", 0) or 0)
    base = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "docker",
    )
    if ev >= 5:
        return os.path.join(base, "validators.devnet5.json")
    if ev >= 3:
        return os.path.join(base, "validators.devnet3.json")
    return ""


def apply_manifest(node, manifest_path: str) -> int:
    """Register all manifest validators; returns count newly registered."""
    if not os.path.isfile(manifest_path):
        return 0
    manifest = load_manifest(manifest_path)
    founder = (
        getattr(node.config, "founder_address", "")
        or node.config.miner_address
        or ""
    )
    added = 0
    existing = {v["address"].lower() for v in (node.db.get_validators() or [])}
    for row in manifest_entries(manifest, founder):
        addr = row.get("address", "")
        if not addr or addr.lower() in existing:
            continue
        stake = float(row.get("stake", node.config.min_stake))
        node.consensus.add_validator(addr, stake)
        existing.add(addr.lower())
        added += 1
        if node.blockchain.get_height() <= 1 and int(row.get("index", 0) or 0) >= 2:
            bal = node.db.get_balance(addr)
            if bal < stake:
                node.db.update_balance(addr, stake)
    if added:
        print(f"[Node] Devnet5 manifest: registered {added} validators")
    return added


def install_validator_wallet(node, index: int) -> bool:
    """Attach deterministic signing wallet for validator index >= 2."""
    if index <= 1 or not getattr(node.config, "mining_enabled", False):
        return False
    w = derive_validator_wallet(index)
    if not w:
        return False
    node.wallet = w
    node.config.signing_address = w.address
    node.config.miner_address = w.address
    node._dev_signer_only = True
    print(f"[Node] Devnet5 validator #{index} signing: {w.address}")
    return True
