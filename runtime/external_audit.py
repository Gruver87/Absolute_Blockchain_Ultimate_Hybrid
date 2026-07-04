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
