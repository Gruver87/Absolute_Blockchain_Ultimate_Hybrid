"""
WebSocket server — broadcasts blockchain events in real-time to browser clients.
Port 8546  (ws://localhost:8546)
"""
import asyncio
import json
import logging
import time

logger = logging.getLogger("WebSocket")

try:
    import websockets
    from websockets.server import serve as ws_serve
    _WS_AVAILABLE = True
except ImportError:
    _WS_AVAILABLE = False
    logger.warning("[WebSocket] 'websockets' package not found — WS disabled. Run: pip install websockets")


class WebSocketServer:
    """Asyncio WebSocket server that broadcasts chain events to browser clients."""

    def __init__(self, event_bus=None, host: str = "0.0.0.0", port: int = 8546):
        self.host = host
        self.port = port
        self._clients: set = set()
        self._running = False
        self._loop = None

        if event_bus:
            # EventBus uses .on() or .subscribe() depending on implementation
            reg = getattr(event_bus, "subscribe", None) or getattr(event_bus, "on", None)
            if reg:
                reg("block.new", self._on_block)
                reg("tx.new", self._on_tx)

    # ── Event handlers (called from other threads) ────────────────────────────

    def _on_block(self, block):
        msg = {
            "type": "event",
            "event": "NEW_BLOCK",
            "data": {
                "height":    getattr(block, "height", 0),
                "hash":      getattr(block, "hash", ""),
                "txs":       len(getattr(block, "transactions", [])),
                "timestamp": getattr(block, "timestamp", time.time()),
                "miner":     getattr(block, "miner", ""),
                "burned":    float(getattr(block, "total_burned", 0)),
                "state_root": getattr(block, "state_root", ""),
            },
            "ts": time.time(),
        }
        self._schedule(msg)

    def _on_tx(self, tx):
        msg = {
            "type": "event",
            "event": "NEW_TX",
            "data": {
                "hash":  getattr(tx, "tx_hash", str(tx)),
                "from":  getattr(tx, "from_addr", ""),
                "to":    getattr(tx, "to_addr", ""),
                "value": getattr(tx, "amount", 0),
            },
            "ts": time.time(),
        }
        self._schedule(msg)

    def _schedule(self, msg: dict):
        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(self._broadcast(msg), self._loop)

    # ── Broadcast ─────────────────────────────────────────────────────────────

    async def _broadcast(self, msg: dict):
        if not self._clients:
            return
        data = json.dumps(msg, default=str)
        dead = set()
        for ws in list(self._clients):
            try:
                await ws.send(data)
            except Exception:
                dead.add(ws)
        self._clients -= dead

    # ── Connection handler ────────────────────────────────────────────────────

    async def _handler(self, websocket):
        self._clients.add(websocket)
        logger.info(f"[WS] client connected ({len(self._clients)} total)")
        try:
            await websocket.send(json.dumps({
                "type": "connected",
                "message": "Absolute Blockchain WebSocket API v1",
                "ts": time.time(),
            }))
            async for raw in websocket:
                try:
                    data = json.loads(raw)
                    if data.get("type") == "ping":
                        await websocket.send(json.dumps({"type": "pong", "ts": time.time()}))
                except Exception:
                    pass
        except Exception:
            pass
        finally:
            self._clients.discard(websocket)
            logger.debug(f"[WS] client disconnected ({len(self._clients)} remaining)")

    # ── Start / Stop ──────────────────────────────────────────────────────────

    async def start(self):
        if not _WS_AVAILABLE:
            logger.warning("[WebSocket] disabled (install websockets>=12.0)")
            return

        self._loop = asyncio.get_event_loop()
        self._running = True
        try:
            async with ws_serve(self._handler, self.host, self.port):
                logger.info(f"[WebSocket] server running on {self.host}:{self.port}")
                while self._running:
                    await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"[WebSocket] error: {e}")

    def stop(self):
        self._running = False
