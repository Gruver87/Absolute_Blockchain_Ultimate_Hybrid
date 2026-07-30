# tests/e2e/test_runtime_signals.py — ADR 0014 SIGTERM clean RocksDB close
"""Send a real OS shutdown signal to a live node during block production.

Asserts RocksDB logs a clean close (no corruption path on container restart).

Gate: ``LIVE_MESH_E2E=1`` (same as live mesh; requires abs_native).
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys

import pytest

from tests.e2e.mesh_orchestrator import (
    LIVE_MESH4_HTTP_PORTS,
    LIVE_MESH4_P2P_PORTS,
    LIVE_MESH4_RPC_PORTS,
    LIVE_MESH4_WS_PORTS,
    LocalMeshTopology,
    require_live_mesh_prereqs,
)


def _live_enabled() -> bool:
    return os.environ.get("LIVE_MESH_E2E", "").strip() == "1"


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.live_mesh,
    pytest.mark.skipif(
        not _live_enabled(),
        reason="set LIVE_MESH_E2E=1 for SIGTERM runtime signal e2e",
    ),
]


def _send_graceful_shutdown(pid: int, process) -> None:
    """POSIX SIGTERM; Windows CTRL_BREAK (CREATE_NEW_PROCESS_GROUP → SIGBREAK)."""
    if sys.platform == "win32":
        os.kill(pid, signal.CTRL_BREAK_EVENT)
    else:
        os.kill(pid, signal.SIGTERM)


@pytest.mark.asyncio
async def test_sigterm_during_mining_rocksdb_clean_close():
    try:
        require_live_mesh_prereqs()
    except RuntimeError as exc:
        pytest.skip(str(exc))

    # Two-node topology for Rocks clone realism; signal targets the mining leader.
    mesh = LocalMeshTopology(
        node_count=2,
        mesh_min_peers_before_mine=0,
        deployment_mode="prod",
        keep_tmpdir=os.environ.get("LIVE_MESH_KEEP", "").strip() == "1",
        http_ports=LIVE_MESH4_HTTP_PORTS[:2],
        p2p_ports=LIVE_MESH4_P2P_PORTS[:2],
        rpc_ports=LIVE_MESH4_RPC_PORTS[:2],
        ws_ports=LIVE_MESH4_WS_PORTS[:2],
    )
    try:
        mesh.prepare()
        # Solo bootstrap mines ≥1 on Rocks, quiesces with graceful stop, clones.
        await mesh.bootstrap_leader_and_seed_followers()

        leader = "node-1"
        await mesh.start_node(leader, append_log=True)
        await mesh.wait_healthy(leader, timeout_sec=180)
        await mesh.ensure_admin_jwt(leader)

        h0 = int(mesh.status(leader).get("height", 0) or 0)
        try:
            await mesh.wait_height_at_least(leader, max(h0 + 1, 1), timeout_sec=120)
        except TimeoutError:
            # Still exercise shutdown even if tip did not advance further.
            pass

        handle = mesh.node(leader)
        assert handle.alive and handle.pid is not None
        pid = int(handle.pid)

        _send_graceful_shutdown(pid, handle.process)

        try:
            await asyncio.wait_for(handle.process.wait(), timeout=60.0)
        except asyncio.TimeoutError:
            await mesh.kill_hard(leader)
            pytest.fail(f"{leader} did not exit within 60s after graceful signal")

        rc = handle.process.returncode
        handle.process = None
        mesh._close_stderr(handle)

        log_text = ""
        if handle.stderr_path.is_file():
            log_text = handle.stderr_path.read_text(encoding="utf-8", errors="replace")
        node_log = handle.data_dir / "node.log"
        if node_log.is_file():
            log_text += "\n" + node_log.read_text(encoding="utf-8", errors="replace")

        assert "[RocksDB] clean close" in log_text or "clean close" in log_text.lower(), (
            f"missing RocksDB clean close in logs (rc={rc})\n{log_text[-2500:]}"
        )
        assert "[Node] Goodbye" in log_text or "Goodbye" in log_text, (
            f"missing graceful goodbye (rc={rc})\n{log_text[-1500:]}"
        )
        assert rc is not None
    finally:
        await mesh.cleanup()
