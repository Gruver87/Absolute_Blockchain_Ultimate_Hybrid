#!/usr/bin/env python3
"""Package mesh evidence artifacts (Wave B) — hashed, commit-bound, honest.

Usage:
  python scripts/package_mesh_evidence.py --out docs/evidence/runs/latest
  python scripts/package_mesh_evidence.py --probe-log path/to/probe.txt --commit HEAD

Does not invent PASS claims. Missing inputs become ``status=missing``.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional


ROOT = Path(__file__).resolve().parents[1]


def _sha256_file(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _git_commit() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True
            )
            .strip()
        )
    except Exception:
        return ""


def package(
    *,
    out_dir: Path,
    probe_log: Optional[Path] = None,
    soak_report: Optional[Path] = None,
    commit: str = "",
) -> Dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    commit = (commit or _git_commit() or "unknown").strip()
    files: Dict[str, Any] = {}
    for label, src in (
        ("probe_log", probe_log),
        ("soak_report", soak_report),
    ):
        if src is None:
            files[label] = {"status": "missing"}
            continue
        src = Path(src)
        digest = _sha256_file(src)
        if digest is None:
            files[label] = {"status": "missing", "path": str(src)}
            continue
        dest = out_dir / src.name
        dest.write_bytes(src.read_bytes())
        files[label] = {
            "status": "present",
            "path": str(dest.relative_to(ROOT)) if str(dest).startswith(str(ROOT)) else str(dest),
            "sha256": digest,
            "bytes": dest.stat().st_size,
        }

    manifest = {
        "schema": "abs.mesh_evidence.v1",
        "created_unix": int(time.time()),
        "commit": commit,
        "honesty": (
            "Artifacts listed here are operator-supplied. "
            "Absence means the claim is not independently verifiable from this package."
        ),
        "claims": {
            "chain_sync": "see probe / node heights",
            "health_ready": "requires /health/ready PASS in probe_log",
            "48h_soak": "requires soak_report with passed=true",
        },
        "files": files,
    }
    man_path = out_dir / "manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    manifest["manifest_sha256"] = _sha256_file(man_path)
    man_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    ap = argparse.ArgumentParser(description="Package versioned mesh evidence")
    ap.add_argument(
        "--out",
        default=str(ROOT / "docs" / "evidence" / "runs" / "latest"),
        help="Output directory",
    )
    ap.add_argument("--probe-log", default="", help="Optional probe log path")
    ap.add_argument("--soak-report", default="", help="Optional soak JSON path")
    ap.add_argument("--commit", default="", help="Override git commit SHA")
    args = ap.parse_args()
    man = package(
        out_dir=Path(args.out),
        probe_log=Path(args.probe_log) if args.probe_log else None,
        soak_report=Path(args.soak_report) if args.soak_report else None,
        commit=args.commit,
    )
    print(json.dumps(man, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
