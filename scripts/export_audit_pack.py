#!/usr/bin/env python3
"""Export a soak-safe static audit pack for third-party review.

Never touches Docker prod mesh or soak monitors — read-only collection + static gates.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _git(*args: str) -> str:
    try:
        out = subprocess.check_output(
            ["git", *args],
            cwd=ROOT,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return ""


def _run_python(script_rel: str, extra: list[str] | None = None) -> tuple[int, str]:
    cmd = [sys.executable, str(ROOT / script_rel), *(extra or [])]
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=600,
        )
        text = (proc.stdout or "") + (proc.stderr or "")
        return int(proc.returncode), text[-8000:]
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except OSError as exc:
        return 1, str(exc)


def _copy_if_exists(src: Path, dest: Path) -> bool:
    if not src.is_file():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dest)
    return True


def _state_root_encoding_snapshot() -> dict:
    from runtime.state_root_encoding import state_root_encoding_status

    return state_root_encoding_status()


def export_audit_pack(
    out_dir: Path | None = None,
    zip_pack: bool = True,
    sync_automated: bool = True,
) -> dict:
    """Build audit pack directory + optional zip. Returns manifest dict."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    pack_dir = out_dir or (ROOT / "logs" / f"audit_pack_{stamp[:8]}")
    pack_dir.mkdir(parents=True, exist_ok=True)
    gates_dir = pack_dir / "gates"
    docs_dir = pack_dir / "docs"
    soak_dir = pack_dir / "soak"
    gates_dir.mkdir(exist_ok=True)
    docs_dir.mkdir(exist_ok=True)
    soak_dir.mkdir(exist_ok=True)

    git_describe = _git("describe", "--tags", "--always")
    git_head = _git("rev-parse", "HEAD")
    git_branch = _git("rev-parse", "--abbrev-ref", "HEAD")

    gate_results: dict[str, dict] = {}

    # Sync automated audit checklist items (writes data/external_audit_status.json)
    if sync_automated:
        rc, text = _run_python(
            "scripts/external_audit_tracker.py",
            ["--sync-automated", "--json"],
        )
        (gates_dir / "external_audit_sync.txt").write_text(text, encoding="utf-8")
        gate_results["external_audit_sync"] = {"exit_code": rc}

    rc, text = _run_python("scripts/external_audit_tracker.py", ["--list", "--json"])
    (gates_dir / "external_audit_list.json").write_text(
        text if text.strip().startswith("{") else json.dumps({"raw": text}),
        encoding="utf-8",
    )
    gate_results["external_audit_list"] = {"exit_code": rc}

    rc, text = _run_python("scripts/industrial_gate.py", ["--json"])
    gate_results["industrial_gate"] = {"exit_code": rc, "tail": text[-500:]}
    _copy_if_exists(ROOT / "data" / "industrial_gate.json", gates_dir / "industrial_gate.json")

    rc, text = _run_python("scripts/prod_gate.py")
    (gates_dir / "prod_gate.txt").write_text(text, encoding="utf-8")
    gate_results["prod_gate"] = {"exit_code": rc}

    rc, text = _run_python("scripts/bridge_off_audit_gate.py")
    (gates_dir / "bridge_off_audit_gate.txt").write_text(text, encoding="utf-8")
    gate_results["bridge_off_audit_gate"] = {"exit_code": rc}
    _copy_if_exists(
        ROOT / "data" / "bridge_off_audit_gate.json",
        gates_dir / "bridge_off_audit_gate.json",
    )

    encoding = _state_root_encoding_snapshot()
    (gates_dir / "state_root_encoding.json").write_text(
        json.dumps(encoding, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Docs
    for name in (
        "EVIDENCE_MATRIX.md",
        "MAINNET_GAP_ANALYSIS.md",
        "INCIDENT_RESPONSE.md",
        "PUBLIC_TESTNET.md",
        "MAINNET_CUTOVER.md",
        "STATE_ROOT_ENCODING_MIGRATION.md",
    ):
        _copy_if_exists(ROOT / "docs" / name, docs_dir / name)

    # Soak artifacts (if present — may be in-progress)
    for name in (
        "soak_report.json",
        "soak_report_48h.json",
        "soak_active.json",
        "soak_preflight.json",
        "prod_mesh_probe.json",
    ):
        _copy_if_exists(ROOT / "logs" / name, soak_dir / name)

    # Release notes + changelog head
    notes = sorted(ROOT.glob("RELEASE_NOTES_v*.md"), reverse=True)
    if notes:
        _copy_if_exists(notes[0], pack_dir / notes[0].name)
    changelog = ROOT / "CHANGELOG.md"
    if changelog.is_file():
        lines = changelog.read_text(encoding="utf-8").splitlines()
        (pack_dir / "CHANGELOG_excerpt.md").write_text(
            "\n".join(lines[:120]) + "\n",
            encoding="utf-8",
        )

    _copy_if_exists(
        ROOT / "data" / "external_audit_status.json",
        gates_dir / "external_audit_status.json",
    )

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pack_dir": str(pack_dir),
        "git": {
            "describe": git_describe or "unknown",
            "head": git_head or "unknown",
            "branch": git_branch or "unknown",
        },
        "constraint": "soak-safe: no docker mesh restart; static gates only",
        "gates": gate_results,
        "state_root_encoding": encoding,
        "honest_gaps": [
            "48h soak not claimed PASS until soak_report_48h.json passed=true",
            "External pen-test and third-party L1 audit remain human organizational items",
            "Public mainnet not launched",
        ],
    }
    (pack_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    zip_path = None
    if zip_pack:
        zip_path = pack_dir.with_suffix(".zip")
        if zip_path.exists():
            zip_path.unlink()
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in pack_dir.rglob("*"):
                if path.is_file():
                    zf.write(path, arcname=str(path.relative_to(pack_dir.parent)))
        manifest["zip_path"] = str(zip_path)
        (pack_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Export soak-safe static audit pack")
    parser.add_argument(
        "--out-dir",
        default="",
        help="Output directory (default: logs/audit_pack_YYYYMMDD)",
    )
    parser.add_argument("--no-zip", action="store_true", help="Skip zip archive")
    parser.add_argument(
        "--no-sync-automated",
        action="store_true",
        help="Do not run external_audit_tracker --sync-automated",
    )
    parser.add_argument("--json", action="store_true", help="Print manifest JSON only")
    args = parser.parse_args()
    out = Path(args.out_dir) if args.out_dir else None
    manifest = export_audit_pack(
        out_dir=out,
        zip_pack=not args.no_zip,
        sync_automated=not args.no_sync_automated,
    )
    if args.json:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
    else:
        print("=" * 60)
        print("AUDIT PACK (soak-safe static export)")
        print("=" * 60)
        print(f"Pack: {manifest['pack_dir']}")
        if manifest.get("zip_path"):
            print(f"Zip:  {manifest['zip_path']}")
        print(f"Git:  {manifest['git']['describe']} ({manifest['git']['head'][:12]})")
        for name, info in manifest["gates"].items():
            print(f"  gate {name}: exit={info.get('exit_code')}")
        print("Honest gaps:")
        for g in manifest["honest_gaps"]:
            print(f"  - {g}")
        print("=" * 60)
    # Pack export itself succeeds even if organizational audit incomplete
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
