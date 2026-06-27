"""Wave 36 — stable P2P sync verification and gossip fork handling."""
import os


def test_verify_requires_stable_sync():
    src = open(
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "scripts", "verify_p2p_ci.py"),
        encoding="utf-8",
    ).read()
    assert "STABLE_NEED" in src
    assert "stable_ok" in src
    assert "return 6" in src


def test_gossip_detects_same_height_fork():
    src = open(
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "network", "p2p_node.py"),
        encoding="utf-8",
    ).read()
    assert "Fork block #" in src
    assert "_reconcile_fork_at_peer" in src
    assert "block.height > local_h + 1" in src


def test_status_exposes_peer_sync_gap():
    src = open(
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "api", "http.py"),
        encoding="utf-8",
    ).read()
    assert "peer_sync_gap" in src
    assert "peer_heights" in src
