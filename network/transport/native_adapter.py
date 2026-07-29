"""NativeTransportAdapter — facade over ``crypto.native`` P2P kernels.

Isolates dial/listen/admit/egress from tip/sync/mempool domains. Does **not**
wire into ``P2PNode._message_loop`` (step C — separate approval).
"""

from __future__ import annotations

import json
from typing import Any, List, Mapping, Optional, Sequence

from network.transport.errors import (
    TransportCapabilityError,
    TransportIoError,
    TransportValidationError,
)
from network.transport.reject import RejectCounters, make_reject
from network.transport.types import (
    AdmitDecision,
    InboundFrame,
    OutboundEnvelope,
    PeerEndpoint,
    TransportRejectClass,
)


class NativeTransportAdapter:
    """Transport port implementation backed by abs_native when available.

    Args:
        require_native: When True, capability / admit paths raise if native
            kernels are missing (prod-style fail-closed). When False, admit
            returns a structured CAPABILITY reject instead of raising.
        wire_codec: Outbound wire codec (``v1`` NDJSON / ``v2`` Borsh AB2).
            ``None`` → ``ABS_P2P_WIRE_CODEC`` (default ``v1``). Inbound always
            auto-detects ``AB2:`` vs JSON.
    """

    __slots__ = ("_require_native", "_counters", "_wire_codec")

    def __init__(
        self,
        *,
        require_native: bool = False,
        wire_codec: Optional[str] = None,
    ) -> None:
        self._require_native = bool(require_native)
        self._counters = RejectCounters()
        self._wire_codec = wire_codec

    @property
    def wire_codec(self) -> str:
        from crypto import native as nat

        if self._wire_codec is not None:
            raw = str(self._wire_codec).strip().lower()
            if raw in {"v2", "borsh", "wire_v2"}:
                return "v2"
            if raw in {"auto"}:
                return "auto"
            return "v1"
        return nat.p2p_wire_codec_mode()

    def resolve_outbound_codec(self, peer_codec: str = "v1") -> str:
        """Map adapter policy + peer's last inbound codec → concrete ``v1``/``v2``."""
        policy = self.wire_codec
        if policy == "auto":
            return "v2" if str(peer_codec).strip().lower() == "v2" else "v1"
        return policy

    @property
    def counters(self) -> RejectCounters:
        """Mutable reject / admit counters for metrics merge."""
        return self._counters

    def capability_status(self) -> Mapping[str, Any]:
        """Return transport/TLS availability flags."""
        from crypto import native as n

        err = n.native_error()
        return {
            "available": bool(n.native_available()),
            "transport": bool(n.p2p_native_transport_available()),
            "tls": bool(n.p2p_native_tls_available()),
            "require_native": self._require_native,
            "wire_codec": self.wire_codec,
            "error": str(err) if err else "",
        }

    def require_transport(self) -> None:
        """Raise if native P2P transport kernel is unavailable."""
        status = self.capability_status()
        if not status["transport"]:
            raise TransportCapabilityError(
                f"native P2P transport unavailable: {status.get('error') or 'not loaded'}",
                code="transport_capability",
            )

    def clamp_batch(self, n: int) -> int:
        """Clamp native read/write batch size."""
        from crypto import native as nat

        return int(nat.p2p_native_clamp_batch(int(n)))

    def clamp_chunk(self, n: int) -> int:
        """Clamp native read chunk bytes."""
        from crypto import native as nat

        return int(nat.p2p_native_clamp_chunk(int(n)))

    def clamp_timeout_ms(self, n: int) -> int:
        """Clamp native socket I/O timeout."""
        from crypto import native as nat

        return int(nat.p2p_native_clamp_timeout_ms(int(n)))

    def connect(
        self,
        endpoint: PeerEndpoint,
        *,
        max_bytes: int = 2 * 1024 * 1024,
        timeout_ms: int = 10_000,
        cert_path: Optional[str] = None,
        key_path: Optional[str] = None,
        ca_path: Optional[str] = None,
    ) -> Any:
        """Outbound TCP(+TLS) framed connect. Returns opaque native handle."""
        if not isinstance(endpoint, PeerEndpoint):
            raise TransportValidationError("endpoint must be PeerEndpoint")
        self.require_transport()
        from crypto import native as nat

        try:
            return nat.p2p_native_connect(
                endpoint.host,
                endpoint.port,
                max_bytes=int(max_bytes),
                timeout_ms=int(timeout_ms),
                cert_path=cert_path,
                key_path=key_path,
                ca_path=ca_path,
            )
        except TransportCapabilityError:
            raise
        except Exception as exc:
            raise TransportIoError(
                f"connect failed {endpoint.host}:{endpoint.port}: {exc}",
                code="transport_io",
            ) from exc

    def admit_inbound_line(
        self,
        line: bytes,
        *,
        peer_id: str,
        now: float,
        max_bytes: int = 2 * 1024 * 1024,
        allowed_types: Optional[Sequence[str]] = None,
        rate_table: Any = None,
    ) -> AdmitDecision:
        """Admit one NDJSON line via native ingress (or capability reject).

        Wire rejects never raise; capability missing raises only when
        ``require_native=True``.
        """
        if not isinstance(line, (bytes, bytearray)):
            reject = make_reject("transport_validation", "line must be bytes")
            self._counters.record_reject(reject)
            return AdmitDecision(ok=False, reject=reject)
        if not peer_id or not str(peer_id).strip():
            reject = make_reject("empty_peer_id", "peer_id required")
            self._counters.record_reject(reject)
            return AdmitDecision(ok=False, reject=reject)

        from crypto import native as nat

        if not nat.native_available() or not hasattr(nat, "p2p_ingress_admit"):
            return self._capability_admit_fail("p2p_ingress_admit unavailable")

        try:
            raw = nat.p2p_ingress_admit(
                bytes(line),
                str(peer_id),
                float(now),
                max_bytes=int(max_bytes),
                allowed_types=list(allowed_types) if allowed_types is not None else None,
                rl=rate_table,
            )
        except Exception as exc:
            if self._require_native:
                raise TransportCapabilityError(
                    f"ingress admit failed: {exc}",
                    code="transport_capability",
                ) from exc
            reject = make_reject("native_unavailable", str(exc))
            self._counters.record_reject(reject)
            return AdmitDecision(ok=False, reject=reject)

        return self._decision_from_ingress(raw, peer_id=str(peer_id), raw_len=len(line))

    def prepare_outbound(
        self,
        envelope: OutboundEnvelope,
        *,
        now: float,
        max_bytes: int = 2 * 1024 * 1024,
        allowed_types: Optional[Sequence[str]] = None,
        rate_table: Any = None,
        data_json: Optional[str] = None,
        peer_wire_codec: str = "v1",
    ) -> AdmitDecision:
        """Encode + allowlist + egress admit via native prepare.

        Args:
            data_json: When set, use this wire JSON for ``data`` instead of
                dumping ``envelope.payload`` (preserves peer ``ensure_ascii=False``
                serialization parity with legacy ``p2p_egress_prepare`` callers).
            peer_wire_codec: Last inbound codec for this peer (``v1``/``v2``);
                used when adapter policy is ``auto``.
        """
        if not isinstance(envelope, OutboundEnvelope):
            reject = make_reject("transport_validation", "envelope must be OutboundEnvelope")
            self._counters.record_reject(reject)
            return AdmitDecision(ok=False, reject=reject)
        if not envelope.peer_id.strip():
            reject = make_reject("empty_peer_id", "peer_id required")
            self._counters.record_reject(reject)
            return AdmitDecision(ok=False, reject=reject)
        if not envelope.msg_type.strip():
            reject = make_reject("transport_validation", "msg_type required")
            self._counters.record_reject(reject)
            return AdmitDecision(ok=False, reject=reject)

        from crypto import native as nat

        if not nat.native_available() or not hasattr(nat, "p2p_egress_prepare"):
            return self._capability_admit_fail("p2p_egress_prepare unavailable")

        try:
            if data_json is None:
                wire_json = json.dumps(
                    dict(envelope.payload), separators=(",", ":"), sort_keys=True
                )
            else:
                wire_json = str(data_json)
            raw = nat.p2p_egress_prepare(
                envelope.msg_type,
                wire_json,
                envelope.peer_id,
                float(now),
                max_bytes=int(max_bytes),
                allowed_types=list(allowed_types) if allowed_types is not None else None,
                rl=rate_table,
                codec=self.resolve_outbound_codec(peer_wire_codec),
            )
        except Exception as exc:
            if self._require_native:
                raise TransportCapabilityError(
                    f"egress prepare failed: {exc}",
                    code="transport_capability",
                ) from exc
            reject = make_reject("native_unavailable", str(exc))
            self._counters.record_reject(reject)
            return AdmitDecision(ok=False, reject=reject)

        return self._decision_from_egress(raw, peer_id=envelope.peer_id, msg_type=envelope.msg_type)

    def merge_into_status(self, status: dict[str, Any]) -> dict[str, Any]:
        """Merge transport counters + capability into a p2p_security-like dict.

        Mutates ``status`` in place (same contract as tip-safety shadow) and
        returns it for chaining.
        """
        status.update(self._counters.as_status())
        cap = self.capability_status()
        status["transport_native_available"] = bool(cap.get("available"))
        status["transport_native_transport"] = bool(cap.get("transport"))
        status["transport_native_tls"] = bool(cap.get("tls"))
        status["transport_wire_codec"] = str(cap.get("wire_codec") or self.wire_codec)
        return status

    def _capability_admit_fail(self, detail: str) -> AdmitDecision:
        if self._require_native:
            raise TransportCapabilityError(detail, code="transport_capability")
        reject = make_reject("native_unavailable", detail)
        # Force CAPABILITY class even if prefix mapping differs.
        reject = type(reject)(
            reason_code=reject.reason_code,
            reject_class=TransportRejectClass.CAPABILITY,
            detail=reject.detail,
        )
        self._counters.record_reject(reject)
        return AdmitDecision(ok=False, reject=reject)

    def _decision_from_ingress(
        self, raw: Any, *, peer_id: str, raw_len: int
    ) -> AdmitDecision:
        if not isinstance(raw, Mapping):
            reject = make_reject("transport_internal", "ingress returned non-mapping")
            self._counters.record_reject(reject)
            return AdmitDecision(ok=False, reject=reject)
        if not raw.get("ok"):
            reason = str(raw.get("reason") or "admit_reject")
            reject = make_reject(reason)
            self._counters.record_reject(reject)
            return AdmitDecision(ok=False, reject=reject)
        msg_type = str(raw.get("type") or "")
        if not msg_type:
            reject = make_reject("p2p_missing_type", "ok response missing type")
            self._counters.record_reject(reject)
            return AdmitDecision(ok=False, reject=reject)
        frame = InboundFrame(
            peer_id=peer_id,
            msg_type=msg_type,
            data=raw.get("data"),
            raw_len=int(raw_len),
            wire_codec=str(raw.get("wire_codec") or "v1"),
        )
        self._counters.record_admit_ok()
        return AdmitDecision(ok=True, frame=frame)

    def _decision_from_egress(
        self, raw: Any, *, peer_id: str, msg_type: str
    ) -> AdmitDecision:
        if not isinstance(raw, Mapping):
            reject = make_reject("transport_internal", "egress returned non-mapping")
            self._counters.record_reject(reject)
            return AdmitDecision(ok=False, reject=reject)
        if not raw.get("ok"):
            reason = str(raw.get("reason") or "egress_reject")
            reject = make_reject(reason)
            self._counters.record_reject(reject)
            return AdmitDecision(ok=False, reject=reject)
        payload = raw.get("payload")
        if payload is None:
            reject = make_reject("transport_internal", "egress ok missing payload")
            self._counters.record_reject(reject)
            return AdmitDecision(ok=False, reject=reject)
        if isinstance(payload, memoryview):
            payload_b = bytes(payload)
        elif isinstance(payload, (bytes, bytearray)):
            payload_b = bytes(payload)
        else:
            payload_b = bytes(payload)
        frame = InboundFrame(
            peer_id=peer_id,
            msg_type=msg_type,
            data={"payload": payload_b},
            raw_len=len(payload_b),
        )
        self._counters.record_egress_ok()
        return AdmitDecision(ok=True, frame=frame)


def default_allowed_types() -> List[str]:
    """Minimal allowlist for adapter unit tests (not production gate set)."""
    return ["PING", "PONG", "STATUS", "TX", "BLOCK"]
