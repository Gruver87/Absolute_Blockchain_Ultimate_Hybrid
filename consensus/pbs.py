# consensus/pbs.py
"""
Proposer/Builder Separation (PBS-lite) — fee-bid simulation only.

Builders receive the same transaction set; the auction scores total gas fees.
It does not extract MEV, reorder for protection, or change inclusion sets.
"""

from typing import List, Dict, Any, Optional


class Builder:
    """Block builder that scores a fee-bid block from a fixed tx set."""

    def __init__(self, builder_id: str):
        self.builder_id = builder_id
        self.blocks = []

    def build_block(self, transactions: List[Dict]) -> Dict:
        """Score block from transactions (same set; fee sum only)."""
        total_fees = sum(tx.get("gas_price", 0) for tx in transactions)
        block = {
            "builder": self.builder_id,
            "transactions": transactions,
            "tx_count": len(transactions),
            "total_fees": total_fees,
            "value": total_fees,
            "ordering_applied": False,
            "mev_protection": False,
            "simulation_only": True,
            "note": "fee-bid simulation; identical tx set, no MEV reorder",
        }
        self.blocks.append(block)
        return block


class Proposer:
    """Proposer that selects the highest fee-bid block."""

    def __init__(self, proposer_id: str):
        self.proposer_id = proposer_id
        self.selected_blocks = []

    def select_block(self, bids: List[Dict]) -> Optional[Dict]:
        """Select block with highest fee value (simulation)."""
        if not bids:
            return None

        best = max(bids, key=lambda x: x.get("value", 0))
        best = dict(best)
        best["selected_by"] = self.proposer_id
        best["ordering_applied"] = False
        best["mev_protection"] = False
        best["simulation_only"] = True
        self.selected_blocks.append(best)
        return best


class PBSMarket:
    """
    Fee-bid PBS simulation market.

    Not MEV protection: all builders see the same txs and return the same set.
    """

    def __init__(self):
        self.builders: List[Builder] = []
        self.proposers: List[Proposer] = []

    def add_builder(self, builder: Builder):
        self.builders.append(builder)

    def add_proposer(self, proposer: Proposer):
        self.proposers.append(proposer)

    def run_auction(self, transactions: List[Dict]) -> Optional[Dict]:
        """
        Run fee-bid auction simulation:
        1. Builders score the same transaction set
        2. Proposer selects highest fee sum
        Does not reorder or protect against MEV.
        """
        if not self.builders or not self.proposers:
            return None

        bids = []
        for builder in self.builders:
            block = builder.build_block(transactions)
            bids.append(block)

        proposer = self.proposers[0]
        selected = proposer.select_block(bids)
        if selected is not None:
            selected["ordering_applied"] = False
            selected["mev_protection"] = False
            selected["simulation_only"] = True
        return selected

    def get_stats(self) -> Dict[str, Any]:
        return {
            "builders": len(self.builders),
            "proposers": len(self.proposers),
            "mev_protection": False,
            "ordering_applied": False,
            "simulation_only": True,
            "note": "fee-bid PBS simulation; not MEV protection",
        }
