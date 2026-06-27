#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Light client — хранит только заголовки блоков и верифицирует SPV-доказательства.
"""

import json
from typing import List, Dict, Optional, Any

from crypto.merkle import verify_proof, generate_proof, merkle_root
from core.block_header import BlockHeader


class LightClient:
    """Light client: заголовки + Merkle SPV без полной загрузки блоков."""

    def __init__(self):
        self.headers: List[BlockHeader] = []
        self.header_by_hash: Dict[str, BlockHeader] = {}
        self.header_by_number: Dict[int, BlockHeader] = {}

    def add_header(self, header: BlockHeader) -> bool:
        """Добавить заголовок (пропускает дубликаты по номеру)."""
        if header.number in self.header_by_number:
            return False
        self.headers.append(header)
        self.header_by_hash[header.hash()] = header
        self.header_by_number[header.number] = header
        return True

    def sync_from_blockchain(self, blockchain) -> int:
        """Загрузить все заголовки из локальной цепочки."""
        if not blockchain or not hasattr(blockchain, "get_height"):
            return 0
        added = 0
        height = blockchain.get_height()
        for n in range(height + 1):
            blk = blockchain.get_block(n)
            if blk:
                hdr = BlockHeader.from_block_dict(blk)
                if self.add_header(hdr):
                    added += 1
        return added

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
        }

    def get_headers(self, from_num: int = 0, limit: int = 50) -> List[Dict]:
        items = sorted(self.headers, key=lambda h: h.number)
        return [h.to_dict() for h in items if h.number >= from_num][:limit]
