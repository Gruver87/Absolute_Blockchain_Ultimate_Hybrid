"""Sync consistency domain (ADR 0003)."""

from __future__ import annotations

from typing import Any

from sync.consistency.machine import ConsistencyMachine
from sync.consistency.store import InMemoryConsistencyStore
from sync.consistency.types import (
    ConsistencyDecision,
    ConsistencyOutcome,
    ConsistencySnapshot,
    ConsistencyState,
    PeerSyncView,
    WireProbeResult,
)

__all__ = [
    "ConsistencyDecision",
    "ConsistencyMachine",
    "ConsistencyOutcome",
    "ConsistencyService",
    "ConsistencySnapshot",
    "ConsistencyState",
    "InMemoryConsistencyStore",
    "PeerSyncView",
    "WireProbeResult",
]


def __getattr__(name: str) -> Any:
    # Lazy: ConsistencyService imports sync.ports; ports imports consistency.types
    # via this package — avoid circular import when ports loads first (ADR 0004).
    if name == "ConsistencyService":
        from sync.consistency.service import ConsistencyService

        return ConsistencyService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
