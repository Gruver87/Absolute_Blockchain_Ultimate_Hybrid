#!/usr/bin/env python3
"""Track external security audit checklist before public mainnet."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runtime.external_audit import (  # noqa: E402
    DEFAULT_CHECKLIST,
    default_status_path,
    evaluate,
    evaluate_automated,
    set_item_done,
    sync_automated_items,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="External security audit checklist tracker")
    parser.add_argument("--list", action="store_true", help="Print checklist with status")
    parser.add_argument("--set", metavar="ITEM", help="Mark checklist item done (exact label)")
    parser.add_argument("--unset", metavar="ITEM", help="Mark checklist item pending")
    parser.add_argument("--note", default="", help="Optional note for --set")
    parser.add_argument(
        "--evidence-url",
        default="",
        help="Optional evidence URL for --set (engagement letter, report link)",
    )
    parser.add_argument(
        "--evidence-note",
        default="",
        help="Optional evidence note for --set",
    )
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--status-file", default="", help="Override status JSON path")
    parser.add_argument(
        "--sync-automated",
        action="store_true",
        help="Mark items done when automated checks pass (DR drill, prod_gate, key scan)",
    )
    parser.add_argument(
        "--show-automated",
        action="store_true",
        help="Dry-run: show automated check pass/fail without writing status",
    )
    args = parser.parse_args()

    status_path = Path(args.status_file) if args.status_file else default_status_path(ROOT)

    if args.show_automated:
        results = evaluate_automated(ROOT)
        rows = [
            {"label": label, "ok": ok, "note": note}
            for label, (ok, note) in results.items()
        ]
        if args.json:
            print(json.dumps({"items": rows}, indent=2, ensure_ascii=False))
        else:
            print("=" * 60)
            print("AUTOMATED AUDIT CHECKS (dry-run, no write)")
            print("=" * 60)
            for row in rows:
                mark = "PASS" if row["ok"] else "FAIL"
                print(f"  [{mark}] {row['label']}")
                print(f"         {row['note']}")
            print("=" * 60)
        return 0

    if args.sync_automated:
        marked = sync_automated_items(ROOT, status_path)
        if args.json:
            print(json.dumps({"ok": True, "marked": marked, "status_file": str(status_path)}))
        else:
            if marked:
                print("Automated checklist updates:")
                for label in marked:
                    print(f"  [x] {label}")
            else:
                print("No automated items passed (nothing updated).")
            print(f"Status: {status_path}")
        return 0

    if args.set:
        if args.set not in DEFAULT_CHECKLIST:
            print(f"Unknown item: {args.set}", file=sys.stderr)
            return 2
        out = set_item_done(
            args.set,
            done=True,
            note=args.note,
            status_path=status_path,
            evidence_url=args.evidence_url,
            evidence_note=args.evidence_note,
        )
        if args.json:
            print(json.dumps({"ok": True, "status_file": str(out)}))
        else:
            print(f"Marked done: {args.set}")
            print(f"Status: {out}")
        return 0

    if args.unset:
        if args.unset not in DEFAULT_CHECKLIST:
            print(f"Unknown item: {args.unset}", file=sys.stderr)
            return 2
        out = set_item_done(args.unset, done=False, status_path=status_path)
        if args.json:
            print(json.dumps({"ok": True, "status_file": str(out)}))
        else:
            print(f"Marked pending: {args.unset}")
            print(f"Status: {out}")
        return 0

    warnings, completed, summary = evaluate(DEFAULT_CHECKLIST, status_path)
    if args.json:
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    print("=" * 60)
    print("EXTERNAL SECURITY AUDIT CHECKLIST")
    print("=" * 60)
    for row in summary["items"]:
        mark = "[x]" if row["done"] else "[ ]"
        print(f"  {mark} {row['label']}")
        if row.get("note"):
            print(f"       note: {row['note']}")
        if row.get("evidence_url"):
            print(f"       evidence_url: {row['evidence_url']}")
        if row.get("evidence_note"):
            print(f"       evidence_note: {row['evidence_note']}")
    print(f"\nCompleted: {summary['completed']}/{summary['total']}")
    print(f"Status file: {summary['status_path']}")
    if warnings:
        print("\nPending items block public mainnet cutover until completed.")
    else:
        print("\nAll organizational checklist items marked complete.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
