"""Wire-format helpers for P2P mempool gossip (full signed tx payloads)."""
from __future__ import annotations

from typing import Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from blockchain.mempool import MempoolTransaction


def mempool_tx_to_wire(tx: "MempoolTransaction") -> Dict:
    """Serialize mempool tx for P2P — must round-trip through _ingest_peer_tx."""
    return {
        "hash": tx.tx_hash,
        "tx_hash": tx.tx_hash,
        "from_addr": tx.from_addr,
        "from": tx.from_addr,
        "to_addr": tx.to_addr,
        "to": tx.to_addr,
        "value": float(tx.amount),
        "amount": float(tx.amount),
        "fee": float(tx.fee),
        "nonce": int(tx.nonce),
        "signature": tx.signature or "",
        "public_key": tx.public_key or "",
        "data": tx.data or "",
        "gas": int(getattr(tx, "gas", 0) or 21_000),
        "timestamp": float(tx.timestamp),
    }
