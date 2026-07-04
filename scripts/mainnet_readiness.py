#!/usr/bin/env python3
"""Mainnet readiness gate — prod stack + pre-mainnet audit in one report."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load_module(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def run_gate(
    live: bool = False,
    base_url: str = "http://127.0.0.1:8080",
    strict_audit: bool = True,
    prod_smoke_spawn: bool = False,
    ceremony_dir: str = "",
) -> Tuple[List[str], List[str], dict]:
    errors: List[str] = []
    warnings: List[str] = []
    sections: dict = {}

    pre = _load_module("pre_mainnet_audit", "scripts/pre_mainnet_audit.py")
    pre_errors, pre_warnings, checklist = pre.run_checks()
    errors.extend(pre_errors)
    warnings.extend(pre_warnings)
    sections["pre_mainnet"] = {"errors": pre_errors, "warnings": pre_warnings}

    manifest_path = str(ROOT / "validators.manifest.mainnet-v1.example.json")
    config_path = str(ROOT / "node.prod.mainnet-v1.example.json")
    saved_manifest_env = os.environ.get("VALIDATORS_MANIFEST_PATH")
    saved_ceremony_hash = os.environ.get("GENESIS_CEREMONY_HASH")
    deploy_meta_path = ROOT / "data" / "ceremony_deploy.json"
    deploy_meta_loaded = False
    if ceremony_dir and deploy_meta_path.is_file():
        try:
            deploy_meta = json.loads(deploy_meta_path.read_text(encoding="utf-8"))
            if deploy_meta.get("ceremony_hash"):
                os.environ["GENESIS_CEREMONY_HASH"] = str(deploy_meta["ceremony_hash"])
            os.environ["VALIDATORS_MANIFEST_PATH"] = "data/validators.manifest.json"
            manifest_path = str(ROOT / "data" / "validators.manifest.json")
            deploy_meta_loaded = True
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    if ceremony_dir:
        cdir = Path(ceremony_dir)
        if not cdir.is_absolute():
            cdir = ROOT / cdir
        local_manifest = cdir / "validators.manifest.json"
        if local_manifest.is_file():
            if not deploy_meta_loaded:
                manifest_path = str(local_manifest)
                os.environ["VALIDATORS_MANIFEST_PATH"] = manifest_path
            from runtime.ceremony_keygen import verify_ceremony_directory

            c_errors, c_warnings = verify_ceremony_directory(str(cdir))
            errors.extend([f"ceremony_dir:{e}" for e in c_errors])
            warnings.extend(c_warnings)
        else:
            errors.append(f"ceremony_dir:manifest_missing:{local_manifest}")

    prod = _load_module("verify_prod_stack", "scripts/verify_prod_stack.py")
    prod_errors = []
    prod_errors.extend(prod.check_prod_gate())
    prod_errors.extend(prod.check_config_validate())
    prod_errors.extend(prod.check_mainnet_v1_config())
    prod_errors.extend(prod.check_docker_prod_compose())
    if live:
        prod_errors.extend(prod.check_live_smoke(base_url.rstrip("/")))
    if prod_smoke_spawn:
        prod_errors.extend(prod.check_prod_smoke_spawn())
    errors.extend(prod_errors)
    sections["prod_stack"] = {
        "errors": prod_errors,
        "live": live,
        "prod_smoke_spawn": prod_smoke_spawn,
    }

    pinned_ceremony_hash = (os.environ.get("GENESIS_CEREMONY_HASH", "") or "").strip()
    try:
        from runtime.genesis_ceremony import build_from_paths

        artifact, ceremony_errors = build_from_paths(
            config_path,
            manifest_path,
            strict_addresses=bool(os.environ.get("GENESIS_STRICT_MAINNET", "").lower() in ("1", "true", "yes")),
        )
        sections["genesis_ceremony"] = {
            "ready": artifact.get("ready"),
            "mainnet_addresses_ready": artifact.get("mainnet_addresses_ready"),
            "ceremony_hash": artifact.get("ceremony_hash"),
            "errors": ceremony_errors,
        }
        if ceremony_errors:
            errors.extend([f"genesis_ceremony:{e}" for e in ceremony_errors])
        if not artifact.get("mainnet_addresses_ready", True):
            warnings.append(
                "genesis_ceremony:placeholder_validator_addresses_in_manifest"
            )
        if ceremony_dir:
            if pinned_ceremony_hash and artifact.get("ceremony_hash") != pinned_ceremony_hash:
                errors.append("genesis_ceremony_hash_mismatch:env_vs_manifest")
            elif not pinned_ceremony_hash:
                warnings.append(
                    "genesis_ceremony: set GENESIS_CEREMONY_HASH after keygen "
                    "(scripts/pin_ceremony_hash.ps1)"
                )
        elif pinned_ceremony_hash:
            warnings.append(
                "genesis_ceremony: GENESIS_CEREMONY_HASH set without --ceremony-dir "
                "(pin verified only with generated manifest path)"
            )
        legacy, legacy_errors = build_from_paths(
            str(ROOT / "node.prod.example.json"),
            str(ROOT / "validators.manifest.example.json"),
        )
        if not legacy.get("mainnet_addresses_ready", True):
            warnings.append(
                "genesis_ceremony:node.prod.example.json still uses placeholder manifest "
                f"(count={legacy.get('placeholder_validator_count', 0)})"
            )
    except Exception as exc:
        errors.append(f"genesis_ceremony:{exc}")
        sections["genesis_ceremony"] = {"errors": [str(exc)]}
    finally:
        if saved_manifest_env is None:
            os.environ.pop("VALIDATORS_MANIFEST_PATH", None)
        else:
            os.environ["VALIDATORS_MANIFEST_PATH"] = saved_manifest_env
        if saved_ceremony_hash is None:
            os.environ.pop("GENESIS_CEREMONY_HASH", None)
        else:
            os.environ["GENESIS_CEREMONY_HASH"] = saved_ceremony_hash

    try:
        from runtime.external_audit import evaluate
        audit_warnings, _, audit_summary = evaluate()
        sections["external_audit"] = audit_summary
        if strict_audit and audit_warnings:
            errors.extend(audit_warnings)
        else:
            warnings.extend(audit_warnings)
    except Exception as exc:
        msg = f"external_audit:{exc}"
        if strict_audit:
            errors.append(msg)
        else:
            warnings.append(msg)

    return errors, warnings, {
        "external_checklist": checklist,
        "sections": sections,
    }


def write_report(errors: List[str], warnings: List[str], meta: dict) -> Path:
    out = ROOT / "data" / "mainnet_readiness.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        **meta,
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Mainnet readiness gate")
    parser.add_argument("--live", action="store_true", help="Include prod_smoke against running node")
    parser.add_argument(
        "--prod-smoke-spawn",
        action="store_true",
        help="Spawn isolated 2-node prod-profile mesh (verify_p2p_ci prod-smoke)",
    )
    parser.add_argument(
        "--ceremony-dir",
        default="",
        help="Use generated ceremony manifest from directory (e.g. data/ceremony_keys)",
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument(
        "--no-strict-audit",
        action="store_true",
        help="Do not fail on incomplete external audit checklist (dev only)",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    args = parser.parse_args()

    errors, warnings, meta = run_gate(
        live=args.live,
        base_url=args.base_url,
        strict_audit=not args.no_strict_audit,
        prod_smoke_spawn=args.prod_smoke_spawn,
        ceremony_dir=args.ceremony_dir,
    )
    report_path = write_report(errors, warnings, meta)

    if args.json:
        print(json.dumps({
            "ok": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "report": str(report_path),
        }, indent=2))
    else:
        print("=" * 60)
        print("MAINNET READINESS GATE")
        print("=" * 60)
        if errors:
            print("RESULT: FAIL")
            for err in errors:
                print(f"  - {err}")
        else:
            audit = (meta.get("sections") or {}).get("external_audit") or {}
            if audit.get("all_complete"):
                print("RESULT: OK — automated gates and external audit checklist complete")
            else:
                print("RESULT: OK — automated gates passed (external audit checklist must still be complete)")
        if warnings:
            print("\nWarnings:")
            for warn in warnings:
                print(f"  ! {warn}")
        audit = (meta.get("sections") or {}).get("external_audit") or {}
        audit_items = audit.get("items") or []
        if audit_items:
            print("\nExternal checklist:")
            for row in audit_items:
                mark = "[x]" if row.get("done") else "[ ]"
                print(f"  {mark} {row.get('label', '')}")
            completed = int(audit.get("completed", 0) or 0)
            total = int(audit.get("total", len(audit_items)) or len(audit_items))
            print(f"\nAudit: {completed}/{total} complete")
        else:
            print("\nExternal checklist:")
            for item in meta.get("external_checklist", []):
                print(f"  [ ] {item}")
        print(f"\nReport: {report_path}")
        print("=" * 60)

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
