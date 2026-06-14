"""Wave 53 — fork-status API and slashing adversarial checks."""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)


class _FakeP2P:
    def __init__(self, peers, consistent=True):
        self._peers = peers
        self._state_consistent = consistent

    def get_peers_info(self):
        return self._peers


class _FakeBC:
    def __init__(self, height=10, root="0xabc", head="0xhead1"):
        self._height = height
        self._root = root
        self._head = head

    def get_height(self):
        return self._height

    def get_state_root(self):
        return self._root

    def get_last_block(self):
        return {"hash": self._head, "height": self._height, "state_root": self._root}


class _FakeCfg:
    node_id = "docker-node-1"
    chain_id = 77777
    testnet_expected_peers = 2


class _FakeDB:
    def __init__(self, events=None):
        self._events = events or []

    def get_slash_events(self, limit=100):
        return self._events[:limit]


def test_fork_status_healthy_mesh():
    from api.http import _build_testnet_fork_status

    p2p = _FakeP2P([
        {"id": "n2", "host": "node2", "port": 5000, "height": 10, "head": "0xhead1"},
        {"id": "n3", "host": "node3", "port": 5000, "height": 9, "head": "0xh2"},
    ])
    fork = _build_testnet_fork_status(p2p, _FakeBC(), _FakeCfg(), _FakeDB())
    assert fork["consensus_healthy"] is True
    assert fork["fork_detected"] is False
    assert fork["api_wave"] == 56


def test_fork_status_detects_same_height_divergence():
    from api.http import _build_testnet_fork_status

    p2p = _FakeP2P([
        {"id": "n2", "host": "node2", "port": 5000, "height": 10, "head": "0xaaa"},
        {"id": "n3", "host": "node3", "port": 5000, "height": 10, "head": "0xbbb"},
    ])
    fork = _build_testnet_fork_status(p2p, _FakeBC(head="0xccc"), _FakeCfg(), _FakeDB())
    assert fork["same_height_divergent_heads"] is True
    assert fork["fork_detected"] is True
    assert fork["consensus_healthy"] is False


def test_slashing_double_vote_persists_event():
    from consensus.slashing import SlashingEngine
    from storage.database import Database

    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "slash.db")
    db = Database(db_path)
    db.initialize()

    engine = SlashingEngine()
    engine.register_validator("0x" + "aa" * 20, 1000)
    engine.register_slash_callback(
        lambda v, r, e, p: db.save_slash_event(v, r, e, p)
    )

    slot = 42
    assert engine.record_vote("0x" + "aa" * 20, slot, "0x" + "11" * 32) is True
    assert engine.record_vote("0x" + "aa" * 20, slot, "0x" + "22" * 32) is False

    events = db.get_slash_events(5)
    assert len(events) == 1
    assert events[0]["reason"] == "double_vote"
