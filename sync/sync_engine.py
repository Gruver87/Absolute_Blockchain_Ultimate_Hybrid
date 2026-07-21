# sync/sync_engine.py
"""
Sync Engine — fast catch-up for late-joining nodes
- Peer head resolution
- Chain download (headers → blocks)
- State reconciliation
"""

from typing import List, Dict, Optional

from crypto import native


class SyncEngine:
    """
    Fast sync engine with deterministic head selection and fail-closed block import.
    """

    def __init__(self, node):
        self.node = node
        self.peers = []
        self.is_syncing = False
        self.sync_progress = 0
        self._last_wire_probe_ok = None

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

    def _local_height(self) -> int:
        if hasattr(self.node, "blockchain") and self.node.blockchain:
            return int(self.node.blockchain.get_height())
        if hasattr(self.node, "get_height"):
            return int(self.node.get_height() or 0)
        return 0

    @staticmethod
    def _block_height(block: Dict) -> int:
        return int(block.get("height", block.get("number", 0)) or 0)

    @staticmethod
    def _block_hash(block: Dict) -> str:
        return str(block.get("hash", ""))

    @staticmethod
    def _parent_hash(block: Dict) -> str:
        return str(block.get("parent_hash") or block.get("parent") or "")

    def _validate_downloaded_chain(self, chain: List[Dict], local_height: int) -> bool:
        """Require contiguous parent links and canonical block hashes before import."""
        previous_hash = ""
        if chain and hasattr(self.node, "blockchain") and self.node.blockchain:
            local_head = self.node.blockchain.get_block(local_height)
            if local_head:
                previous_hash = self._block_hash(local_head)
        return native.validate_imported_block_chain(
            chain,
            expected_parent_hash=previous_hash,
            start_height=local_height,
        )

    def download_chain(self, head: str, stop_at_height: Optional[int] = None) -> List[Dict]:
        """Walk parent chain from head; stop at a block we already have locally."""
        chain = []
        current = head
        seen = set()
        stop_h = self._local_height() if stop_at_height is None else int(stop_at_height)

        while current and current not in seen:
            seen.add(current)
            block = None
            if hasattr(self.node, "blockchain") and self.node.blockchain:
                block = self.node.blockchain.get_block_by_hash(current)
            if not block:
                block = self._resolve_block(current)
            if not block:
                break

            height = self._block_height(block)
            if height <= stop_h:
                break

            chain.append(block)
            current = self._parent_hash(block)
            if len(chain) > 10000:
                break

        return list(reversed(chain))

    def fast_sync(self, target_block: int = 0) -> bool:
        """
        Полная процедура синхронизации.
        Импортирует только блоки выше локальной высоты (без полного replay).
        """
        if self.is_syncing:
            print("[Sync] Already in progress")
            return False

        local_h = self._local_height()
        print(f"[Sync] Starting fast sync from height {local_h}...")
        self.is_syncing = True

        heads = self.request_heads()
        if not heads:
            print("[Sync] No peers available")
            self.is_syncing = False
            return False

        best_head = self.select_best_head(heads)
        if not best_head:
            print("[Sync] No valid head selected")
            self.is_syncing = False
            return False

        best_peer_h = max(int(h.get("height", 0) or 0) for h in heads)
        if target_block > 0:
            best_peer_h = min(best_peer_h, int(target_block))

        if best_peer_h <= local_h:
            print(f"[Sync] Already at head (local={local_h}, peer={best_peer_h})")
            self.sync_state()
            self.is_syncing = False
            return True

        print(f"[Sync] Selected head: {best_head[:8]}... (peer height {best_peer_h})")

        chain = self.download_chain(best_head, stop_at_height=local_h)
        if not chain:
            print("[Sync] Chain download failed")
            self.is_syncing = False
            return False

        target_h = best_peer_h if target_block > 0 else None
        to_import = []
        needs_genesis = False
        if hasattr(self.node, "blockchain") and self.node.blockchain is not None:
            bc_db = getattr(self.node.blockchain, "db", None)
            if bc_db is not None and bc_db.get_last_block() is None:
                needs_genesis = True
        import_floor = -1 if needs_genesis else local_h
        for block in chain:
            height = self._block_height(block)
            if height <= import_floor:
                continue
            if target_h is not None and height > target_h:
                continue
            to_import.append(block)
        to_import.sort(key=self._block_height)

        if not to_import:
            print(f"[Sync] No new blocks (local={local_h}, chain_len={len(chain)})")
            self.sync_state()
            self.is_syncing = False
            return True

        if not self._validate_downloaded_chain(to_import, local_h):
            print("[Sync] Downloaded chain is not contiguous")
            self.is_syncing = False
            return False

        imported = 0
        for i, block in enumerate(to_import):
            ok = False
            if hasattr(self.node, "import_block"):
                ok = bool(self.node.import_block(block))
            elif hasattr(self.node, "consensus") and hasattr(self.node.consensus, "add_block"):
                ok = bool(self.node.consensus.add_block(block))
            if ok:
                imported += 1
            else:
                print(f"[Sync] Import failed at height {self._block_height(block)}")
                self.is_syncing = False
                return False
            self.sync_progress = i + 1

        if hasattr(self.node, "consensus") and hasattr(self.node.consensus, "set_head"):
            self.node.consensus.set_head(best_head)
        elif hasattr(self.node, "chain") and hasattr(self.node.chain, "set_head"):
            self.node.chain.set_head(best_head)

        self.sync_state()
        self.is_syncing = False
        print(f"[Sync] Done: imported {imported}/{len(to_import)} blocks (local now {self._local_height()})")
        return imported > 0 or best_peer_h <= local_h

    def _set_state_consistent(self, ok: bool) -> None:
        """Mirror consistency on AbsoluteNode and/or nested P2PNode."""
        flag = bool(ok)
        if hasattr(self.node, "_state_consistent"):
            self.node._state_consistent = flag
        p2p = getattr(self.node, "p2p", None)
        if p2p is not None and hasattr(p2p, "_state_consistent"):
            p2p._state_consistent = flag

    def sync_state(self) -> bool:
        """Compare local state_root with peer-reported roots when available."""
        print("[Sync] Checking state consistency...")
        if not hasattr(self.node, "blockchain"):
            print("   No blockchain attached")
            return False

        bc = self.node.blockchain
        if not hasattr(bc, "get_state_root"):
            print("   [Sync] blockchain missing get_state_root — fail-closed")
            self._set_state_consistent(False)
            self._last_wire_probe_ok = False
            return False

        local_root = bc.get_state_root()
        local_height = bc.get_height()
        mismatches = []

        wire_roots = []
        wire_probe_ok = True
        peers = self._collect_p2p_peers()
        if hasattr(self.node, "request_peer_state_roots_sync"):
            try:
                wire_roots = self.node.request_peer_state_roots_sync()
                if wire_roots is None:
                    wire_probe_ok = False
                    print("   [Sync] peer state_root wire probe failed: timeout/empty")
                    wire_roots = []
                elif peers and len(wire_roots) == 0:
                    wire_probe_ok = False
                    print(
                        "   [Sync] peer state_root wire probe empty "
                        f"with {len(peers)} peer(s)"
                    )
            except Exception as exc:
                wire_probe_ok = False
                print(f"   [Sync] peer state_root wire probe failed: {exc}")
                wire_roots = []
        self._last_wire_probe_ok = wire_probe_ok

        if not wire_probe_ok:
            self._set_state_consistent(False)
            return False

        for entry in wire_roots:
            peer_root = entry.get("state_root", "")
            peer_h = int(entry.get("height", 0) or 0)
            if peer_h < local_height:
                continue
            if peer_h == local_height and peer_root and peer_root != local_root:
                mismatches.append(entry.get("peer_id", "peer")[:8])

        # Peer still catching up — not a root mismatch.
        for peer in self._collect_p2p_peers():
            peer_height = int(getattr(peer, "height", 0) or 0)
            if peer_height != local_height:
                continue
            blk = self.node.blockchain.get_block(peer_height)
            if not blk:
                continue
            tip_root = blk.get("state_root", "")
            if tip_root and tip_root != local_root:
                pid = getattr(peer, "peer_id", "peer")[:8]
                if pid not in mismatches:
                    mismatches.append(pid)

        if mismatches:
            print(f"   State root mismatch vs peers: {', '.join(mismatches)}")
            self._set_state_consistent(False)
            return False

        print(f"   State consistent (root={local_root[:12]}... height={local_height})")
        self._set_state_consistent(True)
        return True

    def get_status(self) -> dict:
        local_height = self._local_height()
        peers = self._collect_p2p_peers()
        best_peer_height = 0
        for peer in peers:
            best_peer_height = max(best_peer_height, int(getattr(peer, "height", 0) or 0))

        p2p = getattr(self.node, "p2p", None)
        state_consistent = getattr(p2p, "_state_consistent", False) if p2p else False
        probe = getattr(self, "_last_wire_probe_ok", None)

        return {
            "syncing": self.is_syncing,
            "peers": len(peers),
            "progress": self.sync_progress,
            "local_height": local_height,
            "best_peer_height": best_peer_height,
            "behind": max(0, best_peer_height - local_height),
            "state_consistent": state_consistent,
            # Unknown (never probed) is fail-closed False for status honesty.
            "wire_probe_ok": True if probe is True else False,
            "wire_probe_probed": probe is not None,
        }

    def reset(self):
        self.is_syncing = False
        self.sync_progress = 0
