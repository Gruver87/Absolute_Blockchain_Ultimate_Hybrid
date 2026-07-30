# crypto/kernels/python/__init__.py
"""Pure-Python kernel backends (ADR 0009)."""

from crypto.kernels.python.wire_borsh import (
    WIRE_CODEC_VERSION,
    decode_wire_envelope_v2,
    encode_wire_envelope_v2,
    python_wire_detect,
    python_wire_encode,
    python_wire_parse,
)

__all__ = [
    "WIRE_CODEC_VERSION",
    "encode_wire_envelope_v2",
    "decode_wire_envelope_v2",
    "python_wire_detect",
    "python_wire_encode",
    "python_wire_parse",
]
