#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Absolute Cross-Chain Bridge

Два режима работы (задаётся в Config.bridge_mode):
  "simulator" — Python-симулятор на основе cross_chain_bridge.py
  "rust"      — вызов скомпилированного Rust-бинарника через subprocess

Поддерживаемые сети: Ethereum, BSC, Solana, Absolute (ABS)
"""

import json
import sys
import os
import subprocess
import time
import threading
from typing import Dict, List, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from cross_chain_bridge import CrossChainBridge, BridgeTransaction, Chain
from storage.database import Database
from runtime.config import Config
from kernel.event_bus import EventBus


class BridgeLock:
    """Запись о заблокированных средствах (ждут подтверждения на другой стороне)."""

    def __init__(self, tx_hash: str, from_addr: str, to_chain: str,
                 to_addr: str, amount: float):
        self.tx_hash = tx_hash
        self.from_addr = from_addr
        self.to_chain = to_chain
        self.to_addr = to_addr
        self.amount = amount
        self.status = "pending"  # pending | confirmed | failed
        self.created_at = int(time.time())
        self.confirmed_at: Optional[int] = None


class RustBridge:
    """
    Обёртка над Python-симулятором / Rust-бинарником кросс-чейн моста.

    Жизненный цикл транзакции:
      1. lock_and_bridge()   — блокируем ABS на нашей цепи, инициируем перевод
      2. confirm_incoming()  — получаем подтверждение с внешней цепи, начисляем ABS
      3. refund()            — если перевод завершился ошибкой — возвращаем ABS
    """

    SUPPORTED_CHAINS = [c.value for c in Chain]

    CHAIN_ALIASES = {
        "eth": "ethereum",
        "ether": "ethereum",
        "ethereum": "ethereum",
        "bnb": "bsc",
        "bsc": "bsc",
        "binance": "bsc",
        "sol": "solana",
        "solana": "solana",
        "abs": "absolute",
        "absolute": "absolute",
    }

    def _normalize_chain(self, chain: str) -> str:
        key = (chain or "").strip().lower()
        return self.CHAIN_ALIASES.get(key, key)

    # Тарифы моста (% от суммы)
    BRIDGE_FEES = {
        "ethereum": 0.01,   # 1%
        "bsc":      0.002,  # 0.2%
        "solana":   0.001,  # 0.1%
        "absolute": 0.005,  # 0.5%
    }

    def __init__(self, config: Config, db: Database, bus: Optional[EventBus] = None):
        self.config = config
        self.db = db
        self.bus = bus
        self._running = False
        self._lock = threading.Lock()

        # Инициализируем Python-симулятор
        self._simulator = CrossChainBridge()

        # Подписываемся на входящие bridge-события
        if self.bus:
            self.bus.on("bridge.incoming", self._on_incoming)

        # Если включён Rust-режим — проверяем наличие бинарника
        self._rust_bin = self._resolve_rust_bin()
        if config.bridge_mode == "rust":
            if not self._rust_bin:
                msg = "Rust bridge binary not found"
                print(f"[Bridge] ERROR: {msg} at '{config.rust_bridge_path}'")
                if getattr(config, "deployment_mode", "dev") == "prod":
                    raise RuntimeError(msg)
                print("[Bridge] Falling back to simulator (dev only).")
                self._mode = "simulator"
            else:
                self._mode = "rust"
                print(f"[Bridge] Rust bridge: {self._rust_bin}")
        else:
            self._mode = "simulator"

        print(f"[Bridge] Initialized in '{self._mode}' mode. "
              f"Supported chains: {', '.join(self.SUPPORTED_CHAINS)}")

    async def start(self):
        """Запускает фоновую обработку моста (подтверждения)."""
        self._running = True
        import asyncio
        while self._running:
            await asyncio.sleep(5)
            self._process_pending()

    def stop(self):
        self._running = False

    # ── Отправка ─────────────────────────────────────────────────────────────

    def lock_and_bridge(self, from_addr: str, to_chain: str,
                        to_addr: str, amount: float) -> Dict:
        """
        Блокирует ABS на нашей цепи и инициирует перевод на to_chain.

        Возвращает: {"tx_hash": str, "fee": float, "net_amount": float, "status": str}
        """
        to_chain = self._normalize_chain(to_chain)
        if to_chain not in self.SUPPORTED_CHAINS:
            return {"error": f"Unsupported chain: {to_chain}. "
                             f"Supported: {', '.join(self.SUPPORTED_CHAINS)}"}

        fee_rate = self.BRIDGE_FEES.get(to_chain, 0.01)
        fee = amount * fee_rate
        net_amount = amount - fee

        if net_amount <= 0:
            return {"error": "Amount too small after fee"}

        # Проверяем баланс отправителя
        balance = self.db.get_balance(from_addr)
        if balance < amount:
            return {"error": "Insufficient balance"}

        # Выбираем режим
        if self._mode == "rust":
            tx_hash = self._call_rust("bridge", {
                "from_chain": "absolute",
                "to_chain": to_chain,
                "from_addr": from_addr,
                "to_addr": to_addr,
                "amount": net_amount,
            })
            if not tx_hash:
                if getattr(self.config, "deployment_mode", "dev") == "prod":
                    return {"error": "rust bridge call failed"}
                tx_hash = self._simulator.bridge(
                    "absolute", to_chain, from_addr, to_addr, net_amount
                )
        else:
            tx_hash = self._simulator.bridge(
                "absolute", to_chain, from_addr, to_addr, net_amount
            )

        # Списываем с отправителя
        self.db.update_balance(from_addr, -amount)
        # Сжигаем комиссию (2% от fee — bridge burn)
        bridge_burn = fee * self.config.burn_rate
        self.db.update_balance(self.config.burn_address, bridge_burn)

        # Сохраняем lock в БД
        self.db.save_bridge_lock(from_addr, to_chain, to_addr, net_amount, tx_hash)

        if self.bus:
            self.bus.emit("bridge.locked", {
                "tx_hash": tx_hash,
                "from": from_addr,
                "to_chain": to_chain,
                "to_addr": to_addr,
                "amount": net_amount,
                "fee": fee,
            })

        return {
            "tx_hash": tx_hash,
            "from_addr": from_addr,
            "to_chain": to_chain,
            "to_addr": to_addr,
            "amount": amount,
            "fee": fee,
            "net_amount": net_amount,
            "status": "pending",
        }

    # ── Подтверждение входящего перевода ─────────────────────────────────────

    def confirm_incoming(self, tx_hash: str, recipient: str,
                         amount: float, from_chain: str) -> Dict:
        """
        Подтверждает входящий перевод с внешней цепи — начисляет ABS получателю.
        Вызывается оракулом / Rust-мостом при получении подтверждения.
        """
        credit_key = self.db.bridge_credit_key(tx_hash, recipient, amount, from_chain)
        if self.db.has_bridge_credit(credit_key):
            return {
                "confirmed": True,
                "duplicate": True,
                "tx_hash": tx_hash,
                "recipient": recipient,
                "amount": amount,
                "mode": self._mode,
            }

        if self._mode == "rust":
            if not self._call_rust_ok("incoming", {
                "tx_hash": tx_hash,
                "recipient": recipient,
                "amount": amount,
                "from_chain": from_chain,
            }):
                return {"confirmed": False, "error": "rust incoming failed"}

        self.db.update_balance(recipient, amount)
        self.db.save_bridge_credit(tx_hash, recipient, amount, from_chain)
        self.db.confirm_bridge_lock(tx_hash)
        self._simulator.confirm_transaction(tx_hash)

        if self.bus:
            self.bus.emit("bridge.confirmed", {
                "tx_hash": tx_hash,
                "recipient": recipient,
                "amount": amount,
                "from_chain": from_chain,
            })

        return {
            "confirmed": True,
            "tx_hash": tx_hash,
            "recipient": recipient,
            "amount": amount,
            "mode": self._mode,
        }

    def refund(self, tx_hash: str) -> Dict:
        """Возвращает заблокированные средства при ошибке."""
        locks = self.db.get_bridge_locks()
        for lock in locks:
            if lock["tx_hash"] == tx_hash and lock["status"] == "pending":
                self.db.update_balance(lock["from_addr"], lock["amount"])
                self.db.conn.execute(
                    "UPDATE bridge_locks SET status='refunded' WHERE tx_hash=?",
                    (tx_hash,)
                )
                self.db.conn.commit()
                return {"refunded": True, "tx_hash": tx_hash,
                        "amount": lock["amount"]}
        return {"refunded": False, "error": "Lock not found or already processed"}

    # ── Информация ───────────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        sim_stats = self._simulator.get_bridge_stats()
        locks = self.db.get_bridge_locks(limit=1000)
        return {
            "mode": self._mode,
            "supported_chains": self.SUPPORTED_CHAINS,
            "bridge_fees": self.BRIDGE_FEES,
            "total_locks": len(locks),
            "pending_locks": sum(1 for l in locks if l["status"] == "pending"),
            "confirmed_locks": sum(1 for l in locks if l["status"] == "confirmed"),
            "simulator_stats": sim_stats,
        }

    def estimate_fee(self, to_chain: str, amount: float) -> Dict:
        fee_rate = self.BRIDGE_FEES.get(to_chain.lower(), 0.01)
        fee = amount * fee_rate
        return {
            "chain": to_chain,
            "amount": amount,
            "fee": fee,
            "fee_pct": fee_rate * 100,
            "net_amount": amount - fee,
        }

    # ── Служебные методы ─────────────────────────────────────────────────────

    def _on_incoming(self, event: Dict):
        """EventBus колбэк для входящих бридж-транзакций."""
        if isinstance(event, dict):
            self.confirm_incoming(
                tx_hash=event.get("tx_hash", ""),
                recipient=event.get("recipient", ""),
                amount=float(event.get("amount", 0)),
                from_chain=event.get("from_chain", ""),
            )

    def confirm_lock(self, tx_hash: str) -> Dict:
        """Confirm outbound bridge lock (oracle / admin). No balance change — funds already locked."""
        locks = self.db.get_bridge_locks(limit=1000)
        for lock in locks:
            if lock["tx_hash"] == tx_hash and lock["status"] == "pending":
                if self._mode == "rust":
                    if not self._call_rust_ok("confirm", {"tx_hash": tx_hash}):
                        return {"confirmed": False, "error": "rust confirm failed"}
                self._simulator.confirm_transaction(tx_hash)
                self.db.confirm_bridge_lock(tx_hash)
                if self.bus:
                    self.bus.emit("bridge.confirmed", {
                        "tx_hash": tx_hash,
                        "direction": "outbound",
                        "to_chain": lock.get("to_chain", ""),
                    })
                return {
                    "confirmed": True,
                    "tx_hash": tx_hash,
                    "direction": "outbound",
                    "mode": self._mode,
                }
        return {"confirmed": False, "error": "pending lock not found"}

    def confirm_pending_locks(self) -> Dict:
        """Confirm every pending outbound bridge lock (devnet / manual batch)."""
        confirmed: List[str] = []
        errors: List[Dict] = []
        for lock in self.db.get_bridge_locks(limit=1000):
            if lock.get("status") != "pending":
                continue
            tx_hash = lock.get("tx_hash", "")
            result = self.confirm_lock(tx_hash)
            if result.get("confirmed"):
                confirmed.append(tx_hash)
            else:
                errors.append({"tx_hash": tx_hash, "error": result.get("error", "failed")})
        return {
            "success": len(confirmed) > 0,
            "confirmed": confirmed,
            "count": len(confirmed),
            "pending_remaining": sum(
                1 for l in self.db.get_bridge_locks(limit=1000) if l.get("status") == "pending"
            ),
            "errors": errors,
            "mode": self._mode,
        }

    def _process_pending(self):
        """
        Auto-confirm pending outbound locks when bridge_auto_confirm_sec > 0.
        Set bridge_auto_confirm_sec=0 for manual oracle confirmation only.
        """
        sec = int(getattr(self.config, "bridge_auto_confirm_sec", 0) or 0)
        if self._mode != "simulator" or sec <= 0:
            return
        locks = self.db.get_bridge_locks()
        now = int(time.time())
        for lock in locks:
            if lock["status"] == "pending" and now - lock["created_at"] > sec:
                self.confirm_lock(lock["tx_hash"])

    def _resolve_rust_bin(self) -> Optional[str]:
        path = getattr(self.config, "resolve_rust_bridge_path", None)
        if callable(path):
            resolved = self.config.resolve_rust_bridge_path()
            return resolved if os.path.isfile(resolved) else None
        for candidate in (
            self.config.rust_bridge_path,
            self.config.rust_bridge_path + ".exe",
        ):
            if os.path.isfile(candidate):
                return candidate
        return None

    def _call_rust(self, command: str, args: Dict) -> Optional[str]:
        """Вызывает Rust-бинарник через subprocess и возвращает tx_hash."""
        out = self._call_rust_raw(command, args)
        return out.get("tx_hash") if out else None

    def _call_rust_ok(self, command: str, args: Dict) -> bool:
        out = self._call_rust_raw(command, args)
        return bool(out and out.get("status") == "ok" and out.get("tx_hash"))

    def _call_rust_raw(self, command: str, args: Dict) -> Optional[Dict]:
        """Вызывает Rust-бинарник и возвращает полный JSON-ответ."""
        exe = self._rust_bin or self._resolve_rust_bin()
        if not exe:
            return None
        try:
            payload = json.dumps({"command": command, "args": args})
            result = subprocess.run(
                [exe],
                input=payload.encode(),
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                return json.loads(result.stdout.decode())
        except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
            print(f"[Bridge] Rust call failed: {e}. Falling back to simulator.")
        return None
