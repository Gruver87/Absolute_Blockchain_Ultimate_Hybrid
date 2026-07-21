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
from typing import Dict, List, Optional, Callable, Any, Tuple

from network.p2p_tls import (
    build_p2p_client_ssl_context,
    build_p2p_server_ssl_context,
    extract_peer_tls_meta,
    fingerprint_allowlist,
    handshake_node_id_matches_cert,
    p2p_tls_enabled,
    p2p_tls_status,
    validate_p2p_tls_config,
)
from crypto import native

logger = logging.getLogger("P2P")

# Fail closed on oversized wire payloads (DoS hardening).
DEFAULT_MAX_P2P_LINE_BYTES = 2 * 1024 * 1024


class WireReject:
    """Sentinel from Peer.recv: parse/shape reject (not EOF)."""

    __slots__ = ("reason",)

    def __init__(self, reason: str):
        self.reason = str(reason or "bad_wire_line")


def _max_p2p_line_bytes(config) -> int:
    raw = getattr(config, "p2p_max_message_bytes", None)
    if raw is None:
        return DEFAULT_MAX_P2P_LINE_BYTES
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_MAX_P2P_LINE_BYTES
    return max(4096, min(limit, 16 * 1024 * 1024))

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
MSG_IDLE       = "__idle__"
MSG_NEW_BLOCK  = "new_block"
MSG_GET_BLOCK  = "get_block"
MSG_GET_BLOCK_BY_HASH = "get_block_by_hash"
MSG_BLOCK      = "block"
MSG_GET_BLOCKS = "get_blocks"   # диапазон блоков
MSG_BLOCKS     = "blocks"
MSG_NEW_TX     = "new_tx"
MSG_GET_MEMPOOL = "get_mempool"
MSG_MEMPOOL    = "mempool"
MSG_GET_PEERS  = "get_peers"
MSG_PEERS      = "peers"
MSG_STATUS     = "status"       # height + head hash
MSG_ATTESTATION = "attestation"
MSG_STATE_ROOT_REQUEST = "state_root_request"
MSG_STATE_ROOT_RESPONSE = "state_root_response"
MSG_VALIDATOR_REGISTER = "validator_register"
MSG_CROSS_SHARD_TX = "cross_shard_tx"
MSG_CROSS_SHARD_ACK = "cross_shard_ack"
MSG_SHARD_MIGRATION = "shard_migration"

ALLOWED_WIRE_TYPES = frozenset({
    MSG_HANDSHAKE,
    MSG_HANDSHAKE_ACK,
    MSG_PING,
    MSG_PONG,
    MSG_IDLE,
    MSG_NEW_BLOCK,
    MSG_GET_BLOCK,
    MSG_GET_BLOCK_BY_HASH,
    MSG_BLOCK,
    MSG_GET_BLOCKS,
    MSG_BLOCKS,
    MSG_NEW_TX,
    MSG_GET_MEMPOOL,
    MSG_MEMPOOL,
    MSG_GET_PEERS,
    MSG_PEERS,
    MSG_STATUS,
    MSG_ATTESTATION,
    MSG_STATE_ROOT_REQUEST,
    MSG_STATE_ROOT_RESPONSE,
    MSG_VALIDATOR_REGISTER,
    MSG_CROSS_SHARD_TX,
    MSG_CROSS_SHARD_ACK,
    MSG_SHARD_MIGRATION,
})

# Housekeeping + consensus/sync wire types are not counted toward per-peer rate limits.
RATE_LIMIT_EXEMPT_TYPES = frozenset({
    MSG_PING,
    MSG_PONG,
    MSG_IDLE,
    MSG_STATUS,
    MSG_STATE_ROOT_REQUEST,
    MSG_STATE_ROOT_RESPONSE,
    MSG_NEW_BLOCK,
    MSG_GET_BLOCK,
    MSG_GET_BLOCK_BY_HASH,
    MSG_GET_BLOCKS,
    MSG_BLOCK,
    MSG_BLOCKS,
    MSG_NEW_TX,
    MSG_GET_MEMPOOL,
    MSG_MEMPOOL,
})


def _housekeeping_payload_ok(msg_type: str, data: Any) -> bool:
    """Fail-closed payload rules for rate-exempt housekeeping messages."""
    if data is None:
        return True
    if msg_type in (MSG_PING, MSG_PONG):
        if not isinstance(data, dict):
            return False
        if not data:
            return True
        if set(data.keys()) <= {"ts"} and isinstance(data.get("ts"), (int, float)):
            return True
        return False
    if msg_type in (MSG_GET_MEMPOOL, MSG_GET_PEERS):
        return isinstance(data, dict) and len(data) == 0
    return False


def _peer_health_score(
    *,
    height_gap: int,
    last_seen_age: float,
    health_timeout: float,
) -> int:
    score = 100
    score -= min(45, int(height_gap) * 15)
    if last_seen_age >= health_timeout:
        score -= 50
    elif last_seen_age >= health_timeout / 2:
        score -= 20
    return max(0, min(100, score))


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
        self.listen_port = 0
        self.chain_id: int = 0
        self.height: int = 0
        self.head: Optional[str] = None  # head block hash (for SyncEngine/GHOST)
        self.connected_at = time.time()
        self.last_seen = time.time()
        self.is_synced = False
        self.tls_fingerprint = ""
        self.tls_identities: list = []
        self._on_send_fail: Optional[Callable[[], None]] = None

    def touch(self):
        self.last_seen = time.time()

    async def send(self, msg_type: str, data: Any = None) -> bool:
        """Отправляет JSON-сообщение пиру. Returns False on write failure."""
        try:
            payload = native.encode_p2p_wire_message(msg_type, data)
            self.writer.write(payload)
            await self.writer.drain()
            return True
        except Exception as e:
            logger.warning("[P2P] send error to %s: %s", self.peer_id or self.host, e)
            cb = self._on_send_fail
            if cb is not None:
                try:
                    cb()
                except Exception:
                    pass
            return False

    async def recv(self, config=None):
        """Читает одно JSON-сообщение от пира.

        Returns:
            dict — valid envelope; WireReject — parse/size fail; None — EOF;
            MSG_IDLE dict — read timeout (keep-alive).
        """
        limit = _max_p2p_line_bytes(config)
        try:
            line = await asyncio.wait_for(self.reader.readline(), timeout=30)
            if not line:
                return None
            try:
                parsed = native.parse_p2p_wire_line(
                    line,
                    max_bytes=limit,
                    allowed_types=list(ALLOWED_WIRE_TYPES),
                )
            except ValueError as exc:
                reason = str(exc) or "p2p_line_too_large"
                if "p2p_line_too_large" in reason:
                    reason = "p2p_line_too_large"
                logger.warning(
                    "[P2P] wire reject from %s (%s, %s bytes, limit=%s)",
                    self.peer_id or self.host,
                    reason,
                    len(line),
                    limit,
                )
                return WireReject(reason)
            if parsed is None:
                logger.warning(
                    "[P2P] bad wire line from %s (%s bytes)",
                    self.peer_id or self.host,
                    len(line),
                )
                return WireReject("bad_wire_line")
            return parsed
        except asyncio.TimeoutError:
            return {"type": MSG_IDLE, "data": None}
        except Exception as exc:
            logger.warning(
                "[P2P] recv error from %s: %s",
                self.peer_id or self.host,
                exc,
            )
            return WireReject("recv_error")

    def close(self):
        try:
            self.writer.close()
        except Exception as exc:
            logger.debug("[P2P] peer close failed %s:%s: %s", self.host, self.port, exc)

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
        for peer_addr in getattr(config, "bootstrap_peers", []) or []:
            self._remember_addr(peer_addr)
        self._server: Optional[asyncio.Server] = None
        self._running = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        # Sync responses routed from _message_loop (avoid double recv on same socket)
        self._sync_waiters: Dict[str, tuple] = {}  # peer_id -> (expected_types, Future)
        self._peer_sync_locks: Dict[str, asyncio.Lock] = {}
        self._peer_msg_windows: Dict[str, tuple[int, float]] = {}
        self._peer_strikes: Dict[str, int] = {}
        self._peer_bans: Dict[str, float] = {}
        self._handshake_rejects: int = 0
        self._attestation_local_fail: int = 0
        self._propagation_log_fail: int = 0
        self._peer_connect_task_fail: int = 0
        self._peer_status_send_fail: int = 0
        self._peer_send_fail: int = 0
        self._maintenance_loop_fail: int = 0
        self._catch_up_loop_fail: int = 0
        self._peer_tx_reject: int = 0
        self._import_block_fail: int = 0
        self._sync_fail: int = 0
        self._peer_sync_fail: int = 0
        self._discovery_loop_fail: int = 0
        self._bootstrap_loop_fail: int = 0
        self._last_tx_wire_reject: str = ""
        self._shape_reject_counts: Dict[str, int] = {}
        self._consensus = None
        self.validator_keys = None
        # Fail-closed until SyncEngine.sync_state proves peer roots match.
        self._state_consistent = False
        self._sharding = None

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

    def _consensus_adapter(self):
        return self._consensus or getattr(self.blockchain, "consensus_adapter", None)

    def _feed_fork_choice(self, block_data: Dict) -> None:
        """Register block in LMD-GHOST tree (competing forks at same height)."""
        if not isinstance(block_data, dict):
            return
        ca = self._consensus_adapter()
        if not ca or not hasattr(ca, "add_block_to_fork_choice"):
            return
        ca.add_block_to_fork_choice({
            "hash": block_data.get("hash", ""),
            "parent_hash": block_data.get("parent_hash", ""),
            "number": int(block_data.get("height", block_data.get("number", 0)) or 0),
        })

    def _ghost_canonical_head(self) -> Optional[str]:
        ca = self._consensus_adapter()
        if ca and hasattr(ca, "get_canonical_head"):
            return ca.get_canonical_head()
        return None

    def _peer_with_head(self, head_hash: str) -> Optional[PeerConnection]:
        target = (head_hash or "").strip().lower()
        if not target:
            return None
        for peer in self.peers.values():
            peer_head = (peer.head or "").strip().lower()
            if peer_head == target or target in peer_head or peer_head in target:
                return peer
        return None

    def set_sharding(self, sharding) -> None:
        """Wire distributed sharding for cross-shard gossip."""
        self._sharding = sharding
        if sharding is not None and hasattr(sharding, "set_gossip_callback"):
            sharding.set_gossip_callback(self._schedule_cross_shard_gossip)

    def _schedule_cross_shard_gossip(self, payload: Dict) -> None:
        if self._loop and self._running:
            if isinstance(payload, dict) and payload.get("type") == "shard_migration":
                asyncio.run_coroutine_threadsafe(
                    self.broadcast_shard_migration(payload), self._loop
                )
            elif isinstance(payload, dict) and payload.get("type") == "cross_shard_ack":
                asyncio.run_coroutine_threadsafe(
                    self.broadcast_cross_shard_ack(payload), self._loop
                )
            else:
                asyncio.run_coroutine_threadsafe(
                    self.broadcast_cross_shard_tx(payload), self._loop
                )

    def get_block(self, block_hash: str) -> Optional[Dict]:
        """For SyncEngine.download_chain()."""
        if hasattr(self.blockchain, "get_block_by_hash"):
            return self.blockchain.get_block_by_hash(block_hash)
        return None

    def import_block(self, block_data: Dict) -> bool:
        """For SyncEngine.fast_sync()."""
        try:
            if hasattr(self.blockchain, "import_block"):
                ok = bool(self.blockchain.import_block(block_data))
            else:
                from core.blockchain import Block

                blk = Block.from_dict(block_data)
                ok = bool(self.blockchain.add_block(blk))
            if not ok:
                self._import_block_fail = int(self._import_block_fail or 0) + 1
                logger.warning("[P2P] import_block rejected")
            return ok
        except Exception as exc:
            self._import_block_fail = int(self._import_block_fail or 0) + 1
            logger.warning("[P2P] import_block failed: %s", exc)
            return False

    # ── Запуск / остановка ───────────────────────────────────────────────────

    async def start(self):
        """Запускает TCP-сервер и подключается к bootstrap пирам."""
        self._running = True
        self._loop = asyncio.get_event_loop()

        # Запускаем TCP-сервер
        try:
            if p2p_tls_enabled(self.config):
                tls_errors, tls_warn = validate_p2p_tls_config(self.config)
                for warn in tls_warn:
                    logger.warning("[P2P] TLS: %s", warn)
                if tls_errors:
                    print(f"[P2P] TLS enabled but misconfigured: {tls_errors}")
                    self._running = False
                    return
            server_ssl = build_p2p_server_ssl_context(self.config)
            self._server = await asyncio.start_server(
                self._handle_incoming,
                self.config.p2p_host,
                self.config.p2p_port,
                ssl=server_ssl,
            )
            tls_label = "tls" if server_ssl else "plain"
            print(
                f"[P2P] Listening on {self.config.p2p_host}:{self.config.p2p_port} ({tls_label})"
            )
        except OSError as e:
            print(f"[P2P] Could not bind port {self.config.p2p_port}: {e}")
            print("[P2P] Hint: stop other node — .\\scripts\\stop_node.ps1 — or use --port 5001")
            # Bind failure must not leave the node advertised as running.
            self._running = False
            return

        # Подключаемся к bootstrap пирам
        for peer_addr in self.config.bootstrap_peers:
            parts = peer_addr.split(":")
            if len(parts) == 2:
                asyncio.create_task(self.connect_peer(parts[0], int(parts[1])))

        # Периодические задачи
        asyncio.create_task(self._ping_loop())
        asyncio.create_task(self._discovery_loop())
        asyncio.create_task(self._bootstrap_retry_loop())
        asyncio.create_task(self._maintenance_loop())
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

    def _attach_peer_hooks(self, peer: PeerConnection) -> None:
        """Wire peer callbacks into node counters."""
        peer._on_send_fail = self._bump_peer_send_fail

    def _bump_peer_send_fail(self) -> None:
        self._peer_send_fail = int(self._peer_send_fail or 0) + 1

    # ── Входящие соединения ──────────────────────────────────────────────────

    async def _handle_incoming(self, reader: asyncio.StreamReader,
                                writer: asyncio.StreamWriter):
        peer = PeerConnection(reader, writer)
        self._attach_peer_hooks(peer)
        peer_addr = writer.get_extra_info("peername")
        if peer_addr and len(peer_addr) >= 2:
            peer.host = peer_addr[0]
            peer.port = int(peer_addr[1] or 0)
        if self._is_addr_banned(peer.host, peer.port):
            peer.close()
            return
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
        if self._is_banned(self._peer_key(peer)):
            peer.close()
            return

        old = self.peers.get(peer.peer_id)
        if old and old is not peer:
            stale_after = max(15.0, float(getattr(self.config, "peer_timeout", 30) or 30))
            if time.time() - old.last_seen <= stale_after:
                peer.close()
                return
            old.close()
        self.peers[peer.peer_id] = peer
        print(f"[P2P] Connected: {peer}")

        asyncio.create_task(self._sync_with_peer_safe(peer))
        await self._message_loop(peer)

    # ── Исходящие соединения ─────────────────────────────────────────────────

    async def connect_peer(self, host: str, port: int) -> bool:
        """Подключается к пиру по адресу."""
        addr = f"{host}:{port}"
        # Не подключаться к самому себе
        if port == self.config.p2p_port and host in ("127.0.0.1", "localhost", "0.0.0.0"):
            return False
        if self._is_addr_banned(host, port):
            return False
        self._prune_stale_peers()
        # Не дублировать соединения
        if any(
            p.host == host and (p.port == port or p.listen_port == port)
            for p in self.peers.values()
        ):
            return False

        try:
            client_ssl = build_p2p_client_ssl_context(self.config)
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port, ssl=client_ssl),
                timeout=10,
            )
            peer = PeerConnection(reader, writer)
            self._attach_peer_hooks(peer)
            peer.host = host
            peer.port = port

            ok = await self._do_handshake(peer, initiator=True)
            if not ok:
                peer.close()
                return False
            if self._is_banned(self._peer_key(peer)):
                peer.close()
                return False

            if peer.peer_id in self.peers:
                self._remember_addr(addr)
                peer.close()
                return True

            self.peers[peer.peer_id] = peer
            self._remember_addr(addr)

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
            "node_id": getattr(self.config, "node_id", f"abs-{self.config.p2p_port}"),
            "p2p_port": int(getattr(self.config, "p2p_port", 0) or 0),
        }

        if initiator:
            await peer.send(MSG_HANDSHAKE, our_info)
            msg = await peer.recv(self.config)
            if not msg or msg.get("type") != MSG_HANDSHAKE_ACK:
                return False
            ack = msg.get("data", {})
        else:
            msg = await peer.recv(self.config)
            if not msg or msg.get("type") != MSG_HANDSHAKE:
                return False
            ack = msg.get("data", {})
            await peer.send(MSG_HANDSHAKE_ACK, our_info)

        hs = native.validate_p2p_handshake_payload(ack)
        if not hs:
            self._handshake_rejects += 1
            self._strike_peer_sync(peer, "bad_handshake_payload")
            return False
        if hs.get("accepted") is False:
            self._handshake_rejects += 1
            return False

        # Проверяем совместимость
        if hs.get("chain_id") != self.config.chain_id:
            self._handshake_rejects += 1
            self._strike_peer_sync(peer, "chain_id_mismatch")
            print(
                f"[P2P] Rejected {peer.host}:{peer.port}: chain_id mismatch "
                f"(remote={hs.get('chain_id')} local={self.config.chain_id}). "
                f"Use the same node.json on both nodes."
            )
            return False

        claimed_id = str(hs.get("node_id") or "").strip() or f"{peer.host}:{peer.port}"
        if p2p_tls_enabled(self.config):
            tls_meta = extract_peer_tls_meta(peer.writer)
            identities = set(tls_meta.get("identities") or [])
            fp = str(tls_meta.get("fingerprint_sha256") or "")
            peer.tls_fingerprint = fp
            peer.tls_identities = sorted(identities)
            bind_id = bool(getattr(self.config, "p2p_tls_bind_identity", True))
            if not tls_meta.get("ssl"):
                self._handshake_rejects += 1
                self._strike_peer_sync(peer, "tls_missing")
                print(f"[P2P] Rejected {peer.host}:{peer.port}: TLS required but no ssl_object")
                return False
            if bind_id:
                if not identities or not handshake_node_id_matches_cert(claimed_id, identities):
                    self._handshake_rejects += 1
                    self._strike_peer_sync(peer, "tls_identity_mismatch")
                    print(
                        f"[P2P] Rejected {peer.host}:{peer.port}: handshake node_id "
                        f"{claimed_id!r} not in peer cert CN/SAN {sorted(identities)}"
                    )
                    return False
            allow = fingerprint_allowlist(self.config)
            if allow and fp.lower() not in allow:
                self._handshake_rejects += 1
                self._strike_peer_sync(peer, "tls_fingerprint_denied")
                print(
                    f"[P2P] Rejected {peer.host}:{peer.port}: cert fingerprint "
                    f"not in P2P_TLS_PEER_FINGERPRINTS allowlist"
                )
                return False

        peer.peer_id = claimed_id
        peer.chain_id = hs.get("chain_id", 0)
        peer.height = hs.get("height", 0)
        peer.head = hs.get("head_hash") or peer.head
        peer.listen_port = int(hs.get("p2p_port", 0) or peer.port or 0)
        if peer.host and peer.listen_port:
            self._remember_addr(f"{peer.host}:{peer.listen_port}")
        await peer.send(MSG_STATUS, {
            "height": our_height,
            "head_hash": self.head() or "",
        })
        return True

    # ── Цикл сообщений ───────────────────────────────────────────────────────

    async def _message_loop(self, peer: PeerConnection):
        """Основной цикл чтения сообщений от пира."""
        try:
            while self._running and self.peers.get(peer.peer_id) is peer:
                msg = await peer.recv(self.config)
                if msg is None:
                    break
                if isinstance(msg, WireReject):
                    if self._strike_peer_sync(peer, msg.reason):
                        break
                    continue
                if msg.get("type") == MSG_IDLE:
                    continue
                peer.touch()
                if not self._rate_limit_ok(peer.peer_id, msg.get("type")):
                    if self._strike_peer_sync(peer, "rate_limit_exceeded"):
                        break
                    continue
                await self._handle_message(peer, msg)
        finally:
            self._remove_peer(peer.peer_id, peer)

    def _peer_key(self, peer: PeerConnection) -> str:
        if peer.peer_id:
            return peer.peer_id
        port = peer.listen_port or peer.port
        return f"{peer.host}:{port}"

    def _is_banned(self, key: str) -> bool:
        if not key:
            return False
        until = self._peer_bans.get(key)
        if until is None:
            return False
        if time.time() >= until:
            self._peer_bans.pop(key, None)
            return False
        return True

    def _is_addr_banned(self, host: str, port: int) -> bool:
        if self._is_banned(f"{host}:{port}"):
            return True
        return any(
            self._is_banned(key)
            for key in self._peer_bans
            if key.startswith(f"{host}:")
        )

    def _strike_peer_sync(self, peer: PeerConnection, reason: str) -> bool:
        """Record abuse strike; return True if peer should be disconnected (banned)."""
        key = self._peer_key(peer)
        if not key:
            return False
        reason_key = str(reason or "unknown")
        self._shape_reject_counts[reason_key] = int(
            self._shape_reject_counts.get(reason_key, 0) or 0
        ) + 1
        strikes = int(self._peer_strikes.get(key, 0) or 0) + 1
        self._peer_strikes[key] = strikes
        max_strikes = int(getattr(self.config, "p2p_rate_limit_strikes", 5) or 5)
        if strikes < max_strikes:
            logger.warning(
                "[P2P] strike %s/%s for %s (%s)",
                strikes,
                max_strikes,
                key,
                reason_key,
            )
            return False
        ban_sec = int(getattr(self.config, "p2p_ban_seconds", 300) or 300)
        self._peer_bans[key] = time.time() + max(30, ban_sec)
        self._peer_strikes.pop(key, None)
        logger.warning("[P2P] banned %s for %ss (%s)", key, ban_sec, reason)
        return True

    def _rate_limit_ok(self, peer_id: str, msg_type: Optional[str] = None) -> bool:
        """Per-peer message rate limit (0 = disabled). Sync/housekeeping types exempt."""
        if msg_type in RATE_LIMIT_EXEMPT_TYPES:
            return True
        limit = int(getattr(self.config, "p2p_max_messages_per_sec", 0) or 0)
        if limit <= 0 or not peer_id:
            return True
        now = time.time()
        count, start = self._peer_msg_windows.get(peer_id, (0, now))
        if now - start >= 1.0:
            count, start = 0, now
        count += 1
        self._peer_msg_windows[peer_id] = (count, start)
        if count > limit:
            logger.warning("[P2P] rate limit exceeded for %s (%s/s)", peer_id, limit)
            return False
        return True

    async def _handle_message(self, peer: PeerConnection, msg: Dict):
        msg_type = msg.get("type")
        if msg_type not in ALLOWED_WIRE_TYPES:
            if self._strike_peer_sync(peer, f"unknown_type:{msg_type}"):
                self._remove_peer(peer.peer_id, peer)
            return
        # Mid-session handshake is abuse (initial handshake uses _do_handshake recv).
        if msg_type in (MSG_HANDSHAKE, MSG_HANDSHAKE_ACK):
            self._handshake_rejects = int(self._handshake_rejects or 0) + 1
            logger.warning(
                "[P2P] mid-session %s from %s",
                msg_type,
                peer.peer_id or self._peer_key(peer),
            )
            if self._strike_peer_sync(peer, "mid_session_handshake"):
                self._remove_peer(peer.peer_id, peer)
            return
        data = msg.get("data")

        # Fail-closed shape gates before sync waiters consume the message.
        if msg_type == MSG_STATE_ROOT_RESPONSE:
            if not native.validate_p2p_state_root_response(data):
                self._strike_peer_sync(peer, "bad_state_root_response")
                return
        elif msg_type == MSG_STATE_ROOT_REQUEST:
            if native.validate_p2p_state_root_request(data) is None:
                self._strike_peer_sync(peer, "bad_state_root_request")
                return
        elif msg_type == MSG_NEW_BLOCK:
            if not native.validate_p2p_block_announce(data):
                self._strike_peer_sync(peer, "bad_block_announce")
                return
        elif msg_type == MSG_ATTESTATION:
            if not native.validate_p2p_attestation_payload(data):
                self._strike_peer_sync(peer, "bad_attestation_shape")
                return
        elif msg_type == MSG_STATUS:
            if native.validate_p2p_status_payload(data) is None and data is not None:
                # Allow null/empty status keepalives; reject malformed dicts.
                if isinstance(data, dict):
                    self._strike_peer_sync(peer, "bad_status_payload")
                    return

        elif msg_type == MSG_NEW_TX:
            if not native.validate_p2p_wire_tx(data):
                self._strike_peer_sync(peer, "bad_wire_tx")
                return
        elif msg_type == MSG_MEMPOOL:
            if native.validate_p2p_mempool_batch(data) is None:
                self._strike_peer_sync(peer, "bad_mempool_batch")
                return
        elif msg_type == MSG_GET_BLOCKS:
            if native.validate_p2p_get_blocks_payload(data) is None:
                self._strike_peer_sync(peer, "bad_get_blocks")
                return
        elif msg_type == MSG_GET_BLOCK:
            if native.validate_p2p_get_block(data) is None:
                self._strike_peer_sync(peer, "bad_get_block")
                return
        elif msg_type == MSG_GET_BLOCK_BY_HASH:
            if native.validate_p2p_get_block_by_hash(data) is None:
                self._strike_peer_sync(peer, "bad_get_block_by_hash")
                return
        elif msg_type == MSG_BLOCKS:
            if native.validate_p2p_blocks_batch(data) is None:
                self._strike_peer_sync(peer, "bad_blocks_batch")
                return
        elif msg_type == MSG_BLOCK:
            # null/None = not found; non-null must match block announce shape
            if data is not None and native.validate_p2p_block_announce(data) is None:
                self._strike_peer_sync(peer, "bad_block_payload")
                return
        elif msg_type == MSG_PEERS:
            if native.validate_p2p_peers_list(data) is None:
                self._strike_peer_sync(peer, "bad_peers_list")
                return
        elif msg_type == MSG_VALIDATOR_REGISTER:
            if native.validate_p2p_validator_register(data) is None:
                self._strike_peer_sync(peer, "bad_validator_register")
                return
        elif msg_type == MSG_CROSS_SHARD_TX:
            if native.validate_p2p_cross_shard_tx(data) is None:
                self._strike_peer_sync(peer, "bad_cross_shard_tx")
                return
        elif msg_type == MSG_CROSS_SHARD_ACK:
            if native.validate_p2p_cross_shard_ack(data) is None:
                self._strike_peer_sync(peer, "bad_cross_shard_ack")
                return
        elif msg_type == MSG_SHARD_MIGRATION:
            if native.validate_p2p_shard_migration(data) is None:
                self._strike_peer_sync(peer, "bad_shard_migration")
                return
        elif msg_type in (MSG_GET_MEMPOOL, MSG_GET_PEERS, MSG_PING, MSG_PONG):
            if not _housekeeping_payload_ok(msg_type, data):
                if self._strike_peer_sync(peer, f"bad_{msg_type}_payload"):
                    self._remove_peer(peer.peer_id, peer)
                return

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
            height = native.validate_p2p_get_block(data)
            if height is None:
                self._strike_peer_sync(peer, "bad_get_block")
                return
            block = self.blockchain.get_block(int(height))
            await peer.send(MSG_BLOCK, block)

        elif msg_type == MSG_GET_BLOCK_BY_HASH:
            block_hash = native.validate_p2p_get_block_by_hash(data)
            if block_hash is None:
                self._strike_peer_sync(peer, "bad_get_block_by_hash")
                return
            block = None
            if hasattr(self.blockchain, "get_block_by_hash"):
                block = self.blockchain.get_block_by_hash(block_hash)
            await peer.send(MSG_BLOCK, block)

        elif msg_type == MSG_GET_BLOCKS:
            await self._handle_get_blocks(peer, data)

        elif msg_type == MSG_NEW_TX:
            await self._handle_new_tx(peer, data)

        elif msg_type == MSG_GET_MEMPOOL:
            await self._handle_get_mempool(peer)

        elif msg_type == MSG_MEMPOOL:
            await self._handle_mempool_batch(peer, data)

        elif msg_type == MSG_GET_PEERS:
            peer_list = [
                f"{p.host}:{p.listen_port or p.port}" for p in self.peers.values()
                if p.peer_id != peer.peer_id and (p.listen_port or p.port)
            ]
            await peer.send(MSG_PEERS, peer_list)

        elif msg_type == MSG_PEERS:
            peers = native.validate_p2p_peers_list(data)
            if peers is None:
                self._strike_peer_sync(peer, "bad_peers_list")
                return
            for addr in peers[:10]:  # не больше 10 за раз
                self._remember_addr(addr)
                parts = addr.rsplit(":", 1)
                if len(parts) == 2:
                    try:
                        asyncio.create_task(self.connect_peer(parts[0], int(parts[1])))
                    except Exception as exc:
                        self._peer_connect_task_fail += 1
                        logger.warning(
                            "[P2P] connect_peer task failed for %s: %s", addr, exc
                        )

        elif msg_type == MSG_STATUS:
            status = native.validate_p2p_status_payload(data)
            if status:
                incoming_h = int(status.get("height", 0) or 0)
                if incoming_h:
                    peer.height = max(int(peer.height or 0), incoming_h)
                incoming_head = status.get("head_hash") or ""
                if incoming_head:
                    peer.head = str(incoming_head)
                our_h = int(self.blockchain.get_height() or 0)
                if incoming_h and incoming_h != our_h:
                    await peer.send(MSG_STATUS, {
                        "height": our_h,
                        "head_hash": self.head() or "",
                    })

        elif msg_type == MSG_ATTESTATION:
            await self._handle_attestation(peer, data)

        elif msg_type == MSG_VALIDATOR_REGISTER:
            await self._handle_validator_register(peer, data)

        elif msg_type == MSG_STATE_ROOT_REQUEST:
            req_h = native.validate_p2p_state_root_request(data)
            if req_h is None:
                self._strike_peer_sync(peer, "bad_state_root_request")
                return
            height = req_h if req_h > 0 else self.blockchain.get_height()
            await peer.send(MSG_STATE_ROOT_RESPONSE, {
                "height": height,
                "state_root": self.blockchain.get_state_root(),
                "head_hash": self.head() or "",
            })

        elif msg_type == MSG_STATE_ROOT_RESPONSE:
            resp = native.validate_p2p_state_root_response(data)
            if not resp:
                self._strike_peer_sync(peer, "bad_state_root_response")
                return
            peer_h = int(resp.get("height", 0) or 0)
            if peer_h:
                peer.height = max(int(peer.height or 0), peer_h)
            if waiter is None:
                peer_root = resp.get("state_root", "")
                local_root = self.blockchain.get_state_root()
                if peer_h == self.blockchain.get_height() and peer_root and peer_root != local_root:
                    # Mismatch may clear consistency; only SyncEngine.sync_state may set True.
                    self._state_consistent = False
                    logger.warning(
                        f"[P2P] State root mismatch vs {peer.peer_id[:8]}: "
                        f"local={local_root[:12]} peer={peer_root[:12]}"
                    )
                elif peer_h == self.blockchain.get_height() and peer_root and peer_root == local_root:
                    logger.debug(
                        "[P2P] Unsolicited state_root match vs %s (not flipping consistent=True)",
                        (peer.peer_id or "")[:8],
                    )
        elif msg_type == MSG_CROSS_SHARD_TX:
            await self._handle_cross_shard_tx(peer, data)

        elif msg_type == MSG_CROSS_SHARD_ACK:
            await self._handle_cross_shard_ack(peer, data)
        elif msg_type == MSG_SHARD_MIGRATION:
            await self._handle_shard_migration(peer, data)

        else:
            if self._strike_peer_sync(peer, f"unhandled_type:{msg_type}"):
                self._remove_peer(peer.peer_id, peer)

    async def _handle_validator_register(self, peer: PeerConnection, data: Dict):
        """Register peer validator in local consensus when announced."""
        parsed = native.validate_p2p_validator_register(data)
        if not parsed:
            self._strike_peer_sync(peer, "bad_validator_register")
            return
        address = str(parsed.get("address") or "")
        stake = float(parsed.get("stake", 0) or 0)
        if not address or not self._consensus:
            return
        vals = self.blockchain.db.get_validators(active_only=False) or []
        known = {v["address"].lower() for v in vals}
        if address.lower() in known:
            return
        if hasattr(self._consensus, "add_validator"):
            if self._consensus.add_validator(address, stake):
                print(f"[P2P] Registered peer validator {address[:12]}… from {peer.peer_id[:8]}")
                await self._relay_validator_register(
                    {
                        "address": address,
                        "stake": stake,
                        "node_id": str(parsed.get("node_id") or ""),
                    },
                    exclude_peer=peer.peer_id,
                )

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
        if not native.validate_p2p_attestation_payload(data):
            self._strike_peer_sync(peer, "bad_attestation_shape")
            return
        vkeys = self.validator_keys
        if vkeys and hasattr(vkeys, "verify_attestation"):
            if not vkeys.verify_attestation(data):
                logger.warning(
                    "[P2P] Invalid attestation sig from %s",
                    (peer.peer_id or "?")[:12],
                )
                self._strike_peer_sync(peer, "bad_attestation_sig")
                return
        validator = data.get("validator", "")
        block_hash = data.get("target_hash", "")
        if not validator or not block_hash:
            return
        slot_raw = data.get("slot")
        slot = int(slot_raw) if slot_raw is not None else None
        consensus = self._consensus
        if consensus and hasattr(consensus, "attest"):
            if consensus.attest(validator, block_hash, slot=slot):
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
        announce = native.validate_p2p_block_announce(data)
        if not announce:
            self._strike_peer_sync(peer, "bad_block_announce")
            return

        block_h = int(announce.get("height", 0) or 0)
        block_hash = announce.get("hash", "")
        peer.height = max(peer.height, block_h)
        if block_hash:
            peer.head = block_hash

        from core.blockchain import Block
        try:
            block = Block.from_dict(data)
        except Exception as e:
            logger.warning("[P2P] Invalid block from %s: %s", peer.peer_id or peer, e)
            self._strike_peer_sync(peer, "bad_block_from_dict")
            return
        local_h = self.blockchain.get_height()
        existing = self.blockchain.get_block(block.height)
        if existing:
            if existing.get("hash") == block.hash:
                return
            self._feed_fork_choice(data)
            self._feed_fork_choice(existing)
            ghost_head = self._ghost_canonical_head()
            local_head = self.head() or ""
            if ghost_head and ghost_head.lower() != local_head.lower():
                if await self._reconcile_to_head_hash(ghost_head, peer_hint=peer):
                    return
            print(
                f"[P2P] Fork block #{block.height} from {peer.peer_id[:8]} — reconciling"
            )
            await self._reconcile_fork_at_peer(peer)
            return

        self._feed_fork_choice(data)
        if block.height > local_h + 1:
            asyncio.create_task(self._sync_with_peer_safe(peer))
            return

        for tx in block.transactions:
            self.mempool.remove(tx.hash)
        if self.blockchain.import_block(data):
            print(f"[P2P] Accepted block #{block.height} from {peer.peer_id[:8]}")
            if self.sync_engine:
                loop = asyncio.get_running_loop()
                ok = await loop.run_in_executor(None, self.sync_engine.sync_state)
                self._state_consistent = bool(ok)
            if self._consensus and self.validator_keys:
                try:
                    # Match proposer attestation slot (block forged at slot height-1).
                    attest_slot = max(0, int(block.height) - 1)
                    self._consensus.attest(
                        self.validator_keys.get_address(),
                        block.hash,
                        slot=attest_slot,
                    )
                except Exception as exc:
                    self._attestation_local_fail += 1
                    logger.warning(
                        "[P2P] local attest failed after accept #%s: %s",
                        getattr(block, "height", "?"),
                        exc,
                    )
            await self._broadcast_block(data, exclude_peer=peer.peer_id)

    async def _handle_get_blocks(self, peer: PeerConnection, data: Dict):
        """Отправляем диапазон блоков пиру."""
        rng = native.validate_p2p_get_blocks_payload(data)
        if not rng:
            self._strike_peer_sync(peer, "bad_get_blocks")
            return
        start = int(rng.get("from_height", 0))
        end = int(rng.get("to_height", start + self.config.sync_batch_size))
        blocks = []
        for h in range(start, min(end + 1, start + self.config.sync_batch_size)):
            blk = self.blockchain.get_block(h)
            if blk:
                blocks.append(blk)
        await peer.send(MSG_BLOCKS, blocks)

    def _record_tx_propagation(
        self,
        tx_hash: str,
        stage: str,
        peer_id: str = "",
        block_height: int = 0,
        detail: Optional[Dict] = None,
    ) -> None:
        db = getattr(self.blockchain, "db", None)
        if not db or not hasattr(db, "record_tx_propagation_event"):
            return
        try:
            db.record_tx_propagation_event(
                tx_hash,
                stage,
                node_id=getattr(self.config, "node_id", ""),
                peer_id=peer_id,
                block_height=block_height,
                detail=detail or {},
            )
        except Exception as exc:
            self._propagation_log_fail += 1
            logger.warning(
                "[P2P] record_tx_propagation_event failed stage=%s tx=%s: %s",
                stage,
                (tx_hash or "")[:16],
                exc,
            )

    def _build_mempool_tx_from_wire(self, data: Dict):
        """Build a mempool entry from wire-format tx; None if invalid."""
        self._last_tx_wire_reject = ""
        if not native.validate_p2p_wire_tx(data):
            self._last_tx_wire_reject = "bad_wire_tx"
            return None
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
        tx_hash = data.get("hash", data.get("tx_hash", ""))

        tx = Transaction(
            from_addr=from_addr,
            to_addr=to_addr,
            value=value,
            nonce=nonce,
            gas=gas,
            data=calldata,
            signature=signature,
            public_key=public_key,
            tx_hash=tx_hash,
        )
        validation = self.blockchain.validate_transaction(tx)
        if not validation["valid"]:
            self._last_tx_wire_reject = str(validation.get("error") or "invalid")
            return None

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
        return mp_tx, tx.hash

    async def _ingest_peer_tx(
        self,
        data: Dict,
        source: str = "p2p_gossip",
        peer_id: str = "",
        peer: Optional[PeerConnection] = None,
        *,
        strike_on_reject: bool = False,
    ) -> bool:
        """Validate and add a wire-format tx to mempool; record propagation stages."""
        built = self._build_mempool_tx_from_wire(data)
        if not built:
            err = self._last_tx_wire_reject or "invalid"
            self._peer_tx_reject = int(self._peer_tx_reject or 0) + 1
            logger.warning(
                "[P2P] Tx rejected (%s peer=%s): %s",
                source,
                (peer_id or "?")[:12],
                err,
            )
            if strike_on_reject and peer is not None:
                self._strike_peer_sync(peer, "bad_peer_tx")
            return False
        mp_tx, tx_hash = built
        if not self.mempool.add(mp_tx):
            self._peer_tx_reject = int(self._peer_tx_reject or 0) + 1
            logger.warning(
                "[P2P] Tx mempool drop (%s peer=%s hash=%s)",
                source,
                (peer_id or "?")[:12],
                str(tx_hash)[:12],
            )
            return False

        stage_recv = "mempool_sync" if source == "mempool_sync" else "p2p_received"
        self._record_tx_propagation(
            tx_hash,
            stage_recv,
            peer_id=peer_id,
            detail={"source": source},
        )
        self._record_tx_propagation(
            tx_hash,
            "mempool_remote",
            peer_id=peer_id,
            detail={"mempool_size": self.mempool.get_size()},
        )
        logger.debug(f"[P2P] Accepted tx {tx_hash[:12]}… ({source})")
        return True

    async def _handle_new_tx(self, peer: PeerConnection, data: Dict):
        """Принимаем транзакцию из gossip."""
        peer_id = getattr(peer, "peer_id", "") if peer else ""
        await self._ingest_peer_tx(
            data,
            source="p2p_gossip",
            peer_id=peer_id,
            peer=peer,
            strike_on_reject=True,
        )

    async def _handle_get_mempool(self, peer: PeerConnection):
        from blockchain.mempool_wire import mempool_tx_to_wire
        pending = self.mempool.get(limit=200)
        wire = [mempool_tx_to_wire(t) for t in pending]
        await peer.send(MSG_MEMPOOL, {"transactions": wire, "count": len(wire)})

    async def _handle_mempool_batch(self, peer: PeerConnection, data: Dict):
        if native.validate_p2p_mempool_batch(data) is None:
            self._strike_peer_sync(peer, "bad_mempool_batch")
            return
        txs = data.get("transactions", [])
        peer_id = getattr(peer, "peer_id", "") if peer else ""
        mp_txs = []
        wire_rejects = 0
        for tx_data in txs:
            built = self._build_mempool_tx_from_wire(tx_data)
            if built:
                mp_txs.append(built[0])
            else:
                wire_rejects += 1
        if wire_rejects:
            self._peer_tx_reject = int(self._peer_tx_reject or 0) + wire_rejects
            logger.warning(
                "[P2P] Mempool batch rejects peer=%s count=%s",
                (peer_id or "?")[:12],
                wire_rejects,
            )
        if not mp_txs:
            return
        added, batch_rejected, accepted_hashes = self.mempool.add_batch(mp_txs)
        if batch_rejected:
            self._peer_tx_reject = int(self._peer_tx_reject or 0) + int(batch_rejected)
        stage_recv = "mempool_sync"
        for tx_hash in accepted_hashes:
            self._record_tx_propagation(
                tx_hash,
                stage_recv,
                peer_id=peer_id,
                detail={"source": "mempool_sync"},
            )
            self._record_tx_propagation(
                tx_hash,
                "mempool_remote",
                peer_id=peer_id,
                detail={"mempool_size": self.mempool.get_size()},
            )
        if added:
            print(f"[P2P] Mempool sync from {peer_id[:8]}: +{added} tx(s)")

    async def _sync_mempool_with_peer(self, peer: PeerConnection, timeout: float = 12):
        """Pull peer mempool when chain tips are aligned (real pending tx relay)."""
        if abs(peer.height - self.blockchain.get_height()) > 2:
            return
        msg = await self._wait_peer_response(
            peer,
            (MSG_MEMPOOL,),
            timeout=timeout,
            presend=lambda: peer.send(MSG_GET_MEMPOOL, {}),
        )
        if msg and msg.get("type") == MSG_MEMPOOL:
            await self._handle_mempool_batch(peer, msg.get("data") or {})

    # ── Синхронизация ────────────────────────────────────────────────────────

    def _peer_lock(self, peer_id: str) -> asyncio.Lock:
        if peer_id not in self._peer_sync_locks:
            self._peer_sync_locks[peer_id] = asyncio.Lock()
        return self._peer_sync_locks[peer_id]

    async def _sync_with_peer_safe(self, peer: PeerConnection):
        lock = self._peer_lock(peer.peer_id or f"{peer.host}:{peer.port}")
        async with lock:
            try:
                await self._sync_with_peer(peer)
            except Exception as e:
                self._sync_fail = int(self._sync_fail or 0) + 1
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
        """Догоняем пира если он выше нас, или выравниваем форк на той же высоте."""
        our_height = self.blockchain.get_height()
        if peer.height < our_height:
            return
        if peer.height == our_height:
            local_head = self.head() or ""
            peer_head = peer.head or ""
            if peer_head and local_head != peer_head:
                await self._reconcile_fork_at_peer(peer)
            elif self.sync_engine:
                loop = asyncio.get_running_loop()
                ok = await loop.run_in_executor(None, self.sync_engine.sync_state)
                self._state_consistent = bool(ok)
            await self._sync_mempool_with_peer(peer)
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
                    if self.import_block(block_data):
                        h = block_data.get("height", block_data.get("number", current))
                        current = int(h) + 1
                        imported_any = True
                    else:
                        fail_h = int(
                            block_data.get("height", block_data.get("number", current)) or current
                        )
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
                        print(f"[P2P] Import failed at #{fail_h}, aborting batch")
                        break
                except Exception as e:
                    self._sync_fail = int(self._sync_fail or 0) + 1
                    print(f"[P2P] Sync block error at #{current}: {e}")
                    return

            if not imported_any:
                self._sync_fail = int(self._sync_fail or 0) + 1
                break

            peer.height = max(peer.height, self.blockchain.get_height())

        tip = self.blockchain.get_height()
        target = int(peer.height or 0)
        reached_target = tip >= target
        if reached_target:
            print(f"[P2P] Sync complete. Our height: {tip}")
        else:
            self._sync_fail = int(self._sync_fail or 0) + 1
            print(
                f"[P2P] Sync incomplete. Our height: {tip} "
                f"(peer target #{target})"
            )

        if self.sync_engine:
            loop = asyncio.get_running_loop()
            ok = await loop.run_in_executor(None, self.sync_engine.sync_state)
            self._state_consistent = bool(ok)

        # Never raise state-root baseline after a stalled/incomplete sync —
        # that would greenwash partial catch-up as a new strict tip.
        if reached_target and hasattr(self.blockchain, "set_state_root_baseline"):
            self.blockchain.set_state_root_baseline(tip)
            print(f"[P2P] State-root baseline set to #{tip} (strict above)")

        await self._sync_mempool_with_peer(peer)

    async def _reconcile_to_head_hash(
        self,
        target_head: str,
        peer_hint: Optional[PeerConnection] = None,
    ) -> bool:
        """Reorg to target head hash (GHOST canonical or peer tip)."""
        target_head = (target_head or "").strip()
        if not target_head:
            return False
        local_head = self.head() or ""
        if local_head and (
            local_head == target_head
            or local_head.lower() == target_head.lower()
        ):
            return True

        peer = peer_hint if peer_hint and (peer_hint.head or "") == target_head else None
        if peer is None:
            peer = self._peer_with_head(target_head)

        peer_block = None
        if peer:
            peer_block = await self._request_block_by_hash(peer, target_head)
        if not peer_block:
            for candidate in self.peers.values():
                peer_block = await self._request_block_by_hash(candidate, target_head)
                if peer_block:
                    peer = candidate
                    break
        if not peer_block:
            print(f"[P2P] Could not fetch head block {target_head[:12]} for reconcile")
            return False

        block_h = int(peer_block.get("height", peer_block.get("number", 0)))
        parent_hash = peer_block.get("parent_hash", "")
        ancestor = self.blockchain.find_ancestor_height(parent_hash)
        if ancestor is None:
            print("[P2P] No common ancestor for target head")
            return False

        rollback_to = min(ancestor, block_h - 1)
        predictor = getattr(self, "reorg_predictor", None)
        if predictor and hasattr(predictor, "analyze_live_peers"):
            peer_heights = [int(p.height) for p in self.peers.values()]
            risk = predictor.analyze_live_peers(
                self.blockchain.get_height(), peer_heights
            )
            if risk.get("risk", 0) > 0.5:
                print(
                    f"[P2P] High reorg risk ({risk.get('risk'):.2f}) — "
                    f"proceeding with finality guard"
                )

        if not self.blockchain.reorg_to_ancestor(rollback_to):
            return False
        if not self.blockchain.import_block(peer_block):
            print("[P2P] Failed to import target head after reorg")
            return False

        if peer:
            peer.height = block_h
            peer.head = peer_block.get("hash", target_head)
        if peer and block_h > self.blockchain.get_height():
            await self._sync_with_peer_safe(peer)
        print(f"[P2P] Reorg complete — head={target_head[:12]} height=#{block_h}")
        return True

    async def _reconcile_fork_at_peer(self, peer: PeerConnection) -> bool:
        """Same height, different head — reorg to GHOST canonical or peer head."""
        ghost_head = self._ghost_canonical_head()
        local_head = self.head() or ""
        if ghost_head and ghost_head.lower() != local_head.lower():
            if await self._reconcile_to_head_hash(ghost_head, peer_hint=peer):
                return True

        peer_head = peer.head or ""
        if not peer_head or peer_head == local_head:
            return True

        print(
            f"[P2P] Fork at #{peer.height}: "
            f"local={local_head[:12]} peer={peer_head[:12]}"
        )
        return await self._reconcile_to_head_hash(peer_head, peer_hint=peer)

    async def reconcile_peers(self) -> Dict:
        """Align chain tips with connected peers (height + head + state_root)."""
        results = []
        for peer in list(self.peers.values()):
            entry = {"peer": peer.peer_id[:12], "ok": False}
            try:
                if peer.height > self.blockchain.get_height():
                    await self._sync_with_peer_safe(peer)
                    entry["ok"] = True
                    entry["action"] = "catch_up"
                elif peer.height == self.blockchain.get_height():
                    local_head = self.head() or ""
                    ghost_head = self._ghost_canonical_head()
                    if ghost_head and ghost_head.lower() != local_head.lower():
                        entry["ok"] = await self._reconcile_to_head_hash(
                            ghost_head, peer_hint=peer
                        )
                        entry["action"] = "ghost_reorg"
                    elif (peer.head or "") != local_head:
                        entry["ok"] = await self._reconcile_fork_at_peer(peer)
                        entry["action"] = "fork_reorg"
                    else:
                        entry["ok"] = True
                        entry["action"] = "already_aligned"
                else:
                    entry["ok"] = True
                    entry["action"] = "ahead_of_peer"
                if abs(int(peer.height or 0) - int(self.blockchain.get_height() or 0)) <= 2:
                    await self._sync_mempool_with_peer(peer, timeout=3)
            except Exception as exc:
                entry["error"] = str(exc)
            results.append(entry)

        if self.sync_engine:
            loop = asyncio.get_running_loop()
            ok = await loop.run_in_executor(None, self.sync_engine.sync_state)
            self._state_consistent = bool(ok)
        elif self.peers:
            # Reconcile "ok" without a SyncEngine must not leave stale mesh-green.
            self._state_consistent = False

        return {
            "reconciled": results,
            "state_consistent": self._state_consistent,
            "height": self.blockchain.get_height(),
            "head": self.head() or "",
            "ghost_head": self._ghost_canonical_head() or "",
            "state_root": self.blockchain.get_state_root() if self.blockchain else "",
        }

    def trigger_reconcile(self) -> None:
        """Schedule peer reconcile from REST thread."""
        if not self._loop or not self._running:
            return
        asyncio.run_coroutine_threadsafe(self.reconcile_peers(), self._loop)

    def _remember_addr(self, addr: str) -> None:
        """Remember a reconnect candidate as host:port."""
        if not addr or ":" not in addr:
            return
        host, port_s = str(addr).rsplit(":", 1)
        try:
            port = int(port_s)
        except Exception:
            return
        if not host or port <= 0:
            return
        norm = f"{host}:{port}"
        if norm not in self._known_addrs:
            self._known_addrs.append(norm)

    def _prune_stale_peers(self, max_age: Optional[float] = None) -> int:
        """Drop stale or critically unhealthy peer objects before reconnect/dedup."""
        now = time.time()
        if max_age is None:
            max_age = max(30.0, float(getattr(self.config, "peer_timeout", 30) or 30) * 2)
        removed = 0
        local_height = int(self.blockchain.get_height() or 0) if self.blockchain else 0
        health_timeout = max(
            30.0,
            float(getattr(self.config, "peer_timeout", 30) or 30) * 2,
        )
        evict_below = int(getattr(self.config, "p2p_evict_min_score", 0) or 0)
        for pid, peer in list(self.peers.items()):
            if now - peer.last_seen > max_age:
                self._remove_peer(pid, peer)
                removed += 1
                continue
            if evict_below > 0 and len(self.peers) > 1:
                gap = abs(int(peer.height or 0) - local_height)
                age = max(0.0, now - peer.last_seen)
                score = _peer_health_score(
                    height_gap=gap,
                    last_seen_age=age,
                    health_timeout=health_timeout,
                )
                if score < evict_below:
                    self._remove_peer(pid, peer)
                    removed += 1
        expired_bans = [k for k, until in self._peer_bans.items() if now >= until]
        for key in expired_bans:
            self._peer_bans.pop(key, None)
        return removed

    async def reconnect_known_peers(self) -> Dict:
        """Actively reconnect bootstrap/known peers and report the result."""
        pruned = self._prune_stale_peers()
        candidates = []
        for addr in list(getattr(self.config, "bootstrap_peers", []) or []) + list(self._known_addrs):
            if addr not in candidates:
                candidates.append(addr)

        before = self.peer_count()
        if not candidates:
            return {
                "ok": before > 0,
                "before": before,
                "after": before,
                "attempts": [],
                "known_addresses": list(self._known_addrs),
                "message": "no known peer addresses",
            }
        attempts = []
        for addr in candidates:
            parts = str(addr).rsplit(":", 1)
            if len(parts) != 2:
                continue
            host, port_s = parts
            try:
                port = int(port_s)
            except Exception:
                attempts.append({"address": addr, "ok": False, "error": "bad_port"})
                continue
            already_peer = next(
                (
                    p
                    for p in self.peers.values()
                    if p.host == host and (p.port == port or p.listen_port == port)
                ),
                None,
            )
            if already_peer:
                ok_send = await already_peer.send(MSG_STATUS, {
                    "height": self.blockchain.get_height(),
                    "head_hash": self.head() or "",
                })
                if not ok_send:
                    self._peer_status_send_fail = int(self._peer_status_send_fail or 0) + 1
                    logger.warning("[P2P] status refresh to %s failed", addr)
                attempts.append({
                    "address": addr,
                    "ok": bool(ok_send),
                    "action": "already_connected_status_refresh",
                })
                continue
            ok = await self.connect_peer(host, port)
            attempts.append({"address": addr, "ok": bool(ok), "action": "connect"})

        await asyncio.sleep(0.5)
        return {
            "ok": self.peer_count() >= before,
            "before": before,
            "after": self.peer_count(),
            "attempts": attempts,
            "known_addresses": list(self._known_addrs),
            "pruned_stale": pruned,
        }

    def reconnect_known_peers_sync(self, timeout: float = 20) -> Dict:
        """Thread-safe reconnect entrypoint for REST/scripts."""
        if not self._loop or not self._running:
            return {"ok": False, "error": "p2p not running"}
        try:
            return asyncio.run_coroutine_threadsafe(
                self.reconnect_known_peers(), self._loop
            ).result(timeout=timeout)
        except Exception as exc:
            return {"ok": False, "error": str(exc), "after": self.peer_count()}

    async def request_peer_state_root(self, peer: PeerConnection, height: int = None) -> Optional[Dict]:
        """Request state_root at height from a single peer."""
        h = height if height is not None else self.blockchain.get_height()
        msg = await self._wait_peer_response(
            peer,
            (MSG_STATE_ROOT_RESPONSE,),
            timeout=4,
            presend=lambda: peer.send(MSG_STATE_ROOT_REQUEST, {"height": h}),
        )
        if not msg or msg.get("type") != MSG_STATE_ROOT_RESPONSE:
            return None
        data = msg.get("data")
        return data if isinstance(data, dict) else None

    async def request_peer_state_roots(self) -> List[Dict]:
        """Collect state_root responses from all connected peers (parallel)."""
        height = self.blockchain.get_height()
        peers = list(self.peers.values())
        if not peers:
            return []

        async def _one(peer: PeerConnection) -> Optional[Dict]:
            resp = await self.request_peer_state_root(peer, height)
            if resp:
                resp["peer_id"] = peer.peer_id
            return resp

        raw = await asyncio.gather(*(_one(p) for p in peers), return_exceptions=True)
        out: List[Dict] = []
        for r in raw:
            if isinstance(r, Exception):
                self._peer_sync_fail += 1
                logger.warning("[P2P] state_root peer gather failed: %s", r)
                continue
            if isinstance(r, dict):
                out.append(r)
        return out

    def request_peer_state_roots_sync(self, timeout: float = 15) -> Optional[List[Dict]]:
        if not self._loop or not self._running:
            return []
        peer_n = max(1, len(self.peers))
        budget = max(float(timeout), 4.0 + 4.0 * peer_n)
        future = asyncio.run_coroutine_threadsafe(
            self.request_peer_state_roots(), self._loop
        )
        try:
            return future.result(timeout=budget)
        except Exception as exc:
            logger.warning("[P2P] state_root wire probe timeout/error: %s", exc)
            return None

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

    def catch_up_sync(self, timeout: float = 90) -> Dict:
        """Block until lagging peers are synced (REST / devnet scripts)."""
        if not self._loop or not self._running:
            return {"ok": False, "error": "p2p not running"}

        async def _run():
            deadline = time.monotonic() + max(5.0, float(timeout))
            last = {"ok": False, "height": self.blockchain.get_height(), "peer_height": 0}
            while time.monotonic() < deadline:
                our_h = self.blockchain.get_height()
                peer_max = max((p.height for p in self.peers.values()), default=our_h)
                if our_h >= peer_max:
                    return {
                        "ok": True,
                        "height": our_h,
                        "peer_height": peer_max,
                        "action": "synced",
                    }
                tasks = [
                    self._sync_with_peer_safe(peer)
                    for peer in list(self.peers.values())
                    if peer.height > our_h
                ]
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
                new_h = self.blockchain.get_height()
                peer_max = max((p.height for p in self.peers.values()), default=new_h)
                last = {"ok": new_h >= peer_max, "height": new_h, "peer_height": peer_max}
                if last["ok"]:
                    return last
                await asyncio.sleep(2)
            return last

        try:
            return asyncio.run_coroutine_threadsafe(_run(), self._loop).result(timeout=timeout + 5)
        except Exception as exc:
            return {"ok": False, "error": str(exc), "height": self.blockchain.get_height()}

    def reconcile_peers_sync(self, timeout: float = 90) -> Dict:
        """Block until peer reconcile completes (REST / devnet scripts)."""
        if not self._loop or not self._running:
            return {"ok": False, "error": "p2p not running"}
        try:
            return asyncio.run_coroutine_threadsafe(
                self.reconcile_peers(), self._loop
            ).result(timeout=timeout)
        except Exception as exc:
            return {"ok": False, "error": str(exc), "height": self.blockchain.get_height()}

    def fetch_block_from_peers_sync(self, block_hash: str, timeout: float = 15) -> Optional[Dict]:
        """Синхронная обёртка для SyncEngine (из другого потока)."""
        if not self._loop or not self._running:
            return None
        future = asyncio.run_coroutine_threadsafe(
            self.fetch_block_from_peers(block_hash), self._loop
        )
        try:
            return future.result(timeout=timeout)
        except Exception as exc:
            self._peer_sync_fail += 1
            logger.warning(
                "[P2P] fetch_block_from_peers_sync failed hash=%s: %s",
                (block_hash or "")[:16],
                exc,
            )
            return None

    # ── Broadcast ────────────────────────────────────────────────────────────

    async def _broadcast_block(self, block_data: Dict, exclude_peer: str = ""):
        """Рассылает блок и актуальный status всем пирам (кроме exclude_peer)."""
        tasks = []
        block_h = int(block_data.get("height", block_data.get("number", 0)) or 0)
        block_hash = block_data.get("hash", "")
        status = {
            "height": block_h or self.blockchain.get_height(),
            "head_hash": block_hash or self.head() or "",
        }
        for pid, peer in list(self.peers.items()):
            if pid != exclude_peer:
                tasks.append(peer.send(MSG_NEW_BLOCK, block_data))
                tasks.append(peer.send(MSG_STATUS, status))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _handle_cross_shard_tx(self, peer: PeerConnection, data: Dict):
        parsed = native.validate_p2p_cross_shard_tx(data)
        if not parsed:
            self._strike_peer_sync(peer, "bad_cross_shard_tx")
            return
        if not self._sharding:
            return
        credited = False
        if hasattr(self._sharding, "receive_cross_shard_credit"):
            credited = bool(self._sharding.receive_cross_shard_credit(parsed))
        if credited:
            ack = {
                "tx_id": parsed.get("tx_id", ""),
                "shard_id": parsed.get("to_shard"),
                "to_shard": parsed.get("to_shard"),
                "status": "confirmed",
            }
            if self._sharding and hasattr(self._sharding, "validator_id"):
                vid = getattr(self._sharding, "validator_id", "") or getattr(
                    self._sharding, "node_id", ""
                )
                if vid:
                    ack["validator_id"] = vid
            await peer.send(MSG_CROSS_SHARD_ACK, ack)

    async def _handle_cross_shard_ack(self, peer: PeerConnection, data: Dict):
        parsed = native.validate_p2p_cross_shard_ack(data)
        if not parsed:
            self._strike_peer_sync(peer, "bad_cross_shard_ack")
            return
        if not self._sharding:
            return
        if hasattr(self._sharding, "receive_cross_shard_ack"):
            self._sharding.receive_cross_shard_ack(parsed)

    async def broadcast_cross_shard_ack(self, payload: Dict):
        if not isinstance(payload, dict):
            return
        tasks = [peer.send(MSG_CROSS_SHARD_ACK, payload) for peer in self.peers.values()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_cross_shard_tx(self, payload: Dict):
        if not isinstance(payload, dict):
            return
        tasks = [peer.send(MSG_CROSS_SHARD_TX, payload) for peer in self.peers.values()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _handle_shard_migration(self, peer: PeerConnection, data: Dict):
        parsed = native.validate_p2p_shard_migration(data)
        if not parsed:
            self._strike_peer_sync(peer, "bad_shard_migration")
            return
        if not self._sharding:
            return
        if hasattr(self._sharding, "receive_shard_migration"):
            self._sharding.receive_shard_migration(parsed)

    async def broadcast_shard_migration(self, payload: Dict):
        if not isinstance(payload, dict):
            return
        tasks = [peer.send(MSG_SHARD_MIGRATION, payload) for peer in self.peers.values()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_tx(self, tx_data: Dict):
        """Рассылает транзакцию всем пирам (full signed wire payload)."""
        from blockchain.mempool_wire import mempool_tx_to_wire

        tx_hash = tx_data.get("hash", tx_data.get("tx_hash", ""))
        if tx_hash and hasattr(self.mempool, "get_transaction"):
            mp_tx = self.mempool.get_transaction(tx_hash)
            if mp_tx:
                tx_data = mempool_tx_to_wire(mp_tx)
        if tx_hash:
            self._record_tx_propagation(
                tx_hash,
                "p2p_broadcast",
                detail={"peer_count": len(self.peers)},
            )
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
            self._attestation_local_fail = int(self._attestation_local_fail or 0) + 1
            logger.warning("[P2P] Attestation sign failed: %s", e)
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
            target_peers = max(1, int(getattr(self.config, "testnet_expected_peers", 1) or 1))
            if dead and len(self.peers) < target_peers:
                for addr in self._known_addrs:
                    parts = addr.rsplit(":", 1)
                    if len(parts) == 2:
                        try:
                            asyncio.create_task(self.connect_peer(parts[0], int(parts[1])))
                        except Exception as exc:
                            self._peer_connect_task_fail += 1
                            logger.warning(
                                "[P2P] reconnect task failed for %s: %s", addr, exc
                            )

    async def _discovery_loop(self):
        """Периодически запрашиваем список пиров у уже подключённых."""
        while self._running:
            await asyncio.sleep(60)
            try:
                for peer in list(self.peers.values()):
                    await peer.send(MSG_GET_PEERS)
                # Переподключаемся к известным адресам если пиров мало
                target_peers = max(
                    1, int(getattr(self.config, "testnet_expected_peers", 1) or 1)
                )
                if len(self.peers) < target_peers:
                    for addr in self._known_addrs:
                        parts = addr.rsplit(":", 1)
                        if len(parts) == 2:
                            try:
                                asyncio.create_task(
                                    self.connect_peer(parts[0], int(parts[1]))
                                )
                            except Exception as exc:
                                self._peer_connect_task_fail += 1
                                logger.warning(
                                    "[P2P] discovery reconnect failed for %s: %s",
                                    addr,
                                    exc,
                                )
            except Exception as exc:
                self._discovery_loop_fail = int(self._discovery_loop_fail or 0) + 1
                logger.warning("[P2P] discovery_loop: %s", exc)

    async def _bootstrap_retry_loop(self):
        """Переподключение к bootstrap-пирам, пока нет соединений."""
        while self._running:
            await asyncio.sleep(20)
            try:
                if self.peers or not self.config.bootstrap_peers:
                    continue
                for peer_addr in self.config.bootstrap_peers:
                    parts = str(peer_addr).rsplit(":", 1)
                    if len(parts) == 2:
                        try:
                            asyncio.create_task(
                                self.connect_peer(parts[0], int(parts[1]))
                            )
                        except Exception as exc:
                            self._peer_connect_task_fail += 1
                            logger.warning(
                                "[P2P] bootstrap connect failed for %s: %s",
                                peer_addr,
                                exc,
                            )
            except Exception as exc:
                self._bootstrap_loop_fail = int(self._bootstrap_loop_fail or 0) + 1
                logger.warning("[P2P] bootstrap_retry_loop: %s", exc)

    async def _maintenance_loop(self):
        """Periodic peer hygiene: stale eviction, ban expiry, low-score drops."""
        interval = max(
            15.0,
            float(getattr(self.config, "peer_timeout", 30) or 30),
        )
        while self._running:
            await asyncio.sleep(interval)
            try:
                removed = self._prune_stale_peers()
                if removed:
                    logger.info("[P2P] maintenance pruned %s peer(s)", removed)
                active_keys = {self._peer_key(p) for p in self.peers.values()}
                for key in list(self._peer_strikes):
                    if key not in active_keys:
                        self._peer_strikes.pop(key, None)
            except Exception as exc:
                self._maintenance_loop_fail = int(self._maintenance_loop_fail or 0) + 1
                logger.warning("[P2P] maintenance_loop: %s", exc)

    async def _catch_up_loop(self):
        """Периодически догоняем пиров с большей высотой."""
        while self._running:
            await asyncio.sleep(5)
            try:
                our_height = int(self.blockchain.get_height() or 0)
                our_status = {
                    "height": our_height,
                    "head_hash": self.head() or "",
                }
                for peer in list(self.peers.values()):
                    ok_send = await peer.send(MSG_STATUS, our_status)
                    if not ok_send:
                        self._peer_status_send_fail = int(
                            self._peer_status_send_fail or 0
                        ) + 1
                        continue
                    if peer.height > our_height:
                        asyncio.create_task(self._sync_with_peer_safe(peer))
                target_peers = max(1, int(getattr(self.config, "testnet_expected_peers", 1) or 1))
                if len(self.peers) < target_peers:
                    for addr in list(self._known_addrs):
                        parts = addr.rsplit(":", 1)
                        if len(parts) == 2:
                            try:
                                asyncio.create_task(self.connect_peer(parts[0], int(parts[1])))
                            except Exception as exc:
                                self._peer_connect_task_fail += 1
                                logger.warning(
                                    "[P2P] catch-up connect task failed for %s: %s",
                                    addr,
                                    exc,
                                )
            except Exception as exc:
                self._catch_up_loop_fail = int(self._catch_up_loop_fail or 0) + 1
                logger.warning("[P2P] catch_up_loop: %s", exc)

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

    def _remove_peer(self, peer_id: str, expected: Optional[PeerConnection] = None):
        if expected is not None and self.peers.get(peer_id) is not expected:
            return
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
                "listen_port": p.listen_port,
                "height": p.height,
                "head": p.head or "",
                "connected_for": int(time.time() - p.connected_at),
                "last_seen_age": round(max(0.0, time.time() - p.last_seen), 3),
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

    def get_topology(self) -> Dict:
        """Operational P2P topology for real multi-node devnet diagnostics."""
        local_height = self.blockchain.get_height() if self.blockchain else 0
        peers = []
        now = time.time()
        health_timeout = max(
            30.0,
            float(getattr(self.config, "peer_timeout", 30) or 30) * 2,
        )
        for p in self.peers.values():
            gap = abs(int(p.height or 0) - int(local_height or 0))
            last_seen_age = max(0.0, now - p.last_seen)
            score = _peer_health_score(
                height_gap=gap,
                last_seen_age=last_seen_age,
                health_timeout=health_timeout,
            )
            strikes = int(self._peer_strikes.get(self._peer_key(p), 0) or 0)
            peers.append({
                "peer_id": p.peer_id,
                "address": f"{p.host}:{p.listen_port or p.port}",
                "socket_address": f"{p.host}:{p.port}",
                "listen_port": p.listen_port,
                "height": p.height,
                "height_gap": gap,
                "head": p.head or "",
                "connected_for_sec": int(now - p.connected_at),
                "last_seen_age_sec": round(last_seen_age, 3),
                "health_timeout_sec": int(health_timeout),
                "healthy": gap <= 2 and last_seen_age < health_timeout,
                "score": score,
                "strikes": strikes,
                "banned": self._is_banned(self._peer_key(p)),
            })
        expected = int(getattr(self.config, "testnet_expected_peers", 0) or 0)
        scores = [p["score"] for p in peers]
        peer_links_ok = (len(peers) >= expected) if expected else True
        peers_healthy = all(p["healthy"] for p in peers) if peers else True
        # With live peers, topology must not greenwash without state consistency.
        consistent_ok = bool(self._state_consistent) if peers else True
        return {
            "node_id": getattr(self.config, "node_id", ""),
            "chain_id": getattr(self.config, "chain_id", 0),
            "running": self._running,
            "local_height": local_height,
            "local_head": self.head() or "",
            "peer_count": len(peers),
            "expected_peers": expected,
            "topology_healthy": peer_links_ok and peers_healthy and consistent_ok,
            "bootstrap_peers": list(getattr(self.config, "bootstrap_peers", []) or []),
            "known_addresses": list(self._known_addrs),
            "peers": peers,
            "state_consistent": self._state_consistent,
            "peer_score_min": min(scores) if scores else None,
            "peer_score_avg": round(sum(scores) / len(scores), 2) if scores else None,
            "security": self.get_p2p_security_status(),
        }

    def get_p2p_security_status(self) -> Dict:
        now = time.time()
        active_bans = [
            {
                "key": key,
                "seconds_remaining": max(0, int(until - now)),
            }
            for key, until in self._peer_bans.items()
            if until > now
        ]
        return {
            "rate_limit_per_sec": int(getattr(self.config, "p2p_max_messages_per_sec", 0) or 0),
            "max_message_bytes": _max_p2p_line_bytes(self.config),
            "ban_seconds": int(getattr(self.config, "p2p_ban_seconds", 300) or 300),
            "strikes_before_ban": int(getattr(self.config, "p2p_rate_limit_strikes", 5) or 5),
            "evict_min_score": int(getattr(self.config, "p2p_evict_min_score", 0) or 0),
            "active_bans": len(active_bans),
            "banned": active_bans[:20],
            "tracked_strikes": len(self._peer_strikes),
            "handshake_rejects": int(self._handshake_rejects),
            "attestation_local_fail": int(self._attestation_local_fail),
            "shape_rejects_total": int(sum(self._shape_reject_counts.values())),
            "shape_rejects": dict(
                sorted(
                    self._shape_reject_counts.items(),
                    key=lambda kv: (-int(kv[1]), str(kv[0])),
                )[:32]
            ),
            "rate_limit_drops": int(
                self._shape_reject_counts.get("rate_limit_exceeded", 0) or 0
            ),
            "ops_errors": {
                "propagation_log_fail": int(self._propagation_log_fail),
                "peer_connect_task_fail": int(self._peer_connect_task_fail),
                "peer_status_send_fail": int(self._peer_status_send_fail),
                "peer_send_fail": int(self._peer_send_fail),
                "maintenance_loop_fail": int(self._maintenance_loop_fail),
                "catch_up_loop_fail": int(self._catch_up_loop_fail),
                "peer_tx_reject": int(self._peer_tx_reject),
                "import_block_fail": int(self._import_block_fail),
                "sync_fail": int(self._sync_fail),
                "peer_sync_fail": int(self._peer_sync_fail),
                "discovery_loop_fail": int(self._discovery_loop_fail),
                "bootstrap_loop_fail": int(self._bootstrap_loop_fail),
            },
            "rate_limit_exempt_types": len(RATE_LIMIT_EXEMPT_TYPES),
            "tls": p2p_tls_status(self.config),
        }
