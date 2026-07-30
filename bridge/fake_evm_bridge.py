# bridge/fake_evm_bridge.py — FakeL1Rpc + in-memory bridge for ADR 0010 tests
"""Simulates L1 receipt failures, confirmation delays, forged receipts, ZK hooks."""

from __future__ import annotations

import copy
import time
from typing import Any, Dict, List, Optional

from bridge.ports import (
    BridgeOpResult,
    InboundEnvelope,
    InboundStatus,
    LockStatus,
)
from bridge.state_machine import (
    can_transition_lock,
    inbound_status_from_claim,
    next_lock_status,
    normalize_lock_status,
)
from bridge.validators import InboundMessageValidator, compute_replay_key


class FakeL1Rpc:
    """Controllable L1RpcPort for unit/integration tests."""

    def __init__(self) -> None:
        self.receipts: Dict[str, Dict[str, Any]] = {}
        self.confirmations: Dict[str, int] = {}
        self.fail_receipt: bool = False
        self.forge_status_failed: bool = False
        self.delay_confirmations_target: int = 0
        self._conf_calls: Dict[str, int] = {}

    def seed_receipt(
        self,
        tx_hash: str,
        *,
        status: int = 1,
        chain: str = "ethereum",
        logs: Optional[List] = None,
    ) -> None:
        self.receipts[tx_hash.lower()] = {
            "transactionHash": tx_hash,
            "status": hex(status) if status >= 0 else "0x0",
            "status_int": status,
            "logs": logs if logs is not None else [{"dummy": True}],
            "chain": chain,
        }
        self.confirmations[tx_hash.lower()] = max(
            self.confirmations.get(tx_hash.lower(), 0), 12
        )

    def get_tx_receipt(self, chain: str, tx_hash: str) -> Optional[Dict[str, Any]]:
        if self.fail_receipt:
            return None
        key = str(tx_hash or "").strip().lower()
        row = self.receipts.get(key)
        if row is None:
            return None
        out = copy.deepcopy(row)
        if self.forge_status_failed:
            out["status"] = "0x0"
            out["status_int"] = 0
        return out

    def get_confirmations(self, chain: str, tx_hash: str) -> int:
        key = str(tx_hash or "").strip().lower()
        if self.delay_confirmations_target > 0:
            n = int(self._conf_calls.get(key, 0) or 0) + 1
            self._conf_calls[key] = n
            if n < self.delay_confirmations_target:
                return max(0, n - 1)
        return int(self.confirmations.get(key, 0) or 0)

    def receipt_status_ok(self, receipt: Dict[str, Any]) -> bool:
        if not receipt:
            return False
        if "status_int" in receipt:
            return int(receipt["status_int"]) == 1
        st = receipt.get("status")
        if st is None:
            return False
        if isinstance(st, str):
            try:
                return int(st, 16) == 1
            except ValueError:
                return st in ("0x1", "1", "success")
        return int(st) == 1


class FakeBridgeStore:
    """Minimal BridgeStorePort for atomicity tests (dict-backed)."""

    def __init__(self) -> None:
        self.balances: Dict[str, float] = {}
        self.locks: Dict[str, Dict[str, Any]] = {}
        self.credits: Dict[str, Dict[str, Any]] = {}
        self.fail_mid_claim: bool = False

    def bridge_credit_key(
        self, from_chain: str, event_tx_hash: str, log_index: int = 0
    ) -> str:
        return compute_replay_key(from_chain, event_tx_hash, log_index)

    def has_bridge_credit(self, credit_key: str) -> bool:
        return credit_key in self.credits

    def debit_and_create_bridge_lock(
        self,
        from_addr: str,
        amount: float,
        burn_address: str,
        burn_amount: float,
        to_chain: str,
        to_addr: str,
        net_amount: float,
        tx_hash: str,
    ) -> None:
        bal = float(self.balances.get(from_addr, 0.0))
        if bal + 1e-12 < float(amount):
            raise RuntimeError("insufficient_funds")
        self.balances[from_addr] = bal - float(amount)
        if burn_amount and burn_address:
            self.balances[burn_address] = float(self.balances.get(burn_address, 0.0)) + float(
                burn_amount
            )
        self.locks[tx_hash] = {
            "tx_hash": tx_hash,
            "from_addr": from_addr,
            "to_chain": to_chain,
            "to_addr": to_addr,
            "amount": float(net_amount),
            "status": LockStatus.PENDING.value,
            "created_at": int(time.time()),
        }

    def claim_and_credit_bridge_event(
        self,
        from_chain: str,
        event_tx_hash: str,
        recipient: str,
        amount: float,
        log_index: int = 0,
        abs_tx_hash: str = "",
    ) -> Dict[str, Any]:
        key = self.bridge_credit_key(from_chain, event_tx_hash, log_index)
        if key in self.credits:
            return {"credited": False, "duplicate": True, "credit_key": key}
        if self.fail_mid_claim:
            raise RuntimeError("injected_mid_claim_failure")
        self.credits[key] = {
            "credit_key": key,
            "recipient": recipient,
            "amount": float(amount),
            "from_chain": from_chain,
        }
        self.balances[recipient] = float(self.balances.get(recipient, 0.0)) + float(amount)
        return {"credited": True, "duplicate": False, "credit_key": key}

    def refund_pending_bridge_lock(self, tx_hash: str) -> Dict[str, Any]:
        lock = self.locks.get(tx_hash)
        if not lock or lock.get("status") != LockStatus.PENDING.value:
            return {"refunded": False, "error": "Lock not found or already processed"}
        self.balances[lock["from_addr"]] = float(
            self.balances.get(lock["from_addr"], 0.0)
        ) + float(lock["amount"])
        lock["status"] = LockStatus.REFUNDED.value
        return {"refunded": True, "tx_hash": tx_hash, "amount": float(lock["amount"])}

    def get_bridge_lock(self, lock_hash: str) -> Optional[Dict[str, Any]]:
        row = self.locks.get(lock_hash)
        return dict(row) if row else None

    def confirm_bridge_lock_status(
        self, lock_hash: str, *, l1_tx_hash: str = ""
    ) -> Dict[str, Any]:
        lock = self.locks.get(lock_hash)
        if not lock:
            return {"ok": False, "error": "lock_not_found"}
        cur = normalize_lock_status(str(lock.get("status")))
        if not can_transition_lock(cur, "confirm_lock"):
            return {"ok": False, "error": "illegal_transition", "status": cur.value}
        lock["status"] = next_lock_status(cur, "confirm_lock").value  # type: ignore[union-attr]
        lock["l1_tx_hash"] = l1_tx_hash
        return {"ok": True, "status": lock["status"], "l1_tx_hash": l1_tx_hash}


class FakeEvmBridge:
    """In-process BridgePort using FakeBridgeStore + FakeL1Rpc + validator."""

    def __init__(self, config: Any, *, zk_gateway: Any = None):
        self.config = config
        self.store = FakeBridgeStore()
        self.l1 = FakeL1Rpc()
        self.zk_fail = False
        self.zk_delay_ms = 0
        self.contract_revert = False
        self.validator = InboundMessageValidator(
            config=config, l1_rpc=self.l1, zk_gateway=zk_gateway
        )
        self._zk_gateway = zk_gateway
        self._lock_seq = 0

    def lock_and_bridge(
        self, from_addr, to_chain, to_addr, amount, **kwargs
    ) -> BridgeOpResult:
        if self.contract_revert:
            return BridgeOpResult(
                ok=False, status="failed", detail={"error": "l1_contract_revert"}
            )
        mode = str(getattr(self.config, "deployment_mode", "dev") or "dev").lower()
        l1_tx = str(kwargs.get("l1_tx_hash") or "").strip()
        if mode in ("prod", "production") and not l1_tx:
            return BridgeOpResult(
                ok=False,
                status="failed",
                detail={"error": "prod outbound bridge requires l1_tx_hash"},
            )
        fee_rate = 0.001
        fee = float(amount) * fee_rate
        net = float(amount) - fee
        self._lock_seq += 1
        tx_hash = l1_tx or f"fake-lock-{self._lock_seq}"
        try:
            self.store.debit_and_create_bridge_lock(
                from_addr=from_addr,
                amount=float(amount),
                burn_address=str(getattr(self.config, "burn_address", "") or "0xburn"),
                burn_amount=fee * float(getattr(self.config, "burn_rate", 0.5) or 0.5),
                to_chain=to_chain,
                to_addr=to_addr,
                net_amount=net,
                tx_hash=tx_hash,
            )
        except Exception as exc:
            return BridgeOpResult(ok=False, status="failed", detail={"error": str(exc)})
        return BridgeOpResult(
            ok=True,
            status=LockStatus.PENDING.value,
            detail={
                "tx_hash": tx_hash,
                "from_addr": from_addr,
                "to_chain": to_chain,
                "to_addr": to_addr,
                "amount": float(amount),
                "net_amount": net,
                "fee": fee,
                "status": "pending",
            },
        )

    def confirm_incoming(self, envelope: InboundEnvelope) -> BridgeOpResult:
        if self.zk_delay_ms > 0:
            time.sleep(self.zk_delay_ms / 1000.0)
        if self.zk_fail and envelope.zk_proof is not None:
            return BridgeOpResult(
                ok=False,
                status=InboundStatus.REJECTED.value,
                detail={"error": "zk_proof_invalid", "reason": "zk_proof_invalid"},
            )
        vr = self.validator.validate(envelope)
        if not vr.ok:
            return BridgeOpResult(
                ok=False,
                status=InboundStatus.REJECTED.value,
                detail={"error": vr.reason, "reason": vr.reason, "replay_key": vr.replay_key},
            )
        try:
            claim = self.store.claim_and_credit_bridge_event(
                from_chain=envelope.from_chain,
                event_tx_hash=envelope.event_tx_hash,
                recipient=envelope.to_addr,
                amount=float(envelope.amount),
                log_index=int(envelope.log_index or 0),
                abs_tx_hash=envelope.abs_tx_hash or envelope.event_tx_hash,
            )
        except Exception as exc:
            return BridgeOpResult(
                ok=False,
                status=InboundStatus.REJECTED.value,
                detail={"error": str(exc)},
            )
        status = inbound_status_from_claim(claim)
        return BridgeOpResult(
            ok=True,
            status=status.value,
            detail={
                "confirmed": True,
                "duplicate": bool(claim.get("duplicate")),
                "credit_key": claim.get("credit_key"),
                "recipient": envelope.to_addr,
                "amount": float(envelope.amount),
                "event_tx_hash": envelope.event_tx_hash,
            },
        )

    def confirm_lock(self, abs_lock_hash: str, l1_tx_hash: str) -> BridgeOpResult:
        res = self.store.confirm_bridge_lock_status(abs_lock_hash, l1_tx_hash=l1_tx_hash)
        if not res.get("ok"):
            return BridgeOpResult(ok=False, status="failed", detail=dict(res))
        return BridgeOpResult(ok=True, status=LockStatus.CONFIRMED.value, detail=dict(res))

    def refund(self, abs_lock_hash: str, reason: str = "") -> BridgeOpResult:
        lock = self.store.get_bridge_lock(abs_lock_hash)
        if lock:
            cur = normalize_lock_status(str(lock.get("status")))
            if not can_transition_lock(cur, "refund"):
                return BridgeOpResult(
                    ok=False,
                    status="failed",
                    detail={"error": "illegal_transition", "status": cur.value},
                )
        res = self.store.refund_pending_bridge_lock(abs_lock_hash)
        if not res.get("refunded"):
            return BridgeOpResult(ok=False, status="failed", detail=dict(res))
        return BridgeOpResult(
            ok=True,
            status=LockStatus.REFUNDED.value,
            detail={**res, "reason": reason},
        )

    def get_stats(self) -> Dict[str, Any]:
        return {
            "enabled": True,
            "backend": "fake_evm",
            "locks": len(self.store.locks),
            "credits": len(self.store.credits),
        }

    async def start(self):
        return None

    def stop(self) -> None:
        return None
