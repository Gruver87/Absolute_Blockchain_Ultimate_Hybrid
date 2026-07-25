#!/usr/bin/env python3
"""v1.3.88: abs_native P2P fuzz_api + smoke / cargo-fuzz harness."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.config import Config


def test_needles_v1388():
    fuzz_api = (ROOT / "native" / "abs_native" / "src" / "fuzz_api.rs").read_text(
        encoding="utf-8"
    )
    assert "fuzz_p2p_frame_feed" in fuzz_api
    assert "fuzz_p2p_wire_parse" in fuzz_api
    assert "fuzz_p2p_rate_limit_sequence" in fuzz_api
    cargo = (ROOT / "native" / "abs_native" / "Cargo.toml").read_text(encoding="utf-8")
    assert 'crate-type = ["cdylib", "rlib"]' in cargo
    fuzz_toml = (ROOT / "native" / "abs_native" / "fuzz" / "Cargo.toml").read_text(
        encoding="utf-8"
    )
    assert "cargo-fuzz" in fuzz_toml
    assert "p2p_frame" in fuzz_toml
    script = (ROOT / "scripts" / "fuzz_native.ps1").read_text(encoding="utf-8")
    assert "fuzz_p2p_" in script
    wf = (ROOT / ".github" / "workflows" / "fuzz-native.yml").read_text(encoding="utf-8")
    assert "cargo fuzz run" in wf
    notes = (ROOT / "RELEASE_NOTES_v1.3.88.md").read_text(encoding="utf-8")
    assert "1.3.88-industrial" in notes
    assert Config().node_version == "1.3.88-industrial"
