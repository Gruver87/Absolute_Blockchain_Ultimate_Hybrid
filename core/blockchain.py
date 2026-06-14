#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Absolute Blockchain — ядро цепочки блоков.

Содержит:
  - Transaction     : структура транзакции (c ECDSA подписью)
  - Block           : структура блока (c state_root + canonical hash)
  - Blockchain      : основная логика (burn mechanism, StateEngine, BlockValidator)

Интегрирует из всех трёх систем:
  - System A: Transaction/Block/burn/genesis (основа)
  - System C: StateEngine (детерминированный state_root)
  - blockchain/canonical_serializer.py: детерминированный хэш блока
  - execution/block_validator.py: валидация блоков из P2P
"""

import hashlib
import json
import time
import threading
from typing import List, Dict, Optional, Any

from storage.database import Database
from runtime.config import Config
from runtime.tokenomics import genesis_balances, get_tokenomics_summary, MAX_SUPPLY_ABS
from kernel.event_bus import EventBus

# --- System C: StateEngine (детерминированные state transitions) ---
try:
    from execution.state_engine import StateEngine
    _STATE_ENGINE_AVAILABLE = True
except ImportError:
    _STATE_ENGINE_AVAILABLE = False

# --- CanonicalSerializer (детерминированный хэш) ---
try:
    from blockchain.canonical_serializer import CanonicalSerializer
    _CANONICAL_AVAILABLE = True
except ImportError:
    _CANONICAL_AVAILABLE = False

# --- BlockValidator (валидация P2P-блоков) ---
try:
    from execution.block_validator import BlockValidator
    _BLOCK_VALIDATOR_AVAILABLE = True
except ImportError:
    _BLOCK_VALIDATOR_AVAILABLE = False


# ── Структуры данных ─────────────────────────────────────────────────────────

class Transaction:
    """Транзакция в сети Absolute (с поддержкой ECDSA-подписи)."""

    def __init__(
        self,
        from_addr: str,
        to_addr: str,
        value: float,
        nonce: int = 0,
        gas: int = 21_000,
        data: str = "",
        tx_hash: str = "",
        signature: str = "",
        public_key: str = "",
        timestamp: int = 0,
    ):
        self.from_addr = from_addr
        self.to_addr = to_addr
        self.value = value
        self.nonce = nonce
        self.gas = gas
        self.data = data
        self.signature = signature
        self.public_key = public_key
        self.timestamp = timestamp or int(time.time())
        self.hash = tx_hash or self._compute_hash()

        # Заполняется при включении в блок
        self.block_height: int = 0
        self.gas_used: int = gas
        self.fee: float = 0.0
        self.burned: float = 0.0

    def _compute_hash(self) -> str:
        raw = f"{self.from_addr}{self.to_addr}{self.value}{self.nonce}{self.gas}{self.data}{self.timestamp}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self) -> Dict:
        return {
            "hash": self.hash,
            "from_addr": self.from_addr,
            "to_addr": self.to_addr,
            "value": self.value,
            "nonce": self.nonce,
            "gas": self.gas,
            "gas_used": self.gas_used,
            "fee": self.fee,
            "burned": self.burned,
            "data": self.data,
            "signature": self.signature,
            "public_key": self.public_key,
            "timestamp": self.timestamp,
            "block_height": self.block_height,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Transaction":
        tx = cls(
            from_addr=d.get("from_addr", d.get("from", "")),
            to_addr=d.get("to_addr", d.get("to", "")),
            value=float(d.get("value", d.get("amount", 0))),
            nonce=int(d.get("nonce", 0)),
            gas=int(d.get("gas", 21_000)),
            data=d.get("data", d.get("tx_data", "")),
            tx_hash=d.get("hash", d.get("tx_hash", "")),
            signature=d.get("signature", ""),
            public_key=d.get("public_key", ""),
            timestamp=int(d.get("timestamp", 0)),
        )
        tx.fee = float(d.get("fee", 0.0))
        tx.burned = float(d.get("burned", 0.0))
        tx.block_height = int(d.get("block_height", 0))
        return tx

    def __repr__(self) -> str:
        return f"Tx({self.hash[:10]}... {self.from_addr[:8]}->{self.to_addr[:8]} {self.value} ABS)"


class Block:
    """Блок в цепочке Absolute (с state_root и canonical hash)."""

    def __init__(
        self,
        height: int,
        parent_hash: str,
        miner: str,
        transactions: Optional[List[Transaction]] = None,
        timestamp: int = 0,
        block_hash: str = "",
        extra_data: str = "",
        state_root: str = "",
    ):
        self.height = height
        self.parent_hash = parent_hash
        self.miner = miner
        self.transactions: List[Transaction] = transactions or []
        self.timestamp = timestamp or int(time.time())
        self.extra_data = extra_data
        self.state_root = state_root  # deterministic state root (System C)
        self.tx_root = self._compute_tx_root()

        # Вычисляемые поля
        self.tx_count = len(self.transactions)
        self.gas_used: int = sum(tx.gas_used for tx in self.transactions)
        self.total_burned: float = sum(tx.burned for tx in self.transactions)

        self.hash = block_hash or self._compute_hash()

    def _compute_tx_root(self) -> str:
        """Merkle root транзакций блока (для SPV / light client)."""
        try:
            from crypto.merkle import merkle_root
            items = [tx.hash for tx in self.transactions] if self.transactions else []
            return merkle_root(items) if items else merkle_root(["empty"])
        except Exception:
            return hashlib.sha256(b"empty").hexdigest()

    def _compute_hash(self) -> str:
        """Детерминированный хэш блока через CanonicalSerializer."""
        if _CANONICAL_AVAILABLE:
            try:
                block_dict = {
                    "height": self.height,
                    "parent_hash": self.parent_hash,
                    "miner": self.miner,
                    "timestamp": self.timestamp,
                    "extra_data": self.extra_data,
                    "state_root": self.state_root,
                    "transactions": [
                        {"hash": tx.hash, "from": tx.from_addr, "to": tx.to_addr,
                         "amount": tx.value, "fee": tx.fee, "nonce": tx.nonce,
                         "timestamp": tx.timestamp}
                        for tx in sorted(self.transactions, key=lambda t: t.hash)
                    ],
                }
                canonical = CanonicalSerializer.serialize(block_dict)
                return hashlib.sha256(canonical.encode()).hexdigest()
            except Exception:
                pass

        # Fallback: simple hash
        tx_hashes = "".join(tx.hash for tx in self.transactions)
        raw = (
            f"{self.height}{self.parent_hash}{self.miner}"
            f"{self.timestamp}{tx_hashes}{self.extra_data}{self.state_root}"
        )
        return hashlib.sha256(raw.encode()).hexdigest()

    def to_dict(self) -> Dict:
        return {
            "height": self.height,
            "hash": self.hash,
            "parent_hash": self.parent_hash,
            "miner": self.miner,
            "timestamp": self.timestamp,
            "tx_count": self.tx_count,
            "gas_used": self.gas_used,
            "total_burned": self.total_burned,
            "extra_data": self.extra_data,
            "state_root": self.state_root,
            "tx_root": self.tx_root,
            "transactions": [tx.to_dict() for tx in self.transactions],
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Block":
        txs = [Transaction.from_dict(t) for t in d.get("transactions", [])]
        blk = cls(
            height=int(d.get("height", d.get("number", 0))),
            parent_hash=d.get("parent_hash", "0" * 64),
            miner=d.get("miner", d.get("proposer", "")),
            transactions=txs,
            timestamp=d.get("timestamp", 0),
            block_hash=d.get("hash", d.get("block_hash", "")),
            extra_data=d.get("extra_data", ""),
            state_root=d.get("state_root", ""),
        )
        blk.total_burned = float(d.get("total_burned", 0.0))
        return blk

    def __repr__(self) -> str:
        return (
            f"Block(#{self.height} hash={self.hash[:10]}... "
            f"txs={self.tx_count} burned={self.total_burned:.4f})"
        )


# ── Основная логика ───────────────────────────────────────────────────────────

class Blockchain:
    """
    Ядро блокчейна: создание/добавление блоков, применение транзакций,
    механизм сжигания, genesis.

    Включает:
    - StateEngine (System C) для детерминированного state_root
    - BlockValidator (System C) для валидации P2P-блоков
    - CanonicalSerializer для детерминированного хэша
    """

    GENESIS_HASH = "0" * 64

    def __init__(self, config: Config, db: Database, bus: Optional[EventBus] = None):
        self.config = config
        self.db = db
        self.bus = bus
        self.lock = threading.RLock()
        self.require_signatures = False

        # --- System C: StateEngine ---
        if _STATE_ENGINE_AVAILABLE:
            self.state_engine = StateEngine()
            self._init_state_engine()
            print("[Blockchain] StateEngine: enabled (deterministic state_root)")
        else:
            self.state_engine = None

        # --- System C: BlockValidator ---
        if _BLOCK_VALIDATOR_AVAILABLE and self.state_engine:
            self.block_validator = BlockValidator(self.state_engine, None)
            print("[Blockchain] BlockValidator: enabled")
        else:
            self.block_validator = None

        self.pool_locks = None  # runtime.pool_locks.PoolLockManager
        self.consensus_adapter = None  # wired from main.NodeOrchestrator
        self.evm = None  # execution.evm_adapter.EVMAdapter
        self._state_root_baseline = 0

        self._ensure_genesis()
        h = self.get_height()
        cutoff = int(getattr(self.config, "state_root_legacy_cutoff_height", 0) or 0)
        self._state_root_baseline = max(cutoff, h)

    def _init_state_engine(self):
        """Инициализирует StateEngine из данных genesis или текущего состояния БД."""
        if not self.state_engine:
            return
        founder = (
            getattr(self.config, "founder_address", "")
            or self.config.miner_address
            or ""
        )
        genesis_alloc = genesis_balances(founder or None)
        if self.config.miner_address and self.config.miner_address not in genesis_alloc:
            genesis_alloc[self.config.miner_address] = int(
                getattr(self.config, "min_stake", 1000)
            )
        self.state_engine.create_genesis(genesis_alloc)

    # ── Genesis ──────────────────────────────────────────────────────────────

    def _ensure_genesis(self):
        if self.db.get_chain_tip() == 0 and self.db.get_last_block() is None:
            founder = (
                getattr(self.config, "founder_address", "")
                or self.config.miner_address
                or ""
            )
            alloc = genesis_balances(founder or None)
            state_root = self.state_engine.get_state_root() if self.state_engine else ""
            initials = getattr(self.config, "founder_initials", "D.U.P.")
            genesis = Block(
                height=0,
                parent_hash=self.GENESIS_HASH,
                miner="genesis",
                timestamp=int(time.time()),
                extra_data=(
                    f"{self.config.network_name} Genesis | "
                    f"max_supply={MAX_SUPPLY_ABS:,} ABS | founder={initials} {self.config.founder_percent}%"
                ),
                state_root=state_root,
            )
            self.db.save_block(genesis.to_dict())
            total_minted = 0.0
            for addr, amount in alloc.items():
                self.db.set_balance(addr, float(amount))
                total_minted += amount
            # Сохраняем метаданные токеномики
            try:
                self.db.set_meta("tokenomics", get_tokenomics_summary(founder or None))
            except Exception:
                pass
            print(
                f"[Blockchain] Genesis block created "
                f"(minted={total_minted:,.0f} {self.config.coin_symbol}, "
                f"max_supply={MAX_SUPPLY_ABS:,}, founder={initials} "
                f"{getattr(self.config, 'founder_percent', 17.4)}%)"
            )

    def set_state_root_baseline(self, height: int) -> None:
        """Blocks at or below baseline may use legacy warn-on-drift on P2P import."""
        self._state_root_baseline = int(height)

    def _state_root_check_mode(
        self, block_height: int, peer_root: str, preserve_peer: bool
    ) -> str:
        """Returns strict | legacy_warn | skip for peer state_root verification."""
        if not getattr(self.config, "verify_peer_state_root", True):
            return "skip"
        peer_root = str(peer_root or "").strip()
        if not peer_root:
            return "skip"
        if len(peer_root) < 64:
            return "legacy_warn"
        if preserve_peer:
            if getattr(self.config, "state_root_strict_p2p", True):
                if block_height <= self._state_root_baseline:
                    return "legacy_warn"
                return "strict"
            return "legacy_warn"
        if block_height <= self._state_root_baseline:
            return "legacy_warn"
        return "strict"

    def get_state_root_policy(self) -> Dict:
        return {
            "verify_peer_state_root": bool(
                getattr(self.config, "verify_peer_state_root", True)
            ),
            "state_root_strict_p2p": bool(
                getattr(self.config, "state_root_strict_p2p", True)
            ),
            "legacy_cutoff_height": int(
                getattr(self.config, "state_root_legacy_cutoff_height", 0) or 0
            ),
            "baseline_height": int(self._state_root_baseline),
            "policy": (
                "strict_p2p"
                if getattr(self.config, "state_root_strict_p2p", True)
                else "legacy_warn"
            ),
        }

    # ── Создание блока ───────────────────────────────────────────────────────

    def create_block(self, transactions: List[Transaction], proposer: str) -> Block:
        """Собирает новый блок: валидирует txs, state применяется в add_block()."""
        with self.lock:
            last = self.db.get_last_block()
            height = last["height"] + 1 if last else 1
            parent_hash = last["hash"] if last else self.GENESIS_HASH

            applied_txs = []
            nonce_cursor: Dict[str, int] = {}

            for tx in transactions:
                check = self._validate_tx_for_block(tx, nonce_cursor)
                if check["valid"]:
                    applied_txs.append(tx)
                    nonce_cursor[tx.from_addr] = tx.nonce + 1

            parent_ts = int(last["timestamp"]) if last else 0
            block_ts = max(int(time.time()), parent_ts + 1)

            return Block(
                height=height,
                parent_hash=parent_hash,
                miner=proposer,
                transactions=applied_txs,
                timestamp=block_ts,
                extra_data=f"v{self.config.node_version}",
            )

    # ── Добавление блока ─────────────────────────────────────────────────────

    def add_block(self, block: Block, preserve_peer_hash: bool = False) -> bool:
        """Валидирует, выполняет все txs + reward атомарно, сохраняет в БД."""
        peer_hash = block.hash if preserve_peer_hash else None
        with self.lock:
            if self.db.get_block(block.height):
                return False

            validation = self._validate_block_structure(block)
            if not validation["valid"]:
                print(f"[Blockchain] Reject block #{block.height}: {validation.get('error')}")
                return False

            proposer_check = self._verify_block_proposer(block)
            if not proposer_check["valid"]:
                print(f"[Blockchain] Reject block #{block.height}: {proposer_check.get('error')}")
                return False

            peer_state_root = block.state_root if preserve_peer_hash and block.state_root else None
            slashing = self._resolve_slashing_core()
            computed_root = None
            peer_root_for_audit = None

            try:
                with self.db.atomic():
                    block_burned = 0.0
                    for tx in block.transactions:
                        result = self._apply_transaction(
                            tx, block.height, proposer=block.miner, in_atomic=True
                        )
                        if not result["success"]:
                            raise RuntimeError(result.get("error", "tx_failed"))
                        block_burned += tx.burned

                    self._apply_block_reward(block.miner, in_atomic=True)
                    block.total_burned = block_burned
                    computed_root = self._compute_state_root_from_db()
                    if peer_state_root:
                        mode = self._state_root_check_mode(
                            block.height, peer_state_root, preserve_peer_hash
                        )
                        peer_root = str(peer_state_root).strip()
                        if mode != "skip" and peer_root != computed_root:
                            if mode == "strict":
                                peer_root_for_audit = peer_root
                                raise RuntimeError(
                                    f"state_root_mismatch expected={peer_root[:16]} "
                                    f"computed={computed_root[:16]}"
                                )
                            print(
                                f"[Blockchain] WARN #{block.height} state_root drift "
                                f"(peer={peer_root[:12]}… computed={computed_root[:12]}…) — legacy"
                            )
                    block.state_root = computed_root
                    block.hash = peer_hash if peer_hash else block._compute_hash()

                    if slashing and block.miner and block.miner != "genesis":
                        if not slashing.record_proposal(block.miner, block.height, block.hash):
                            raise RuntimeError("double_proposal")

                    tx_dicts = []
                    for tx in block.transactions:
                        tx.block_height = block.height
                        tx_dicts.append(tx.to_dict())

                    self.db._persist_block_locked(
                        block.to_dict(),
                        tx_dicts,
                        burned_amount=block.total_burned,
                        burn_address=self.config.burn_address if block.total_burned > 0 else "",
                    )
            except Exception as e:
                if (
                    peer_root_for_audit
                    and computed_root
                    and hasattr(self.db, "record_state_root_mismatch")
                ):
                    try:
                        self.db.record_state_root_mismatch(
                            block.height,
                            peer_root_for_audit,
                            computed_root,
                            source="p2p" if preserve_peer_hash else "local",
                            proposer=block.miner,
                        )
                    except Exception:
                        pass
                print(f"[Blockchain] Block execution failed #{block.height}: {e}")
                return False

            if self.bus:
                self.bus.emit("block.new", block.to_dict())
            return True

    def import_block(self, block_dict: Dict) -> bool:
        """Импортирует блок от P2P-пира с полным replay состояния."""
        normalized = self._normalize_block_dict(block_dict)
        height = int(normalized.get("height", normalized.get("number", 0)))
        with self.lock:
            existing = self.db.get_block(height)
            if existing and height == 0 and existing.get("hash") != normalized.get("hash"):
                self.db.truncate_all_blocks()
            elif existing:
                return False

            if self.block_validator:
                last = self.db.get_last_block()
                valid, msg = self.block_validator.validate_block(
                    normalized, last, strict_timestamp=False
                )
                if not valid:
                    print(f"[Blockchain] import_block rejected: {msg}")
                    return False
            try:
                return self.add_block(Block.from_dict(normalized), preserve_peer_hash=True)
            except Exception as e:
                print(f"[Blockchain] import_block error: {e}")
                return False

    def _normalize_block_dict(self, block_dict: Dict) -> Dict:
        b = dict(block_dict)
        if "height" not in b and "number" in b:
            b["height"] = b["number"]
        if "miner" not in b and "proposer" in b:
            b["miner"] = b["proposer"]
        txs = []
        for tx in b.get("transactions", []):
            t = dict(tx)
            if "from_addr" not in t and "from" in t:
                t["from_addr"] = t["from"]
            if "to_addr" not in t and "to" in t:
                t["to_addr"] = t["to"]
            if "value" not in t and "amount" in t:
                t["value"] = t["amount"]
            txs.append(t)
        b["transactions"] = txs
        return b

    def _validate_tx_for_block(self, tx: Transaction, nonce_cursor: Dict[str, int]) -> Dict:
        expected = nonce_cursor.get(tx.from_addr, self.db.get_nonce(tx.from_addr))
        if tx.nonce != expected:
            return {"valid": False, "error": "nonce_mismatch_in_block"}
        return self.validate_transaction(tx)

    def _apply_block_reward(self, proposer: str, in_atomic: bool = False) -> float:
        current_supply = self.db.get_total_supply()
        max_supply = float(getattr(self.config, "max_supply", MAX_SUPPLY_ABS))
        reward = self.config.block_reward
        if current_supply + reward > max_supply:
            reward = max(0.0, max_supply - current_supply)
        if reward > 0:
            if in_atomic:
                self.db.balance_delta(proposer, reward)
            else:
                self.db.update_balance(proposer, reward)
        return reward

    def _compute_state_root_from_db(self) -> str:
        accounts = self.db.get_all_accounts()
        payload = []
        for r in accounts:
            code = r.get("code") or ""
            storage = r.get("storage") or "{}"
            code_hash = hashlib.sha256(code.encode()).hexdigest() if code else ""
            storage_hash = hashlib.sha256(storage.encode()).hexdigest() if storage else ""
            payload.append({
                "a": r["address"],
                "b": round(float(r["balance"]), 12),
                "n": int(r["nonce"]),
                "c": code_hash,
                "s": storage_hash,
            })
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()

    # ── Применение транзакции ────────────────────────────────────────────────

    def _apply_transaction(
        self, tx: Transaction, block_height: int, proposer: str = None, in_atomic: bool = False
    ) -> Dict:
        """
        Применяет одну транзакцию к состоянию.
        Реализует механизм сжигания: burn_rate% от комиссии уничтожается.
        """
        proposer = proposer or self.config.miner_address or "genesis"
        fee = tx.gas * self.config.gas_price_wei
        burn_amount = fee * self.config.burn_rate
        miner_fee = fee - burn_amount

        expected_nonce = self.db.get_nonce(tx.from_addr)
        if tx.nonce != expected_nonce:
            return {"success": False, "error": "nonce_mismatch"}

        sender_balance = self.db.get_balance(tx.from_addr)
        total_cost = tx.value + fee

        if sender_balance < total_cost:
            return {"success": False, "error": "insufficient_funds"}

        if self.pool_locks:
            allowed, reason = self.pool_locks.is_outgoing_allowed(
                tx.from_addr, total_cost, sender_balance
            )
            if not allowed:
                return {"success": False, "error": reason}

        sig_check = self._verify_tx_signature(tx)
        if not sig_check["valid"]:
            return {"success": False, "error": sig_check.get("error", "invalid_signature")}

        # EVM: contract call or deploy when calldata present
        if tx.data and getattr(self, "evm", None):
            target_acct = self.db.get_account(tx.to_addr)
            if target_acct and target_acct.get("code"):
                evm_res = self.evm.call_contract(
                    tx.from_addr,
                    tx.to_addr,
                    tx.data,
                    tx.value,
                    gas_limit=tx.gas or self.config.evm_gas_limit,
                )
                if not evm_res.success:
                    return {"success": False, "error": evm_res.error or "evm_call_failed"}
                fee = max(fee, evm_res.gas_used * self.config.gas_price_wei)
                burn_amount = fee * self.config.burn_rate
                miner_fee = fee - burn_amount
                if sender_balance < fee + tx.value:
                    return {"success": False, "error": "insufficient_funds_for_gas"}
                if in_atomic:
                    self.db.balance_delta(tx.from_addr, -fee)
                    self.db.balance_delta(proposer, miner_fee)
                    if burn_amount > 0 and self.config.burn_address:
                        self.db.balance_delta(self.config.burn_address, burn_amount)
                    self.db.nonce_increment(tx.from_addr)
                else:
                    self.db.update_balance(tx.from_addr, -fee)
                    self.db.update_balance(proposer, miner_fee)
                    if burn_amount > 0 and self.config.burn_address:
                        self.db.update_balance(self.config.burn_address, burn_amount)
                    self.db.increment_nonce(tx.from_addr)
                if self.pool_locks:
                    self.pool_locks.record_outgoing(tx.from_addr, fee + tx.value)
                tx.fee = fee
                tx.burned = burn_amount
                tx.gas_used = evm_res.gas_used or tx.gas
                tx.block_height = block_height
                if self.bus:
                    self.bus.emit("tx.applied", tx.to_dict())
                return {
                    "success": True,
                    "fee": fee,
                    "burned": burn_amount,
                    "miner_fee": miner_fee,
                    "evm": True,
                }

            deploy_data = (tx.data or "").strip()
            hex_body = deploy_data.replace("0x", "")
            if deploy_data and len(hex_body) >= 4 and len(hex_body) % 2 == 0:
                deploy_salt = f"{block_height}:{tx.nonce}:{tx.hash}"
                evm_res = self.evm.deploy_contract(
                    tx.from_addr,
                    deploy_data,
                    tx.value,
                    gas_limit=tx.gas or self.config.evm_gas_limit,
                    salt=deploy_salt,
                )
                if not evm_res.success:
                    return {"success": False, "error": evm_res.error or "evm_deploy_failed"}
                fee = max(fee, evm_res.gas_used * self.config.gas_price_wei)
                burn_amount = fee * self.config.burn_rate
                miner_fee = fee - burn_amount
                deploy_cost = fee + tx.value
                if sender_balance < deploy_cost:
                    return {"success": False, "error": "insufficient_funds_for_deploy"}
                if in_atomic:
                    self.db.balance_delta(tx.from_addr, -fee)
                    self.db.balance_delta(proposer, miner_fee)
                    if burn_amount > 0 and self.config.burn_address:
                        self.db.balance_delta(self.config.burn_address, burn_amount)
                    self.db.nonce_increment(tx.from_addr)
                else:
                    self.db.update_balance(tx.from_addr, -fee)
                    self.db.update_balance(proposer, miner_fee)
                    if burn_amount > 0 and self.config.burn_address:
                        self.db.update_balance(self.config.burn_address, burn_amount)
                    self.db.increment_nonce(tx.from_addr)
                if self.pool_locks:
                    self.pool_locks.record_outgoing(tx.from_addr, deploy_cost)
                tx.fee = fee
                tx.burned = burn_amount
                tx.gas_used = evm_res.gas_used or tx.gas
                tx.block_height = block_height
                if self.bus:
                    self.bus.emit("tx.applied", tx.to_dict())
                return {
                    "success": True,
                    "fee": fee,
                    "burned": burn_amount,
                    "miner_fee": miner_fee,
                    "evm": True,
                    "contract_address": evm_res.return_value,
                }

        if in_atomic:
            self.db.balance_delta(tx.from_addr, -total_cost)
            self.db.balance_delta(tx.to_addr, tx.value)
            self.db.balance_delta(proposer, miner_fee)
            if burn_amount > 0 and self.config.burn_address:
                self.db.balance_delta(self.config.burn_address, burn_amount)
            self.db.nonce_increment(tx.from_addr)
        else:
            self.db.update_balance(tx.from_addr, -total_cost)
            self.db.update_balance(tx.to_addr, tx.value)
            self.db.update_balance(proposer, miner_fee)
            if burn_amount > 0 and self.config.burn_address:
                self.db.update_balance(self.config.burn_address, burn_amount)
            self.db.increment_nonce(tx.from_addr)

        if self.pool_locks:
            self.pool_locks.record_outgoing(tx.from_addr, total_cost)

        tx.fee = fee
        tx.burned = burn_amount
        tx.gas_used = tx.gas
        tx.block_height = block_height

        if self.bus:
            self.bus.emit("tx.applied", tx.to_dict())

        return {
            "success": True,
            "fee": fee,
            "burned": burn_amount,
            "miner_fee": miner_fee,
        }

    # ── Валидация ────────────────────────────────────────────────────────────

    def validate_transaction(self, tx: Transaction) -> Dict:
        """Проверяет транзакцию перед добавлением в мемпул."""
        if not tx.from_addr or not tx.to_addr:
            return {"valid": False, "error": "missing_address"}
        if tx.value < 0:
            return {"valid": False, "error": "negative_value"}
        if tx.gas < self.config.base_gas_price:
            return {"valid": False, "error": "gas_too_low"}

        expected_nonce = self.db.get_nonce(tx.from_addr)
        if tx.nonce != expected_nonce:
            return {"valid": False, "error": f"nonce_mismatch (got {tx.nonce}, expected {expected_nonce})"}

        fee = tx.gas * self.config.gas_price_wei
        balance = self.db.get_balance(tx.from_addr)
        total_cost = tx.value + fee
        if balance < total_cost:
            return {"valid": False, "error": "insufficient_funds"}

        if self.pool_locks:
            allowed, reason = self.pool_locks.is_outgoing_allowed(
                tx.from_addr, total_cost, balance
            )
            if not allowed:
                return {"valid": False, "error": reason}

        sig_check = self._verify_tx_signature(tx)
        if not sig_check["valid"]:
            return sig_check

        deploy_check = self._validate_evm_deploy_bytecode(tx)
        if not deploy_check["valid"]:
            return deploy_check

        return {"valid": True}

    def _is_evm_deploy_tx(self, tx: Transaction) -> bool:
        if not tx.data or not getattr(self, "evm", None):
            return False
        target_acct = self.db.get_account(tx.to_addr)
        if target_acct and target_acct.get("code"):
            return False
        deploy_data = (tx.data or "").strip()
        hex_body = deploy_data.replace("0x", "")
        return bool(deploy_data and len(hex_body) >= 4 and len(hex_body) % 2 == 0)

    def _validate_evm_deploy_bytecode(self, tx: Transaction) -> Dict:
        if not self._is_evm_deploy_tx(tx):
            return {"valid": True}
        from execution.evm_bytecode_validator import validate_bytecode_hex
        v = validate_bytecode_hex(tx.data)
        if v.get("valid"):
            return {"valid": True}
        bad = v.get("unsupported") or []
        name = bad[0].get("name", "?") if bad else v.get("error", "invalid")
        return {"valid": False, "error": f"unsupported_evm_bytecode:{name}"}

    def _verify_tx_signature(self, tx: Transaction) -> Dict:
        """Require and verify ECDSA when config.require_signatures is enabled."""
        require = getattr(self.config, "require_signatures", False)
        if not tx.signature:
            if require:
                return {"valid": False, "error": "missing_signature"}
            return {"valid": True}
        if not tx.public_key:
            return {"valid": False, "error": "missing_public_key"}
        try:
            from crypto.wallet import verify_transaction_signature
            tx_dict = {
                "from": tx.from_addr,
                "to": tx.to_addr,
                "value": int(tx.value) if tx.value == int(tx.value) else tx.value,
                "nonce": tx.nonce,
                "chain_id": self.config.chain_id,
                "signature": tx.signature,
                "public_key": tx.public_key,
                "data": tx.data or "",
                "gas_limit": tx.gas,
            }
            if not verify_transaction_signature(tx_dict):
                return {"valid": False, "error": "invalid_signature"}
        except Exception as e:
            return {"valid": False, "error": f"signature_check_failed: {e}"}
        return {"valid": True}

    def _verify_block_proposer(self, block: Block) -> Dict:
        """Slashing + authorized proposer checks before block execution."""
        proposer = block.miner or ""
        if not proposer or proposer == "genesis":
            return {"valid": True}

        slashing = self._resolve_slashing_core()
        if slashing:
            if proposer in slashing.slashed:
                return {"valid": False, "error": "proposer_slashed"}

        if not getattr(self.config, "enforce_proposer", True):
            return {"valid": True}

        validators = self.db.get_validators(active_only=True) if hasattr(self.db, "get_validators") else []
        if len(validators) <= 1:
            return {"valid": True}

        allowed = {v["address"].lower() for v in validators}
        for addr in (self.config.miner_address, self.config.signing_address):
            if addr:
                allowed.add(addr.lower())
        if proposer.lower() not in allowed:
            return {"valid": False, "error": "unauthorized_proposer"}
        return {"valid": True}

    def _resolve_slashing_core(self):
        """Return underlying SlashingEngine from consensus adapter."""
        adapter = self.consensus_adapter
        if not adapter:
            return None
        engine = getattr(adapter, "slashing_engine", None)
        if engine is None:
            return None
        if hasattr(engine, "slashing"):
            return engine.slashing
        if hasattr(engine, "slashed"):
            return engine
        return None

    def find_ancestor_height(self, parent_hash: str) -> Optional[int]:
        """Local height of parent_hash (fork common ancestor lookup)."""
        if not parent_hash or parent_hash == self.GENESIS_HASH:
            return 0
        blk = self.get_block_by_hash(parent_hash)
        if blk:
            return int(blk.get("height", blk.get("number", 0)))
        return None

    def reorg_to_ancestor(self, ancestor_height: int) -> bool:
        """Rollback blocks above ancestor and replay state from genesis allocation."""
        from runtime.tokenomics import genesis_balances

        with self.lock:
            tip = self.get_height()
            if ancestor_height >= tip:
                return True

            founder = (
                getattr(self.config, "founder_address", "")
                or self.config.miner_address
                or ""
            )
            alloc = genesis_balances(founder or None)
            if self.config.miner_address and self.config.miner_address not in alloc:
                alloc[self.config.miner_address] = int(
                    getattr(self.config, "min_stake", 1000)
                )

            try:
                if hasattr(self.db, "truncate_chain_state"):
                    self.db.truncate_chain_state(ancestor_height)
                else:
                    self.db.truncate_blocks_above(ancestor_height)

                self.db.reset_accounts_from_alloc(alloc)

                for h in range(1, ancestor_height + 1):
                    blk_dict = self.db.get_block(h)
                    if not blk_dict:
                        raise RuntimeError(f"missing_block_at_replay_{h}")
                    block = Block.from_dict(blk_dict)
                    with self.db.atomic():
                        for tx in block.transactions:
                            result = self._apply_transaction(
                                tx, block.height, proposer=block.miner, in_atomic=True
                            )
                            if not result["success"]:
                                raise RuntimeError(result.get("error", "replay_tx_failed"))
                        self._apply_block_reward(block.miner, in_atomic=True)

                replay_root = self._compute_state_root_from_db()
                ancestor_blk = self.db.get_block(ancestor_height)
                if ancestor_blk and ancestor_blk.get("state_root"):
                    expected = ancestor_blk["state_root"]
                    if expected and expected != replay_root:
                        raise RuntimeError("reorg_state_root_mismatch")
                print(f"[Blockchain] Reorg complete at height #{ancestor_height}")
                return True
            except Exception as e:
                print(f"[Blockchain] Reorg failed: {e}")
                return False

    def _validate_block_structure(self, block: Block) -> Dict:
        """Height/parent/hash checks before state execution."""
        last = self.db.get_last_block()
        if last:
            expected_height = last["height"] + 1
            if block.height != expected_height:
                return {"valid": False, "error": f"height_mismatch (got {block.height}, expected {expected_height})"}
            if block.parent_hash != last["hash"]:
                return {"valid": False, "error": "parent_hash_mismatch"}
        elif block.height not in (0, 1):
            return {"valid": False, "error": "expected_genesis_height_0_or_1"}
        return {"valid": True}

    def validate_block(self, block: Block) -> Dict:
        """Полная структурная валидация блока (для P2P-синхронизации)."""
        base = self._validate_block_structure(block)
        if not base["valid"]:
            return base
        recomputed = block._compute_hash()
        if block.hash != recomputed:
            return {"valid": False, "error": "invalid_hash"}
        proposer = self._verify_block_proposer(block)
        if not proposer["valid"]:
            return proposer
        return {"valid": True}

    # ── Публичные геттеры ────────────────────────────────────────────────────

    def get_height(self) -> int:
        return self.db.get_chain_tip()

    def get_balance(self, address: str) -> float:
        return self.db.get_balance(address)

    def get_last_block(self) -> Optional[Dict]:
        return self.db.get_last_block()

    def get_block(self, height: int) -> Optional[Dict]:
        return self.db.get_block(height)

    def get_block_by_hash(self, block_hash: str) -> Optional[Dict]:
        return self.db.get_block_by_hash(block_hash) if hasattr(self.db, "get_block_by_hash") else None

    def truncate_to_height(self, height: int) -> int:
        """Drop blocks above height (keep genesis at 0). Used when joining a longer peer chain."""
        with self.lock:
            return self.db.truncate_blocks_above(height)

    def get_transaction(self, tx_hash: str) -> Optional[Dict]:
        return self.db.get_transaction(tx_hash)

    def get_state_root(self) -> str:
        """Текущий state root из реальных балансов SQLite."""
        return self._compute_state_root_from_db()

    def get_stats(self) -> Dict:
        db_stats = self.db.get_stats()
        burn_stats = self.db.get_burn_stats()
        chain_metrics = (
            self.db.get_chain_metrics()
            if hasattr(self.db, "get_chain_metrics")
            else {}
        )
        return {
            **db_stats,
            **burn_stats,
            **chain_metrics,
            "coin_symbol": self.config.coin_symbol,
            "chain_id": self.config.chain_id,
            "network": self.config.network_name,
            "max_supply": getattr(self.config, "max_supply", MAX_SUPPLY_ABS),
            "founder_initials": getattr(self.config, "founder_initials", "D.U.P."),
            "founder_percent": getattr(self.config, "founder_percent", 17.4),
            "founder_address": getattr(self.config, "founder_address", ""),
            "state_root": self.get_state_root(),
            "state_engine": self.state_engine is not None,
            "block_validator": self.block_validator is not None,
            "canonical_hash": _CANONICAL_AVAILABLE,
            "require_signatures": getattr(self, "require_signatures", False),
        }
