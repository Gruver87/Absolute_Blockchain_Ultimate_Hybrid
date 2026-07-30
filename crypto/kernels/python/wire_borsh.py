# crypto/kernels/python/wire_borsh.py
"""Pure-Python Borsh WireEnvelopeV2 + AB2 framing (ADR 0008/0009).

Byte-compatible with ``abs_native`` Borsh layout:

    struct WireEnvelopeV2 {
        version: u8,
        msg_type: String,   // u32 LE len + UTF-8
        payload: Vec<u8>,   // u32 LE len + bytes
    }

Wire line: ``AB2:`` + hex(borsh_body) + ``\\n``
"""

from __future__ import annotations

import json
import struct
from typing import Any, List, Literal, Optional

WIRE_CODEC_VERSION = 2
MAX_MSG_TYPE_LEN = 64
MAX_PAYLOAD_BYTES = 2 * 1024 * 1024
MAX_FRAME_BYTES = MAX_PAYLOAD_BYTES + 128


def _borsh_encode_string(s: str) -> bytes:
    raw = s.encode("utf-8")
    return struct.pack("<I", len(raw)) + raw


def _borsh_encode_bytes(blob: bytes) -> bytes:
    return struct.pack("<I", len(blob)) + blob


def _borsh_decode_string(buf: bytes, offset: int) -> tuple[str, int]:
    if offset + 4 > len(buf):
        raise ValueError("wire_codec_decode_failed: truncated string len")
    (n,) = struct.unpack_from("<I", buf, offset)
    offset += 4
    if n > MAX_MSG_TYPE_LEN + 16 or offset + n > len(buf):
        raise ValueError("wire_codec_decode_failed: bad string length")
    return buf[offset : offset + n].decode("utf-8"), offset + n


def _borsh_decode_bytes(buf: bytes, offset: int) -> tuple[bytes, int]:
    if offset + 4 > len(buf):
        raise ValueError("wire_codec_decode_failed: truncated vec len")
    (n,) = struct.unpack_from("<I", buf, offset)
    offset += 4
    if n > MAX_PAYLOAD_BYTES or offset + n > len(buf):
        raise ValueError("wire_codec_decode_failed: bad payload length")
    return buf[offset : offset + n], offset + n


def encode_wire_envelope_v2(msg_type: str, payload: bytes) -> bytes:
    """Encode raw Borsh ``WireEnvelopeV2`` body."""
    mt = str(msg_type or "")
    if not mt or len(mt.encode("utf-8")) > MAX_MSG_TYPE_LEN:
        raise ValueError("wire_codec_type_invalid")
    raw = bytes(payload)
    if len(raw) > MAX_PAYLOAD_BYTES:
        raise ValueError(
            f"wire_codec_payload_too_large: {len(raw)} > {MAX_PAYLOAD_BYTES}"
        )
    return (
        bytes([WIRE_CODEC_VERSION])
        + _borsh_encode_string(mt)
        + _borsh_encode_bytes(raw)
    )


def decode_wire_envelope_v2(body: bytes) -> dict:
    """Decode Borsh body → ``{version, type, payload}``."""
    buf = bytes(body)
    if not buf:
        raise ValueError("wire_codec_empty")
    if len(buf) > MAX_FRAME_BYTES:
        raise ValueError(f"wire_codec_frame_too_large: {len(buf)} bytes")
    version = buf[0]
    if version != WIRE_CODEC_VERSION:
        raise ValueError(
            f"wire_codec_version_unsupported: {version} (want {WIRE_CODEC_VERSION})"
        )
    msg_type, off = _borsh_decode_string(buf, 1)
    if not msg_type or len(msg_type.encode("utf-8")) > MAX_MSG_TYPE_LEN:
        raise ValueError("wire_codec_type_invalid")
    payload, off = _borsh_decode_bytes(buf, off)
    if off != len(buf):
        raise ValueError("wire_codec_decode_failed: trailing bytes")
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise ValueError(
            f"wire_codec_payload_too_large: {len(payload)} > {MAX_PAYLOAD_BYTES}"
        )
    return {
        "version": int(version),
        "type": msg_type,
        "payload": payload,
    }


def python_wire_detect(line: bytes) -> Literal["v1", "v2"]:
    text = bytes(line).decode("utf-8", errors="ignore").strip()
    return "v2" if text.startswith("AB2:") else "v1"


def python_wire_encode(msg_type: str, data: Any, *, codec: str) -> bytes:
    mode = (codec or "v1").strip().lower()
    if mode in {"v2", "borsh", "wire_v2"}:
        data_json = (
            "null"
            if data is None
            else json.dumps(data, separators=(",", ":"), ensure_ascii=False)
        )
        body = encode_wire_envelope_v2(str(msg_type), data_json.encode("utf-8"))
        return ("AB2:" + body.hex() + "\n").encode("ascii")
    return (
        json.dumps(
            {"type": str(msg_type), "data": data},
            separators=(",", ":"),
            ensure_ascii=False,
        )
        + "\n"
    ).encode("utf-8")


def python_wire_parse(
    line: bytes,
    *,
    max_bytes: int,
    allowed_types: Optional[List[str]] = None,
) -> Optional[dict]:
    raw = bytes(line)
    cap = max(4096, min(int(max_bytes), 16 * 1024 * 1024))
    if len(raw) > cap:
        raise ValueError(f"p2p_line_too_large: {len(raw)} > {max_bytes} bytes")
    text = raw.decode("utf-8", errors="strict").strip()
    if not text:
        return None
    if text.startswith("AB2:"):
        hex_body = text[4:]
        try:
            body = bytes.fromhex(hex_body)
            env = decode_wire_envelope_v2(body)
        except (ValueError, TypeError):
            return None
        msg_type = str(env["type"])
        if allowed_types is not None and allowed_types and msg_type not in allowed_types:
            return None
        try:
            data = json.loads(bytes(env["payload"]).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeError):
            return None
        return {"type": msg_type, "data": data, "wire_codec": "v2"}
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, UnicodeError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    msg_type = payload.get("type")
    if not isinstance(msg_type, str) or not msg_type or len(msg_type) > 64:
        return None
    if allowed_types is not None and allowed_types and msg_type not in allowed_types:
        return None
    return {"type": msg_type, "data": payload.get("data"), "wire_codec": "v1"}
