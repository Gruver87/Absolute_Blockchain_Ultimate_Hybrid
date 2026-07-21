#!/usr/bin/env python3
"""Automated gate for Bridge OFF pre-enable audit checklist (EVIDENCE_MATRIX)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PROD_MESH_JSON = [
    "docker/node.prod.json",
    "docker/node.prod.mesh1.json",
    "docker/node.prod.mesh2.json",
    "docker/node.prod.mesh3.json",
    "node.prod.mainnet-v1.example.json",
    "deploy/k8s/node.prod.k8s.json",
]


def _read(path: str) -> str:
    p = ROOT / path
    return p.read_text(encoding="utf-8") if p.is_file() else ""


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    passed: list[str] = []
    compose = _read("docker-compose.prod.3node.yml")

    # 1 — prod mesh JSON bridge_enabled=false
    for rel in PROD_MESH_JSON:
        p = ROOT / rel
        if not p.is_file():
            errors.append(f"[1] missing {rel}")
            continue
        cfg = json.loads(p.read_text(encoding="utf-8"))
        if cfg.get("bridge_enabled") is not False:
            errors.append(f"[1] {rel}: bridge_enabled must be false")
        else:
            passed.append(f"[1] {rel}")

    # 2 — docker compose prod BRIDGE_ENABLED default false
    for rel in ("docker-compose.prod.3node.yml", "docker-compose.prod.yml"):
        txt = _read(rel) if rel != "docker-compose.prod.3node.yml" else compose
        if not txt:
            errors.append(f"[2] missing {rel}")
        elif "BRIDGE_ENABLED" not in txt or "false" not in txt:
            errors.append(f"[2] {rel}: BRIDGE_ENABLED=false required")
        else:
            passed.append(f"[2] {rel}")

    # 3 — k8s configmap
    cm = _read("deploy/k8s/configmap.yaml")
    if 'BRIDGE_ENABLED: "false"' not in cm:
        errors.append("[3] deploy/k8s/configmap.yaml: BRIDGE_ENABLED must be false")
    else:
        passed.append("[3] k8s configmap")

    # 4 — API honesty (static + unit test file)
    http_py = _read("api/http.py")
    if "bridge_relayer_live" not in http_py:
        errors.append("[4] api/http.py: bridge_relayer_live missing in /status")
    test = ROOT / "tests/unit/test_status_honesty.py"
    if not test.is_file() or "bridge_relayer_live" not in test.read_text(encoding="utf-8"):
        errors.append("[4] tests/unit/test_status_honesty.py must assert bridge_relayer_live")
    else:
        passed.append("[4] API honesty")

    # 5 — L1 RPC keys not embedded in prod node JSON; compose must not require ETH_RPC_URL
    for rel in PROD_MESH_JSON:
        txt = _read(rel)
        if rel and any(k in txt.lower() for k in ("eth_rpc_url", "ethereum_rpc_url")):
            errors.append(f"[5] {rel}: must not embed L1 RPC URLs (use env secrets)")
    if "ETH_RPC_URL:?" in compose:
        errors.append("[5] prod compose must not require ETH_RPC_URL while bridge off")
    secret_ex = _read("deploy/k8s/secret.example.yaml")
    if "ETH_RPC_URL" not in secret_ex:
        warnings.append("[5] deploy/k8s/secret.example.yaml: document ETH_RPC_URL placeholder")
    else:
        passed.append("[5] L1 RPC via secrets only")

    # 6 — rust bridge path documented + health surface
    if not (ROOT / "docs/BRIDGE_L1_MAINNET.md").is_file():
        errors.append("[6] missing docs/BRIDGE_L1_MAINNET.md")
    elif "/bridge/relayer/status" not in http_py and "_rust_bridge_health" not in http_py:
        errors.append("[6] api/http.py: bridge health surface required (/bridge/relayer/status or rust_bridge)")
    else:
        passed.append("[6] rust bridge idle path")

    # 7 — oracle secret not required in prod compose
    if "BRIDGE_ORACLE_SECRET:?" in compose or "BRIDGE_ORACLE_SECRET: ?" in compose:
        errors.append("[7] prod compose must not require BRIDGE_ORACLE_SECRET while bridge off")
    else:
        passed.append("[7] oracle secret optional while bridge off")

    # 8 — queue path configured (env/compose; no live L1 writes while bridge off)
    queue_ok = False
    if "BRIDGE_L1_QUEUE_PATH" in compose:
        queue_ok = True
    if "bridge_l1_queue_path" in cm.lower() or "BRIDGE_L1_QUEUE_PATH" in cm:
        queue_ok = True
    if not queue_ok:
        errors.append("[8] prod compose/configmap: bridge L1 queue path not configured")
    else:
        passed.append("[8] queue path configured")

    # 9 — CI isolation ci-bridge modes
    vpc = _read("scripts/verify_p2p_ci.py")
    for mode in ("ci-bridge", "ci-bridge-relayer"):
        if f'"{mode}"' not in vpc and f"'{mode}'" not in vpc:
            errors.append(f"[9] verify_p2p_ci.py missing mode {mode}")
    if "bridge_enabled=false" in vpc or "_verify_p2p_skip_or_fail" in vpc:
        passed.append("[9] CI bridge isolation")

    # 10 — decision record automation
    for rel in (
        "scripts/operator_cutover_prep.ps1",
        "docs/MAINNET_CUTOVER.md",
        "scripts/record_evidence_run.py",
    ):
        if not (ROOT / rel).is_file():
            errors.append(f"[10] missing {rel}")
    cutover = _read("docs/MAINNET_CUTOVER.md")
    if "bridge_decision_off" not in cutover:
        errors.append("[10] MAINNET_CUTOVER.md must document bridge_decision_off")
    prep = _read("scripts/operator_cutover_prep.ps1")
    if "bridge_decision_off" not in prep:
        errors.append("[10] operator_cutover_prep.ps1 must run bridge_decision_off step")
    evidence = ROOT / "data/evidence_run.json"
    if evidence.is_file():
        try:
            doc = json.loads(evidence.read_text(encoding="utf-8"))
            steps = doc.get("steps") or []
            hit = next((s for s in steps if s.get("name") == "bridge_decision_off"), None)
            if not hit or hit.get("result") != "PASS":
                warnings.append("[10] data/evidence_run.json: bridge_decision_off PASS not recorded")
            else:
                passed.append("[10] bridge_decision_off evidence PASS")
        except (OSError, json.JSONDecodeError) as exc:
            warnings.append(f"[10] evidence_run.json unreadable: {exc}")
    else:
        warnings.append("[10] data/evidence_run.json absent (run record_evidence_run.py locally)")
    if "bridge_decision_off" in cutover and "bridge_decision_off" in prep:
        passed.append("[10] decision record automation")

    out = {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "passed_controls": len({p.split("]")[0] for p in passed}),
        "passed": passed,
    }
    report = ROOT / "data" / "bridge_off_audit_gate.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(out, indent=2), encoding="utf-8")

    if errors:
        print("FAIL: bridge OFF audit gate")
        for err in errors:
            print(f"  - {err}")
        for warn in warnings:
            print(f"  WARN: {warn}")
        return 1
    print("OK: bridge OFF audit gate")
    for warn in warnings:
        print(f"  WARN: {warn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
