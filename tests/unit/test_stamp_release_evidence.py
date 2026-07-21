"""stamp_release_evidence.py"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_stamp_release_evidence_writes_bridge_decision_off(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "stamp_release_evidence",
        ROOT / "scripts" / "stamp_release_evidence.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    out = tmp_path / "evidence.json"
    monkeypatch.setattr(
        sys,
        "argv",
        ["stamp_release_evidence.py", "--out", str(out), "--skip-soak"],
    )
    assert mod.main() == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    names = [s.get("name") for s in doc.get("steps", [])]
    assert "bridge_decision_off" in names
    assert "state_root_encoding_v1" in names


def test_stamp_release_evidence_require_soak_hours_fails_without_report(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "stamp_release_evidence",
        ROOT / "scripts" / "stamp_release_evidence.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    out = tmp_path / "evidence.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "stamp_release_evidence.py",
            "--out",
            str(out),
            "--require-soak-hours",
            "48",
            "--soak-report",
            str(tmp_path / "missing_soak.json"),
        ],
    )
    assert mod.main() == 1


def test_stamp_release_evidence_require_soak_hours_passes_with_report(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(
        "stamp_release_evidence",
        ROOT / "scripts" / "stamp_release_evidence.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    soak = tmp_path / "soak_report_48h.json"
    soak.write_text(
        json.dumps(
            {
                "passed": True,
                "hours_requested": 48,
                "git_tag": "v1.3.01",
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "evidence.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "stamp_release_evidence.py",
            "--out",
            str(out),
            "--require-soak-hours",
            "48",
            "--soak-report",
            str(soak),
        ],
    )
    assert mod.main() == 0
    doc = json.loads(out.read_text(encoding="utf-8"))
    soak_steps = [s for s in doc.get("steps", []) if s.get("name") == "soak_48h_stamp"]
    assert soak_steps and soak_steps[0]["result"] == "PASS"
    assert "soak_git_tag=v1.3.01" in soak_steps[0]["notes"]
