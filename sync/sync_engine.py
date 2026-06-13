# sync/sync_engine.py
"""
Sync Engine — fast catch-up for late-joining nodes
- Peer head resolution
- Chain download (headers → blocks)
- State reconciliation
"""

from typing import List, Dict, Optional


class SyncEngine:
    """
    Fast sync engine (simplified Ethereum-style)
    """

    def __init__(self, node):
        self.node = node
        self.peers = []
        self.is_syncing = False
        self.sync_progress = 0

    def add_peer(self, peer):
        """Добавляет пира для синхронизации"""
        if peer not in self.peers:
            self.peers.append(peer)

    def remove_peer(self, peer):
        if peer in self.peers:
            self.peers.remove(peer)

    def get_peers(self) -> List:
        return self.peers

    def _collect_p2p_peers(self) -> List:
        """Peers from live P2P connections or explicit sync peer list."""
        p2p = getattr(self.node, "p2p", None)
        if p2p and getattr(p2p, "peers", None):
            live = list(p2p.peers.values())
            if live:
                return live
        return list(self.peers)

    def request_heads(self) -> List[Dict]:
        """Collect head hashes from connected P2P peers."""
        heads = []
        for peer in self._collect_p2p_peers():
            head_raw = getattr(peer, "head", None)
            head_hash = ""
            if isinstance(head_raw, dict):
                head_hash = head_raw.get("hash", "")
            elif isinstance(head_raw, str):
                head_hash = head_raw
            if not head_hash and getattr(peer, "height", 0):
                p2p = getattr(self.node, "p2p", None)
                if p2p and hasattr(self.node, "blockchain"):
                    blk = self.node.blockchain.get_block(peer.height)
                    if blk:
                        head_hash = blk.get("hash")
            if head_hash:
                heads.append({
                    "hash": head_hash,
                    "height": int(getattr(peer, "height", 0) or 0),
                    "peer_id": getattr(peer, "peer_id", ""),
                })
        return heads

    def select_best_head(self, heads: List[Dict]) -> Optional[str]:
        """
        LMD-GHOST cumulative weight when consensus is available;
        otherwise highest peer height (longest chain).
        """
        if not heads:
            return None

        best_head = None
        best_key = (-1, -1)  # (weight, height)

        consensus = getattr(self.node, "consensus", None)
        for head_info in heads:
            if isinstance(head_info, dict):
                head_hash = head_info.get("hash", "")
                height = int(head_info.get("height", 0) or 0)
            else:
                head_hash = str(head_info)
                height = 0
            if not head_hash:
                continue

            weight = 0
            if consensus and hasattr(consensus, "get_cumulative_weight"):
                weight = int(consensus.get_cumulative_weight(head_hash) or 0)

            key = (weight, height)
            if key > best_key:
                best_key = key
                best_head = head_hash

        return best_head

    def _resolve_block(self, block_hash: str) -> Optional[Dict]:
        """Local DB first, then P2P peer fetch."""
        if hasattr(self.node, "get_block"):
            blk = self.node.get_block(block_hash)
            if blk:
                return blk
        if hasattr(self.node, "blockchain"):
            blk = self.node.blockchain.get_block_by_hash(block_hash)
            if blk:
                return blk
        p2p = getattr(self.node, "p2p", None)
        if p2p and hasattr(p2p, "fetch_block_from_peers_sync"):
            return p2p.fetch_block_from_peers_sync(block_hash)
        return None

    def download_chain(self, head: str) -> List[Dict]:
        """Walk parent chain from head; fetch missing blocks from peers."""
        chain = []
        current = head
        seen = set()

        while current and current not in seen:
            seen.add(current)
            block = self._resolve_block(current)
            if not block:
                break

            chain.append(block)
            current = block.get("parent_hash") or block.get("parent")
            if len(chain) > 10000:
                break

        return list(reversed(chain))

    def fast_sync(self, target_block: int = 0) -> bool:
        """
        Полная процедура синхронизации
        """
        if self.is_syncing:
            print("⚠️ Sync already in progress")
            return False

        print("🔄 Starting fast sync...")
        self.is_syncing = True

        # 1. Get heads from peers
        heads = self.request_heads()
        if not heads:
            print("❌ No peers available for sync")
            self.is_syncing = False
            return False

        # 2. Select best head
        best_head = self.select_best_head(heads)
        if not best_head:
            print("❌ No valid head selected")
            self.is_syncing = False
            return False

        print(f"   Selected head: {best_head[:8]}...")

        # 3. Download chain
        chain = self.download_chain(best_head)
        if not chain:
            print("❌ Chain download failed")
            self.is_syncing = False
            return False

        print(f"   Downloaded {len(chain)} blocks")

        # 4. Import blocks
        for i, block in enumerate(chain):
            if hasattr(self.node, "import_block"):
                self.node.import_block(block)
            elif hasattr(self.node, "consensus") and hasattr(self.node.consensus, "add_block"):
                self.node.consensus.add_block(block)
            self.sync_progress = i + 1

        # 5. Set head
        if hasattr(self.node, "consensus") and hasattr(self.node.consensus, "set_head"):
            self.node.consensus.set_head(best_head)
        elif hasattr(self.node, "chain") and hasattr(self.node.chain, "set_head"):
            self.node.chain.set_head(best_head)

        self.is_syncing = False
        print(f"✅ Fast sync complete! Synced {len(chain)} blocks")
        return True

    def sync_state(self) -> bool:
        """Compare local state_root with peer-reported roots when available."""
        print("🔍 Checking state consistency...")
        if not hasattr(self.node, "blockchain"):
            print("   No blockchain attached")
            return False

        local_root = self.node.blockchain.get_state_root()
        local_height = self.node.blockchain.get_height()
        mismatches = []

        wire_roots = []
        if hasattr(self.node, "request_peer_state_roots_sync"):
            try:
                wire_roots = self.node.request_peer_state_roots_sync()
            except Exception:
                wire_roots = []

        for entry in wire_roots:
            peer_root = entry.get("state_root", "")
            peer_h = int(entry.get("height", 0) or 0)
            if peer_h == local_height and peer_root and peer_root != local_root:
                mismatches.append(entry.get("peer_id", "peer")[:8])

        for peer in self._collect_p2p_peers():
            peer_height = int(getattr(peer, "height", 0) or 0)
            if peer_height != local_height:
                continue
            blk = self.node.blockchain.get_block(peer_height)
            if not blk:
                continue
            peer_root = blk.get("state_root", "")
            if peer_root and peer_root != local_root:
                pid = getattr(peer, "peer_id", "peer")[:8]
                if pid not in mismatches:
                    mismatches.append(pid)

        if mismatches:
            print(f"   State root mismatch vs peers: {', '.join(mismatches)}")
            if hasattr(self.node, "_state_consistent"):
                self.node._state_consistent = False
            return False

        print(f"   State consistent (root={local_root[:12]}... height={local_height})")
        if hasattr(self.node, "_state_consistent"):
            self.node._state_consistent = True
        return True

    def get_status(self) -> dict:
        local_height = 0
        if hasattr(self.node, "blockchain"):
            local_height = self.node.blockchain.get_height()
        elif hasattr(self.node, "get_height"):
            local_height = self.node.get_height()
        elif hasattr(self.node, "chain") and hasattr(self.node.chain, "get_head_height"):
            local_height = self.node.chain.get_head_height()

        best_peer_height = 0
        for peer in self._collect_p2p_peers():
            best_peer_height = max(best_peer_height, int(getattr(peer, "height", 0) or 0))

        return {
            "syncing": self.is_syncing,
            "peers": len(self.peers),
            "progress": self.sync_progress,
            "local_height": local_height,
            "best_peer_height": best_peer_height,
        }

    def reset(self):
        self.is_syncing = False
        self.sync_progress = 0
