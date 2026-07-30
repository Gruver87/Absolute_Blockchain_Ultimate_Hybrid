# bridge/state_machine.py — ADR 0010 lock / inbound transitions
"""Explicit legal transitions for bridge lock and inbound credit."""

from __future__ import annotations

from typing import Optional

from bridge.ports import InboundStatus, LockStatus


_OUTBOUND_EDGES = {
    (LockStatus.PENDING, "confirm_lock"): LockStatus.CONFIRMED,
    (LockStatus.PENDING, "refund"): LockStatus.REFUNDED,
    (LockStatus.PENDING, "l1_fail"): LockStatus.FAILED,
    (LockStatus.FAILED, "refund"): LockStatus.REFUNDED,
}


def normalize_lock_status(raw: str) -> LockStatus:
    key = str(raw or "").strip().lower()
    for st in LockStatus:
        if st.value == key:
            return st
    return LockStatus.PENDING


def can_transition_lock(current: LockStatus, action: str) -> bool:
    return (current, str(action)) in _OUTBOUND_EDGES


def next_lock_status(current: LockStatus, action: str) -> Optional[LockStatus]:
    return _OUTBOUND_EDGES.get((current, str(action)))


def inbound_status_from_claim(claim: dict) -> InboundStatus:
    if claim.get("duplicate"):
        return InboundStatus.DUPLICATE
    if claim.get("credited"):
        return InboundStatus.ACCEPTED
    return InboundStatus.REJECTED
