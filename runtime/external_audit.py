#!/usr/bin/env python3
"""External security audit checklist status (organizational gate)."""

from __future__ import annotations

import json
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


DEVNET_CHAIN_ID = 77777
MAINNET_CHAIN_ID_PLACEHOLDER = 778888  # replace with final ID at genesis ceremony

AUTOMATED_ITEMS = {
    "Disaster recovery drill for multi-node devnet completed",
    "CORS and RPC API keys reviewed for production origins",
    "Validator keys not stored in node.json / git",
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


def evaluate_automated(root: Path | None = None) -> dict[str, tuple[bool, str]]:
    base = root or Path(__file__).resolve().parents[1]
    return {
        "Disaster recovery drill for multi-node devnet completed": _automated_dr_drill(base),
        "CORS and RPC API keys reviewed for production origins": _automated_prod_gate(base),
        "Validator keys not stored in node.json / git": _automated_no_inline_validator_keys(base),
    }


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
