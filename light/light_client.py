# light/light_client.py
"""
Light client — only stores headers + verifies proofs
"""

from typing import List, Dict, Optional
from crypto.merkle import verify_proof
from core.block_header import BlockHeader


class LightClient:
    """
    Light client that only stores block headers
    Can verify transactions without full blocks
    """

    def __init__(self):
        self.headers: List[BlockHeader] = []
        self.header_by_hash: Dict[str, BlockHeader] = {}

    def add_header(self, header: BlockHeader):
        """Add block header to light client"""
        self.headers.append(header)
        self.header_by_hash[header.hash()] = header

    def get_header(self, number: int) -> Optional[BlockHeader]:
        if number < len(self.headers):
            return self.headers[number]
        return None

    def get_latest_header(self) -> Optional[BlockHeader]:
        if self.headers:
            return self.headers[-1]
        return None

    def verify_transaction(self, tx: dict, tx_root: str, proof: List[str], index: int) -> bool:
        """
        Verify that transaction is included in block with given tx_root
        """
        import json
        tx_str = json.dumps(tx, sort_keys=True)
        return verify_proof(tx_str, proof, tx_root, index)

    def get_header_count(self) -> int:
        return len(self.headers)

    def get_chain_height(self) -> int:
        if self.headers:
            return self.headers[-1].number
        return 0
