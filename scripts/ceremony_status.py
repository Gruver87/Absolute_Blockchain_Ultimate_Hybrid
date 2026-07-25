#!/usr/bin/env python3
"""Honest ceremony readiness status — never invents GENESIS_CEREMONY_HASH.

Reports pin / dir / deploy-meta state for operators and check_all.
Default exit 0 (informational). Use --require-pin to fail closed when unset.

Honesty: status green ≠ public mainnet / completed external audit.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_preflight():
    path = ROOT / "scripts" / "ceremony_preflight.py"
    spec = importlib.util.spec_from_file_location("ceremony_preflight", path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def ceremony_status(
    *,
    ceremony_dir: str = "data/ceremony_keys",
    config_path: str = "node.prod.mainnet-v1.example.json",
) -> dict:
    """Build an honest readiness snapshot (no side effects, no fake pin)."""
    pinned = (os.environ.get("GENESIS_CEREMONY_HASH") or "").strip()
    cdir = Path(ceremony_dir)
    if not cdir.is_absolute():
        cdir = ROOT / cdir

    out: dict = {
        "ceremony_dir": str(cdir),
        "dir_exists": cdir.is_dir(),
        "env_pin_set": bool(pinned),
        "env_pin_prefix": (pinned[:16] + "…") if len(pinned) > 16 else pinned,
        "pin_matches_manifest": None,
        "ready": False,
        "org_blockers": [
            "GENESIS_CEREMONY_HASH must be set by operator after keygen",
            "external audit remains an org gate",
        ],
        "errors": [],
        "warnings": [],
        "honesty": [
            "status is not public mainnet",
            "this tool never invents or commits a ceremony hash",
        ],
    }

    if not cdir.is_dir():
        out["warnings"].append(
            f"ceremony_dir missing ({cdir}) — run genesis_ceremony_keygen.py"
        )
        out["next_steps"] = [
            "python scripts/genesis_ceremony_keygen.py --out-dir data/ceremony_keys",
            ".\\scripts\\pin_ceremony_hash.ps1 -CeremonyDir data/ceremony_keys",
        ]
        return out

    mod = _load_preflight()
    errors, warnings, meta = mod.run_ceremony_preflight(
        str(cdir),
        config_path=config_path,
        require_env_pin=False,
    )
    out["errors"] = list(errors)
    out["warnings"] = list(warnings)
    out["ceremony_hash"] = meta.get("ceremony_hash") or ""
    out["manifest_ready"] = bool(meta.get("ready"))
    if pinned and out["ceremony_hash"]:
        out["pin_matches_manifest"] = pinned == out["ceremony_hash"]
        if not out["pin_matches_manifest"]:
            out["errors"].append("GENESIS_CEREMONY_HASH mismatch vs ceremony manifest")
    elif not pinned:
        out["warnings"].append(
            "GENESIS_CEREMONY_HASH unset — pin after keygen (scripts/pin_ceremony_hash.ps1)"
        )

    out["ready"] = bool(
        out["manifest_ready"]
        and out["env_pin_set"]
        and out["pin_matches_manifest"] is True
        and not out["errors"]
    )
    out["next_steps"] = []
    if not out["env_pin_set"]:
        out["next_steps"].append(
            ".\\scripts\\pin_ceremony_hash.ps1 -CeremonyDir " + str(cdir)
        )
    if out["errors"]:
        out["next_steps"].append(
            "python scripts/ceremony_preflight.py --ceremony-dir "
            + str(cdir)
            + " --require-env-pin"
        )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ceremony-dir", default="data/ceremony_keys")
    ap.add_argument("--config", default="node.prod.mainnet-v1.example.json")
    ap.add_argument(
        "--require-pin",
        action="store_true",
        help="Exit non-zero if GENESIS_CEREMONY_HASH unset or mismatched",
    )
    ap.add_argument(
        "--json",
        default="",
        help="Optional path to write JSON report",
    )
    args = ap.parse_args()
    status = ceremony_status(
        ceremony_dir=args.ceremony_dir,
        config_path=args.config,
    )
    report_path = args.json.strip() or str(ROOT / "data" / "ceremony_status.json")
    Path(report_path).parent.mkdir(parents=True, exist_ok=True)
    Path(report_path).write_text(
        json.dumps(status, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"ceremony_dir={status['ceremony_dir']}")
    print(f"dir_exists={status['dir_exists']}")
    print(f"env_pin_set={status['env_pin_set']}")
    print(f"pin_matches_manifest={status['pin_matches_manifest']}")
    print(f"ready={status['ready']}")
    for w in status.get("warnings") or []:
        print(f"warn: {w}")
    for e in status.get("errors") or []:
        print(f"error: {e}")
    print(f"report: {report_path}")
    print("honesty: status green != public mainnet / audit complete")

    if args.require_pin:
        if not status.get("env_pin_set"):
            return 2
        if status.get("pin_matches_manifest") is False:
            return 3
        if status.get("errors"):
            return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
