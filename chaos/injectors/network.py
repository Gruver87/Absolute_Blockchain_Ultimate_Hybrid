# chaos/injectors/network.py — tear / delay / garbage wire_codec_v2 (ADR 0012)
"""Inject at codec / scripted-conn seam — never patch Rust allow_threads.

NET_GARBAGE feeds truncated / mutated ``AB2:`` frames into ``decode_wire_v2``
and asserts fail-closed reject (no tip rewrite from garbage).
"""

from __future__ import annotations

import time
from typing import List, Optional

from chaos.ports import (
    FaultKind,
    InjectionOutcome,
    InjectionResult,
    InjectionSpec,
)


class ScriptedConn:
    """Stand-in for P2PNativeConn — tear / delay / garbage without native FFI."""

    def __init__(self) -> None:
        self.torn = False
        self.delay_ms = 0
        self.inbox: List[bytes] = []
        self.outbox: List[bytes] = []

    def tear(self) -> None:
        self.torn = True

    def write_message(self, data: bytes) -> None:
        if self.torn:
            raise ConnectionError("socket torn")
        if self.delay_ms:
            time.sleep(self.delay_ms / 1000.0)
        self.outbox.append(bytes(data))

    def read_message(self) -> bytes:
        if self.torn:
            raise ConnectionError("socket torn")
        if self.delay_ms:
            time.sleep(self.delay_ms / 1000.0)
        if not self.inbox:
            raise ConnectionError("empty / peer closed")
        return self.inbox.pop(0)


class NetworkChaosInjector:
    """ChaosPort wrapper for NET_TEAR / NET_DELAY / NET_GARBAGE."""

    KIND_MAP = {
        FaultKind.NET_TEAR,
        FaultKind.NET_DELAY,
        FaultKind.NET_GARBAGE,
    }

    def __init__(self) -> None:
        self.conn = ScriptedConn()
        self._armed: Optional[InjectionSpec] = None

    def arm(self, spec: InjectionSpec) -> None:
        self._armed = spec

    def disarm(self) -> None:
        self._armed = None
        self.conn = ScriptedConn()

    def fire(self, spec: InjectionSpec) -> InjectionResult:
        try:
            if spec.kind == FaultKind.NET_TEAR:
                return self._fire_tear(spec)
            if spec.kind == FaultKind.NET_DELAY:
                return self._fire_delay(spec)
            if spec.kind == FaultKind.NET_GARBAGE:
                return self._fire_garbage(spec)
            return InjectionResult(
                kind=spec.kind,
                outcome=InjectionOutcome.PANIC.value,
                detail="unsupported_kind",
                wave_id=spec.wave_id,
            )
        except Exception as exc:
            return InjectionResult(
                kind=spec.kind,
                outcome=InjectionOutcome.PANIC.value,
                detail=f"uncaught:{exc!r}",
                wave_id=spec.wave_id,
            )

    def _fire_tear(self, spec: InjectionSpec) -> InjectionResult:
        self.conn.tear()
        try:
            self.conn.write_message(b"ping")
            return InjectionResult(
                kind=spec.kind,
                outcome=InjectionOutcome.PANIC.value,
                detail="tear did not raise",
                wave_id=spec.wave_id,
            )
        except ConnectionError:
            return InjectionResult(
                kind=spec.kind,
                outcome=InjectionOutcome.FAIL_CLOSED.value,
                detail="socket_torn",
                wave_id=spec.wave_id,
            )

    def _fire_delay(self, spec: InjectionSpec) -> InjectionResult:
        delay = int(spec.params.get("delay_ms", 1) or 1)
        delay = max(0, min(delay, 5))
        self.conn.delay_ms = delay
        self.conn.inbox.append(b"ok")
        t0 = time.perf_counter()
        _ = self.conn.read_message()
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        self.conn.delay_ms = 0
        self.conn.inbox.append(b"ok2")
        self.conn.read_message()
        return InjectionResult(
            kind=spec.kind,
            outcome=InjectionOutcome.RECOVERED.value,
            detail=f"delayed_ms≈{elapsed_ms:.1f}",
            wave_id=spec.wave_id,
        )

    def _fire_garbage(self, spec: InjectionSpec) -> InjectionResult:
        garbage = spec.params.get("payload")
        if not isinstance(garbage, (bytes, bytearray)):
            garbage = b"AB2:\x00\xffgarbage<<<"
        payload = bytes(garbage)
        # Dual seam: wire_codec_v2 decode + scripted conn ingest.
        rejected = self._admit_garbage(payload)
        self.conn.inbox.append(payload)
        try:
            raw = self.conn.read_message()
            # Reading garbage bytes is fine; decode must still reject.
            if not self._admit_garbage(raw):
                rejected = False
        except ConnectionError:
            rejected = True
        if rejected:
            return InjectionResult(
                kind=spec.kind,
                outcome=InjectionOutcome.FAIL_CLOSED.value,
                detail="garbage_rejected_wire_codec_v2",
                wave_id=spec.wave_id,
            )
        return InjectionResult(
            kind=spec.kind,
            outcome=InjectionOutcome.PANIC.value,
            detail="garbage_accepted",
            wave_id=spec.wave_id,
        )

    @staticmethod
    def _admit_garbage(payload: bytes) -> bool:
        """True when garbage is rejected at wire_codec_v2 (fail-closed)."""
        try:
            from network.wire_codec import decode_wire_v2

            decode_wire_v2(payload)
            return False
        except Exception:
            return True
