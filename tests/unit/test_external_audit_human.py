#!/usr/bin/env python3
"""External audit — human-required items cannot be auto-completed."""

import json
import tempfile
from pathlib import Path

from runtime.external_audit import (
    HUMAN_REQUIRED_AUDIT_ITEMS,
    evaluate,
    set_item_done,
)


def test_human_audit_items_reject_auto_notes():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "audit.json"
        for label in HUMAN_REQUIRED_AUDIT_ITEMS:
            set_item_done(label, done=True, note="auto: placeholder", status_path=path)
        pending, completed, summary = evaluate(status_path=path)
        assert summary["all_complete"] is False
        pending_labels = [p.replace("external_audit_pending:", "") for p in pending]
        for label in HUMAN_REQUIRED_AUDIT_ITEMS:
            assert label in pending_labels
            assert label not in completed


def test_human_audit_items_accept_vendor_note():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "audit.json"
        label = next(iter(HUMAN_REQUIRED_AUDIT_ITEMS))
        set_item_done(
            label,
            done=True,
            note="Vendor report ACME-2026-042 signed off",
            status_path=path,
        )
        pending, completed, _summary = evaluate(status_path=path)
        assert label in completed
        assert label not in pending
