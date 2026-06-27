from sync.sync_engine import SyncEngine


class _Peer:
    def __init__(self, head, height=0, peer_id="p1"):
        self.head = head
        self.height = height
        self.peer_id = peer_id


class _Consensus:
    def __init__(self, weights):
        self._weights = weights

    def get_cumulative_weight(self, block_hash):
        return self._weights.get(block_hash, 0)


class _Node:
    def __init__(self, peers=None, weights=None):
        self.p2p = type("P2P", (), {"peers": {p.peer_id: p for p in (peers or [])}})()
        self.consensus = _Consensus(weights or {}) if weights is not None else None
        self.blockchain = None


def test_select_best_head_by_lmd_weight():
    peers = [
        _Peer("0xaaa", height=10, peer_id="p1"),
        _Peer("0xbbb", height=9, peer_id="p2"),
    ]
    node = _Node(peers=peers, weights={"0xbbb": 500, "0xaaa": 100})
    engine = SyncEngine(node=node)
    heads = engine.request_heads()
    assert len(heads) == 2
    assert engine.select_best_head(heads) == "0xbbb"


def test_select_best_head_height_tiebreak():
    peers = [_Peer("0xlow", height=5, peer_id="p1"), _Peer("0xhigh", height=20, peer_id="p2")]
    node = _Node(peers=peers, weights={})
    engine = SyncEngine(node=node)
    heads = engine.request_heads()
    assert engine.select_best_head(heads) == "0xhigh"
