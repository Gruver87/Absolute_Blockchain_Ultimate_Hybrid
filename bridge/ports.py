# bridge/ports.py — ADR 0010 L1 bridge switching surfaces
"""Protocols and DTOs for the EVM / L1 bridge layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Protocol, runtime_checkable


class BridgeDirection(str, Enum):
    OUTBOUND = "outbound"
    INBOUND = "inbound"


class LockStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    REFUNDED = "refunded"
    FAILED = "failed"


class InboundStatus(str, Enum):
    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    REJECTED = "rejected"


@dataclass(frozen=True)
class InboundEnvelope:
    from_chain: str
    to_addr: str
    amount: float
    event_tx_hash: str
    log_index: int = 0
    receipt: Optional[Dict[str, Any]] = None
    zk_proof: Optional[Dict[str, Any]] = None
    oracle_meta: Dict[str, Any] = field(default_factory=dict)
    abs_tx_hash: str = ""


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str = ""
    replay_key: str = ""


@dataclass(frozen=True)
class BridgeOpResult:
    ok: bool
    status: str
    detail: Dict[str, Any] = field(default_factory=dict)

    def as_legacy_dict(self) -> Dict[str, Any]:
        """Shape compatible with pre-port HTTP / tests."""
        out = dict(self.detail)
        out.setdefault("ok", self.ok)
        out.setdefault("status", self.status)
        if self.status == InboundStatus.ACCEPTED.value:
            out.setdefault("confirmed", True)
        if self.status == InboundStatus.DUPLICATE.value:
            out.setdefault("confirmed", True)
            out.setdefault("duplicate", True)
        if self.status == InboundStatus.REJECTED.value:
            out.setdefault("confirmed", False)
            out.setdefault("error", self.detail.get("error") or self.detail.get("reason") or "rejected")
        if not self.ok and "error" not in out:
            out["error"] = self.detail.get("error") or self.status
        return out


@runtime_checkable
class InboundMessageValidatorPort(Protocol):
    def validate(self, envelope: InboundEnvelope) -> ValidationResult:
        ...


@runtime_checkable
class L1RpcPort(Protocol):
    def get_tx_receipt(self, chain: str, tx_hash: str) -> Optional[Dict[str, Any]]:
        ...

    def get_confirmations(self, chain: str, tx_hash: str) -> int:
        ...

    def receipt_status_ok(self, receipt: Dict[str, Any]) -> bool:
        ...


# Re-export storage BridgeStorePort for bridge-layer consumers (ADR 0010).
try:
    from storage.ports import BridgeStorePort as BridgeStorePort
except Exception:  # pragma: no cover — typing fallback when storage unavailable
    @runtime_checkable
    class BridgeStorePort(Protocol):  # type: ignore[no-redef]
        def bridge_credit_key(
            self, from_chain: str, event_tx_hash: str, log_index: int = 0
        ) -> str:
            ...

        def has_bridge_credit(self, credit_key: str) -> bool:
            ...

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
        ) -> Any:
            ...

        def claim_and_credit_bridge_event(
            self,
            from_chain: str,
            event_tx_hash: str,
            recipient: str,
            amount: float,
            log_index: int = 0,
            abs_tx_hash: str = "",
        ) -> Dict[str, Any]:
            ...

        def refund_pending_bridge_lock(self, tx_hash: str) -> Dict[str, Any]:
            ...

        def get_bridge_lock(self, lock_hash: str) -> Optional[Dict[str, Any]]:
            ...


@runtime_checkable
class BridgePort(Protocol):
    def lock_and_bridge(
        self,
        from_addr: str,
        to_chain: str,
        to_addr: str,
        amount: float,
        **kwargs: Any,
    ) -> BridgeOpResult:
        ...

    def confirm_incoming(self, envelope: InboundEnvelope) -> BridgeOpResult:
        ...

    def confirm_lock(self, abs_lock_hash: str, l1_tx_hash: str) -> BridgeOpResult:
        ...

    def refund(self, abs_lock_hash: str, reason: str = "") -> BridgeOpResult:
        ...

    def get_stats(self) -> Dict[str, Any]:
        ...


class NullBridgePort:
    """bridge_enabled=False — all ops refuse."""

    def lock_and_bridge(self, from_addr, to_chain, to_addr, amount, **kwargs) -> BridgeOpResult:
        return BridgeOpResult(ok=False, status="disabled", detail={"error": "bridge_disabled"})

    def confirm_incoming(self, envelope: InboundEnvelope) -> BridgeOpResult:
        return BridgeOpResult(ok=False, status="disabled", detail={"error": "bridge_disabled"})

    def confirm_lock(self, abs_lock_hash: str, l1_tx_hash: str) -> BridgeOpResult:
        return BridgeOpResult(ok=False, status="disabled", detail={"error": "bridge_disabled"})

    def refund(self, abs_lock_hash: str, reason: str = "") -> BridgeOpResult:
        return BridgeOpResult(ok=False, status="disabled", detail={"error": "bridge_disabled"})

    def get_stats(self) -> Dict[str, Any]:
        return {"enabled": False, "backend": "null"}

    # Legacy HTTP duck-typing
    async def start(self):
        return None

    def stop(self) -> None:
        return None
