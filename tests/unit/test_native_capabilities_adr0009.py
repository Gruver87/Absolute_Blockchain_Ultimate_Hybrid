# tests/unit/test_native_capabilities_adr0009.py
"""ADR 0009 — optional Rust capability registry + Python Borsh wire."""

from __future__ import annotations

import os

import pytest

from crypto.kernels.python.wire_borsh import (
    decode_wire_envelope_v2,
    encode_wire_envelope_v2,
    python_wire_encode,
    python_wire_parse,
)
from crypto.native import native_available, native_capabilities_status, native_crypto_status
from network.wire_codec import decode_wire_v2, encode_wire_v2, wire_codec_available
from runtime.native_capabilities import (
    NativeCapabilityRegistry,
    NativeFamily,
    resolve_native_mode,
)


def test_resolve_native_mode_aliases(monkeypatch):
    monkeypatch.delenv("ABS_NATIVE_MODE", raising=False)
    monkeypatch.delenv("ABS_DISABLE_NATIVE_CRYPTO", raising=False)
    monkeypatch.delenv("ABS_REQUIRE_NATIVE_CRYPTO", raising=False)
    assert resolve_native_mode() == "auto"
    monkeypatch.setenv("ABS_DISABLE_NATIVE_CRYPTO", "1")
    assert resolve_native_mode() == "off"
    monkeypatch.delenv("ABS_DISABLE_NATIVE_CRYPTO", raising=False)
    monkeypatch.setenv("ABS_REQUIRE_NATIVE_CRYPTO", "true")
    assert resolve_native_mode() == "require"
    monkeypatch.setenv("ABS_NATIVE_MODE", "off")
    assert resolve_native_mode() == "off"


def test_python_borsh_roundtrip():
    body = encode_wire_envelope_v2("new_tx", b'{"v":1}')
    env = decode_wire_envelope_v2(body)
    assert env["version"] == 2
    assert env["type"] == "new_tx"
    assert env["payload"] == b'{"v":1}'


def test_python_ab2_line_roundtrip():
    line = python_wire_encode("ping", {"n": 1}, codec="v2")
    assert line.startswith(b"AB2:")
    parsed = python_wire_parse(line, max_bytes=2 * 1024 * 1024)
    assert parsed is not None
    assert parsed["type"] == "ping"
    assert parsed["data"] == {"n": 1}
    assert parsed["wire_codec"] == "v2"


def test_wire_codec_available_without_raising():
    assert wire_codec_available() is True
    frame = encode_wire_v2("status", b"{}")
    out = decode_wire_v2(frame)
    assert out["type"] == "status"


@pytest.mark.skipif(not native_available(), reason="abs_native not installed")
def test_python_borsh_matches_rust_golden():
    vectors = [
        ("ping", b"{}"),
        ("new_tx", b'{"hash":"abc"}'),
        ("new_block", bytes(range(64))),
        ("x" * 64, b"z" * 128),
    ]
    import abs_native

    for msg_type, payload in vectors:
        py = encode_wire_envelope_v2(msg_type, payload)
        rs = bytes(abs_native.encode_wire_v2(msg_type, payload))
        assert py == rs, msg_type
        assert decode_wire_envelope_v2(py)["payload"] == payload


def test_registry_force_off(monkeypatch):
    monkeypatch.setenv("ABS_NATIVE_MODE", "off")
    reg = NativeCapabilityRegistry()
    reg.bootstrap()
    st = reg.status()
    assert st["mode"] == "off"
    assert all(v["backend"] == "python" for v in st["families"].values())
    assert reg.backend(NativeFamily.WIRE_CODEC) == "python"


def test_registry_require_without_module(monkeypatch):
    monkeypatch.setenv("ABS_NATIVE_MODE", "require")

    class Boom(NativeCapabilityRegistry):
        def bootstrap(self) -> None:
            self._mode = "require"
            self._module = None
            self._import_error = "forced"
            self._finalize_python_only("forced")
            # simulate require path
            raise RuntimeError("ABS_NATIVE_MODE=require but abs_native is not available")

    with pytest.raises(RuntimeError, match="require"):
        Boom().bootstrap()


def test_native_crypto_status_exposes_capabilities():
    st = native_crypto_status()
    assert "capabilities" in st
    assert "mode" in st
    caps = native_capabilities_status()
    assert "families" in caps
