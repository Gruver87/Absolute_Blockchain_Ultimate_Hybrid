"""Wave 34 — legacy cleanup, mega_audit, sync_manager."""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_mega_audit_no_removed_legacy_files():
    """extended_api_server.py and rpc_proxy.py were merged into main.py + api/http.py."""
    src = open(os.path.join(ROOT, "scripts", "mega_audit.py"), encoding="utf-8").read()
    assert '"extended_api_server.py":' not in src
    assert '"rpc_proxy.py":' not in src
    assert '"api/http.py":' in src


def test_sync_manager_uses_real_blocks_not_placeholders():
    from network.sync.sync_manager import SyncManager

    class _Storage:
        def get_latest_block_number(self):
            return 2

        def get_block(self, height):
            if height == 1:
                return {"number": 1, "hash": "0xabc123"}
            return None

    class _Node:
        storage = _Storage()

    mgr = SyncManager(_Node())
    blocks = mgr._get_blocks_from_height(1, limit=3)
    assert len(blocks) == 1
    assert blocks[0]["hash"] == "0xabc123"
    assert blocks[0]["number"] == 1


def test_bridge_overview_includes_l1_rpc():
    from api.http import _build_bridge_overview

    class _Cfg:
        bridge_enabled = True
        bridge_mode = "rust"
        bridge_auto_confirm_sec = 0
        bridge_l1_queue_path = "data/bridge_l1_queue.json"

    overview = _build_bridge_overview(None, None, _Cfg(), None)
    assert "l1_queue" in overview["endpoints"]
    assert "l1_rpc" in overview


@pytest.mark.skipif(
    os.environ.get("SKIP_MEGA_AUDIT") == "1",
    reason="full mega_audit is slow in CI slice",
)
def test_mega_audit_zero_critical_for_legacy_removal():
    proc = subprocess.run(
        [sys.executable, "scripts/mega_audit.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0 or proc.returncode is None
    assert "[FILE MISSING] extended_api_server.py" not in proc.stdout
    assert "[FILE MISSING] rpc_proxy.py" not in proc.stdout
