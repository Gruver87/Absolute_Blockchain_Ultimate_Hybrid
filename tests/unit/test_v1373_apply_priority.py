#!/usr/bin/env python3
"""v1.3.73: ChainApplyQueue priority lanes (REORG > FORGE > ADD > IMPORT)."""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.chain_apply_queue import ChainApplyQueue


def test_forge_outranks_queued_imports():
    """While a slow import runs, forge enqueued after another import runs next."""
    order: list = []
    gate = threading.Event()

    class BC:
        def import_block(self, data):
            if data.get("hold"):
                gate.wait(timeout=2.0)
            order.append(("import", data.get("id")))
            return True

        def create_block(self, txs, proposer):
            order.append(("forge", proposer))
            return {"hash": "x", "proposer": proposer}

        def add_block(self, block):
            order.append(("add", block.get("proposer")))
            return True

    q = ChainApplyQueue(BC(), maxsize=32, timeout_sec=5.0, name="t73")
    try:
        # Hold worker on first import
        t_hold = threading.Thread(
            target=q.submit_import, args=({"hold": True, "id": "A"},), daemon=True
        )
        t_hold.start()
        time.sleep(0.05)
        # Queue: IMPORT-B then FORGE — forge must run before B
        t_b = threading.Thread(
            target=q.submit_import, args=({"id": "B"},), daemon=True
        )
        t_b.start()
        time.sleep(0.02)
        ok, _ = q.submit_forge_and_apply([], "miner-1")
        assert ok
        gate.set()
        t_hold.join(timeout=3)
        t_b.join(timeout=3)
        # Expected: A (holding), then forge/add, then B
        kinds = [x[0] for x in order]
        assert "forge" in kinds
        forge_i = kinds.index("forge")
        b_i = next(i for i, x in enumerate(order) if x == ("import", "B"))
        assert forge_i < b_i, order
    finally:
        gate.set()
        q.stop()


def test_reorg_outranks_forge():
    order: list = []
    gate = threading.Event()

    class BC:
        def import_block(self, data):
            if data.get("hold"):
                gate.wait(timeout=2.0)
            order.append("import")
            return True

        def create_block(self, txs, proposer):
            order.append("forge")
            return {"h": 1}

        def add_block(self, block):
            return True

        def reorg_to_ancestor(self, h):
            order.append(("reorg", h))
            return True

    q = ChainApplyQueue(BC(), maxsize=32, timeout_sec=5.0, name="t73r")
    try:
        t_hold = threading.Thread(
            target=q.submit_import, args=({"hold": True},), daemon=True
        )
        t_hold.start()
        time.sleep(0.05)
        t_forge = threading.Thread(
            target=q.submit_forge_and_apply, args=([], "m"), daemon=True
        )
        t_forge.start()
        time.sleep(0.02)
        assert q.submit_reorg(1) is True
        gate.set()
        t_hold.join(timeout=3)
        t_forge.join(timeout=3)
        # After hold import: reorg before forge
        after = order[1:]  # skip first import
        assert after[0] == ("reorg", 1), order
    finally:
        gate.set()
        q.stop()


def test_stats_and_needles():
    from observability.metrics import MetricsCollector

    q = ChainApplyQueue(object(), maxsize=4, name="t73s")
    try:
        st = q.stats()
        assert st["priority_lanes"] is True
        assert "reorg>forge>add>import" in st["priority_order"]
    finally:
        q.stop()
    text = MetricsCollector().render_prometheus(
        node_id="n1",
        apply_isolation={"error_total": 3, "priority_lanes": True},
    )
    assert "abs_chain_apply_error_total" in text
    assert 'abs_chain_apply_error_total{node_id="n1"} 3' in text
    assert "abs_chain_apply_priority_lanes" in text
    src = (ROOT / "core" / "chain_apply_queue.py").read_text(encoding="utf-8")
    assert "PriorityQueue" in src
    assert "_APPLY_PRIORITY" in src
    assert "v1.3.73" in src
