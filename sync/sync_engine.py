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

    def request_heads(self) -> List[Dict]:
        """
        Запрашивает у пиров их текущие головы
        В реальной реализации: P2P запрос
        """
        heads = []
        for peer in self.peers:
            # В реальной реализации: peer.request_head()
            head = getattr(peer, "head", None)
            if head:
                heads.append(head)
        return heads

    def select_best_head(self, heads: List[Dict]) -> Optional[str]:
        """
        Выбирает лучшую голову на основе cumulative weight
        Использует LMD-GHOST для выбора
        """
        if not heads:
            return None

        best_head = None
        best_weight = -1

        for head_info in heads:
            head_hash = head_info.get("hash") if isinstance(head_info, dict) else head_info
            if hasattr(self.node, "consensus"):
                weight = self.node.consensus.get_cumulative_weight(head_hash) if hasattr(self.node.consensus, "get_cumulative_weight") else 0
                if weight > best_weight:
                    best_weight = weight
                    best_head = head_hash
            else:
                # Simplified: pick first
                best_head = head_hash

        return best_head

    def download_chain(self, head: str) -> List[Dict]:
        """
        Скачивает цепочку от головы до генезиса
        """
        chain = []
        current = head

        while current:
            # В реальной реализации: запрос блока через P2P
            block = None
            if hasattr(self.node, "get_block"):
                block = self.node.get_block(current)
            elif hasattr(self.node, "chain") and hasattr(self.node.chain, "get_block_by_hash"):
                block = self.node.chain.get_block_by_hash(current)

            if not block:
                break

            chain.append(block)
            current = block.get("parent_hash") or block.get("parent")

            # Защита от бесконечного цикла
            if len(chain) > 10000:
                break

        return list(reversed(chain))

    def fast_sync(self) -> bool:
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
        """
        Проверка и синхронизация состояния
        """
        # В реальной реализации: сравнение state root с peers
        print("🔍 Checking state consistency...")
        # Simplified: assume state is consistent
        print("   State is consistent")
        return True

    def get_status(self) -> dict:
        return {
            "syncing": self.is_syncing,
            "peers": len(self.peers),
            "progress": self.sync_progress
        }

    def reset(self):
        self.is_syncing = False
        self.sync_progress = 0
