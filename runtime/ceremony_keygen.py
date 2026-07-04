#!/usr/bin/env python3
"""Offline validator key generation and manifest binding for mainnet ceremony."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from runtime.validator_loader import load_manifest, manifest_entries


def wallet_matches_manifest_row(wallet_data: Dict[str, Any], row: Dict[str, Any]) -> Tuple[bool, str]:
    expected_addr = str(row.get("address", "") or "").strip().lower()
    wallet_addr = str(wallet_data.get("address", "") or "").strip().lower()
    if not expected_addr:
        return False, "manifest_row_missing_address"
    if wallet_addr != expected_addr:
        return False, f"address_mismatch:wallet={wallet_addr} manifest={expected_addr}"
    manifest_pk = str(row.get("public_key", "") or "").strip().lower().removeprefix("0x")
    wallet_pk = str(wallet_data.get("public_key", "") or "").strip().lower().removeprefix("0x")
    if manifest_pk and wallet_pk and manifest_pk != wallet_pk:
        return False, "public_key_mismatch"
    return True, ""


def verify_wallet_file(wallet_path: str, manifest_path: str, index: int) -> Tuple[bool, str]:
    wallet_file = Path(wallet_path)
    if not wallet_file.is_file():
        return False, f"wallet_missing:{wallet_path}"
    manifest = load_manifest(manifest_path)
    row = _row_by_index(manifest, index)
    if row is None:
        return False, f"manifest_index_missing:{index}"
    wallet_data = json.loads(wallet_file.read_text(encoding="utf-8"))
    ok, reason = wallet_matches_manifest_row(wallet_data, row)
    return ok, reason


def _row_by_index(manifest: Dict[str, Any], index: int) -> Dict[str, Any] | None:
    for row in manifest_entries(manifest):
        if int(row.get("index", 0) or 0) == int(index):
            return row
    return None


def validate_manifest_public_keys(
    manifest: Dict[str, Any],
    *,
    require_mining_keys: bool = True,
) -> List[str]:
    errors: List[str] = []
    for row in manifest_entries(manifest):
        addr = str(row.get("address", "") or "").strip()
        mines = bool(row.get("mines", True))
        pk = str(row.get("public_key", "") or "").strip()
        if require_mining_keys and mines and not pk:
            errors.append(f"mining_validator_missing_public_key:{addr or row.get('node_id', '')}")
    return errors


def generate_validator_set(
    template_manifest_path: str,
    out_dir: str,
    *,
    chain_id: int | None = None,
) -> Tuple[Dict[str, Any], List[str], Path]:
    """Generate ECDSA wallets and a public manifest with bound public keys."""
    from crypto.wallet import Wallet

    template = load_manifest(template_manifest_path)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    wallets_dir = out / "wallets"
    wallets_dir.mkdir(parents=True, exist_ok=True)

    validators_out: List[Dict[str, Any]] = []
    errors: List[str] = []
    for row in manifest_entries(template):
        index = int(row.get("index", 0) or 0)
        node_id = str(row.get("node_id", "") or f"validator-{index}")
        wallet = Wallet.create_new()
        wallet_path = wallets_dir / f"validator-{index}.wallet.json"
        wallet.export(str(wallet_path))
        validators_out.append(
            {
                "index": index,
                "node_id": node_id,
                "address": wallet.address,
                "public_key": wallet.public_key,
                "mines": bool(row.get("mines", True)),
                "stake": float(row.get("stake", 0) or 0),
                "shard_id": row.get("shard_id", 0),
            }
        )

    manifest_out = {
        "version": int(template.get("version", 1) or 1),
        "description": (
            "Generated mainnet validator manifest — private keys in wallets/ only; "
            "never commit this directory."
        ),
        "validators": validators_out,
    }
    if chain_id is not None:
        manifest_out["chain_id"] = int(chain_id)
    manifest_path = out / "validators.manifest.json"
    manifest_path.write_text(json.dumps(manifest_out, indent=2, ensure_ascii=False), encoding="utf-8")

    readme = out / "CEREMONY_README.txt"
    readme.write_text(
        "\n".join(
            [
                "Mainnet ceremony key material (LOCAL ONLY — do not commit).",
                "",
                "Files:",
                "  validators.manifest.json  — public validator set (deploy to all nodes)",
                "  wallets/validator-N.wallet.json — one signing key per validator",
                "",
                "Next steps:",
                "  1. Copy validators.manifest.json to prod config validators_manifest_path",
                "  2. Copy matching wallet to each node's data/wallet.json (or use HSM)",
                "  3. python scripts/genesis_ceremony.py --strict-mainnet --manifest validators.manifest.json",
                "  4. Set GENESIS_CEREMONY_HASH from ceremony_hash output",
                "  5. python scripts/mainnet_launch_checklist.py --strict-keys",
            ]
        ),
        encoding="utf-8",
    )
    return manifest_out, errors, manifest_path


def verify_ceremony_directory(ceremony_dir: str) -> Tuple[List[str], List[str]]:
    """Verify wallets/ align with validators.manifest.json in a ceremony output dir."""
    base = Path(ceremony_dir)
    manifest_path = base / "validators.manifest.json"
    if not manifest_path.is_file():
        return [f"ceremony_manifest_missing:{manifest_path}"], []
    manifest = load_manifest(str(manifest_path))
    errors: List[str] = []
    warnings: List[str] = []
    errors.extend(validate_manifest_public_keys(manifest, require_mining_keys=True))
    for row in manifest_entries(manifest):
        index = int(row.get("index", 0) or 0)
        wallet_path = base / "wallets" / f"validator-{index}.wallet.json"
        if not wallet_path.is_file():
            errors.append(f"wallet_missing:validator-{index}")
            continue
        wallet_data = json.loads(wallet_path.read_text(encoding="utf-8"))
        ok, reason = wallet_matches_manifest_row(wallet_data, row)
        if not ok:
            errors.append(f"validator-{index}:{reason}")
    return errors, warnings
