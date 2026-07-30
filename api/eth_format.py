# api/eth_format.py — ADR 0011 WS-safe eth formatters (no RESTHandler)
"""Block/tx/receipt/log formatting shared by JSON-RPC and WebSocket."""

from __future__ import annotations

from typing import Dict, List, Optional

from api.ports import BlockQuery, LogsQuery, QueryLimitError, QueryTimeoutError


def format_block(blk: Optional[Dict], full_tx: bool = False) -> Optional[Dict]:
    if not blk:
        return None
    if blk.get("_full_tx_truncated"):
        full_tx = False
    state_root = blk.get("state_root", "") or ""
    if state_root and not str(state_root).startswith("0x"):
        state_root = "0x" + str(state_root)
    txs = blk.get("transactions", [])
    tx_hashes = [
        tx.get("hash", "") if isinstance(tx, dict) else str(tx)
        for tx in (txs if isinstance(txs, list) else [])
    ]
    return {
        "number": hex(blk.get("height", 0)),
        "hash": blk.get("hash", blk.get("block_hash", "")),
        "parentHash": blk.get("parent_hash", ""),
        "nonce": "0x0000000000000000",
        "sha3Uncles": "0x" + "0" * 64,
        "logsBloom": "0x" + "0" * 512,
        "transactionsRoot": "0x" + "0" * 64,
        "stateRoot": state_root or ("0x" + "0" * 64),
        "receiptsRoot": "0x" + "0" * 64,
        "miner": blk.get("miner", blk.get("proposer", "")),
        "difficulty": "0x0",
        "totalDifficulty": "0x0",
        "extraData": "0x",
        "size": hex(256 + len(tx_hashes) * 32),
        "gasLimit": hex(30_000_000),
        "gasUsed": hex(blk.get("gas_used", 0)),
        "timestamp": hex(blk.get("timestamp", 0)),
        "uncles": [],
        "transactions": txs if full_tx else tx_hashes,
        "totalBurned": blk.get("total_burned", 0.0),
        "txCount": blk.get("tx_count", len(tx_hashes)),
    }


def format_tx(tx: Optional[Dict]) -> Optional[Dict]:
    if not tx:
        return None
    return {
        "hash": tx.get("hash", tx.get("tx_hash", "")),
        "blockNumber": hex(tx.get("block_height", 0)),
        "from": tx.get("from_addr", tx.get("from", "")),
        "to": tx.get("to_addr", tx.get("to", "")),
        "value": hex(int(float(tx.get("value", tx.get("amount", 0))) * 10**18)),
        "gas": hex(tx.get("gas", 21000)),
        "gasUsed": hex(tx.get("gas_used", tx.get("gas", 21000))),
        "nonce": hex(tx.get("nonce", 0)),
        "input": tx.get("data", tx.get("tx_data", "0x")),
        "burned": tx.get("burned", 0.0),
    }


def resolve_block_tag_to_height(bc_or_query, tag) -> int:
    tip_fn = getattr(bc_or_query, "tip_height", None)
    get_height = getattr(bc_or_query, "get_height", None)
    if tag in (None, "", "earliest"):
        return 0
    if tag in ("latest", "pending"):
        if callable(tip_fn):
            return int(tip_fn())
        if callable(get_height):
            return int(get_height())
        return 0
    try:
        return int(tag, 16) if str(tag).startswith("0x") else int(tag)
    except (TypeError, ValueError):
        return 0


def normalize_log_data(data) -> str:
    raw = str(data or "")
    if not raw or raw == "0x":
        return "0x"
    return raw if raw.startswith("0x") else "0x" + raw


def tx_index_in_block(bc, block_height: int, tx_hash: str) -> int:
    if not bc or not tx_hash:
        return 0
    blk = None
    get_block = getattr(bc, "get_block", None)
    if callable(get_block):
        try:
            blk = bc.get_block(BlockQuery(height=int(block_height)))
        except TypeError:
            blk = bc.get_block(int(block_height))
        except Exception:
            blk = None
    if not blk:
        return 0
    txs = blk.get("transactions", [])
    if not isinstance(txs, list):
        return 0
    target = tx_hash.lower()
    for idx, entry in enumerate(txs):
        if isinstance(entry, dict):
            h = str(entry.get("hash", entry.get("tx_hash", ""))).lower()
        else:
            h = str(entry).lower()
        if h == target:
            return idx
    return 0


def format_eth_log(row: Dict, bc=None) -> Dict:
    block_height = int(row.get("block_height", 0))
    block_hash = ""
    if bc is not None:
        blk = None
        get_block = getattr(bc, "get_block", None)
        if callable(get_block):
            try:
                blk = bc.get_block(BlockQuery(height=block_height))
            except TypeError:
                try:
                    blk = bc.get_block(block_height)
                except Exception:
                    blk = None
            except Exception:
                blk = None
        if blk:
            block_hash = blk.get("hash", blk.get("block_hash", ""))
    tx_hash = row.get("tx_hash", "")
    topics = row.get("topics", [])
    if not isinstance(topics, list):
        topics = []
    return {
        "removed": False,
        "logIndex": hex(int(row.get("log_index", 0))),
        "transactionIndex": hex(tx_index_in_block(bc, block_height, tx_hash)),
        "transactionHash": tx_hash,
        "blockHash": block_hash,
        "blockNumber": hex(block_height),
        "address": row.get("contract_address", ""),
        "data": normalize_log_data(row.get("data", "")),
        "topics": topics,
    }


def format_receipt(tx: Optional[Dict], bc=None, query=None) -> Optional[Dict]:
    if not tx:
        return None
    from storage.database import Database

    tx_hash = tx.get("hash", tx.get("tx_hash", ""))
    logs: List[Dict] = []
    facade = query
    if facade is not None and hasattr(facade, "get_evm_logs_by_tx"):
        rows = facade.get_evm_logs_by_tx(tx_hash)
        logs = [format_eth_log(row, facade) for row in rows]
    elif bc is not None and getattr(bc, "query_facade", None) is not None:
        rows = bc.query_facade.get_evm_logs_by_tx(tx_hash)
        logs = [format_eth_log(row, bc.query_facade) for row in rows]
    status_i = Database._normalize_tx_status(tx.get("status"))
    return {
        "transactionHash": tx_hash,
        "blockNumber": hex(tx.get("block_height", 0)),
        "from": tx.get("from_addr", tx.get("from", "")),
        "to": tx.get("to_addr", tx.get("to", "")),
        "status": hex(status_i),
        "gasUsed": hex(tx.get("gas_used", tx.get("gas", 21000))),
        "logs": logs,
        "burned": tx.get("burned", 0.0),
    }


def handle_eth_get_logs(filt: Dict, bc=None, query=None) -> List[Dict]:
    facade = query
    if facade is None and bc is not None:
        facade = getattr(bc, "query_facade", None)

    from_block = resolve_block_tag_to_height(facade or bc, filt.get("fromBlock", "0x0"))
    to_block = resolve_block_tag_to_height(facade or bc, filt.get("toBlock", "latest"))
    if to_block < from_block:
        return []

    address = filt.get("address")
    addresses: tuple = ()
    if address:
        addresses = tuple(address if isinstance(address, list) else [address])
    topics = filt.get("topics")
    topics_t = tuple(topics) if isinstance(topics, list) else ()

    if facade is not None and hasattr(facade, "query_logs"):
        q = LogsQuery(
            from_block=from_block,
            to_block=to_block,
            addresses=addresses,
            topics=topics_t,
            limit=int(filt.get("limit") or 1000),
        )
        try:
            rows = facade.query_logs(q)
        except (QueryLimitError, QueryTimeoutError):
            raise
        return [format_eth_log(row, facade) for row in rows]

    store = getattr(bc, "db", None) if bc is not None else None
    if store is None or not hasattr(store, "query_evm_logs"):
        return []
    rows = store.query_evm_logs(
        from_block=from_block,
        to_block=to_block,
        addresses=list(addresses) if addresses else None,
        topics=list(topics_t) if topics_t else None,
    )
    return [format_eth_log(row, bc) for row in rows]


def resolve_block_by_tag(bc, tag: str, query=None) -> Optional[Dict]:
    facade = query or (getattr(bc, "query_facade", None) if bc else None)
    if facade is not None:
        return facade.get_block(BlockQuery(tag=str(tag or "latest")))
    if not bc:
        return None
    if tag in ("latest", "pending"):
        return bc.get_last_block()
    try:
        height = int(tag, 16) if str(tag).startswith("0x") else int(tag)
        return bc.get_block(height)
    except (TypeError, ValueError):
        return None


def tx_at_block_index(bc, blk: Optional[Dict], index: int, query=None) -> Optional[Dict]:
    facade = query or (getattr(bc, "query_facade", None) if bc else None)
    if not blk or index < 0:
        return None
    txs = blk.get("transactions", [])
    if not isinstance(txs, list) or index >= len(txs):
        return None
    entry = txs[index]
    if isinstance(entry, dict):
        return entry
    tx_hash = str(entry)
    if facade is not None:
        return facade.get_transaction(tx_hash)
    if bc is not None and hasattr(bc, "get_transaction"):
        return bc.get_transaction(tx_hash)
    return None


# Compat aliases
_format_block = format_block
_format_tx = format_tx
_format_receipt = format_receipt
_handle_eth_get_logs = handle_eth_get_logs
_resolve_block_by_tag = resolve_block_by_tag
_format_eth_log = format_eth_log
