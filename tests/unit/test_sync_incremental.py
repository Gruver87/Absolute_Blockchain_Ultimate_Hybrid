#!/usr/bin/env python3
"""Incremental fast_sync: skip blocks already on disk."""
from core.blockchain import Block
from sync.sync_engine import SyncEngine


class _BlockChain:
    def __init__(self, height, blocks_by_hash):
        self._height = height
        self._blocks = blocks_by_hash

    def get_height(self):
        return self._height

    def get_state_root(self):
        return "s" * 64

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


class _P2P:
    def __init__(self, peers):
        self.peers = {p.peer_id: p for p in peers}
        self._state_consistent = False
        self._running = True

    def request_peer_state_roots_sync(self):
        return [
            {
                "peer_id": peer_id,
                "height": int(getattr(peer, "height", 0) or 0),
                "state_root": "s" * 64,
            }
            for peer_id, peer in self.peers.items()
        ]


class _Node:
    def __init__(self, peers, blockchain, imported=None, fail_height=None):
        self.p2p = _P2P(peers)
        self.blockchain = blockchain
        self.consensus = None
        self._imported = imported if imported is not None else []
        self._fail_height = fail_height

    def import_block(self, block):
        if int(block.get("height", 0)) == self._fail_height:
            return False
        self._imported.append(block)
        # Keep tip height aligned after successful import (fast_sync → sync_state).
        h = int(block.get("height", 0) or 0)
        if h > int(self.blockchain.get_height()):
            self.blockchain._height = h
        return True

    def request_peer_state_roots_sync(self):
        return self.p2p.request_peer_state_roots_sync()

    def get_height(self):
        return self.blockchain.get_height()


def _chain_blocks():
    blocks = {}
    prev = "0" * 64
    for h in range(9):
        block = Block(
            height=h,
            parent_hash=prev,
            miner="0x" + "1" * 40,
            transactions=[],
            timestamp=1000 + h,
            state_root="s" * 64,
        )
        data = block.to_dict()
        blocks[data["hash"]] = data
        prev = data["hash"]
    return blocks


def test_download_chain_stops_at_local_height():
    blocks = _chain_blocks()
    bc = _BlockChain(height=5, blocks_by_hash=blocks)
    head = [b for b in blocks.values() if int(b["height"]) == 8][0]["hash"]
    peer = _Peer(head, height=8, peer_id="p1")
    node = _Node([peer], bc)
    engine = SyncEngine(node=node)

    chain = engine.download_chain(head)
    heights = [int(b["height"]) for b in chain]
    assert heights == list(range(6, 9))


def _head_hash(blocks, height=8):
    return [b for b in blocks.values() if int(b["height"]) == height][0]["hash"]


def test_fast_sync_imports_only_new_blocks():
    blocks = _chain_blocks()
    bc = _BlockChain(height=5, blocks_by_hash=blocks)
    peer = _Peer(_head_hash(blocks), height=8, peer_id="p1")
    imported = []
    node = _Node([peer], bc, imported=imported)
    engine = SyncEngine(node=node)

    assert engine.fast_sync() is True
    assert [int(b["height"]) for b in imported] == [6, 7, 8]


def test_fast_sync_noop_when_already_synced():
    blocks = _chain_blocks()
    bc = _BlockChain(height=8, blocks_by_hash=blocks)
    peer = _Peer(_head_hash(blocks), height=8, peer_id="p1")
    imported = []
    node = _Node([peer], bc, imported=imported)
    engine = SyncEngine(node=node)

    assert engine.fast_sync() is True
    assert imported == []


def test_fast_sync_respects_target_block():
    blocks = _chain_blocks()
    bc = _BlockChain(height=5, blocks_by_hash=blocks)
    peer = _Peer(_head_hash(blocks), height=8, peer_id="p1")
    imported = []
    node = _Node([peer], bc, imported=imported)
    engine = SyncEngine(node=node)

    assert engine.fast_sync(target_block=6) is True
    assert [int(b["height"]) for b in imported] == [6]


def test_fast_sync_rejects_non_contiguous_download():
    blocks = _chain_blocks()
    bad_parent = [b for b in blocks.values() if int(b["height"]) == 6][0]["hash"]
    blocks[[b for b in blocks.values() if int(b["height"]) == 7][0]["hash"]]["parent_hash"] = bad_parent + "broken"
    bc = _BlockChain(height=5, blocks_by_hash=blocks)
    peer = _Peer(_head_hash(blocks), height=8, peer_id="p1")
    imported = []
    node = _Node([peer], bc, imported=imported)
    engine = SyncEngine(node=node)

    assert engine.fast_sync() is False
    assert imported == []


def test_fast_sync_stops_on_import_failure():
    blocks = _chain_blocks()
    bc = _BlockChain(height=5, blocks_by_hash=blocks)
    peer = _Peer(_head_hash(blocks), height=8, peer_id="p1")
    imported = []
    node = _Node([peer], bc, imported=imported, fail_height=7)
    engine = SyncEngine(node=node)

    assert engine.fast_sync() is False
    assert [int(b["height"]) for b in imported] == [6]
    assert engine.is_syncing is False
