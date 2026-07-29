"""Sync domain ports (ADR 0003 / 0004). No ``network.p2p_node`` imports."""

from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

from sync.consistency.types import (
    ConsistencySnapshot,
    PeerSyncView,
    WireProbeResult,
)


@runtime_checkable
class SyncPeerViewPort(Protocol):
    """List peers as immutable sync views (no socket I/O)."""

    def list_peer_views(self) -> Sequence[PeerSyncView]:
        ...


@runtime_checkable
class SyncChainPort(Protocol):
    """Chain read + tip-safety-aware import."""

    def height(self) -> int:
        ...

    def get_block(self, height_or_hash: Any) -> Any:
        ...

    def get_state_root(self) -> str:
        ...

    def import_block(self, data: Mapping[str, Any]) -> bool:
        """Must route through tip-safety when available."""
        ...


@runtime_checkable
class SyncBlockFetchPort(Protocol):
    """Fetch a block by hash via solicit façade (does not own waiter tables)."""

    def fetch_block_by_hash(
        self, block_hash: str, timeout: float = 30.0
    ) -> Optional[Mapping[str, Any]]:
        ...


@runtime_checkable
class SyncWireProbePort(Protocol):
    """Solicit peer state roots (never paint green on unsolicited)."""

    def probe_peer_state_roots(self) -> WireProbeResult:
        ...


@runtime_checkable
class SyncConsistencyStorePort(Protocol):
    """Single-writer façade for consistency snapshot."""

    def get_snapshot(self) -> ConsistencySnapshot:
        ...

    def set_snapshot(self, snapshot: ConsistencySnapshot) -> None:
        ...


@runtime_checkable
class SyncCatchUpPolicyPort(Protocol):
    """Pure catch-up refuse/bind decisions (no I/O)."""

    def ahead_refuse_reason(
        self,
        *,
        local_height: int,
        peer_height: int,
        peer_head: str,
        local_block_for_head: Any = None,
        require_head: bool = True,
    ) -> str:
        ...

    def height_continuity_refuse_reason(
        self,
        block_data: Mapping[str, Any],
        expected_height: int,
        *,
        enabled: bool = True,
    ) -> str:
        ...

    def contiguous_parent_refuse_reason(
        self,
        block_data: Mapping[str, Any],
        expected_parent: str,
        *,
        enabled: bool = True,
    ) -> str:
        ...

    def tip_head_refuse_reason(
        self,
        *,
        local_head: str,
        peer_head: str,
        enabled: bool = True,
    ) -> str:
        ...


@runtime_checkable
class SyncSolicitPort(Protocol):
    """Solicit waiter façade (ADR 0003 Step C/D). Owns arm/fulfill/timeout only.

    The network dispatcher must forward inbound messages here and must not
    inspect or mutate waiter tables itself.
    """

    def arm(
        self,
        peer_id: str,
        expected_types: tuple,
        fut: Any,
        request_ctx: Optional[Mapping[str, Any]] = None,
    ) -> None:
        ...

    def clear(self, peer_id: str) -> None:
        ...

    def timeout(self, peer_id: str, *, result: Any = None) -> bool:
        ...

    def expire_stale(
        self,
        max_age_sec: Optional[float] = None,
        *,
        now: Optional[float] = None,
    ) -> int:
        ...

    def fulfill_or_reject(
        self,
        peer: Any,
        msg_type: str,
        data: Any,
        full_msg: Mapping[str, Any],
        *,
        strike: Any,
        bump: Any = None,
    ) -> Any:
        ...

    def mempool_solicit_armed(self, peer_id: str) -> bool:
        ...


# ── ADR 0004 Path A catch-up ports ───────────────────────────────────────────


@runtime_checkable
class CatchUpChainPort(Protocol):
    """Local chain read + tip-safety-aware import / reorg for Path A."""

    def height(self) -> int:
        ...

    def head(self) -> str:
        ...

    def expected_parent(self, height: int) -> str:
        ...

    def get_block(self, height_or_hash: Any) -> Any:
        ...

    def import_block(self, data: Mapping[str, Any]) -> bool:
        """Must route through tip-safety when available."""
        ...

    def find_ancestor_height(self, parent_hash: str) -> Optional[int]:
        ...

    def reorg_to_ancestor(self, height: int) -> bool:
        ...


@runtime_checkable
class CatchUpFetchPort(Protocol):
    """Fetch a height-range batch from a peer (solicit façade; no waiter ownership)."""

    def fetch_blocks(
        self,
        peer_id: str,
        from_height: int,
        to_height: int,
        parent_hash: str,
        *,
        timeout: float = 45.0,
    ) -> Optional[Sequence[Mapping[str, Any]]]:
        """Return block dicts, empty sequence, or None on timeout / bad response."""
        ...


@runtime_checkable
class CatchUpProbePort(Protocol):
    """Pre-download wire probes (blocking façades over solicit)."""

    def local_tip_probe_refuse(self, peer: Any) -> str:
        """Empty string = ok; otherwise a catch_up_* refuse reason."""
        ...

    def peer_head_probe_refuse(self, peer: Any) -> str:
        """Empty string = ok; otherwise a catch_up_* refuse reason."""
        ...


@runtime_checkable
class CatchUpSideEffectPort(Protocol):
    """Telemetry / peer bookkeeping side effects (no policy decisions)."""

    def bump_refuse(self, reason: str) -> None:
        ...

    def note_import_fail(self, peer_id: str) -> None:
        ...

    def set_peer_height(self, peer_id: str, height: int) -> None:
        ...

    def is_running(self) -> bool:
        ...

    def batch_size(self) -> int:
        ...

    def on_progress(self, message: str) -> None:
        ...


# ── ADR 0005 same-height fork reconcile ports ────────────────────────────────


@runtime_checkable
class ForkReconcileChainPort(Protocol):
    """Local chain read + tip-safety-aware reorg+import for fork reconcile."""

    def height(self) -> int:
        ...

    def head(self) -> str:
        ...

    def expected_parent(self, height: int) -> str:
        ...

    def get_block(self, height_or_hash: Any) -> Any:
        ...

    def find_ancestor_height(self, parent_hash: str) -> Optional[int]:
        ...

    def reorg_and_import(self, rollback_to: int, block: Mapping[str, Any]) -> bool:
        """Must route through tip-safety when available."""
        ...


@runtime_checkable
class ForkReconcileFetchPort(Protocol):
    """Fetch one block by hash (solicit façade; no waiter ownership)."""

    def fetch_block_by_hash(
        self,
        peer_id: str,
        block_hash: str,
        *,
        timeout: float = 30.0,
    ) -> Optional[Mapping[str, Any]]:
        ...


@runtime_checkable
class ForkReconcileProbePort(Protocol):
    """Pre-reorg wire probes (blocking façades over solicit)."""

    def fork_peer_head_probe_refuse(self, peer: Any) -> str:
        """Empty string = ok; otherwise a fork_* refuse reason."""
        ...

    def ghost_head_probe_refuse(self, ghost_head: str, peer_hint: Any = None) -> str:
        """Empty string = ok; otherwise a ghost_* refuse reason."""
        ...


@runtime_checkable
class ForkReconcileSideEffectPort(Protocol):
    """Telemetry / peer bookkeeping / security evidence (no policy decisions)."""

    def bump_refuse(self, reason: str) -> None:
        ...

    def set_peer_tip(self, peer_id: str, height: int, head_hash: str) -> None:
        ...

    def ghost_canonical_head(self) -> str:
        ...

    def peer_ids_for_head(self, head_hash: str) -> Sequence[str]:
        ...

    def all_peer_ids(self) -> Sequence[str]:
        ...

    def note_reorg_risk(self) -> None:
        ...

    def is_running(self) -> bool:
        ...

    def on_progress(self, message: str) -> None:
        ...

    def tip_evidence_refuse(self, block: Mapping[str, Any]) -> str:
        """Empty = ok; otherwise tip-evidence enforce refuse reason."""
        ...

    def note_malicious_attempt(self, peer_id: str, reason: str) -> int:
        """Record hostile same-height attempt; return per-peer attempt count."""
        ...

    def emit_security_evidence(self, evidence: Any) -> None:
        """Publish fail-closed evidence to security bus / status surface."""
        ...

    def strike_malicious_peer(self, peer_id: str, reason: str) -> bool:
        """Strike (and possibly ban) the offending peer. True if removed."""
        ...
