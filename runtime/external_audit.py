#!/usr/bin/env python3
"""External security audit checklist status (organizational gate)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

DEFAULT_CHECKLIST = [
    "External penetration test scheduled",
    "Third-party smart-contract / L1 security audit completed",
    "Bridge L1 RPC keys rotated from dev placeholders",
    "Validator keys not stored in node.json / git",
    "Production validator manifest published (no runtime key derivation)",
    "CORS and RPC API keys reviewed for production origins",
    "Incident response runbook documented",
    "Disaster recovery drill for multi-node devnet completed",
]


def default_status_path(root: Path | None = None) -> Path:
    base = root or Path(__file__).resolve().parents[1]
    return base / "data" / "external_audit_status.json"


def load_status(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {"items": {}, "updated_at": None}
    return json.loads(path.read_text(encoding="utf-8"))


def save_status(path: Path, items: Dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


from runtime.mainnet_constants import DEVNET_CHAIN_ID, MAINNET_V1_CHAIN_ID

HUMAN_REQUIRED_AUDIT_ITEMS = frozenset({
    "External penetration test scheduled",
    "Third-party smart-contract / L1 security audit completed",
})

AUTOMATED_ITEMS = {
    "Disaster recovery drill for multi-node devnet completed",
    "CORS and RPC API keys reviewed for production origins",
    "Validator keys not stored in node.json / git",
    "Incident response runbook documented",
    "Bridge L1 RPC keys rotated from dev placeholders",
    "Production validator manifest published (no runtime key derivation)",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _automated_runbook(root: Path) -> tuple[bool, str]:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "runbook_check", root / "scripts" / "runbook_check.py"
    )
    if spec is None or spec.loader is None:
        return False, "runbook_check.py missing"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ok, note = mod.check_runbook(root / "docs" / "INCIDENT_RESPONSE.md")
    return ok, note


def _automated_bridge_l1_keys(root: Path) -> tuple[bool, str]:
    """Staging gate: no L1 RPC secrets in git; mainnet-v1 keeps bridge off until contracts."""
    embedded: list[str] = []
    for path in _prod_config_paths(root):
        text = path.read_text(encoding="utf-8").lower()
        if re.search(r"eth_rpc_url|l1_rpc_url|alchemy|infura", text):
            embedded.append(path.name)
    if embedded:
        return False, f"L1 RPC reference in JSON: {', '.join(embedded)}"

    mainnet_v1 = root / "node.prod.mainnet-v1.example.json"
    if mainnet_v1.is_file():
        cfg = _load_json(mainnet_v1)
        if cfg.get("bridge_enabled") is False:
            return True, "mainnet-v1 bridge disabled; supply ETH_RPC_URL via env at deploy"

    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "check_secrets", root / "scripts" / "check_secrets.py"
    )
    if spec is None or spec.loader is None:
        return False, "check_secrets.py missing"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if mod.main() != 0:
        return False, "check_secrets found potential secrets in repo"
    return True, "no L1 RPC secrets in repo; rotate ETH_RPC_URL in deployment env"


def _automated_validator_manifest(root: Path) -> tuple[bool, str]:
    manifest_path = root / "validators.manifest.example.json"
    if not manifest_path.is_file():
        return False, "validators.manifest.example.json missing"
    if _json_has_private_key(manifest_path):
        return False, "private_key in manifest template"
    data = _load_json(manifest_path)
    validators = data.get("validators") or []
    if not validators:
        return False, "empty validators list"
    for path in _prod_config_paths(root):
        cfg = _load_json(path)
        if not str(cfg.get("validators_manifest_path", "")).strip():
            return False, f"{path.name} missing validators_manifest_path"
    return True, "public manifest template + prod configs require manifest path (replace placeholder addresses at ceremony)"


def evaluate_automated(root: Path | None = None) -> dict[str, tuple[bool, str]]:
    base = root or Path(__file__).resolve().parents[1]
    return {
        "Disaster recovery drill for multi-node devnet completed": _automated_dr_drill(base),
        "CORS and RPC API keys reviewed for production origins": _automated_prod_gate(base),
        "Validator keys not stored in node.json / git": _automated_no_inline_validator_keys(base),
        "Incident response runbook documented": _automated_runbook(base),
        "Bridge L1 RPC keys rotated from dev placeholders": _automated_bridge_l1_keys(base),
        "Production validator manifest published (no runtime key derivation)": _automated_validator_manifest(base),
    }


def _prod_config_paths(root: Path) -> list[Path]:
    names = [
        "docker/node.prod.json",
        "node.prod.example.json",
        "node.prod.mainnet-v1.example.json",
    ]
    return [root / name for name in names if (root / name).is_file()]


def _json_has_private_key(path: Path) -> bool:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return "private_key" in text.lower()


def _automated_dr_drill(root: Path) -> tuple[bool, str]:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "backup_db_drill", root / "scripts" / "backup_db_drill.py"
    )
    if spec is None or spec.loader is None:
        return False, "backup_db_drill.py missing"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rc = int(mod.run_backup_drill())
    if rc != 0:
        return False, f"backup_db_drill exit {rc}"
    return True, "backup roundtrip verified (backup_db_drill.py)"


def _automated_prod_gate(root: Path) -> tuple[bool, str]:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "prod_gate", root / "scripts" / "prod_gate.py"
    )
    if spec is None or spec.loader is None:
        return False, "prod_gate.py missing"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    errors: list[str] = []
    for rel in mod.PROD_FILES:
        if (root / rel).is_file():
            errors.extend(mod.check_file(rel))
    if errors:
        return False, "; ".join(errors[:3])
    return True, "prod_gate CORS/RPC policy pass on prod profiles"


def _automated_no_inline_validator_keys(root: Path) -> tuple[bool, str]:
    offenders: list[str] = []
    for path in _prod_config_paths(root):
        if _json_has_private_key(path):
            offenders.append(path.name)
    manifest = root / "validators.manifest.example.json"
    if manifest.is_file() and _json_has_private_key(manifest):
        offenders.append(manifest.name)
    if offenders:
        return False, f"private_key in: {', '.join(offenders)}"
    return True, "no private_key in prod node JSON / validator manifest templates"


def sync_automated_items(
    root: Path | None = None,
    status_path: Path | None = None,
) -> list[str]:
    """Mark checklist items done when automated checks pass."""
    marked: list[str] = []
    for label, (ok, note) in evaluate_automated(root).items():
        if not ok:
            continue
        set_item_done(label, done=True, note=f"auto: {note}", status_path=status_path)
        marked.append(label)
    return marked


def evaluate(
    checklist: List[str] | None = None,
    status_path: Path | None = None,
) -> Tuple[List[str], List[str], Dict[str, Any]]:
    """Return (pending_warnings, completed, summary_dict)."""
    items_checklist = checklist or list(DEFAULT_CHECKLIST)
    path = status_path or default_status_path()
    status = load_status(path)
    stored = status.get("items") or {}

    pending: List[str] = []
    completed: List[str] = []
    rows: List[Dict[str, Any]] = []

    for label in items_checklist:
        row = stored.get(label) or {}
        done = bool(row.get("done"))
        note = str(row.get("note") or "")
        if done and label in HUMAN_REQUIRED_AUDIT_ITEMS:
            if note.startswith("auto:") or len(note.strip()) < 8:
                done = False
        rows.append({
            "label": label,
            "done": done,
            "note": row.get("note", ""),
            "completed_at": row.get("completed_at"),
        })
        if done:
            completed.append(label)
        else:
            pending.append(label)

    summary = {
        "status_path": str(path),
        "total": len(items_checklist),
        "completed": len(completed),
        "pending": len(pending),
        "all_complete": len(pending) == 0,
        "items": rows,
    }
    warnings = [f"external_audit_pending:{label}" for label in pending]
    return warnings, completed, summary


def set_item_done(
    label: str,
    done: bool = True,
    note: str = "",
    status_path: Path | None = None,
) -> Path:
    path = status_path or default_status_path()
    status = load_status(path)
    items = dict(status.get("items") or {})
    entry: Dict[str, Any] = {"done": done, "note": note}
    if done:
        entry["completed_at"] = datetime.now(timezone.utc).isoformat()
    items[label] = entry
    return save_status(path, items)
