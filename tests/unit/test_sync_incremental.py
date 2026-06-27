#!/usr/bin/env python3
"""Incremental fast_sync: skip blocks already on disk."""
from sync.sync_engine import SyncEngine


class _BlockChain:
    def __init__(self, height, blocks_by_hash):
        self._height = height
        self._blocks = blocks_by_hash

    def get_height(self):
        return self._height

    def get_block_by_hash(self, h):
        return self._blocks.get(h)

    def get_block(self, height):
        for b in self._blocks.values():
            if int(b.get("height", 0)) == height:
                return b
        return None


class _Peer:
    def __init__(self, head, height=0, peer_id="p1"):
        self.head = head
        self.height = height
        self.peer_id = peer_id


class _Node:
    def __init__(self, peers, blockchain, imported=None, fail_height=None):
        self.p2p = type("P2P", (), {"peers": {p.peer_id: p for p in peers}})()
        self.blockchain = blockchain
        self.consensus = None
        self._imported = imported if imported is not None else []
        self._fail_height = fail_height

    def import_block(self, block):
        if int(block.get("height", 0)) == self._fail_height:
            return False
        self._imported.append(block)
        return True

    def get_height(self):
        return self.blockchain.get_height()


def _chain_blocks():
    # genesis .. #5 local; peer head at #8
    blocks = {}
    prev = "0x00"
    for h in range(9):
        hsh = f"0x{h:02x}"
        blocks[hsh] = {
            "hash": hsh,
            "height": h,
            "parent_hash": prev,
            "transactions": [],
        }
        prev = hsh
    return blocks


def test_download_chain_stops_at_local_height():
    blocks = _chain_blocks()
    bc = _BlockChain(height=5, blocks_by_hash=blocks)
    peer = _Peer("0x08", height=8, peer_id="p1")
    node = _Node([peer], bc)
    engine = SyncEngine(node=node)

    chain = engine.download_chain("0x08")
    heights = [int(b["height"]) for b in chain]
    assert heights == list(range(6, 9))


def test_fast_sync_imports_only_new_blocks():
    blocks = _chain_blocks()
    bc = _BlockChain(height=5, blocks_by_hash=blocks)
    peer = _Peer("0x08", height=8, peer_id="p1")
    imported = []
    node = _Node([peer], bc, imported=imported)
    engine = SyncEngine(node=node)

    assert engine.fast_sync() is True
    assert [int(b["height"]) for b in imported] == [6, 7, 8]


def test_fast_sync_noop_when_already_synced():
    blocks = _chain_blocks()
    bc = _BlockChain(height=8, blocks_by_hash=blocks)
    peer = _Peer("0x08", height=8, peer_id="p1")
    imported = []
    node = _Node([peer], bc, imported=imported)
    engine = SyncEngine(node=node)

    assert engine.fast_sync() is True
    assert imported == []


def test_fast_sync_respects_target_block():
    blocks = _chain_blocks()
    bc = _BlockChain(height=5, blocks_by_hash=blocks)
    peer = _Peer("0x08", height=8, peer_id="p1")
    imported = []
    node = _Node([peer], bc, imported=imported)
    engine = SyncEngine(node=node)

    assert engine.fast_sync(target_block=6) is True
    assert [int(b["height"]) for b in imported] == [6]


def test_fast_sync_rejects_non_contiguous_download():
    blocks = _chain_blocks()
    blocks["0x07"]["parent_hash"] = "0xnot-local-parent"
    bc = _BlockChain(height=5, blocks_by_hash=blocks)
    peer = _Peer("0x08", height=8, peer_id="p1")
    imported = []
    node = _Node([peer], bc, imported=imported)
    engine = SyncEngine(node=node)

    assert engine.fast_sync() is False
    assert imported == []


def test_fast_sync_stops_on_import_failure():
    blocks = _chain_blocks()
    bc = _BlockChain(height=5, blocks_by_hash=blocks)
    peer = _Peer("0x08", height=8, peer_id="p1")
    imported = []
    node = _Node([peer], bc, imported=imported, fail_height=7)
    engine = SyncEngine(node=node)

    assert engine.fast_sync() is False
    assert [int(b["height"]) for b in imported] == [6]
    assert engine.is_syncing is False
