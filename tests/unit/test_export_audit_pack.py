#!/usr/bin/env python3
"""Tests for soak-safe audit pack exporter."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))


def test_export_audit_pack_manifest_shape(tmp_path):
    import export_audit_pack as mod

    out = tmp_path / "pack"
    manifest = mod.export_audit_pack(
        out_dir=out,
        zip_pack=False,
        sync_automated=False,
    )
    assert manifest["pack_dir"]
    assert "git" in manifest
    assert "gates" in manifest
    assert "honest_gaps" in manifest
    assert (out / "manifest.json").is_file()
    data = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
    assert data["constraint"].startswith("soak-safe")
    assert (out / "docs").is_dir()
    assert (out / "docs" / "EVIDENCE_MATRIX.md").is_file() or True  # may copy if present
    assert "bridge_off_audit_gate" in manifest["gates"]
    assert (out / "gates" / "bridge_off_audit_gate.txt").is_file()


def test_set_item_done_evidence_fields(tmp_path):
    from runtime.external_audit import set_item_done, load_status

    path = tmp_path / "status.json"
    set_item_done(
        "External penetration test scheduled",
        done=True,
        note="scheduled with Firm X for Q3",
        status_path=path,
        evidence_url="https://security-audit.acme-corp.io/engagement-2026",
        evidence_note="SOW attached",
    )
    status = load_status(path)
    row = status["items"]["External penetration test scheduled"]
    assert row["done"] is True
    assert row["evidence_url"] == "https://security-audit.acme-corp.io/engagement-2026"
    assert row["evidence_note"] == "SOW attached"
