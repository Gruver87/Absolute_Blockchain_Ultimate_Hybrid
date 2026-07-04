#!/usr/bin/env python3
"""Oracle L1 queue sync endpoint tests."""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from bridge.l1_rpc import load_l1_queue, save_l1_queue


def test_l1_queue_sync_roundtrip_via_save(tmp_path):
    path = str(tmp_path / "queue.json")
    save_l1_queue(path, {"outbound": [{"abs_tx_hash": "0x1"}], "incoming": []})
    data = load_l1_queue(path)
    assert len(data["outbound"]) == 1
