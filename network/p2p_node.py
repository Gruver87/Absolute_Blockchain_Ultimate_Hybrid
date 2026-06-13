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
MSG_GET_BLOCK_BY_HASH = "get_block_by_hash"
MSG_BLOCK      = "block"
MSG_GET_BLOCKS = "get_blocks"   # диапазон блоков
MSG_BLOCKS     = "blocks"
MSG_NEW_TX     = "new_tx"
MSG_GET_PEERS  = "get_peers"
MSG_PEERS      = "peers"
MSG_STATUS     = "status"       # height + head hash
MSG_ATTESTATION = "attestation"
MSG_STATE_ROOT_REQUEST = "state_root_request"
MSG_STATE_ROOT_RESPONSE = "state_root_response"
MSG_VALIDATOR_REGISTER = "validator_register"


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
        # Sync responses routed from _message_loop (avoid double recv on same socket)
        self._sync_waiters: Dict[str, tuple] = {}  # peer_id -> (expected_types, Future)
        self._consensus = None
        self.validator_keys = None
        self._state_consistent = True

        # Подписка на события шины — транслируем в сеть
        if self.bus:
            self.bus.on("block.new", self._on_local_block)
            self.bus.on("tx.new", self._on_local_tx)
            self.bus.on("consensus.attestation", self._on_consensus_attestation)

        # SyncEngine (System C) — fast catch-up
        if _SYNC_ENGINE_AVAILABLE:
            self.sync_engine = SyncEngine(node=self)
            print("[P2P] SyncEngine: enabled (fast catch-up)")
        else:
            self.sync_engine = None

    def head(self) -> Optional[str]:
        """Current head block hash for SyncEngine."""
        last = self.blockchain.get_last_block()
        return last["hash"] if last else None

    @property
    def height(self) -> int:
        return self.blockchain.get_height()

    @property
    def consensus(self):
        return self._consensus

    @consensus.setter
    def consensus(self, value):
        self._consensus = value

    def set_consensus(self, consensus, validator_keys=None) -> None:
        """Wire consensus for attestation gossip and fork choice."""
        self._consensus = consensus
        self.validator_keys = validator_keys

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
        asyncio.create_task(self._catch_up_loop())

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

        asyncio.create_task(self._sync_with_peer_safe(peer))
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
            asyncio.create_task(self._sync_with_peer_safe(peer))
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
            "head_hash": self.head() or "",
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
            "head_hash": self.head() or "",
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

        waiter = self._sync_waiters.get(peer.peer_id)
        if waiter:
            expected_types, fut = waiter
            if msg_type in expected_types and not fut.done():
                fut.set_result(msg)
                return

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

        elif msg_type == MSG_GET_BLOCK_BY_HASH:
            block_hash = ""
            if isinstance(data, dict):
                block_hash = data.get("hash", "")
            elif isinstance(data, str):
                block_hash = data
            block = None
            if block_hash and hasattr(self.blockchain, "get_block_by_hash"):
                block = self.blockchain.get_block_by_hash(block_hash)
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

        elif msg_type == MSG_ATTESTATION:
            await self._handle_attestation(peer, data)

        elif msg_type == MSG_VALIDATOR_REGISTER:
            await self._handle_validator_register(peer, data)

        elif msg_type == MSG_STATE_ROOT_REQUEST:
            height = int(data.get("height", self.blockchain.get_height())) if isinstance(data, dict) else self.blockchain.get_height()
            await peer.send(MSG_STATE_ROOT_RESPONSE, {
                "height": height,
                "state_root": self.blockchain.get_state_root(),
                "head_hash": self.head() or "",
            })

        elif msg_type == MSG_STATE_ROOT_RESPONSE:
            if isinstance(data, dict) and waiter is None:
                peer_root = data.get("state_root", "")
                local_root = self.blockchain.get_state_root()
                peer_h = int(data.get("height", 0))
                if peer_h == self.blockchain.get_height() and peer_root and peer_root != local_root:
                    self._state_consistent = False
                    logger.warning(
                        f"[P2P] State root mismatch vs {peer.peer_id[:8]}: "
                        f"local={local_root[:12]} peer={peer_root[:12]}"
                    )

    async def _handle_validator_register(self, peer: PeerConnection, data: Dict):
        """Register peer validator in local consensus when announced."""
        if not isinstance(data, dict):
            return
        address = data.get("address", "")
        stake = float(data.get("stake", getattr(self.config, "min_stake", 1000)))
        if not address or not self._consensus:
            return
        vals = self.blockchain.db.get_validators(active_only=False) or []
        known = {v["address"].lower() for v in vals}
        if address.lower() in known:
            return
        if hasattr(self._consensus, "add_validator"):
            if self._consensus.add_validator(address, stake):
                print(f"[P2P] Registered peer validator {address[:12]}… from {peer.peer_id[:8]}")
                await self._relay_validator_register(data, exclude_peer=peer.peer_id)

    async def _relay_validator_register(self, payload: Dict, exclude_peer: str = ""):
        tasks = []
        for pid, peer in list(self.peers.items()):
            if pid != exclude_peer:
                tasks.append(peer.send(MSG_VALIDATOR_REGISTER, payload))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def announce_validator(self, address: str, stake: float) -> None:
        """Gossip local validator registration to connected peers."""
        payload = {"address": address, "stake": stake, "node_id": f"abs-{self.config.p2p_port}"}
        if self._loop and self._running:
            asyncio.run_coroutine_threadsafe(
                self._relay_validator_register(payload), self._loop
            )

    async def _handle_attestation(self, peer: PeerConnection, data: Dict):
        """Accept signed attestation from peer and apply to local consensus."""
        if not isinstance(data, dict):
            return
        vkeys = self.validator_keys
        if vkeys and hasattr(vkeys, "verify_attestation"):
            if not vkeys.verify_attestation(data):
                logger.debug(f"[P2P] Invalid attestation sig from {peer.peer_id[:8]}")
                return
        validator = data.get("validator", "")
        block_hash = data.get("target_hash", "")
        if not validator or not block_hash:
            return
        consensus = self._consensus
        if consensus and hasattr(consensus, "attest"):
            if consensus.attest(validator, block_hash):
                await self._relay_attestation(data, exclude_peer=peer.peer_id)

    async def _relay_attestation(self, attestation: Dict, exclude_peer: str = ""):
        tasks = []
        for pid, peer in list(self.peers.items()):
            if pid != exclude_peer:
                tasks.append(peer.send(MSG_ATTESTATION, attestation))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

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
                if self._consensus and self.validator_keys:
                    try:
                        self._consensus.attest(
                            self.validator_keys.get_address(), block.hash
                        )
                    except Exception:
                        pass
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
        """Принимаем транзакцию из сети — с полной валидацией как в RPC."""
        if not isinstance(data, dict):
            return
        from core.blockchain import Transaction
        from blockchain.mempool import MempoolTransaction

        from_addr = data.get("from_addr", data.get("from", ""))
        to_addr = data.get("to_addr", data.get("to", ""))
        value = float(data.get("value", data.get("amount", 0)))
        nonce = int(data.get("nonce", 0))
        gas = int(data.get("gas", 0) or 0) or 21_000
        signature = data.get("signature", "")
        public_key = data.get("public_key", "")
        calldata = data.get("data", data.get("input", ""))

        tx = Transaction(
            from_addr=from_addr,
            to_addr=to_addr,
            value=value,
            nonce=nonce,
            gas=gas,
            data=calldata,
            signature=signature,
            public_key=public_key,
            tx_hash=data.get("hash", data.get("tx_hash", "")),
        )
        validation = self.blockchain.validate_transaction(tx)
        if not validation["valid"]:
            logger.debug(f"[P2P] Tx rejected: {validation.get('error')}")
            return

        fee = float(data.get("fee", gas * getattr(self.config, "gas_price_wei", 0.001)))
        mp_tx = MempoolTransaction(
            tx_hash=tx.hash,
            from_addr=from_addr,
            to_addr=to_addr,
            amount=value,
            fee=fee,
            nonce=nonce,
            signature=signature,
            public_key=public_key,
            data=calldata,
            gas=gas,
        )
        if self.mempool.add(mp_tx):
            logger.debug(f"[P2P] Accepted tx {tx.hash[:12]}… from network")

    # ── Синхронизация ────────────────────────────────────────────────────────

    async def _sync_with_peer_safe(self, peer: PeerConnection):
        try:
            await self._sync_with_peer(peer)
        except Exception as e:
            print(f"[P2P] Sync error via {peer.peer_id[:8]}: {e}")
            logger.exception("[P2P] sync failed")

    async def _wait_peer_response(
        self,
        peer: PeerConnection,
        expected_types: tuple,
        timeout: float = 30,
        presend=None,
    ) -> Optional[Dict]:
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._sync_waiters[peer.peer_id] = (expected_types, fut)
        try:
            if presend:
                await presend()
            return await asyncio.wait_for(fut, timeout=timeout)
        except asyncio.TimeoutError:
            return None
        finally:
            self._sync_waiters.pop(peer.peer_id, None)

    async def _sync_with_peer(self, peer: PeerConnection):
        """Догоняем пира если он выше нас."""
        our_height = self.blockchain.get_height()
        if peer.height <= our_height:
            return

        if self.sync_engine:
            self.sync_engine.add_peer(peer)

        print(f"[P2P] Syncing from #{our_height} to #{peer.height} via {peer.peer_id[:8]}")
        current = 0 if our_height == 0 else our_height + 1

        while current <= peer.height and self._running:
            batch_end = min(current + self.config.sync_batch_size - 1, peer.height)

            msg = await self._wait_peer_response(
                peer,
                (MSG_BLOCKS,),
                timeout=45,
                presend=lambda c=current, e=batch_end: peer.send(
                    MSG_GET_BLOCKS, {"from_height": c, "to_height": e}
                ),
            )
            if not msg or msg.get("type") != MSG_BLOCKS:
                print(f"[P2P] Sync stalled at #{current} (no blocks response)")
                break

            blocks_data = msg.get("data", [])
            if not blocks_data:
                break

            imported_any = False
            for block_data in blocks_data:
                try:
                    if self.blockchain.import_block(block_data):
                        h = block_data.get("height", block_data.get("number", current))
                        current = int(h) + 1
                        imported_any = True
                    else:
                        parent_hash = block_data.get("parent_hash", "")
                        ancestor = None
                        if hasattr(self.blockchain, "find_ancestor_height"):
                            ancestor = self.blockchain.find_ancestor_height(parent_hash)
                        if (
                            ancestor is not None
                            and ancestor < self.blockchain.get_height()
                            and hasattr(self.blockchain, "reorg_to_ancestor")
                            and self.blockchain.reorg_to_ancestor(ancestor)
                        ):
                            print(f"[P2P] Fork resolved — reorg to #{ancestor}, retry import")
                            our_height = ancestor
                            current = ancestor + 1
                            break
                        print(f"[P2P] Import failed at #{current}, aborting batch")
                        break
                except Exception as e:
                    logger.debug(f"[P2P] Sync block error: {e}")
                    return

            if not imported_any:
                break

            peer.height = max(peer.height, self.blockchain.get_height())

        print(f"[P2P] Sync complete. Our height: {self.blockchain.get_height()}")

        if self.sync_engine:
            loop = asyncio.get_running_loop()
            ok = await loop.run_in_executor(None, self.sync_engine.sync_state)
            self._state_consistent = bool(ok)

        new_h = self.blockchain.get_height()
        if hasattr(self.blockchain, "set_state_root_baseline"):
            self.blockchain.set_state_root_baseline(new_h)
            print(f"[P2P] State-root baseline set to #{new_h} (strict above)")

    async def request_peer_state_root(self, peer: PeerConnection, height: int = None) -> Optional[Dict]:
        """Request state_root at height from a single peer."""
        h = height if height is not None else self.blockchain.get_height()
        msg = await self._wait_peer_response(
            peer,
            (MSG_STATE_ROOT_RESPONSE,),
            timeout=12,
            presend=lambda: peer.send(MSG_STATE_ROOT_REQUEST, {"height": h}),
        )
        if not msg or msg.get("type") != MSG_STATE_ROOT_RESPONSE:
            return None
        data = msg.get("data")
        return data if isinstance(data, dict) else None

    async def request_peer_state_roots(self) -> List[Dict]:
        """Collect state_root responses from all connected peers."""
        height = self.blockchain.get_height()
        results = []
        for peer in list(self.peers.values()):
            resp = await self.request_peer_state_root(peer, height)
            if resp:
                resp["peer_id"] = peer.peer_id
                results.append(resp)
        return results

    def request_peer_state_roots_sync(self, timeout: float = 15) -> List[Dict]:
        if not self._loop or not self._running:
            return []
        future = asyncio.run_coroutine_threadsafe(
            self.request_peer_state_roots(), self._loop
        )
        try:
            return future.result(timeout=timeout)
        except Exception:
            return []

    async def _request_block_by_hash(self, peer: PeerConnection, block_hash: str) -> Optional[Dict]:
        """Запрашивает у пира полный блок по hash."""
        if not block_hash:
            return None
        msg = await self._wait_peer_response(
            peer,
            (MSG_BLOCK,),
            timeout=15,
            presend=lambda: peer.send(MSG_GET_BLOCK_BY_HASH, {"hash": block_hash}),
        )
        if not msg or msg.get("type") != MSG_BLOCK:
            return None
        data = msg.get("data")
        return data if isinstance(data, dict) else None

    async def fetch_block_from_peers(self, block_hash: str) -> Optional[Dict]:
        """Ищет блок локально, затем у подключённых пиров."""
        if hasattr(self.blockchain, "get_block_by_hash"):
            local = self.blockchain.get_block_by_hash(block_hash)
            if local:
                return local
        for peer in list(self.peers.values()):
            blk = await self._request_block_by_hash(peer, block_hash)
            if blk and blk.get("hash") == block_hash:
                return blk
        return None

    def trigger_catch_up(self) -> None:
        """Schedule sync with all higher peers (callable from REST thread)."""
        if not self._loop or not self._running:
            return
        for peer in list(self.peers.values()):
            if peer.height > self.blockchain.get_height():
                asyncio.run_coroutine_threadsafe(self._sync_with_peer_safe(peer), self._loop)

    def fetch_block_from_peers_sync(self, block_hash: str, timeout: float = 15) -> Optional[Dict]:
        """Синхронная обёртка для SyncEngine (из другого потока)."""
        if not self._loop or not self._running:
            return None
        future = asyncio.run_coroutine_threadsafe(
            self.fetch_block_from_peers(block_hash), self._loop
        )
        try:
            return future.result(timeout=timeout)
        except Exception:
            return None

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

    def _on_consensus_attestation(self, att_data: Dict):
        """Gossip signed attestation after local consensus.attest()."""
        if not self.validator_keys or not isinstance(att_data, dict):
            return
        validator = att_data.get("validator", "")
        block_hash = att_data.get("target_hash") or att_data.get("block_hash", "")
        if validator != self.validator_keys.get_address() or not block_hash:
            return
        block_data = {"hash": block_hash, "number": att_data.get("target_height")}
        if not block_data.get("number") and self.blockchain:
            last = self.blockchain.get_last_block()
            if last:
                block_data["number"] = last.get("height", last.get("number"))
        slot = att_data.get("slot", 0)
        try:
            signed = self.validator_keys.sign_attestation(block_data, slot)
        except Exception as e:
            logger.debug(f"[P2P] Attestation sign failed: {e}")
            return
        if self._loop and self._running:
            asyncio.run_coroutine_threadsafe(
                self._relay_attestation(signed), self._loop
            )

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

    async def _catch_up_loop(self):
        """Периодически догоняем пиров с большей высотой."""
        while self._running:
            await asyncio.sleep(15)
            our_height = self.blockchain.get_height()
            for peer in list(self.peers.values()):
                if peer.height > our_height:
                    asyncio.create_task(self._sync_with_peer_safe(peer))

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
            "state_consistent": self._state_consistent,
            "state_root": self.blockchain.get_state_root() if self.blockchain else "",
        }
        if self.sync_engine:
            stats["sync_status"] = self.sync_engine.get_status()
        return stats
