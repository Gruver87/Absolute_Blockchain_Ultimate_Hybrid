# network/sync_engine.py
"""
Network Sync Engine — header-first sync + block bodies
Как в реальных Ethereum клиентах (Geth/Nethermind)
"""

from typing import Dict, List, Optional
import time


class SyncEngine:
    """
    Header-first sync protocol:
    1. Download only headers
    2. Request missing block bodies
    3. Recompute head after sync
    """

    def __init__(self, node):
        self.node = node
        self.peers = []
        self.syncing = False
        self.best_peer = None
        self.sync_start_time = 0

    # =========================
    # PEER MANAGEMENT
    # =========================
    def add_peer(self, peer):
        """Добавляет пира для синхронизации"""
        if peer not in self.peers:
            self.peers.append(peer)

    def remove_peer(self, peer):
        if peer in self.peers:
            self.peers.remove(peer)

    def select_best_peer(self):
        """
        Simple scoring: highest chain height wins
        """
        if not self.peers:
            return None

        best = None
        best_height = -1

        for peer in self.peers:
            height = getattr(peer, "height", 0)
            if height > best_height:
                best_height = height
                best = peer

        self.best_peer = best
        return best

    def get_peer_count(self) -> int:
        return len(self.peers)

    # =========================
    # SYNC FLOW
    # =========================
    def start_sync(self):
        """Запускает полную синхронизацию"""
        if self.syncing:
            print("⚠️ Sync already in progress")
            return False

        peer = self.select_best_peer()
        if not peer:
            print("⚠️ No peers available for sync")
            return False

        print(f"🔄 Starting sync with peer at height {peer.height}")
        self.syncing = True
        self.sync_start_time = time.time()

        try:
            self._sync_headers(peer)
            self._sync_bodies(peer)
            self._finalize_sync()
            return True
        except Exception as e:
            print(f"❌ Sync failed: {e}")
            self.syncing = False
            return False

    def sync_step(self):
        """Один шаг синхронизации (вызывается из main loop)"""
        if not self.syncing:
            # Check if we need to sync
            best_peer = self.select_best_peer()
            if best_peer and best_peer.height > self.node.chain.get_head_height():
                self.start_sync()

    # =========================
    # HEADERS SYNC
    # =========================
    def _sync_headers(self, peer):
        """
        Step 1: download only headers (fast)
        """
        print("   📥 Downloading headers...")

        start_height = self.node.chain.get_head_height() + 1
        headers = peer.get_headers(start=start_height, limit=100)

        if not headers:
            print("   No new headers")
            return

        for header in headers:
            self.node.chain.add_header(header)

        print(f"   ✅ Downloaded {len(headers)} headers")

    # =========================
    # BLOCK BODY SYNC
    # =========================
    def _sync_bodies(self, peer):
        """
        Step 2: fetch full blocks for downloaded headers
        """
        print("   📦 Fetching block bodies...")

        missing = self.node.chain.get_missing_bodies()
        fetched = 0

        for header in missing[:100]:  # Batch limit
            block = peer.get_block(header.get("hash"))
            if block:
                self.node.chain.add_block(block)
                fetched += 1

        print(f"   ✅ Fetched {fetched} block bodies")

    # =========================
    # FINALIZATION
    # =========================
    def _finalize_sync(self):
        """
        Step 3: recompute head using fork choice
        """
        print("   🎯 Finalizing sync...")

        if hasattr(self.node, "consensus") and hasattr(self.node.consensus, "recompute_head"):
            self.node.consensus.recompute_head()

        self.syncing = False
        elapsed = time.time() - self.sync_start_time
        print(f"   ✅ Sync complete in {elapsed:.2f}s. Head = {self.node.chain.get_head_hash()}")

    # =========================
    # STATUS
    # =========================
    def get_status(self) -> dict:
        return {
            "syncing": self.syncing,
            "peers": len(self.peers),
            "best_peer_height": self.best_peer.height if self.best_peer else 0,
            "local_height": self.node.chain.get_head_height()
        }
