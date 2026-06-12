#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
P2P Network — TCP-сеть для синхронизации блоков и транзакций.

Протокол: JSON-сообщения через asyncio TCP сокеты.
Возможности:
  - Handshake (проверка chain_id)
  - Анонс и получение блоков (block gossip)
  - Трансляция транзакций (tx gossip)
  - Синхронизация цепочки (sync)
  - Обмен списком пиров (peer discovery)
"""

import asyncio
import json
import time
import threading
import logging
from typing import Dict, List, Optional, Callable, Any

logger = logging.getLogger("P2P")

# --- SyncEngine (System C: fast catch-up) ---
try:
    from sync.sync_engine import SyncEngine
    _SYNC_ENGINE_AVAILABLE = True
except ImportError:
    _SYNC_ENGINE_AVAILABLE = False

# ── Типы сообщений ────────────────────────────────────────────────────────────

MSG_HANDSHAKE  = "handshake"
MSG_HANDSHAKE_ACK = "handshake_ack"
MSG_PING       = "ping"
MSG_PONG       = "pong"
MSG_NEW_BLOCK  = "new_block"
MSG_GET_BLOCK  = "get_block"
MSG_BLOCK      = "block"
MSG_GET_BLOCKS = "get_blocks"   # диапазон блоков
MSG_BLOCKS     = "blocks"
MSG_NEW_TX     = "new_tx"
MSG_GET_PEERS  = "get_peers"
MSG_PEERS      = "peers"
MSG_STATUS     = "status"       # height + head hash


class PeerConnection:
    """Активное соединение с одним пиром."""

    def __init__(self, reader: asyncio.StreamReader,
                 writer: asyncio.StreamWriter,
                 peer_id: str = ""):
        self.reader = reader
        self.writer = writer
        self.peer_id = peer_id
        self.host = writer.get_extra_info("peername", ("?", 0))[0]
        self.port = 0
        self.chain_id: int = 0
        self.height: int = 0
        self.head: Optional[str] = None  # head block hash (for SyncEngine/GHOST)
        self.connected_at = time.time()
        self.last_seen = time.time()
        self.is_synced = False

    def touch(self):
        self.last_seen = time.time()

    async def send(self, msg_type: str, data: Any = None):
        """Отправляет JSON-сообщение пиру."""
        payload = json.dumps({"type": msg_type, "data": data}) + "\n"
        try:
            self.writer.write(payload.encode())
            await self.writer.drain()
        except Exception as e:
            logger.debug(f"[P2P] send error to {self.peer_id}: {e}")

    async def recv(self) -> Optional[Dict]:
        """Читает одно JSON-сообщение от пира."""
        try:
            line = await asyncio.wait_for(self.reader.readline(), timeout=30)
            if not line:
                return None
            return json.loads(line.decode().strip())
        except (asyncio.TimeoutError, json.JSONDecodeError, Exception):
            return None

    def close(self):
        try:
            self.writer.close()
        except Exception:
            pass

    def __repr__(self) -> str:
        return f"Peer({self.peer_id[:8]}… {self.host}:{self.port} h={self.height})"


class P2PNode:
    """
    TCP P2P-узел: принимает входящие соединения и подключается к bootstrap пирам.
    Интегрирован с Blockchain, Mempool и EventBus.
    """

    def __init__(self, config, blockchain, mempool, bus=None):
        self.config = config
        self.blockchain = blockchain
        self.mempool = mempool
        self.bus = bus

        self.peers: Dict[str, PeerConnection] = {}  # peer_id → PeerConnection
        self._known_addrs: List[str] = []            # host:port для переподключения
        self._server: Optional[asyncio.Server] = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Подписка на события шины — транслируем в сеть
        if self.bus:
            self.bus.on("block.new", self._on_local_block)
            self.bus.on("tx.new", self._on_local_tx)

        # SyncEngine (System C) — fast catch-up
        if _SYNC_ENGINE_AVAILABLE:
            self.sync_engine = SyncEngine(node=self)
            print("[P2P] SyncEngine: enabled (fast catch-up)")
        else:
            self.sync_engine = None

    # --- SyncEngine interface (called by SyncEngine) ---

    @property
    def head(self) -> Optional[str]:
        """Current head block hash for SyncEngine."""
        last = self.blockchain.get_last_block()
        return last["hash"] if last else None

    def get_block(self, block_hash: str) -> Optional[Dict]:
        """For SyncEngine.download_chain()."""
        if hasattr(self.blockchain, "get_block_by_hash"):
            return self.blockchain.get_block_by_hash(block_hash)
        return None

    def import_block(self, block_data: Dict) -> bool:
        """For SyncEngine.fast_sync()."""
        if hasattr(self.blockchain, "import_block"):
            return self.blockchain.import_block(block_data)
        from core.blockchain import Block
        try:
            blk = Block.from_dict(block_data)
            return self.blockchain.add_block(blk)
        except Exception:
            return False

    # ── Запуск / остановка ───────────────────────────────────────────────────

    async def start(self):
        """Запускает TCP-сервер и подключается к bootstrap пирам."""
        self._running = True
        self._loop = asyncio.get_event_loop()

        # Запускаем TCP-сервер
        try:
            self._server = await asyncio.start_server(
                self._handle_incoming,
                self.config.p2p_host,
                self.config.p2p_port,
            )
            print(f"[P2P] Listening on {self.config.p2p_host}:{self.config.p2p_port}")
        except OSError as e:
            print(f"[P2P] Could not bind port {self.config.p2p_port}: {e}")
            print("[P2P] Hint: stop other node — .\\scripts\\stop_node.ps1 — or use --port 5001")

        # Подключаемся к bootstrap пирам
        for peer_addr in self.config.bootstrap_peers:
            parts = peer_addr.split(":")
            if len(parts) == 2:
                asyncio.create_task(self.connect_peer(parts[0], int(parts[1])))

        # Периодические задачи
        asyncio.create_task(self._ping_loop())
        asyncio.create_task(self._discovery_loop())
        asyncio.create_task(self._bootstrap_retry_loop())
        asyncio.create_task(self._solo_node_hint())

        if self._server:
            async with self._server:
                await self._server.serve_forever()

    def stop(self):
        self._running = False
        if self._server:
            self._server.close()
        for peer in list(self.peers.values()):
            peer.close()
        self.peers.clear()
        print("[P2P] Stopped")

    # ── Входящие соединения ──────────────────────────────────────────────────

    async def _handle_incoming(self, reader: asyncio.StreamReader,
                                writer: asyncio.StreamWriter):
        peer = PeerConnection(reader, writer)
        peer_addr = writer.get_extra_info("peername")
        if peer_addr and len(peer_addr) >= 2:
            peer.host = peer_addr[0]
            peer.port = int(peer_addr[1] or 0)
        logger.debug(f"[P2P] Incoming from {peer_addr}")

        if len(self.peers) >= self.config.max_peers:
            await peer.send(MSG_HANDSHAKE_ACK, {"accepted": False, "reason": "max_peers"})
            peer.close()
            return

        # Handshake
        ok = await self._do_handshake(peer, initiator=False)
        if not ok:
            peer.close()
            return

        self.peers[peer.peer_id] = peer
        print(f"[P2P] Connected: {peer}")

        await self._message_loop(peer)
        self._remove_peer(peer.peer_id)

    # ── Исходящие соединения ─────────────────────────────────────────────────

    async def connect_peer(self, host: str, port: int) -> bool:
        """Подключается к пиру по адресу."""
        addr = f"{host}:{port}"
        # Не подключаться к самому себе
        if port == self.config.p2p_port and host in ("127.0.0.1", "localhost", "0.0.0.0"):
            return False
        # Не дублировать соединения
        if any(p.host == host and p.port == port for p in self.peers.values()):
            return False

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=10
            )
            peer = PeerConnection(reader, writer)
            peer.host = host
            peer.port = port

            ok = await self._do_handshake(peer, initiator=True)
            if not ok:
                peer.close()
                return False

            self.peers[peer.peer_id] = peer
            if addr not in self._known_addrs:
                self._known_addrs.append(addr)

            print(f"[P2P] Connected to {peer}")

            # Синхронизация если отстаём
            asyncio.create_task(self._sync_with_peer(peer))
            asyncio.create_task(self._message_loop(peer))
            return True

        except (asyncio.TimeoutError, ConnectionRefusedError, OSError) as e:
            logger.debug(f"[P2P] Cannot connect to {addr}: {e}")
            return False

    # ── Handshake ────────────────────────────────────────────────────────────

    async def _do_handshake(self, peer: PeerConnection, initiator: bool) -> bool:
        our_height = self.blockchain.get_height()
        our_info = {
            "chain_id": self.config.chain_id,
            "version": self.config.node_version,
            "height": our_height,
            "head_hash": self.head or "",
            "node_id": f"abs-{self.config.p2p_port}",
        }

        if initiator:
            await peer.send(MSG_HANDSHAKE, our_info)
            msg = await peer.recv()
            if not msg or msg.get("type") != MSG_HANDSHAKE_ACK:
                return False
            ack = msg.get("data", {})
        else:
            msg = await peer.recv()
            if not msg or msg.get("type") != MSG_HANDSHAKE:
                return False
            ack = msg.get("data", {})
            await peer.send(MSG_HANDSHAKE_ACK, our_info)

        # Проверяем совместимость
        if ack.get("chain_id") != self.config.chain_id:
            logger.debug(f"[P2P] Chain ID mismatch: {ack.get('chain_id')} vs {self.config.chain_id}")
            return False

        peer.peer_id = ack.get("node_id", f"{peer.host}:{peer.port}")
        peer.chain_id = ack.get("chain_id", 0)
        peer.height = ack.get("height", 0)
        peer.head = ack.get("head_hash") or peer.head
        await peer.send(MSG_STATUS, {
            "height": our_height,
            "head_hash": self.head or "",
        })
        return True

    # ── Цикл сообщений ───────────────────────────────────────────────────────

    async def _message_loop(self, peer: PeerConnection):
        """Основной цикл чтения сообщений от пира."""
        while self._running and peer.peer_id in self.peers:
            msg = await peer.recv()
            if msg is None:
                break
            peer.touch()
            await self._handle_message(peer, msg)

    async def _handle_message(self, peer: PeerConnection, msg: Dict):
        msg_type = msg.get("type")
        data = msg.get("data")

        if msg_type == MSG_PING:
            await peer.send(MSG_PONG, {"ts": time.time()})

        elif msg_type == MSG_PONG:
            pass  # обновление last_seen уже сделано в _message_loop

        elif msg_type == MSG_NEW_BLOCK:
            await self._handle_new_block(peer, data)

        elif msg_type == MSG_GET_BLOCK:
            height = data.get("height") if isinstance(data, dict) else data
            block = self.blockchain.get_block(int(height))
            await peer.send(MSG_BLOCK, block)

        elif msg_type == MSG_GET_BLOCKS:
            await self._handle_get_blocks(peer, data)

        elif msg_type == MSG_NEW_TX:
            await self._handle_new_tx(data)

        elif msg_type == MSG_GET_PEERS:
            peer_list = [f"{p.host}:{p.port}" for p in self.peers.values()
                         if p.peer_id != peer.peer_id]
            await peer.send(MSG_PEERS, peer_list)

        elif msg_type == MSG_PEERS:
            if isinstance(data, list):
                for addr in data[:10]:  # не больше 10 за раз
                    parts = addr.split(":")
                    if len(parts) == 2:
                        asyncio.create_task(self.connect_peer(parts[0], int(parts[1])))

        elif msg_type == MSG_STATUS:
            if isinstance(data, dict):
                peer.height = data.get("height", peer.height)
                peer.head = data.get("head_hash", peer.head)

    async def _handle_new_block(self, peer: PeerConnection, data: Dict):
        """Принимаем анонс нового блока от пира."""
        if not isinstance(data, dict):
            return

        peer.height = data.get("height", peer.height)

        from core.blockchain import Block
        try:
            block = Block.from_dict(data)
        except Exception as e:
            logger.debug(f"[P2P] Invalid block from {peer}: {e}")
            return

        # Проверяем не знаем ли мы этот блок
        if self.blockchain.get_block(block.height):
            return

        validation = self.blockchain.validate_block(block)
        if validation["valid"]:
            for tx in block.transactions:
                self.mempool.remove(tx.hash)
            if self.blockchain.import_block(data):
                print(f"[P2P] Accepted block #{block.height} from {peer.peer_id[:8]}")
                await self._broadcast_block(data, exclude_peer=peer.peer_id)

    async def _handle_get_blocks(self, peer: PeerConnection, data: Dict):
        """Отправляем диапазон блоков пиру."""
        if not isinstance(data, dict):
            return
        start = int(data.get("from_height", 0))
        end = int(data.get("to_height", start + self.config.sync_batch_size))
        blocks = []
        for h in range(start, min(end + 1, start + self.config.sync_batch_size)):
            blk = self.blockchain.get_block(h)
            if blk:
                blocks.append(blk)
        await peer.send(MSG_BLOCKS, blocks)

    async def _handle_new_tx(self, data: Dict):
        """Принимаем транзакцию из сети."""
        if not isinstance(data, dict):
            return
        from blockchain.mempool import MempoolTransaction
        try:
            tx = MempoolTransaction(
                tx_hash=data.get("hash", ""),
                from_addr=data.get("from_addr", ""),
                to_addr=data.get("to_addr", ""),
                amount=float(data.get("value", 0)),
                fee=float(data.get("fee", 0)),
                nonce=int(data.get("nonce", 0)),
            )
            self.mempool.add(tx)
        except Exception as e:
            logger.debug(f"[P2P] Invalid tx: {e}")

    # ── Синхронизация ────────────────────────────────────────────────────────

    async def _sync_with_peer(self, peer: PeerConnection):
        """Догоняем пира если он выше нас."""
        our_height = self.blockchain.get_height()
        if peer.height <= our_height:
            return

        # Register peer with SyncEngine
        if self.sync_engine:
            self.sync_engine.add_peer(peer)

        print(f"[P2P] Syncing from #{our_height} to #{peer.height} via {peer.peer_id[:8]}")
        current = our_height + 1

        while current <= peer.height and self._running:
            batch_end = min(current + self.config.sync_batch_size - 1, peer.height)
            await peer.send(MSG_GET_BLOCKS, {"from_height": current, "to_height": batch_end})

            msg = await asyncio.wait_for(peer.recv(), timeout=30)
            if not msg or msg.get("type") != MSG_BLOCKS:
                break

            blocks_data = msg.get("data", [])
            for block_data in blocks_data:
                try:
                    if self.blockchain.import_block(block_data):
                        h = block_data.get("height", block_data.get("number", current))
                        current = int(h) + 1
                except Exception as e:
                    logger.debug(f"[P2P] Sync block error: {e}")
                    return

        print(f"[P2P] Sync complete. Our height: {self.blockchain.get_height()}")

    # ── Broadcast ────────────────────────────────────────────────────────────

    async def _broadcast_block(self, block_data: Dict, exclude_peer: str = ""):
        """Рассылает блок всем пирам (кроме exclude_peer)."""
        tasks = []
        for pid, peer in list(self.peers.items()):
            if pid != exclude_peer:
                tasks.append(peer.send(MSG_NEW_BLOCK, block_data))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_tx(self, tx_data: Dict):
        """Рассылает транзакцию всем пирам."""
        tasks = [peer.send(MSG_NEW_TX, tx_data) for peer in self.peers.values()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    # ── Колбэки EventBus ─────────────────────────────────────────────────────

    def _on_local_block(self, block_data: Dict):
        """Вызывается EventBus при новом блоке — рассылаем пирам."""
        if self._loop and self._running:
            asyncio.run_coroutine_threadsafe(
                self._broadcast_block(block_data), self._loop
            )

    def _on_local_tx(self, tx_data: Dict):
        """Вызывается EventBus при новой транзакции — рассылаем пирам."""
        if self._loop and self._running:
            asyncio.run_coroutine_threadsafe(
                self.broadcast_tx(tx_data), self._loop
            )

    # ── Служебные задачи ─────────────────────────────────────────────────────

    async def _ping_loop(self):
        """Пинг всех пиров каждые 30 секунд, отключаем мёртвых."""
        while self._running:
            await asyncio.sleep(30)
            dead = []
            now = time.time()
            for pid, peer in list(self.peers.items()):
                if now - peer.last_seen > self.config.peer_timeout * 2:
                    dead.append(pid)
                else:
                    await peer.send(MSG_PING, {"ts": now})
            for pid in dead:
                self._remove_peer(pid)

    async def _discovery_loop(self):
        """Периодически запрашиваем список пиров у уже подключённых."""
        while self._running:
            await asyncio.sleep(60)
            for peer in list(self.peers.values()):
                await peer.send(MSG_GET_PEERS)
            # Переподключаемся к известным адресам если пиров мало
            if len(self.peers) < 3:
                for addr in self._known_addrs:
                    parts = addr.split(":")
                    if len(parts) == 2:
                        asyncio.create_task(self.connect_peer(parts[0], int(parts[1])))

    async def _bootstrap_retry_loop(self):
        """Переподключение к bootstrap-пирам, пока нет соединений."""
        while self._running:
            await asyncio.sleep(20)
            if self.peers or not self.config.bootstrap_peers:
                continue
            for peer_addr in self.config.bootstrap_peers:
                parts = peer_addr.split(":")
                if len(parts) == 2:
                    asyncio.create_task(self.connect_peer(parts[0], int(parts[1])))

    async def _solo_node_hint(self):
        """One-time hint when running without peers (normal for solo dev)."""
        await asyncio.sleep(45)
        if not self._running or self.peers:
            return
        if self.config.bootstrap_peers:
            print("[P2P] No peers connected — check BOOTSTRAP_PEERS / firewall")
        else:
            print(
                "[P2P] Solo mode (0 peers). For a second node: "
                f"python main.py --port 5001 --peers 127.0.0.1:{self.config.p2p_port}"
            )

    def _remove_peer(self, peer_id: str):
        peer = self.peers.pop(peer_id, None)
        if peer:
            peer.close()
            print(f"[P2P] Disconnected: {peer_id[:12]}")

    # ── Статистика ───────────────────────────────────────────────────────────

    def get_peers_info(self) -> List[Dict]:
        return [
            {
                "id": p.peer_id,
                "host": p.host,
                "port": p.port,
                "height": p.height,
                "connected_for": int(time.time() - p.connected_at),
            }
            for p in self.peers.values()
        ]

    def peer_count(self) -> int:
        return len(self.peers)

    def get_stats(self) -> Dict:
        stats = {
            "peers": self.peer_count(),
            "known_addresses": len(self._known_addrs),
            "running": self._running,
            "port": self.config.p2p_port,
            "sync_engine": self.sync_engine is not None,
        }
        if self.sync_engine:
            stats["sync_status"] = self.sync_engine.get_status()
        return stats
