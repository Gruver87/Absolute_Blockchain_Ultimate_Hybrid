#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Light client — хранит только заголовки блоков и верифицирует SPV-доказательства.
"""

import json
from typing import List, Dict, Optional, Any

from crypto import native
from crypto.merkle import verify_proof, generate_proof
from core.block_header import BlockHeader


class LightClient:
    """Light client: заголовки + Merkle SPV без полной загрузки блоков."""

    def __init__(self):
        self.headers: List[BlockHeader] = []
        self.header_by_hash: Dict[str, BlockHeader] = {}
        self.header_by_number: Dict[int, BlockHeader] = {}
        # trusted_local_replay = synced from local canonical chain;
        # unanchored = empty (no trusted checkpoint yet).
        self._trust_mode: str = "unanchored"
        self._peer_import_rejected: int = 0

    def add_header(self, header: BlockHeader) -> bool:
        """Добавить заголовок (пропускает дубликаты по номеру)."""
        if header.number in self.header_by_number:
            return False
        self.headers.append(header)
        self.header_by_hash[header.hash()] = header
        self.header_by_number[header.number] = header
        return True

    def add_headers(
        self,
        headers: List[BlockHeader],
        *,
        require_trusted_anchor: bool = False,
    ) -> int:
        """Добавить пачку заголовков с native batch hash + chain validation.

        Peer import must set require_trusted_anchor=True so an empty client
        cannot bootstrap trust from the candidate headers themselves.
        """
        candidates = sorted(
            [h for h in headers if h.number not in self.header_by_number],
            key=lambda item: item.number,
        )
        if not candidates:
            return 0

        latest = self.get_latest_header()
        if require_trusted_anchor and latest is None:
            self._peer_import_rejected += 1
            return 0

        anchor_height = latest.number if latest else candidates[0].number - 1
        anchor_parent = latest.hash() if latest else candidates[0].parent_hash
        chain_payload = [
            (
                header.number,
                header.hash(),
                header.parent_hash,
                header.proposer,
                header.state_root,
                header.tx_root,
                header.timestamp,
                header.extra_data,
            )
            for header in candidates
        ]
        if not native.validate_peer_header_chain(
            chain_payload,
            expected_parent_hash=anchor_parent,
            start_height=anchor_height,
        ):
            if require_trusted_anchor:
                self._peer_import_rejected += 1
            return 0

        hashes = BlockHeader.batch_hash(candidates)
        added = 0
        for header, header_hash in zip(candidates, hashes):
            self.headers.append(header)
            self.header_by_hash[header_hash] = header
            self.header_by_number[header.number] = header
            added += 1
        return added

    def sync_from_blockchain(self, blockchain) -> int:
        """Load headers from the local canonical chain (trusted DB replay)."""
        if not blockchain or not hasattr(blockchain, "get_height"):
            return 0
        height = int(blockchain.get_height() or 0)
        added = 0
        for number in range(height + 1):
            block = blockchain.get_block(number)
            if not block:
                continue
            if self.add_header(BlockHeader.from_block_dict(block)):
                added += 1
        if added or self.headers:
            self._trust_mode = "trusted_local_replay"
        return added

    def sync_headers_from_peers(self, peer_headers: List[Dict]) -> int:
        """Import peer headers only when a trusted local checkpoint exists."""
        if not peer_headers:
            return 0
        headers = [BlockHeader.from_dict(item) for item in peer_headers]
        return self.add_headers(headers, require_trusted_anchor=True)

    def get_header(self, number: int) -> Optional[BlockHeader]:
        return self.header_by_number.get(number)

    def get_latest_header(self) -> Optional[BlockHeader]:
        if not self.headers:
            return None
        return max(self.headers, key=lambda h: h.number)

    def get_header_count(self) -> int:
        return len(self.headers)

    def get_chain_height(self) -> int:
        latest = self.get_latest_header()
        return latest.number if latest else 0

    def verify_transaction(
        self,
        tx: dict,
        tx_root: str,
        proof: List[str],
        index: int,
    ) -> bool:
        """Проверяет включение транзакции в блок с заданным tx_root."""
        tx_str = json.dumps(tx, sort_keys=True)
        return verify_proof(tx_str, proof, tx_root, index)

    def verify_transaction_in_block(
        self,
        block_number: int,
        tx: dict,
        transactions: List[dict],
    ) -> Dict[str, Any]:
        """
        Полная SPV-проверка: находит tx в списке, строит proof, сверяет с заголовком.
        """
        header = self.get_header(block_number)
        if not header:
            return {"valid": False, "error": "header_not_found"}

        tx_strings = [json.dumps(t, sort_keys=True) for t in transactions]
        target_str = json.dumps(tx, sort_keys=True)
        try:
            index = tx_strings.index(target_str)
        except ValueError:
            return {"valid": False, "error": "tx_not_in_block"}

        proof = generate_proof(tx_strings, index)
        valid = verify_proof(target_str, proof, header.tx_root, index)
        return {
            "valid": valid,
            "block": block_number,
            "tx_root": header.tx_root,
            "header_hash": header.hash(),
            "proof": proof,
            "index": index,
        }

    def get_stats(self) -> Dict[str, Any]:
        latest = self.get_latest_header()
        return {
            "header_count": self.get_header_count(),
            "chain_height": self.get_chain_height(),
            "latest_hash": latest.hash() if latest else None,
            "latest_tx_root": latest.tx_root if latest else None,
            "latest_state_root": latest.state_root if latest else None,
            "trust_mode": self._trust_mode,
            "peer_import_requires_trusted_anchor": True,
            "peer_import_rejected": int(self._peer_import_rejected),
            "unanchored_peer_bootstrap": False,
        }

    def get_headers(self, from_num: int = 0, limit: int = 50) -> List[Dict]:
        items = sorted(self.headers, key=lambda h: h.number)
        return [h.to_dict() for h in items if h.number >= from_num][:limit]
