# -*- coding: utf-8 -*-
"""Fast sync manager for legacy v51 tests."""
from typing import Any, Dict, Optional


class FastSyncManager:
    LAG_THRESHOLD = 20

    def __init__(self, node: Any):
        self.node = node
        self.syncing = False
        self.state_root: Optional[str] = None
        self.target_height = 0

    def should_fast_sync(self) -> bool:
        local = 0
        storage = getattr(self.node, "storage", None)
        if storage and hasattr(storage, "get_latest_block_number"):
            local = int(storage.get_latest_block_number())
        sync_mgr = getattr(self.node, "sync_manager", None)
        peer_height = 0
        if sync_mgr and hasattr(sync_mgr, "get_peer_height"):
            best = sync_mgr.get_best_peer()
            if best:
                peer_height = int(sync_mgr.get_peer_height(best))
        return peer_height - local > self.LAG_THRESHOLD

    def start_sync(self, peer_id: str, target_height: int) -> bool:
        self.syncing = True
        self.target_height = target_height
        self.state_root = None
        return True

    def start_fast_sync(self, peer_id: str) -> bool:
        return self.start_sync(peer_id, 500)

    def handle_snapshot_response(self, peer_id: str, snapshot: Dict) -> None:
        self.target_height = int(snapshot.get("height", 0))
        self.state_root = snapshot.get("state_root", self.state_root)
        dump = snapshot.get("state_dump")
        if dump:
            self._restore_state(dump)
        self.syncing = False

    def _restore_state(self, state_dump: Dict) -> None:
        storage = getattr(self.node, "storage", None)
        if not storage:
            return
        for address, account in state_dump.get("accounts", {}).items():
            if hasattr(storage, "save_account_state"):
                storage.save_account_state(
                    address,
                    account.get("balance", 0),
                    account.get("nonce", 0),
                )
        for validator in state_dump.get("validators", []):
            if hasattr(storage, "save_validator"):
                storage.save_validator(validator.get("address", ""), validator.get("stake", 0))

    def complete_fast_sync(self) -> bool:
        self.syncing = False
        return True

    def get_fast_sync_status(self) -> Dict:
        return {
            "is_syncing": self.syncing,
            "target_height": self.target_height,
            "state_root": self.state_root,
        }

    def get_status(self) -> Dict:
        return self.get_fast_sync_status()
