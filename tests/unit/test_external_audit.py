#!/usr/bin/env python3
"""External audit checklist tracker tests."""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from runtime.external_audit import DEFAULT_CHECKLIST, evaluate, set_item_done


def test_evaluate_pending_by_default():
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "status.json")
        warnings, completed, summary = evaluate(DEFAULT_CHECKLIST, __import__("pathlib").Path(path))
        assert len(warnings) == len(DEFAULT_CHECKLIST)
        assert completed == []
        assert summary["all_complete"] is False


def test_set_item_done_marks_complete():
    with tempfile.TemporaryDirectory() as tmp:
        path = __import__("pathlib").Path(tmp) / "status.json"
        # Non-human checklist item (human items require evidence_url)
        label = "Incident response runbook documented"
        assert label in DEFAULT_CHECKLIST
        set_item_done(label, done=True, note="scheduled Q3", status_path=path)
        warnings, completed, summary = evaluate(DEFAULT_CHECKLIST, path)
        assert label in completed
        assert len(warnings) == len(DEFAULT_CHECKLIST) - 1
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["items"][label]["done"] is True
        assert data["items"][label]["note"] == "scheduled Q3"
