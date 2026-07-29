# network/wire_codec.py
"""
ADR 0008 — Borsh wire codec v2 façade (Python ↔ abs_native).

Replaces hot-path `json.dumps` / NDJSON `data_json` envelopes with a binary
Borsh frame:

    WireEnvelopeV2 { version=2, msg_type: str, payload: bytes }

Legacy helpers remain for dual-stack peers and benchmark baselines.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from crypto.native import native_available, native_error

PayloadLike = Union[bytes, bytearray, memoryview, str, Dict[str, Any], list]

_DISABLE = os.getenv("ABS_DISABLE_NATIVE_CRYPTO", "").lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_REQUIRE = os.getenv("ABS_REQUIRE_NATIVE_CRYPTO", "").lower() in {
    "1",
    "true",
    "yes",
    "on",
}

_native = None
_native_err: Optional[BaseException] = None
if not _DISABLE and native_available():
    try:
        import abs_native as _native  # type: ignore
    except Exception as exc:  # pragma: no cover
        _native_err = exc
elif not _DISABLE:
    _native_err = native_error()


class WireCodecError(ValueError):
    """Raised when encode/decode fails validation or native is unavailable."""


def wire_codec_available() -> bool:
    return _native is not None and hasattr(_native, "encode_wire_v2")


def wire_codec_version() -> int:
    if not wire_codec_available():
        raise WireCodecError(
            f"abs_native wire_codec unavailable: {_native_err or _native_err}"
        )
    return int(_native.wire_codec_version())  # type: ignore[union-attr]


def nominal_packet_bytes() -> int:
    if wire_codec_available():
        return int(_native.wire_codec_nominal_packet_bytes())  # type: ignore[union-attr]
    return 1024


def _coerce_payload(payload: PayloadLike) -> bytes:
    if isinstance(payload, (bytes, bytearray, memoryview)):
        return bytes(payload)
    if isinstance(payload, str):
        return payload.encode("utf-8")
    if isinstance(payload, (dict, list)):
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode(
            "utf-8"
        )
    raise TypeError(f"unsupported payload type: {type(payload)!r}")


def encode_wire_v2(msg_type: str, payload: PayloadLike) -> bytes:
    """Encode a single Borsh v2 envelope. Returns frame bytes (typically ≤1 KiB)."""
    if not wire_codec_available():
        if _REQUIRE:
            raise WireCodecError(
                "ABS_REQUIRE_NATIVE_CRYPTO set but abs_native wire_codec missing"
            )
        raise WireCodecError(f"wire_codec unavailable: {_native_err}")
    raw = _coerce_payload(payload)
    try:
        return bytes(_native.encode_wire_v2(str(msg_type), raw))  # type: ignore[union-attr]
    except Exception as exc:
        raise WireCodecError(str(exc)) from exc


def decode_wire_v2(frame: bytes) -> Dict[str, Any]:
    """Decode Borsh v2 envelope → {version, type, payload: bytes}."""
    if not wire_codec_available():
        raise WireCodecError(f"wire_codec unavailable: {_native_err}")
    try:
        out = _native.decode_wire_v2(bytes(frame))  # type: ignore[union-attr]
    except Exception as exc:
        raise WireCodecError(str(exc)) from exc
    return {
        "version": int(out["version"]),
        "type": str(out["type"]),
        "payload": bytes(out["payload"]),
    }


def encode_wire_v2_batch(
    items: Sequence[Tuple[str, PayloadLike]],
) -> List[bytes]:
    """Batch-encode under native `allow_threads` (GIL released)."""
    if not wire_codec_available():
        raise WireCodecError(f"wire_codec unavailable: {_native_err}")
    prepared: List[Tuple[str, bytes]] = [
        (str(msg_type), _coerce_payload(payload)) for msg_type, payload in items
    ]
    try:
        frames = _native.encode_wire_v2_batch(prepared)  # type: ignore[union-attr]
    except Exception as exc:
        raise WireCodecError(str(exc)) from exc
    return [bytes(f) for f in frames]


def decode_wire_v2_batch(frames: Sequence[bytes]) -> List[Dict[str, Any]]:
    if not wire_codec_available():
        raise WireCodecError(f"wire_codec unavailable: {_native_err}")
    try:
        decoded = _native.decode_wire_v2_batch([bytes(f) for f in frames])  # type: ignore[union-attr]
    except Exception as exc:
        raise WireCodecError(str(exc)) from exc
    return [
        {
            "version": int(item["version"]),
            "type": str(item["type"]),
            "payload": bytes(item["payload"]),
        }
        for item in decoded
    ]


def encode_wire_v2_json_payload(msg_type: str, data: Any) -> bytes:
    """Migration helper: UTF-8 JSON body inside Borsh envelope (not NDJSON)."""
    if isinstance(data, str):
        data_json = data
    else:
        data_json = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    if wire_codec_available() and hasattr(_native, "encode_wire_v2_json_payload"):
        try:
            return bytes(
                _native.encode_wire_v2_json_payload(str(msg_type), data_json)  # type: ignore[union-attr]
            )
        except Exception as exc:
            raise WireCodecError(str(exc)) from exc
    return encode_wire_v2(msg_type, data_json.encode("utf-8"))


def encode_legacy_data_json_line(msg_type: str, data: Any) -> bytes:
    """Baseline NDJSON line used by legacy P2P (`{"type", "data"}\\n`)."""
    if isinstance(data, str):
        data_json = data
    else:
        data_json = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    if wire_codec_available() and hasattr(_native, "encode_legacy_data_json_line"):
        return bytes(
            _native.encode_legacy_data_json_line(str(msg_type), data_json)  # type: ignore[union-attr]
        )
    envelope = {"type": str(msg_type), "data": json.loads(data_json) if data_json else None}
    return (json.dumps(envelope, separators=(",", ":"), ensure_ascii=False) + "\n").encode(
        "utf-8"
    )


def decode_legacy_data_json_line(line: bytes) -> Dict[str, Any]:
    if wire_codec_available() and hasattr(_native, "decode_legacy_data_json_line"):
        out = _native.decode_legacy_data_json_line(bytes(line))  # type: ignore[union-attr]
        return {
            "type": str(out["type"]),
            "data_json": str(out["data_json"]),
            "data": json.loads(out["data_json"]),
        }
    text = bytes(line).decode("utf-8").strip().rstrip("\0")
    obj = json.loads(text)
    data = obj.get("data")
    return {
        "type": str(obj["type"]),
        "data_json": json.dumps(data, separators=(",", ":"), ensure_ascii=False),
        "data": data,
    }


def create_ghost_forest():
    """Opaque native GhostForest handle (no per-call json.dumps of the tree)."""
    if not wire_codec_available() or not hasattr(_native, "GhostForest"):
        raise WireCodecError("GhostForest requires abs_native hotpath")
    return _native.GhostForest()  # type: ignore[union-attr]


# Re-export native class when available for `isinstance` / direct construction.
GhostForest = getattr(_native, "GhostForest", None) if _native is not None else None


__all__ = [
    "WireCodecError",
    "wire_codec_available",
    "wire_codec_version",
    "nominal_packet_bytes",
    "encode_wire_v2",
    "decode_wire_v2",
    "encode_wire_v2_batch",
    "decode_wire_v2_batch",
    "encode_wire_v2_json_payload",
    "encode_legacy_data_json_line",
    "decode_legacy_data_json_line",
    "create_ghost_forest",
    "GhostForest",
]
