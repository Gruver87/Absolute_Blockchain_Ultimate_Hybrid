#!/usr/bin/env python3
"""Industrial readiness gate — code-level checks without external audit blockers."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _check_native_wheel() -> tuple[list[str], list[str]]:
    """Require abs_native self-test and prod-critical exports when wheel is present."""
    errors: list[str] = []
    warnings: list[str] = []
    from crypto import native

    status = native.native_crypto_status(required=True)
    if not status.get("available"):
        errors.append(f"abs_native unavailable: {status.get('error') or 'import failed'}")
        return errors, warnings
    if not status.get("self_test"):
        errors.append("abs_native self_test failed")
    try:
        import abs_native as _abs

        for sym in (
            "RocksEngine",
            "evm_run_until_halt",
            "validate_imported_block_chain",
            "pubkey_to_eth_address",
            "rlp_encode",
            "rlp_decode_single",
        ):
            if not hasattr(_abs, sym):
                errors.append(f"abs_native missing export: {sym}")
    except ImportError as exc:
        errors.append(f"abs_native import failed: {exc}")
    return errors, warnings


def run_industrial_gate(
    *,
    prod_smoke_spawn: bool = False,
    min_soak_hours: float = 0,
    ceremony_dir: str = "",
    require_ceremony_pin: bool = False,
) -> int:
    import importlib.util

    native_errors, native_warnings = _check_native_wheel()
    soak_errors: list[str] = []
    ceremony_errors: list[str] = []
    ceremony_warnings: list[str] = []

    if ceremony_dir:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "ceremony_preflight", ROOT / "scripts" / "ceremony_preflight.py"
        )
        cp = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(cp)
        ceremony_errors, ceremony_warnings, _meta = cp.run_ceremony_preflight(
            ceremony_dir,
            require_env_pin=require_ceremony_pin,
        )

    if min_soak_hours > 0:
        soak_path = ROOT / "logs" / "soak_report.json"
        if not soak_path.is_file():
            soak_errors.append(
                f"soak_report missing: {soak_path} (need {min_soak_hours}h prod soak)"
            )
        else:
            try:
                soak = json.loads(soak_path.read_text(encoding="utf-8"))
                hrs = float(soak.get("hours_requested", 0) or 0)
                if hrs < min_soak_hours:
                    soak_errors.append(f"soak_report hours_requested={hrs} < {min_soak_hours}")
                if not soak.get("passed"):
                    soak_errors.append(f"soak_report passed=false (see {soak_path})")
            except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
                soak_errors.append(f"soak_report unreadable: {exc}")

    spec = importlib.util.spec_from_file_location(
        "mainnet_readiness", ROOT / "scripts" / "mainnet_readiness.py"
    )
    mr = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mr)

    errors, warnings, sections = mr.run_gate(
        live=False,
        strict_audit=False,
    )
    errors.extend(soak_errors)
    errors.extend(native_errors)
    errors.extend(ceremony_errors)
    warnings.extend(native_warnings)
    warnings.extend(ceremony_warnings)
    report = {
        "ok": not errors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "errors": errors,
        "warnings": warnings,
        "sections": sections,
        "native_wheel": not native_errors,
    }

    if prod_smoke_spawn:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "verify_p2p_ci", ROOT / "scripts" / "verify_p2p_ci.py"
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        rc = mod.run_prod_smoke_spawn()
        report["prod_smoke_spawn_rc"] = rc
        if rc != 0:
            errors.append(f"prod_smoke_spawn exited {rc}")

    for label, (script, attr) in (
        ("runbook", ("runbook_check.py", "main")),
        ("evm_opcode_parity", ("evm_opcode_parity_gate.py", "main")),
        ("prod_gate", ("prod_gate.py", "main")),
    ):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            label, ROOT / "scripts" / script
        )
        mod = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(mod)
        rc = int(getattr(mod, attr)())
        report[f"{label}_rc"] = rc
        if rc != 0:
            errors.append(f"{label} gate exited {rc}")

    out = ROOT / "data" / "industrial_gate.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    report["ok"] = not errors
    report["errors"] = errors
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if errors:
        print("FAIL: industrial gate")
        for err in errors:
            print(f"  - {err}")
        return 1
    print("OK: industrial gate")
    if warnings:
        print(f"  ({len(warnings)} warning(s) — see {out})")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Industrial code gate (no strict audit)")
    parser.add_argument(
        "--prod-smoke-spawn",
        action="store_true",
        help="Run isolated verify_p2p_ci --mode prod-smoke after static checks",
    )
    parser.add_argument(
        "--min-soak-hours",
        type=float,
        default=0,
        help="Require logs/soak_report.json with passed=true and hours_requested >= N (0=skip)",
    )
    parser.add_argument(
        "--ceremony-dir",
        default="",
        help="Run ceremony_preflight on this dir before static checks (empty=skip)",
    )
    parser.add_argument(
        "--require-ceremony-pin",
        action="store_true",
        help="With --ceremony-dir, require GENESIS_CEREMONY_HASH to match",
    )
    parser.add_argument("--json", action="store_true", help="Print report path only")
    args = parser.parse_args()
    rc = run_industrial_gate(
        prod_smoke_spawn=args.prod_smoke_spawn,
        min_soak_hours=args.min_soak_hours,
        ceremony_dir=args.ceremony_dir,
        require_ceremony_pin=args.require_ceremony_pin,
    )
    if args.json:
        print(str(ROOT / "data" / "industrial_gate.json"))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
