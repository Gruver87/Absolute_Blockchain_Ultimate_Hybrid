#!/usr/bin/env python3
"""Append live operational evidence steps to data/evidence_run.json (gitignored)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict:
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass
    return {
        "run_id": f"evidence-{datetime.now(timezone.utc).strftime('%Y%m%d')}",
        "steps": [],
        "gaps_remaining": [
            "24-48h soak completion",
            "external security audit",
            "production genesis ceremony + secret rotation",
            "bridge mainnet cutover decision",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Record live evidence step")
    parser.add_argument("--name", required=True, help="Step name (e.g. prod_evm_smoke)")
    parser.add_argument("--result", required=True, choices=("PASS", "FAIL", "WARN", "IN_PROGRESS"))
    parser.add_argument("--command", default="", help="Command that was run")
    parser.add_argument("--artifact", default="", help="Log or report path")
    parser.add_argument("--notes", default="", help="Free-form notes")
    parser.add_argument(
        "--out",
        default=str(ROOT / "data" / "evidence_run.json"),
        help="Output JSON (default: data/evidence_run.json)",
    )
    parser.add_argument("--git-tag", default="", help="Optional git tag / release")
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc = _load(out)
    if args.git_tag:
        doc["git_tag"] = args.git_tag
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    step = {
        "name": args.name,
        "result": args.result,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    if args.command:
        step["command"] = args.command
    if args.artifact:
        step["artifact"] = args.artifact
    if args.notes:
        step["notes"] = args.notes

    steps = doc.setdefault("steps", [])
    replaced = False
    for i, row in enumerate(steps):
        if isinstance(row, dict) and row.get("name") == args.name:
            steps[i] = step
            replaced = True
            break
    if not replaced:
        steps.append(step)

    out.write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"OK: evidence step '{args.name}' -> {args.result} ({out})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
