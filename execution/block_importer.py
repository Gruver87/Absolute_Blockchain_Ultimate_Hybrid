# -*- coding: utf-8 -*-
"""Block importer for legacy pipeline tests."""
from typing import Dict, Tuple


class BlockImporter:
    def __init__(self, state_engine, validator, storage):
        self.state_engine = state_engine
        self.validator = validator
        self.storage = storage

    def import_block(self, block: Dict, parent_block: Dict) -> Tuple[bool, str]:
        valid, error = self.validator.validate_block(block, parent_block)
        if not valid:
            return False, error
        height = block.get("number", 0)
        self.storage.save_block(height, block)
        for tx in block.get("transactions", []):
            sender = tx.get("from", "")
            recipient = tx.get("to", "")
            value = float(tx.get("value", 0))
            if sender and recipient:
                self.state_engine.transfer(sender, recipient, value)
        return True, "imported"
