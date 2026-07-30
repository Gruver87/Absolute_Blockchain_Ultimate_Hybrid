# network/wire_codec.py
"""
ADR 0008 / 0009 — Borsh wire codec v2 façade (Rust or pure-Python).

Replaces hot-path `json.dumps` / NDJSON `data_json` envelopes with a binary
Borsh frame:

    WireEnvelopeV2 { version=2, msg_type: str, payload: bytes }

Legacy helpers remain for dual-stack peers and benchmark baselines.
Without abs_native, pure-Python Borsh (ADR 0009) keeps AB2 framing working.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

from crypto.kernels.python.wire_borsh import (
    WIRE_CODEC_VERSION,
    decode_wire_envelope_v2,
    encode_wire_envelope_v2,
)
from crypto.native import native_available, native_error
from runtime.native_capabilities import NativeFamily, get_registry

PayloadLike = Union[bytes, bytearray, memoryview, str, Dict[str, Any], list]


class WireCodecError(ValueError):
    """Raised when encode/decode fails validation."""


def wire_codec_available() -> bool:
    """Always true: Python Borsh is a first-class backend (ADR 0009)."""
    return True


def wire_codec_backend() -> str:
    return get_registry().backend(NativeFamily.WIRE_CODEC)


def wire_codec_version() -> int:
    reg = get_registry()
    if reg.use_rust(NativeFamily.WIRE_CODEC):
        mod = reg.module()
        if mod is not None and hasattr(mod, "wire_codec_version"):
            try:
                return int(mod.wire_codec_version())
            except Exception as exc:
                reg.demote(NativeFamily.WIRE_CODEC, str(exc))
    return int(WIRE_CODEC_VERSION)


def nominal_packet_bytes() -> int:
    reg = get_registry()
    if reg.use_rust(NativeFamily.WIRE_CODEC):
        mod = reg.module()
        if mod is not None and hasattr(mod, "wire_codec_nominal_packet_bytes"):
            try:
                return int(mod.wire_codec_nominal_packet_bytes())
            except Exception as exc:
                reg.demote(NativeFamily.WIRE_CODEC, str(exc))
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
    """Encode a single Borsh v2 envelope body (no AB2 framing)."""
    raw = _coerce_payload(payload)
    reg = get_registry()
    if reg.use_rust(NativeFamily.WIRE_CODEC):
        mod = reg.module()
        try:
            return bytes(mod.encode_wire_v2(str(msg_type), raw))  # type: ignore[union-attr]
        except Exception as exc:
            reg.demote(NativeFamily.WIRE_CODEC, str(exc))
    try:
        return encode_wire_envelope_v2(str(msg_type), raw)
    except ValueError as exc:
        raise WireCodecError(str(exc)) from exc


def decode_wire_v2(frame: bytes) -> Dict[str, Any]:
    """Decode Borsh v2 envelope → {version, type, payload: bytes}."""
    reg = get_registry()
    if reg.use_rust(NativeFamily.WIRE_CODEC):
        mod = reg.module()
        try:
            out = mod.decode_wire_v2(bytes(frame))  # type: ignore[union-attr]
            return {
                "version": int(out["version"]),
                "type": str(out["type"]),
                "payload": bytes(out["payload"]),
            }
        except Exception as exc:
            reg.demote(NativeFamily.WIRE_CODEC, str(exc))
    try:
        return decode_wire_envelope_v2(bytes(frame))
    except ValueError as exc:
        raise WireCodecError(str(exc)) from exc


def encode_wire_v2_batch(
    items: Sequence[Tuple[str, PayloadLike]],
) -> List[bytes]:
    """Batch-encode (native ``allow_threads`` when Rust wire backend is active)."""
    prepared: List[Tuple[str, bytes]] = [
        (str(msg_type), _coerce_payload(payload)) for msg_type, payload in items
    ]
    reg = get_registry()
    if reg.use_rust(NativeFamily.WIRE_CODEC):
        mod = reg.module()
        if mod is not None and hasattr(mod, "encode_wire_v2_batch"):
            try:
                frames = mod.encode_wire_v2_batch(prepared)
                return [bytes(f) for f in frames]
            except Exception as exc:
                reg.demote(NativeFamily.WIRE_CODEC, str(exc))
    return [encode_wire_envelope_v2(mt, pl) for mt, pl in prepared]


def decode_wire_v2_batch(frames: Sequence[bytes]) -> List[Dict[str, Any]]:
    reg = get_registry()
    if reg.use_rust(NativeFamily.WIRE_CODEC):
        mod = reg.module()
        if mod is not None and hasattr(mod, "decode_wire_v2_batch"):
            try:
                decoded = mod.decode_wire_v2_batch([bytes(f) for f in frames])
                return [
                    {
                        "version": int(item["version"]),
                        "type": str(item["type"]),
                        "payload": bytes(item["payload"]),
                    }
                    for item in decoded
                ]
            except Exception as exc:
                reg.demote(NativeFamily.WIRE_CODEC, str(exc))
    return [decode_wire_envelope_v2(bytes(f)) for f in frames]


def encode_wire_v2_json_payload(msg_type: str, data: Any) -> bytes:
    """Migration helper: UTF-8 JSON body inside Borsh envelope (not NDJSON)."""
    if isinstance(data, str):
        data_json = data
    else:
        data_json = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    reg = get_registry()
    if reg.use_rust(NativeFamily.WIRE_CODEC):
        mod = reg.module()
        if mod is not None and hasattr(mod, "encode_wire_v2_json_payload"):
            try:
                return bytes(mod.encode_wire_v2_json_payload(str(msg_type), data_json))
            except Exception as exc:
                reg.demote(NativeFamily.WIRE_CODEC, str(exc))
    return encode_wire_v2(msg_type, data_json.encode("utf-8"))


def encode_legacy_data_json_line(msg_type: str, data: Any) -> bytes:
    """Baseline NDJSON line used by legacy P2P (`{"type", "data"}\\n`)."""
    if isinstance(data, str):
        data_json = data
    else:
        data_json = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    reg = get_registry()
    if reg.use_rust(NativeFamily.WIRE_CODEC):
        mod = reg.module()
        if mod is not None and hasattr(mod, "encode_legacy_data_json_line"):
            try:
                return bytes(mod.encode_legacy_data_json_line(str(msg_type), data_json))
            except Exception as exc:
                reg.demote(NativeFamily.WIRE_CODEC, str(exc))
    envelope = {
        "type": str(msg_type),
        "data": json.loads(data_json) if data_json and data_json != "null" else None,
    }
    return (
        json.dumps(envelope, separators=(",", ":"), ensure_ascii=False) + "\n"
    ).encode("utf-8")


def decode_legacy_data_json_line(line: bytes) -> Dict[str, Any]:
    reg = get_registry()
    if reg.use_rust(NativeFamily.WIRE_CODEC):
        mod = reg.module()
        if mod is not None and hasattr(mod, "decode_legacy_data_json_line"):
            try:
                out = mod.decode_legacy_data_json_line(bytes(line))
                return {
                    "type": str(out["type"]),
                    "data_json": str(out["data_json"]),
                    "data": json.loads(out["data_json"]),
                }
            except Exception as exc:
                reg.demote(NativeFamily.WIRE_CODEC, str(exc))
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
    reg = get_registry()
    if not reg.use_rust(NativeFamily.GHOST):
        raise WireCodecError("GhostForest requires abs_native hotpath (ghost=rust)")
    mod = reg.module()
    if mod is None or not hasattr(mod, "GhostForest"):
        raise WireCodecError(
            f"GhostForest requires abs_native hotpath: {native_error()}"
        )
    return mod.GhostForest()


_reg_mod = get_registry().module() if native_available() else None
GhostForest = getattr(_reg_mod, "GhostForest", None) if _reg_mod is not None else None


__all__ = [
    "WireCodecError",
    "wire_codec_available",
    "wire_codec_backend",
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
