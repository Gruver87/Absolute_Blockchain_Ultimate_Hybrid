# consensus/pbs.py
"""
Proposer/Builder Separation (PBS-lite)
Builder creates blocks, proposer selects most profitable
"""

from typing import List, Dict, Any


class Builder:
    """
    Block builder that creates profitable blocks
    """

    def __init__(self, builder_id: str):
        self.builder_id = builder_id
        self.blocks = []

    def build_block(self, transactions: List[Dict]) -> Dict:
        """Create block from transactions"""
        total_fees = sum(tx.get("gas_price", 0) for tx in transactions)
        block = {
            "builder": self.builder_id,
            "transactions": transactions,
            "tx_count": len(transactions),
            "total_fees": total_fees,
            "value": total_fees  # In real MEV, value can be higher
        }
        self.blocks.append(block)
        return block


class Proposer:
    """
    Proposer that selects the most valuable block
    """

    def __init__(self, proposer_id: str):
        self.proposer_id = proposer_id
        self.selected_blocks = []

    def select_block(self, bids: List[Dict]) -> Dict:
        """Select block with highest value"""
        if not bids:
            return None

        best = max(bids, key=lambda x: x.get("value", 0))
        best["selected_by"] = self.proposer_id
        self.selected_blocks.append(best)
        return best


class PBSMarket:
    """
    Simplified Proposer/Builder Separation market
    """

    def __init__(self):
        self.builders: List[Builder] = []
        self.proposers: List[Proposer] = []

    def add_builder(self, builder: Builder):
        self.builders.append(builder)

    def add_proposer(self, proposer: Proposer):
        self.proposers.append(proposer)

    def run_auction(self, transactions: List[Dict]) -> Dict:
        """
        Run block auction:
        1. Builders create blocks
        2. Proposer selects best block
        """
        if not self.builders or not self.proposers:
            return None

        # Builders create blocks
        bids = []
        for builder in self.builders:
            block = builder.build_block(transactions)
            bids.append(block)

        # Proposer selects best
        proposer = self.proposers[0]  # For simplicity, use first proposer
        selected = proposer.select_block(bids)

        return selected
