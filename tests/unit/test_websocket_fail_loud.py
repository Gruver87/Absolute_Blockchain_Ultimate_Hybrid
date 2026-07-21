#!/usr/bin/env python3
"""WebSocket fail-loud counters."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from network.websocket import WebSocketServer


def test_send_json_counts_failures():
    ws = WebSocketServer()
    assert ws._send_failures == 0

    class _BadWs:
        async def send(self, _data):
            raise RuntimeError("send failed")

    asyncio.run(ws._send_json(_BadWs(), {"type": "ping"}))
    assert ws._send_failures == 1
