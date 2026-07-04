#!/usr/bin/env python3
"""Ethereum JSON-RPC WebSocket subscriptions (eth_subscribe / eth_unsubscribe)."""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional, Set


class EthWsSubscriptionManager:
    """Per-connection and global subscription registry for eth_subscribe."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._next_id = 1
        self._subs: Dict[int, Dict[str, Any]] = {}
        self._conn_subs: Dict[int, Set[int]] = {}

    def subscribe(self, conn_id: int, sub_type: str, filt: Optional[dict] = None) -> str:
        sub_type = (sub_type or "").strip()
        if sub_type not in ("newHeads", "logs", "newPendingTransactions", "syncing"):
            raise ValueError(f"unsupported subscription type: {sub_type}")
        with self._lock:
            sid = self._next_id
            self._next_id += 1
            self._subs[sid] = {
                "type": sub_type,
                "filter": dict(filt or {}),
                "conn_id": conn_id,
                "created_at": time.time(),
                "last_block": -1,
            }
            self._conn_subs.setdefault(conn_id, set()).add(sid)
        return hex(sid)

    def unsubscribe(self, conn_id: int, sub_id) -> bool:
        try:
            sid = int(sub_id, 16) if str(sub_id).startswith("0x") else int(sub_id)
        except (TypeError, ValueError):
            return False
        with self._lock:
            row = self._subs.get(sid)
            if not row or row.get("conn_id") != conn_id:
                return False
            del self._subs[sid]
            conn_set = self._conn_subs.get(conn_id)
            if conn_set:
                conn_set.discard(sid)
            return True

    def drop_connection(self, conn_id: int) -> None:
        with self._lock:
            for sid in list(self._conn_subs.get(conn_id, set())):
                self._subs.pop(sid, None)
            self._conn_subs.pop(conn_id, None)

    def subscribers(self, sub_type: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                {"id": sid, **row}
                for sid, row in self._subs.items()
                if row.get("type") == sub_type
            ]

    def format_notification(self, sub_id: int, result: Any) -> dict:
        return {
            "jsonrpc": "2.0",
            "method": "eth_subscription",
            "params": {"subscription": hex(sub_id), "result": result},
        }

    def get_subscription(self, sub_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            row = self._subs.get(sub_id)
            return dict(row) if row else None

    def handle_rpc(
        self,
        conn_id: int,
        method: str,
        params: list,
        format_block: Callable[[Any], Optional[dict]],
        query_logs: Callable[[dict, Any], List[dict]],
        blockchain,
    ) -> Any:
        if method == "eth_subscribe":
            sub_type = params[0] if params else ""
            filt = params[1] if len(params) > 1 else {}
            if filt is not None and not isinstance(filt, dict):
                raise ValueError("eth_subscribe filter must be object")
            sub_id = self.subscribe(conn_id, sub_type, filt)
            if sub_type == "syncing":
                return sub_id
            return sub_id

        if method == "eth_unsubscribe":
            sub_id = params[0] if params else ""
            return self.unsubscribe(conn_id, sub_id)

        if method == "eth_chainId":
            cfg = getattr(blockchain, "config", None)
            chain_id = getattr(cfg, "chain_id", 77777) if cfg else 77777
            return hex(chain_id)

        raise ValueError(f"Method not supported: {method}")

    def on_new_block(
        self,
        block: dict,
        format_block: Callable[[Any], Optional[dict]],
        query_logs: Callable[[dict, Any], List[dict]],
        blockchain,
        send_fn: Callable[[int, dict], None],
    ) -> None:
        if not block:
            return
        height = int(block.get("height", block.get("number", 0)) or 0)
        header = format_block(block)
        for row in self.subscribers("newHeads"):
            send_fn(row["id"], self.format_notification(row["id"], header))
        for row in self.subscribers("logs"):
            sid = row["id"]
            last = int(row.get("last_block", -1))
            if height <= last:
                continue
            filt = dict(row.get("filter") or {})
            filt["fromBlock"] = hex(last + 1 if last >= 0 else height)
            filt["toBlock"] = hex(height)
            logs = query_logs(filt, blockchain) if blockchain else []
            for log in logs:
                send_fn(sid, self.format_notification(sid, log))
            with self._lock:
                if sid in self._subs:
                    self._subs[sid]["last_block"] = height

    def on_new_tx(self, tx: dict, send_fn: Callable[[int, dict], None]) -> None:
        tx_hash = tx.get("hash", tx.get("tx_hash", "")) if isinstance(tx, dict) else ""
        if not tx_hash:
            return
        if not str(tx_hash).startswith("0x"):
            tx_hash = "0x" + str(tx_hash)
        for row in self.subscribers("newPendingTransactions"):
            sid = row["id"]
            send_fn(sid, self.format_notification(sid, tx_hash))
