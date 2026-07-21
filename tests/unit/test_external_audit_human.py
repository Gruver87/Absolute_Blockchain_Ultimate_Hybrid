#!/usr/bin/env python3
"""External audit — human-required items cannot be auto-completed."""

import json
import tempfile
from pathlib import Path

import pytest

from runtime.external_audit import (
    HUMAN_REQUIRED_AUDIT_ITEMS,
    evaluate,
    human_audit_evidence_accepted,
    set_item_done,
)


def test_human_audit_items_reject_auto_notes():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "audit.json"
        items = {}
        for label in HUMAN_REQUIRED_AUDIT_ITEMS:
            items[label] = {"done": True, "note": "auto: placeholder"}
        path.write_text(json.dumps({"items": items}), encoding="utf-8")
        pending, completed, summary = evaluate(status_path=path)
        assert summary["all_complete"] is False
        pending_labels = [p.replace("external_audit_pending:", "") for p in pending]
        for label in HUMAN_REQUIRED_AUDIT_ITEMS:
            assert label in pending_labels
            assert label not in completed


def test_human_audit_items_reject_template_vendor_note():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "audit.json"
        label = next(iter(HUMAN_REQUIRED_AUDIT_ITEMS))
        items = {
            label: {
                "done": True,
                "note": "Vendor YYYY-MM-DD report #ID",
                "evidence_url": "https://example.com/audit",
            }
        }
        path.write_text(json.dumps({"items": items}), encoding="utf-8")
        pending, completed, _summary = evaluate(status_path=path)
        pending_labels = [p.replace("external_audit_pending:", "") for p in pending]
        assert label in pending_labels
        assert label not in completed


def test_human_audit_items_accept_real_evidence():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "audit.json"
        label = next(iter(HUMAN_REQUIRED_AUDIT_ITEMS))
        set_item_done(
            label,
            done=True,
            note="ACME Labs engagement letter 2026-07-01; report ACME-2026-042",
            evidence_url="https://reports.acmelabs.example.org/abs-2026-042.pdf",
            status_path=path,
        )
        pending, completed, _summary = evaluate(status_path=path)
        assert label in completed
        assert label not in pending


def test_set_item_done_rejects_human_without_evidence_url():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "audit.json"
        label = next(iter(HUMAN_REQUIRED_AUDIT_ITEMS))
        with pytest.raises(ValueError, match="evidence_url"):
            set_item_done(
                label,
                done=True,
                note="Vendor report ACME-2026-042 signed off",
                status_path=path,
            )


def test_human_audit_evidence_accepted_helper():
    assert not human_audit_evidence_accepted({"note": "short", "evidence_url": ""})
    assert human_audit_evidence_accepted(
        {
            "note": "ACME Labs penetration test scheduled for Q3",
            "evidence_url": "https://trust.acme.example/engagement.pdf",
        }
    )
