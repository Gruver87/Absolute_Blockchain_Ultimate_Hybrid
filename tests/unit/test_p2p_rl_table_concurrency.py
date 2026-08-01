"""Concurrent native rate-limit table access must not raise borrow errors."""

from __future__ import annotations

import threading
import time

import pytest

from crypto import native


@pytest.mark.skipif(
    not native.native_available() or not hasattr(native, "P2PRateLimitTable"),
    reason="abs_native P2PRateLimitTable required",
)
def test_rate_limit_table_concurrent_prepare_and_strike():
    """Reproduce mesh race: egress prepare vs PeerManager.strike on shared table."""
    table = native.P2PRateLimitTable(500, 5, 300, None, 0, 0, 0)
    errors: list[BaseException] = []
    stop = threading.Event()

    def preparer():
        while not stop.is_set():
            try:
                out = native.p2p_egress_prepare(
                    "status",
                    '{"height":0}',
                    "peer-a",
                    time.time(),
                    2 * 1024 * 1024,
                    ["status", "ping", "pong"],
                    table,
                    "v1",
                )
                assert isinstance(out, dict)
            except Exception as exc:  # noqa: BLE001 — collect race failures
                errors.append(exc)
                return

    def striker():
        while not stop.is_set():
            try:
                table.strike("peer-b", time.time())
                _ = table.is_banned("peer-b", time.time())
                _ = table.ban_keys()
                _ = table.tracked_strikes()
                _ = int(getattr(table, "egress_rejects", 0) or 0)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
                return

    threads = [
        threading.Thread(target=preparer, name="rl-prepare"),
        threading.Thread(target=striker, name="rl-strike"),
        threading.Thread(target=preparer, name="rl-prepare-2"),
    ]
    for t in threads:
        t.start()
    time.sleep(0.8)
    stop.set()
    for t in threads:
        t.join(timeout=5)

    borrow = [e for e in errors if "borrow" in str(e).lower()]
    assert not borrow, f"PyO3 borrow races: {borrow[:3]}"
    assert not errors, f"unexpected rl table errors: {errors[:3]}"
