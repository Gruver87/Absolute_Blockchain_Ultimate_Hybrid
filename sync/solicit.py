"""SyncSolicitHub — solicit waiter table + fulfill/reject (ADR 0003 Step C / D).

Owns waiter semantics (arm / fulfill / reject / stale timeout cleanup).
P2P owns TCP send and ``asyncio.wait_for``; the network dispatcher must only
forward inbound messages into ``fulfill_or_reject`` — it must not inspect
waiter state.

No P2P node module imports.
"""

from __future__ import annotations

import logging
import time
from typing import (
    Any,
    Callable,
    Dict,
    Mapping,
    MutableMapping,
    Optional,
    Tuple,
)

logger = logging.getLogger("Sync.Solicit")

StrikeFn = Callable[[Any, str], bool]
BumpFn = Callable[[str, int], None]

# Wire type strings (parity with network message constants; no network import).
MSG_BLOCK = "block"
MSG_BLOCKS = "blocks"
MSG_MEMPOOL = "mempool"
MSG_PEERS = "peers"
MSG_STATE_ROOT_RESPONSE = "state_root_response"

# Waiter tuple layout: (expected_types, future, request_ctx, armed_at_monotonic)
WaiterTuple = Tuple[tuple, Any, Optional[Mapping[str, Any]], float]


class SolicitResult:
    """Outcome of fulfill_or_reject."""

    __slots__ = ("consumed", "detail")

    def __init__(self, consumed: bool, detail: str = "") -> None:
        self.consumed = bool(consumed)
        self.detail = str(detail or "")


def _unpack_waiter(waiter: tuple) -> WaiterTuple:
    """Normalize legacy 3-tuples and current 4-tuples."""
    if len(waiter) >= 4:
        return (
            tuple(waiter[0] or ()),
            waiter[1],
            waiter[2],
            float(waiter[3] or 0.0),
        )
    if len(waiter) >= 3:
        return (
            tuple(waiter[0] or ()),
            waiter[1],
            waiter[2],
            0.0,
        )
    return (tuple(waiter[0] or ()), waiter[1], None, 0.0)


class SyncSolicitHub:
    """Arm / fulfill / timeout solicit-only waiters.

    Waiter value: ``(expected_types, future, request_ctx, armed_at)``.
    """

    __slots__ = (
        "_waiters",
        "_peers_solicit_only",
        "_verify_blocks",
        "_verify_block",
        "_verify_state_root",
        "_default_max_age",
        "_timeouts_total",
        "_stale_sweeps_total",
        "_fulfills_total",
        "_rejects_total",
    )

    def __init__(
        self,
        *,
        peers_solicit_only: bool = True,
        verify_blocks: Optional[Callable[..., Any]] = None,
        verify_block: Optional[Callable[..., Any]] = None,
        verify_state_root: Optional[Callable[..., Any]] = None,
        default_max_age_sec: float = 120.0,
    ) -> None:
        self._waiters: Dict[str, tuple] = {}
        self._peers_solicit_only = bool(peers_solicit_only)
        self._verify_blocks = verify_blocks
        self._verify_block = verify_block
        self._verify_state_root = verify_state_root
        self._default_max_age = float(default_max_age_sec or 120.0)
        self._timeouts_total = 0
        self._stale_sweeps_total = 0
        self._fulfills_total = 0
        self._rejects_total = 0

    @property
    def waiters(self) -> MutableMapping[str, tuple]:
        """Mutable view for back-compat aliases only — prefer arm/clear/timeout."""
        return self._waiters

    @property
    def armed_count(self) -> int:
        return len(self._waiters)

    def set_peers_solicit_only(self, enabled: bool) -> None:
        self._peers_solicit_only = bool(enabled)

    def arm(
        self,
        peer_id: str,
        expected_types: tuple,
        fut: Any,
        request_ctx: Optional[Mapping[str, Any]] = None,
        *,
        armed_at: Optional[float] = None,
    ) -> None:
        pid = str(peer_id or "")
        if not pid:
            raise ValueError("peer_id required to arm solicit waiter")
        ts = float(armed_at) if armed_at is not None else float(time.monotonic())
        self._waiters[pid] = (
            tuple(expected_types or ()),
            fut,
            request_ctx,
            ts,
        )

    def clear(self, peer_id: str) -> None:
        """Drop waiter without touching the future (caller owns timeout result)."""
        self._waiters.pop(str(peer_id or ""), None)

    def get(self, peer_id: str) -> Optional[tuple]:
        return self._waiters.get(str(peer_id or ""))

    def timeout(
        self,
        peer_id: str,
        *,
        result: Any = None,
    ) -> bool:
        """Expire one waiter: fulfill future with ``result`` (default None) and clear.

        Returns True if a waiter was present.
        """
        pid = str(peer_id or "")
        waiter = self._waiters.pop(pid, None)
        if waiter is None:
            return False
        _types, fut, _ctx, _armed = _unpack_waiter(waiter)
        if fut is not None and not fut.done():
            try:
                fut.set_result(result)
            except Exception as exc:
                logger.warning("[Solicit] timeout set_result failed peer=%s: %s", pid[:12], exc)
        self._timeouts_total = int(self._timeouts_total or 0) + 1
        return True

    def expire_stale(
        self,
        max_age_sec: Optional[float] = None,
        *,
        now: Optional[float] = None,
    ) -> int:
        """Clear waiters older than ``max_age_sec``; set their futures to None.

        Returns the number of waiters expired. Used for hub-side stale cleanup
        independent of the transport's ``asyncio.wait_for``.
        """
        max_age = float(
            self._default_max_age if max_age_sec is None else max_age_sec
        )
        if max_age < 0:
            max_age = 0.0
        clock = float(now) if now is not None else float(time.monotonic())
        expired: list[str] = []
        for pid, waiter in list(self._waiters.items()):
            _types, fut, _ctx, armed_at = _unpack_waiter(waiter)
            # Legacy 3-tuples (armed_at==0) are treated as immediately sweepable
            # only when max_age is 0; otherwise keep until stamped or cleared.
            if armed_at <= 0.0:
                if max_age <= 0.0:
                    expired.append(pid)
                continue
            if (clock - float(armed_at)) >= max_age:
                expired.append(pid)
        for pid in expired:
            self.timeout(pid, result=None)
        if expired:
            self._stale_sweeps_total = int(self._stale_sweeps_total or 0) + 1
        return len(expired)

    def clear_all(self, *, timeout_futures: bool = False) -> int:
        """Drop every waiter. Optionally fulfill futures with None first."""
        pids = list(self._waiters.keys())
        if timeout_futures:
            for pid in pids:
                self.timeout(pid, result=None)
            return len(pids)
        n = len(pids)
        self._waiters.clear()
        return n

    def mempool_solicit_armed(self, peer_id: str) -> bool:
        waiter = self.get(peer_id)
        if not waiter:
            return False
        expected_types, _fut, request_ctx, _armed = _unpack_waiter(waiter)
        try:
            types_ok = MSG_MEMPOOL in tuple(expected_types or ())
        except TypeError:
            types_ok = False
        if not types_ok:
            return False
        return isinstance(request_ctx, dict) and request_ctx.get("kind") == "mempool"

    def merge_into_status(self, status: MutableMapping[str, Any]) -> None:
        """Expose hub telemetry into P2P / node status dicts."""
        status["solicit_hub"] = True
        status["solicit_armed"] = int(self.armed_count)
        status["solicit_timeouts_total"] = int(self._timeouts_total or 0)
        status["solicit_stale_sweeps_total"] = int(self._stale_sweeps_total or 0)
        status["solicit_fulfills_total"] = int(self._fulfills_total or 0)
        status["solicit_rejects_total"] = int(self._rejects_total or 0)

    def fulfill_or_reject(
        self,
        peer: Any,
        msg_type: str,
        data: Any,
        full_msg: Mapping[str, Any],
        *,
        strike: StrikeFn,
        bump: Optional[BumpFn] = None,
    ) -> SolicitResult:
        """Process an inbound message against an armed waiter.

        Returns ``consumed=True`` when the caller must stop (fulfilled or struck).
        Returns ``consumed=False`` when no waiter applies — continue to dispatcher.
        """

        def _bump(name: str, delta: int = 1) -> None:
            if bump is not None:
                bump(name, delta)

        peer_id = str(getattr(peer, "peer_id", "") or "")
        waiter = self._waiters.get(peer_id) if peer_id else None
        if not waiter:
            # No armed waiter → leave solicit-only unsolicited rejects to dispatcher.
            return SolicitResult(False, "no_waiter")

        expected_types, fut, request_ctx, _armed = _unpack_waiter(waiter)

        if msg_type not in expected_types or fut.done():
            return SolicitResult(False, "waiter_mismatch")

        if (
            msg_type == MSG_BLOCKS
            and isinstance(request_ctx, dict)
            and request_ctx.get("kind") == "blocks"
        ):
            if self._verify_blocks is not None:
                reason = self._verify_blocks(
                    data if isinstance(data, list) else (data or []),
                    int(request_ctx.get("from_height", 0) or 0),
                    int(request_ctx.get("to_height", 0) or 0),
                    str(request_ctx.get("parent_hash") or ""),
                    allow_empty=bool(request_ctx.get("allow_empty", False)),
                )
                if reason:
                    _bump("blocks_response_semantic_rejects_total")
                    self._rejects_total = int(self._rejects_total or 0) + 1
                    strike(peer, str(reason))
                    if not fut.done():
                        fut.set_result(None)
                    return SolicitResult(True, str(reason))
            if not fut.done():
                fut.set_result(full_msg)
            self._fulfills_total = int(self._fulfills_total or 0) + 1
            return SolicitResult(True, "blocks_ok")

        if (
            msg_type == MSG_BLOCK
            and isinstance(request_ctx, dict)
            and request_ctx.get("kind") == "block"
        ):
            if self._verify_block is not None:
                reason = self._verify_block(
                    data,
                    str(request_ctx.get("expected_hash") or ""),
                    allow_null=bool(request_ctx.get("allow_null", True)),
                )
                if reason:
                    _bump("block_response_semantic_rejects_total")
                    self._rejects_total = int(self._rejects_total or 0) + 1
                    strike(peer, str(reason))
                    if not fut.done():
                        fut.set_result(None)
                    return SolicitResult(True, str(reason))
            if not fut.done():
                fut.set_result(full_msg)
            self._fulfills_total = int(self._fulfills_total or 0) + 1
            return SolicitResult(True, "block_ok")

        if (
            msg_type == MSG_STATE_ROOT_RESPONSE
            and isinstance(request_ctx, dict)
            and request_ctx.get("kind") == "state_root"
        ):
            if self._verify_state_root is not None:
                reason = self._verify_state_root(
                    data if isinstance(data, dict) else (data or {}),
                    int(request_ctx.get("height", 0) or 0),
                    str(request_ctx.get("expected_head") or ""),
                )
                if reason:
                    _bump("state_root_response_request_rejects_total")
                    self._rejects_total = int(self._rejects_total or 0) + 1
                    strike(peer, str(reason))
                    if not fut.done():
                        fut.set_result(None)
                    return SolicitResult(True, str(reason))
            expect_root = str(request_ctx.get("expected_state_root") or "").strip()
            if expect_root and isinstance(data, dict):
                got_root = str(data.get("state_root") or "").strip()
                if got_root and got_root.lower() != expect_root.lower():
                    _bump("state_root_local_rejects_total")
                    self._rejects_total = int(self._rejects_total or 0) + 1
                    strike(peer, "bad_state_root_response_local_root")
                    if not fut.done():
                        fut.set_result(None)
                    return SolicitResult(True, "local_root_mismatch")
            if not fut.done():
                fut.set_result(full_msg)
            self._fulfills_total = int(self._fulfills_total or 0) + 1
            return SolicitResult(True, "state_root_ok")

        if msg_type == MSG_STATE_ROOT_RESPONSE:
            _bump("unsolicited_state_root_rejects_total")
            self._rejects_total = int(self._rejects_total or 0) + 1
            strike(peer, "unsolicited_state_root_response")
            if not fut.done():
                fut.set_result(None)
            return SolicitResult(True, "unsolicited_state_root")

        if msg_type == MSG_MEMPOOL:
            if isinstance(request_ctx, dict) and request_ctx.get("kind") == "mempool":
                if not fut.done():
                    fut.set_result(full_msg)
                self._fulfills_total = int(self._fulfills_total or 0) + 1
                return SolicitResult(True, "mempool_ok")
            _bump("unsolicited_mempool_rejects_total")
            self._rejects_total = int(self._rejects_total or 0) + 1
            strike(peer, "unsolicited_mempool")
            if not fut.done():
                fut.set_result(None)
            return SolicitResult(True, "unsolicited_mempool")

        if msg_type == MSG_BLOCKS:
            if isinstance(request_ctx, dict) and request_ctx.get("kind") == "blocks":
                if not fut.done():
                    fut.set_result(full_msg)
                self._fulfills_total = int(self._fulfills_total or 0) + 1
                return SolicitResult(True, "blocks_ok")
            _bump("unsolicited_block_rejects_total")
            self._rejects_total = int(self._rejects_total or 0) + 1
            strike(peer, "unsolicited_blocks")
            if not fut.done():
                fut.set_result(None)
            return SolicitResult(True, "unsolicited_blocks")

        if msg_type == MSG_BLOCK:
            if isinstance(request_ctx, dict) and request_ctx.get("kind") == "block":
                if not fut.done():
                    fut.set_result(full_msg)
                self._fulfills_total = int(self._fulfills_total or 0) + 1
                return SolicitResult(True, "block_ok")
            _bump("unsolicited_block_rejects_total")
            self._rejects_total = int(self._rejects_total or 0) + 1
            strike(peer, "unsolicited_block")
            if not fut.done():
                fut.set_result(None)
            return SolicitResult(True, "unsolicited_block")

        if msg_type == MSG_PEERS:
            if isinstance(request_ctx, dict) and request_ctx.get("kind") == "peers":
                if not fut.done():
                    fut.set_result(full_msg)
                self._fulfills_total = int(self._fulfills_total or 0) + 1
                return SolicitResult(True, "peers_ok")
            if self._peers_solicit_only:
                _bump("unsolicited_peers_rejects_total")
                self._rejects_total = int(self._rejects_total or 0) + 1
                strike(peer, "unsolicited_peers")
                if not fut.done():
                    fut.set_result(None)
                return SolicitResult(True, "unsolicited_peers")
            if not fut.done():
                fut.set_result(full_msg)
            self._fulfills_total = int(self._fulfills_total or 0) + 1
            return SolicitResult(True, "peers_push_ok")

        if not fut.done():
            fut.set_result(full_msg)
        self._fulfills_total = int(self._fulfills_total or 0) + 1
        return SolicitResult(True, "generic_fulfill")
