# crypto/kernels/ports.py — ADR 0009 switching surfaces
"""Protocols for optional Rust / pure-Python kernel backends."""

from __future__ import annotations

from typing import Any, List, Literal, Optional, Protocol, Sequence, Tuple, runtime_checkable


@runtime_checkable
class WireCodecPort(Protocol):
    """Dual-stack P2P wire (v1 NDJSON + v2 Borsh/AB2)."""

    def detect(self, line: bytes) -> Literal["v1", "v2"]:
        ...

    def encode(self, msg_type: str, data: Any, *, codec: str) -> bytes:
        ...

    def parse(
        self,
        line: bytes,
        *,
        max_bytes: int,
        allowed_types: Optional[List[str]] = None,
    ) -> Optional[dict]:
        ...

    def encode_envelope_v2(self, msg_type: str, payload: bytes) -> bytes:
        """Raw Borsh ``WireEnvelopeV2`` body (no AB2/hex framing)."""
        ...

    def decode_envelope_v2(self, body: bytes) -> dict:
        """Decode Borsh body → ``{version, type, payload}``."""
        ...


@runtime_checkable
class HashKernelPort(Protocol):
    def sha256_hex(self, data: bytes) -> str:
        ...

    def hash_text(self, text: str) -> str:
        ...

    def keccak256_hex(self, data: bytes) -> str:
        ...


@runtime_checkable
class MerklePort(Protocol):
    def merkle_root_strings(self, items: Sequence[str]) -> str:
        ...


@runtime_checkable
class SigPort(Protocol):
    def verify_secp256k1_sha256(
        self, message: bytes, signature: bytes, public_key: bytes
    ) -> bool:
        ...


@runtime_checkable
class P2PTransportCapability(Protocol):
    """Whether native TCP/TLS conn is usable (else asyncio adapter)."""

    def native_transport_available(self) -> bool:
        ...
