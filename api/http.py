#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Absolute Blockchain — HTTP API серверы.

Два сервера:
  1. JSONRPCServer  — Ethereum-совместимый JSON-RPC на порту 8545
  2. RESTServer     — REST API + статистика на порту 8080

Оба используют только stdlib (http.server + asyncio) — Flask не нужен.
"""

import asyncio
import json
import os
import time
import hashlib
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
from typing import Optional, Any, Dict, List
import threading


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handles each request in a separate thread — required for Windows stability."""
    daemon_threads = True
    allow_reuse_address = True

logger = logging.getLogger("API")

# --- Rate Limiter (middleware/rate_limit.py) ---
try:
    from middleware.rate_limit import create_rate_limiter
    _rate_limiter = create_rate_limiter(requests_per_minute=120, window_seconds=60)
    _RATE_LIMIT_AVAILABLE = True
except ImportError:
    _rate_limiter = None
    _RATE_LIMIT_AVAILABLE = False


def configure_rate_limiter(config) -> None:
    """Переинициализирует rate limiter из Config (in-memory или Redis)."""
    global _rate_limiter, _RATE_LIMIT_AVAILABLE
    if not config:
        return
    rpm = int(getattr(config, "rate_limit_rpm", 120) or 0)
    if rpm <= 0:
        _rate_limiter = None
        _RATE_LIMIT_AVAILABLE = False
        logger.info("Rate limiter: disabled (rate_limit_rpm=%s)", rpm)
        return
    try:
        from middleware.rate_limit import create_rate_limiter
        _rate_limiter = create_rate_limiter(
            redis_url=getattr(config, "redis_url", ""),
            redis_enabled=getattr(config, "redis_rate_limit_enabled", False),
            requests_per_minute=getattr(config, "rate_limit_rpm", 120),
            window_seconds=60,
        )
        _RATE_LIMIT_AVAILABLE = _rate_limiter is not None
        backend = "redis" if getattr(config, "redis_rate_limit_enabled", False) else "memory"
        logger.info("Rate limiter: %s (%s rpm)", backend, getattr(config, "rate_limit_rpm", 120))
    except ImportError:
        _rate_limiter = None
        _RATE_LIMIT_AVAILABLE = False

# --- Input validators (middleware/validators.py) ---
try:
    from middleware.validators import validate_address, validate_amount, sanitize_input
    _INPUT_VALIDATORS_AVAILABLE = True
except ImportError:
    _INPUT_VALIDATORS_AVAILABLE = False
    def sanitize_input(x): return x

# --- JWT Auth (middleware/jwt_auth.py) ---
try:
    from middleware.jwt_auth import jwt_auth
    _JWT_AVAILABLE = True
except ImportError:
    jwt_auth = None
    _JWT_AVAILABLE = False

# POST without JWT in dev. Node-admin repair/sync/recovery endpoints are
# intentionally excluded so dev/staging can exercise the same admin boundary.
_DEV_PUBLIC_POST = frozenset({
    "/transactions", "/tx/send", "/devnet/faucet", "/pools/dao/vote", "/devnet/pool-spend",
    "/bridge/confirm-lock", "/bridge/confirm-pending", "/bridge/dev-confirm-pending",
    "/bridge/lock", "/bridge/confirm", "/bridge2/transfer",
})

_PROD_BLOCKED_PATH_PREFIXES = ("/devnet", "/testnet")
_PROD_BLOCKED_PATHS = frozenset({
    "/auth/token",
    "/bridge/confirm",
    "/bridge/confirm-lock",
    "/bridge/refund",
    "/chain/consistency/repair",
    "/crypto/eth-address",
    "/crypto/keygen",
    "/crypto/sign",
    "/p2p/reconnect",
    "/pq/decapsulate",
    "/pq/hybrid-decrypt",
    "/pq/hybrid-sign",
    "/pq/sphincs/sign",
    "/pools/spend",
    "/state/credit",
    "/sync/add-peer",
    "/tx/sign",
})

_BRIDGE_ORACLE_PATHS = frozenset({
    "/bridge/oracle/confirm-lock",
    "/bridge/oracle/incoming",
    "/bridge/oracle/l1-register",
    "/bridge/oracle/l1-queue-sync",
    "/oracles/feeds/submit",
})


def _public_post_paths(cfg) -> frozenset:
    if getattr(cfg, "deployment_mode", "dev") == "prod":
        return frozenset({"/transactions", "/tx/send"})
    return _DEV_PUBLIC_POST


def _is_production_cfg(cfg) -> bool:
    return bool(
        getattr(cfg, "is_production", False)
        or getattr(cfg, "deployment_mode", "dev") == "prod"
    )


def _reject_auto_sign_in_prod(body: Dict, cfg) -> None:
    if _is_production_cfg(cfg) and body.get("auto_sign"):
        raise ValueError("auto_sign is disabled in production; submit a signed transaction")


def _reject_deploy_without_salt_in_prod(body: Dict, cfg) -> None:
    if not _is_production_cfg(cfg):
        return
    if not getattr(cfg, "evm_require_deploy_salt", False):
        return
    salt = body.get("salt")
    if salt is None or str(salt).strip() == "":
        raise ValueError("deploy salt required in production for deterministic contract address")


def _is_prod_blocked_path(path: str, cfg) -> bool:
    if not _is_production_cfg(cfg):
        return False
    return path in _PROD_BLOCKED_PATHS or any(
        path == prefix or path.startswith(f"{prefix}/")
        for prefix in _PROD_BLOCKED_PATH_PREFIXES
    )


def _bridge_for_request(handler_cls, cfg):
    rust_bridge = getattr(handler_cls, "bridge", None)
    if _is_production_cfg(cfg):
        if rust_bridge and getattr(rust_bridge, "_mode", "") == "rust":
            return rust_bridge
        return None
    return rust_bridge or getattr(handler_cls, "cross_bridge", None)


def _rust_bridge_health(cfg) -> Dict:
    """Return Rust bridge CLI health for readiness and metrics."""
    enabled = bool(getattr(cfg, "bridge_enabled", False)) if cfg else False
    mode = getattr(cfg, "bridge_mode", "unknown") if cfg else "unknown"
    required = bool(enabled and mode == "rust" and _is_production_cfg(cfg))
    out = {
        "enabled": enabled,
        "mode": mode,
        "required": required,
        "ok": True,
        "path": "",
        "error": "",
    }
    if not enabled or mode != "rust":
        return out

    try:
        from bridge.health import check_l1_rpc_health, check_rust_bridge_binary
        resolve = getattr(cfg, "resolve_rust_bridge_path", None)
        path = resolve() if callable(resolve) else getattr(cfg, "rust_bridge_path", "")
        status = check_rust_bridge_binary(path, timeout=1.5)
        out.update({
            "ok": bool(status.get("ok")),
            "path": status.get("path", path),
            "error": status.get("error", ""),
        })
        if status.get("response"):
            out["response"] = status["response"]
    except Exception as exc:
        out.update({"ok": False, "error": str(exc)})

    l1 = check_l1_rpc_health(cfg, timeout=1.5)
    out["l1_rpc"] = l1
    if out.get("required") and l1.get("required"):
        out["ok"] = bool(out.get("ok")) and bool(l1.get("ok"))
    return out

# Devnet / probes: не считаем в rate limit (start_two_nodes, devnet_status, K8s)
_RATE_LIMIT_EXEMPT_PATHS = frozenset({
    "/status",
    "/peers",
    "/network/peers",
    "/p2p/topology",
    "/p2p/peer-score",
    "/sync/status",
    "/testnet/mesh",
    "/testnet/fork-status",
    "/slashing/events",
    "/chain/consistency/harness",
    "/testnet/state-consistency",
    "/testnet/validators",
    "/testnet/multi-node-proof",
    "/testnet/bridge-relayer-proof",
    "/testnet/fork-exercise",
    "/consensus/stats",
    "/metrics",
    "/sync/fast-sync",
    "/sync/reconcile",
})


def _is_rate_limit_exempt(path: str) -> bool:
    p = (path or "").rstrip("/")
    return p in _RATE_LIMIT_EXEMPT_PATHS or p.startswith("/health/")


def _check_rate_limit(handler, path: Optional[str] = None) -> bool:
    """Return True if request may proceed; sends 429 and returns False when limited."""
    if not _RATE_LIMIT_AVAILABLE or not _rate_limiter:
        return True
    if path is None:
        path = urlparse(handler.path).path
    if _is_rate_limit_exempt(path):
        return True
    client_ip = handler.client_address[0]
    allowed, _remaining = _rate_limiter.allow_request(client_ip)
    if allowed:
        return True
    handler.send_response(429)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Retry-After", "60")
    handler.end_headers()
    handler.wfile.write(json.dumps({"error": "rate_limit_exceeded"}).encode())
    return False

# Ключевые маршруты для /openapi.json и /docs
_PUBLIC_API_ROUTES = [
    {"method": "GET", "path": "/status", "summary": "Node status"},
    {"method": "GET", "path": "/health/live", "summary": "Liveness probe"},
    {"method": "GET", "path": "/health/ready", "summary": "Readiness probe"},
    {"method": "GET", "path": "/native/crypto", "summary": "Rust/PyO3 native crypto diagnostics"},
    {"method": "GET", "path": "/tokenomics", "summary": "ABS tokenomics"},
    {"method": "GET", "path": "/founder", "summary": "Founder allocation"},
    {"method": "GET", "path": "/allocation", "summary": "Genesis allocation"},
    {"method": "GET", "path": "/mempool", "summary": "Pending transactions"},
    {"method": "GET", "path": "/mempool/audit", "summary": "Mempool fee stats and validation flags"},
    {"method": "GET", "path": "/sharding/pending", "summary": "Pending cross-shard transactions"},
    {"method": "GET", "path": "/sharding/cross-shard/quorum/{tx_id}", "summary": "Cross-shard validator quorum status"},
    {"method": "GET", "path": "/peers", "summary": "Connected P2P peers (alias)"},
    {"method": "GET", "path": "/network/peers", "summary": "Connected P2P peers"},
    {"method": "GET", "path": "/p2p/topology", "summary": "Live P2P topology and rejoin candidates (Wave 61)"},
    {"method": "POST", "path": "/p2p/reconnect", "summary": "Reconnect bootstrap/known P2P peers (dev, Wave 61)"},
    {"method": "GET", "path": "/testnet/mesh", "summary": "P2P mesh health (3-node testnet)"},
    {"method": "GET", "path": "/testnet/fork-status", "summary": "Fork heads, gaps, slashing summary (Wave 53)"},
    {"method": "GET", "path": "/slashing/events", "summary": "Persisted slash events from SQLite"},
    {"method": "GET", "path": "/chain/genesis/ceremony", "summary": "Mainnet genesis ceremony artifact"},
    {"method": "GET", "path": "/chain/consistency/harness", "summary": "State consistency harness (Wave 54)"},
    {"method": "POST", "path": "/chain/consistency/repair", "summary": "Replay chain if live state drifted from tip"},
    {"method": "GET", "path": "/testnet/validators", "summary": "5-validator set health and proposer rotation (Wave 55)"},
    {"method": "GET", "path": "/testnet/multi-node-proof", "summary": "Multi-node proof dashboard (Wave 56)"},
    {"method": "GET", "path": "/testnet/bridge-relayer-proof", "summary": "Bridge relayer + CI L1 RPC proof (Wave 60)"},
    {"method": "POST", "path": "/testnet/reorg-exercise", "summary": "Canonical replay reorg drill (dev only, Wave 56)"},
    {"method": "GET", "path": "/testnet/fork-exercise", "summary": "Fork recovery drill status (Wave 58)"},
    {"method": "POST", "path": "/testnet/fork-exercise", "summary": "P2P fork reconcile recovery drill (dev, Wave 58)"},
    {"method": "GET", "path": "/sync/status", "summary": "Chain sync status"},
    {"method": "GET", "path": "/features", "summary": "Feature flags and module availability"},
    {"method": "GET", "path": "/evm/supported-opcodes", "summary": "EVM opcode support matrix"},
    {"method": "GET", "path": "/consensus/attestations", "summary": "Latest validator attestations (LMD)"},
    {"method": "GET", "path": "/consensus/attestations/by-block", "summary": "Attestation votes aggregated per block"},
    {"method": "GET", "path": "/bridge", "summary": "Bridge overview"},
    {"method": "GET", "path": "/bridge/locks", "summary": "Bridge lock records"},
    {"method": "GET", "path": "/oracles/prices", "summary": "Crypto price feeds (registry or live)"},
    {"method": "GET", "path": "/oracles/feeds", "summary": "Persisted oracle feed registry"},
    {"method": "GET", "path": "/oracles/feeds/{symbol}", "summary": "Oracle feeds filtered by symbol"},
    {"method": "POST", "path": "/bridge/oracle/l1-queue-sync", "summary": "Relayer L1 queue persist (oracle HMAC)"},
    {"method": "GET", "path": "/bridge/l1-queue", "summary": "L1 RPC watch queue (relayer)"},
    {"method": "GET", "path": "/oracles/l1-queue", "summary": "Bridge L1 queue (alias)"},
    {"method": "GET", "path": "/lightning/stats", "summary": "Lightning channel stats (SQLite)"},
    {"method": "GET", "path": "/plasma/stats", "summary": "Plasma L2 stats (SQLite)"},
    {"method": "GET", "path": "/plasma/deposits", "summary": "Plasma L2 deposits"},
    {"method": "GET", "path": "/will/stats", "summary": "Crypto will stats (SQLite)"},
    {"method": "POST", "path": "/will/execute", "summary": "Execute crypto will (force in dev)"},
    {"method": "GET", "path": "/wasm/stats", "summary": "WASM VM stats (SQLite)"},
    {"method": "GET", "path": "/bridge/relayer/status", "summary": "Bridge relayer queue + pending locks"},
    {"method": "GET", "path": "/ai-agent/stats", "summary": "AI trading agents stats (SQLite)"},
    {"method": "GET", "path": "/l2/status", "summary": "Unified L2 modules dashboard"},
    {"method": "GET", "path": "/mev/history", "summary": "MEV analyzer history (SQLite)"},
    {"method": "POST", "path": "/oracles/feeds/submit", "summary": "Submit signed oracle feed (HMAC)"},
    {"method": "GET", "path": "/bridge/l1-proofs", "summary": "Registered L1 proof metadata"},
    {"method": "POST", "path": "/sync/reconcile", "summary": "P2P fork reconcile + state sync"},
    {"method": "GET", "path": "/wallet/status", "summary": "Signing wallet status"},
    {"method": "POST", "path": "/transactions", "summary": "Submit transaction"},
    {"method": "POST", "path": "/tx/send", "summary": "Submit transaction (alias, optional auto_sign)"},
    {"method": "POST", "path": "/tx/deploy", "summary": "Submit EVM deploy tx to mempool"},
    {"method": "POST", "path": "/tx/call", "summary": "Submit EVM contract call tx to mempool"},
]

try:
    from observability.metrics import MetricsCollector
    _METRICS_AVAILABLE = True
except ImportError:
    MetricsCollector = None
    _METRICS_AVAILABLE = False


# ═══════════════════════════════════════════════════════════════════════════════
#  JSON-RPC 2.0  (порт 8545, Ethereum-совместимый)
# ═══════════════════════════════════════════════════════════════════════════════

class JSONRPCHandler(BaseHTTPRequestHandler):
    """HTTP-обработчик для JSON-RPC запросов."""

    blockchain = None
    mempool = None
    config = None
    evm = None
    p2p = None
    wallet = None
    sync_engine = None
    rpc_auth = None
    eth_filters = None

    def log_message(self, fmt, *args):
        logger.debug(fmt % args)

    @staticmethod
    def _sanitize_header_value(value: str) -> str:
        if not value:
            return ""
        return value.replace("\r", "").replace("\n", "").replace("\0", "").strip()

    @classmethod
    def _cors_origin(cls, request_origin: str = "") -> str:
        request_origin = cls._sanitize_header_value(request_origin)
        cfg = cls.config
        origins = list(getattr(cfg, "cors_origins", ["*"]) or ["*"]) if cfg else ["*"]
        if "*" in origins:
            return "*"
        if request_origin and request_origin in origins:
            return request_origin
        return origins[0] if origins else ""

    def do_OPTIONS(self):
        self._send_cors()

    def do_GET(self):
        """Redirect browser GET requests to the Explorer UI on http_port."""
        if _is_production_cfg(self.__class__.config):
            self.send_response(405)
            self.send_header("Allow", "POST, OPTIONS")
            self.send_header("Access-Control-Allow-Origin", self._cors_origin(self.headers.get("Origin", "")))
            self.end_headers()
            return
        http_port = self.__class__.config.http_port if self.__class__.config else 8080
        self.send_response(302)
        self.send_header("Location", f"http://localhost:{http_port}/")
        self.send_header("Access-Control-Allow-Origin", self._cors_origin(self.headers.get("Origin", "")))
        self.end_headers()

    def do_POST(self):
        if not _check_rate_limit(self):
            return

        rpc_auth = self.__class__.rpc_auth
        if rpc_auth:
            ok, err = rpc_auth.verify(self.headers)
            if not ok:
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", self._cors_origin(self.headers.get("Origin", "")))
                self.end_headers()
                self.wfile.write(json.dumps({
                    "jsonrpc": "2.0",
                    "error": {"code": -32001, "message": err},
                    "id": None,
                }).encode())
                return

        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        try:
            req = json.loads(body)
            if _INPUT_VALIDATORS_AVAILABLE:
                req = sanitize_input(req)
        except json.JSONDecodeError:
            self._send_json({"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None})
            return

        # Batch requests
        if isinstance(req, list):
            responses = [self._dispatch(r) for r in req]
            self._send_json(responses)
        else:
            self._send_json(self._dispatch(req))

    def _dispatch(self, req: Dict) -> Dict:
        rid = req.get("id")
        method = req.get("method", "")
        params = req.get("params", [])

        try:
            result = self._call(method, params)
            return {"jsonrpc": "2.0", "id": rid, "result": result}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": rid,
                    "error": {"code": -32603, "message": str(e)}}

    def _call(self, method: str, params: list) -> Any:
        bc = self.__class__.blockchain
        mp = self.__class__.mempool
        cfg = self.__class__.config
        evm_adapter = self.__class__.evm
        p2p = self.__class__.p2p
        wallet = self.__class__.wallet
        sync_engine = self.__class__.sync_engine

        # ── net / web3 ─────────────────────────────────────────────────────
        if method == "net_version":
            return str(cfg.chain_id)

        if method == "web3_clientVersion":
            return f"Absolute/{cfg.node_version}/python"

        if method == "net_peerCount":
            count = p2p.peer_count() if p2p else 0
            return hex(count)

        if method == "eth_chainId":
            return hex(cfg.chain_id)

        if method == "eth_mining":
            return bool(getattr(cfg, "mining_enabled", False))

        if method == "eth_syncing":
            status = _build_sync_status(sync_engine, p2p, bc, cfg)
            behind = int(status.get("behind", 0) or 0)
            syncing = bool(status.get("syncing", False)) or behind > 0
            if syncing:
                return {
                    "startingBlock": hex(max(0, int(status.get("local_height", 0)) - behind)),
                    "currentBlock": hex(int(status.get("local_height", 0))),
                    "highestBlock": hex(int(status.get("best_peer_height", status.get("local_height", 0)))),
                }
            return False

        # ── Блоки ─────────────────────────────────────────────────────────
        if method == "eth_blockNumber":
            return hex(bc.get_height())

        if method == "eth_getBlockByNumber":
            tag = params[0] if params else "latest"
            full_tx = params[1] if len(params) > 1 else False
            blk = _resolve_block_by_tag(bc, tag)
            return _format_block(blk, full_tx)

        if method == "eth_getBlockByHash":
            block_hash = params[0] if params else ""
            from storage.database import Database
            blk = bc.db.get_block_by_hash(block_hash)
            full_tx = params[1] if len(params) > 1 else False
            return _format_block(blk, full_tx)

        # ── Аккаунты ──────────────────────────────────────────────────────
        if method == "eth_getBalance":
            address = params[0] if params else ""
            balance = bc.get_balance(address)
            # Возвращаем в wei (1 ABS = 1e18 wei для совместимости)
            return hex(int(balance * 10**18))

        if method == "eth_getTransactionCount":
            address = params[0] if params else ""
            nonce = bc.db.get_nonce(address)
            return hex(nonce)

        if method == "eth_getCode":
            address = params[0] if params else ""
            account = bc.db.get_account(address)
            if account and account.get("code"):
                return "0x" + account["code"].replace("0x", "")
            return "0x"

        # ── Транзакции ────────────────────────────────────────────────────
        if method == "eth_sendRawTransaction":
            raw = params[0] if params else ""
            return _handle_send_tx(raw, bc, mp, cfg)

        if method == "eth_sendTransaction":
            tx_obj = dict(params[0] if params else {})
            _reject_auto_sign_in_prod(tx_obj, cfg)
            if wallet and not _is_production_cfg(cfg):
                from_addr = str(tx_obj.get("from", "")).lower()
                if from_addr and from_addr == wallet.address.lower() and not tx_obj.get("signature"):
                    tx_obj["auto_sign"] = True
            return _handle_send_tx_with_wallet(tx_obj, bc, mp, cfg, wallet)

        if method == "eth_getTransactionByHash":
            tx_hash = params[0] if params else ""
            tx = bc.get_transaction(tx_hash)
            return _format_tx(tx)

        if method == "eth_getTransactionReceipt":
            tx_hash = params[0] if params else ""
            tx = bc.get_transaction(tx_hash)
            return _format_receipt(tx, bc)

        # ── EVM ────────────────────────────────────────────────────────────
        if method == "eth_call":
            tx_obj = params[0] if params else {}
            to_addr = tx_obj.get("to", "")
            data = tx_obj.get("data", "")
            if evm_adapter and to_addr:
                result = evm_adapter.static_call(to_addr, data)
                if result.success and result.return_value is not None:
                    return hex(result.return_value)
            return "0x"

        if method == "eth_estimateGas":
            tx_obj = params[0] if params else {}
            to_addr = tx_obj.get("to", "")
            data = tx_obj.get("data", tx_obj.get("input", ""))
            if evm_adapter and to_addr:
                gas = evm_adapter.estimate_gas(to_addr, data)
                return hex(max(21_000, int(gas or 0)))
            return hex(21_000)

        if method == "eth_gasPrice":
            return hex(int(cfg.gas_price_wei * 10**18))

        if method == "eth_maxPriorityFeePerGas":
            return hex(int(getattr(cfg, "priority_fee_wei", 0) or 0))

        if method == "eth_feeHistory":
            block_count = int(params[0], 16) if params else 1
            block_count = max(1, min(block_count, 1024))
            tip = _resolve_block_by_tag(bc, params[1] if len(params) > 1 else "latest")
            tip_h = int(tip.get("height", bc.get_height())) if tip else bc.get_height()
            oldest = max(0, tip_h - block_count + 1)
            base = hex(int(cfg.gas_price_wei * 10**18))
            return {
                "oldestBlock": hex(oldest),
                "baseFeePerGas": [base] * block_count,
                "gasUsedRatio": [0.5] * block_count,
                "reward": [["0x0"]] * block_count,
            }

        if method == "eth_accounts":
            if wallet and getattr(wallet, "address", ""):
                return [wallet.address]
            miner = getattr(cfg, "miner_address", "") or ""
            return [miner] if miner else []

        if method == "eth_coinbase":
            return getattr(cfg, "miner_address", "") or "0x0"

        if method == "eth_hashrate":
            return "0x0"

        if method == "eth_protocolVersion":
            return hex(65)

        if method == "eth_getStorageAt":
            address = params[0] if params else ""
            slot_raw = params[1] if len(params) > 1 else "0x0"
            slot = int(slot_raw, 16) if str(slot_raw).startswith("0x") else int(slot_raw)
            account = bc.db.get_account(address) if bc else None
            storage = {}
            if account and account.get("storage"):
                try:
                    storage = json.loads(account["storage"])
                except (TypeError, ValueError, json.JSONDecodeError):
                    storage = {}
            val = storage.get(str(slot), storage.get(slot, 0))
            return hex(int(val or 0))

        if method == "eth_getBlockTransactionCountByHash":
            block_hash = params[0] if params else ""
            blk = bc.db.get_block_by_hash(block_hash) if bc else None
            if not blk:
                return hex(0)
            txs = blk.get("transactions", [])
            return hex(len(txs) if isinstance(txs, list) else int(blk.get("tx_count", 0) or 0))

        if method == "eth_getTransactionByBlockNumberAndIndex":
            tag = params[0] if params else "latest"
            idx = int(params[1], 16) if len(params) > 1 and str(params[1]).startswith("0x") else int(params[1] if len(params) > 1 else 0)
            blk = _resolve_block_by_tag(bc, tag)
            return _format_tx(_tx_at_block_index(bc, blk, idx))

        if method == "eth_getTransactionByBlockHashAndIndex":
            block_hash = params[0] if params else ""
            idx = int(params[1], 16) if len(params) > 1 and str(params[1]).startswith("0x") else int(params[1] if len(params) > 1 else 0)
            blk = bc.db.get_block_by_hash(block_hash) if bc else None
            return _format_tx(_tx_at_block_index(bc, blk, idx))

        if method == "eth_getUncleCountByBlockNumber":
            return hex(0)

        if method == "eth_getUncleCountByBlockHash":
            return hex(0)

        if method == "eth_getLogs":
            filt = params[0] if params else {}
            if not isinstance(filt, dict):
                raise ValueError("eth_getLogs expects object filter")
            return _handle_eth_get_logs(filt, bc)

        filters = self.__class__.eth_filters
        if method == "eth_newFilter":
            filt = params[0] if params else {}
            if not isinstance(filt, dict):
                raise ValueError("eth_newFilter expects object filter")
            if not filters:
                raise ValueError("eth filters unavailable")
            return filters.new_log_filter(filt, bc)

        if method == "eth_newBlockFilter":
            if not filters:
                raise ValueError("eth filters unavailable")
            return filters.new_block_filter(bc)

        if method == "eth_newPendingTransactionFilter":
            if not filters:
                raise ValueError("eth filters unavailable")
            return filters.new_pending_filter(mp)

        if method == "eth_getFilterChanges":
            if not filters:
                return []
            filter_id = params[0] if params else ""
            return filters.get_filter_changes(
                filter_id, bc, mp, _handle_eth_get_logs
            )

        if method == "eth_getFilterLogs":
            if not filters:
                return []
            filter_id = params[0] if params else ""
            return filters.get_filter_logs(filter_id, bc, _handle_eth_get_logs)

        if method == "eth_uninstallFilter":
            if not filters:
                return False
            filter_id = params[0] if params else ""
            return filters.uninstall(filter_id)

        # ── Мемпул ────────────────────────────────────────────────────────
        if method == "eth_getMempoolSize":
            return hex(mp.get_size())

        if method == "eth_getBlockTransactionCountByNumber":
            tag = params[0] if params else "latest"
            blk = _resolve_block_by_tag(bc, tag)
            if not blk:
                return hex(0)
            txs = blk.get("transactions", [])
            count = len(txs) if isinstance(txs, list) else int(blk.get("tx_count", 0) or 0)
            return hex(count)

        raise ValueError(f"Method not supported: {method}")

    def _send_cors(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", self._cors_origin(self.headers.get("Origin", "")))
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key, Authorization")
        self.end_headers()

    def _send_json(self, data: Any):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", self._cors_origin(self.headers.get("Origin", "")))
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)


# ═══════════════════════════════════════════════════════════════════════════════
#  REST API  (порт 8080)
# ═══════════════════════════════════════════════════════════════════════════════

class RESTHandler(BaseHTTPRequestHandler):
    """HTTP-обработчик для REST API запросов."""

    blockchain = None
    mempool = None
    config = None
    p2p = None
    db = None
    evm = None
    nft = None                       # NFTMarketplace
    zk = None                        # ZKProofSystem
    sharding = None                  # ShardingManager
    oracles = None                   # OracleManager
    oracle_registry = None           # OracleFeedRegistry
    contract_manager = None          # MiniVM ContractManager
    assembler = None                 # MiniVM Assembler
    pq_manager = None                # PostQuantumManager
    smart_accounts = None            # SmartAccountManager
    multisig = None                  # MultiSigWallet class
    ai_validator = None              # AIValidatorEngine
    reorg_predictor = None           # ReorgPredictor
    mev_simulator = None             # MEVAnalyzer
    immutable_state = None           # ImmutableStateManager
    # ── NEW features ───────────────────────────────────────────────────────────
    lightning = None                 # LightningNetwork
    crypto_will = None               # CryptoWillManager
    plasma = None                    # PlasmaChain
    wasm_vm = None                   # WASMVirtualMachine
    ai_manager = None                # AIAgentManager
    cross_bridge = None              # CrossChainBridge
    consensus_engine_standalone = None  # Standalone ConsensusEngine
    consensus_adapter = None           # consensus.adapter.ConsensusAdapter
    finality_engine = None           # FinalityEngine
    sync_engine = None               # SyncEngine
    state_engine = None              # StateEngine
    slashing_engine = None           # SlashingEngine
    validator_registry = None        # ValidatorRegistry
    public_validator_set = None      # prod manifest snapshot (addresses only)
    validators_manifest_path = ""    # path to public validator manifest
    epoch_manager = None             # EpochManager
    beacon_finality = None           # BeaconFinality
    lmd_table = None                 # LMDTable
    consensus_casper = None          # ConsensusEngineCasper
    block_validator = None           # BlockValidator
    sphincs = None                   # SPHINCS+
    canonical_serializer = None      # CanonicalSerializer
    consensus_beacon = None          # ConsensusEngineBeacon
    consensus_engine_slashing = None # ConsensusEngineSlashing
    casper_finality = None           # CasperFinality
    pool_locks = None                # PoolLockManager
    light_client = None              # LightClient (SPV)
    wallet = None                    # Operational signing wallet (crypto.wallet.Wallet)
    bridge = None                    # bridge.abs_bridge.RustBridge
    bus = None                       # kernel.event_bus.EventBus
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    metrics_collector = None

    def log_message(self, fmt, *args):
        logger.debug(fmt % args)

    @staticmethod
    def _sanitize_header_value(value: str) -> str:
        if not value:
            return ""
        return value.replace("\r", "").replace("\n", "").replace("\0", "").strip()

    @classmethod
    def _cors_origin(cls, request_origin: str = "") -> str:
        request_origin = cls._sanitize_header_value(request_origin)
        cfg = cls.config
        origins = list(getattr(cfg, "cors_origins", ["*"]) or ["*"]) if cfg else ["*"]
        if "*" in origins:
            return "*"
        if request_origin and request_origin in origins:
            return request_origin
        return origins[0] if origins else "*"

    def _track_request(self) -> None:
        mc = self.__class__.metrics_collector
        if mc:
            mc.inc_http()

    def _require_jwt_admin(self, path: str) -> bool:
        cfg = self.__class__.config
        if not cfg or not getattr(cfg, "jwt_enforce_admin", False):
            return True
        if path in _public_post_paths(cfg):
            return True
        auth = self.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            self._error(401, "JWT required (Authorization: Bearer <token>)")
            return False
        if not _JWT_AVAILABLE or not jwt_auth:
            self._error(503, "JWT auth not available (install PyJWT)")
            return False
        ok, _payload = jwt_auth.verify_token(auth[7:].strip())
        if not ok:
            self._error(401, "Invalid or expired JWT")
            return False
        return True

    def _verify_bridge_oracle(self, path: str, raw_body: bytes) -> bool:
        cfg = self.__class__.config
        secret = getattr(cfg, "bridge_oracle_secret", "") or os.environ.get("BRIDGE_ORACLE_SECRET", "")
        if not secret:
            self._error(503, "BRIDGE_ORACLE_SECRET not configured")
            return False
        sig = self.headers.get("X-Bridge-Oracle-Signature", "")
        try:
            from bridge.oracle_auth import verify_signature
            if verify_signature(secret, raw_body, sig):
                return True
        except Exception:
            pass
        self._error(401, "Invalid bridge oracle signature")
        return False

    def do_OPTIONS(self):
        self._cors()

    def do_GET(self):
        # Read-only Explorer/dashboard traffic — no rate limit on GET
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        qs = parse_qs(parsed.query)

        bc = self.__class__.blockchain
        mp = self.__class__.mempool
        cfg = self.__class__.config
        p2p = self.__class__.p2p
        db = self.__class__.db
        evm_adapter = self.__class__.evm

        try:
            self._track_request()
            if _is_prod_blocked_path(path, cfg):
                self._error(403, "dev/testnet endpoint disabled in production")
                return

            # ── Health & metrics (K8s / Prometheus) ──────────────────────────
            if path == "/health/live":
                mc = self.__class__.metrics_collector
                self._json({
                    "status": "alive",
                    "node_id": getattr(cfg, "node_id", "node-1"),
                    "deployment_mode": getattr(cfg, "deployment_mode", "dev"),
                    "uptime_seconds": round(mc.uptime_seconds(), 2) if mc else 0,
                })
                return

            if path == "/health/ready":
                from crypto import native
                native_crypto = native.native_crypto_status(
                    required=bool(getattr(cfg, "require_native_crypto", False))
                )
                bridge_health = _rust_bridge_health(cfg)
                checks = {
                    "blockchain": bc is not None,
                    "database": db is not None,
                    "mempool": mp is not None,
                    "native_crypto": (
                        native_crypto["available"] and native_crypto["self_test"]
                        if native_crypto["required"]
                        else True
                    ),
                    "rust_bridge": (
                        bool(bridge_health.get("ok"))
                        if bridge_health.get("required")
                        else True
                    ),
                    "l1_rpc": (
                        bool(bridge_health.get("l1_rpc", {}).get("ok"))
                        if bridge_health.get("l1_rpc", {}).get("required")
                        else True
                    ),
                }
                ready = all(checks.values())
                payload = {
                    "status": "ready" if ready else "not_ready",
                    "checks": checks,
                    "native_crypto": native_crypto,
                    "rust_bridge": bridge_health,
                    "l1_rpc": bridge_health.get("l1_rpc"),
                    "height": bc.get_height() if bc else 0,
                }
                if ready:
                    self._json(payload)
                else:
                    body = json.dumps(payload, default=str).encode()
                    origin = self._cors_origin(self.headers.get("Origin", ""))
                    self.send_response(503)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Content-Length", len(body))
                    self.end_headers()
                    self.wfile.write(body)
                return

            if path == "/metrics":
                if not cfg or not getattr(cfg, "metrics_enabled", True):
                    self._error(404, "Metrics disabled")
                    return
                mc = self.__class__.metrics_collector
                if not mc:
                    self._error(503, "Metrics collector unavailable")
                    return
                validators = db.get_validators() if db else []
                from crypto import native
                native_crypto = native.native_crypto_status(
                    required=bool(getattr(cfg, "require_native_crypto", False))
                )
                bridge_health = _rust_bridge_health(cfg)
                text = mc.render_prometheus(
                    height=bc.get_height() if bc else 0,
                    peers=p2p.peer_count() if p2p else 0,
                    mempool=mp.get_size() if mp else 0,
                    validators=len(validators),
                    deployment_mode=getattr(cfg, "deployment_mode", "dev"),
                    node_id=getattr(cfg, "node_id", "node-1"),
                    native_crypto=native_crypto,
                    bridge_health=bridge_health,
                )
                body = text.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
                return

            if path == "/native/crypto":
                from crypto import native
                native_crypto = native.native_crypto_status(
                    required=bool(getattr(cfg, "require_native_crypto", False))
                )
                self._json({
                    "native_crypto": native_crypto,
                    "ready": (
                        native_crypto["available"] and native_crypto["self_test"]
                        if native_crypto["required"]
                        else True
                    ),
                    "node_id": getattr(cfg, "node_id", "node-1"),
                    "deployment_mode": getattr(cfg, "deployment_mode", "dev"),
                })
                return

            # ── favicon (browsers always request it) ─────────────────────────
            if path in ("/favicon.ico", "/favicon.png"):
                self.send_response(204)
                self.end_headers()
                return

            # ── Static HTML serving ──────────────────────────────────────────
            if path in ("", "/", "/index.html") or path.endswith(".html"):
                root = self.__class__.project_root
                html_path = os.path.join(root, "web", "explorer", "index.html")
                if not os.path.exists(html_path):
                    # fallback: serve a simple redirect page
                    body = b"<html><body><h2>Absolute Blockchain</h2><p>index.html not found at: " + html_path.encode() + b"</p></body></html>"
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", len(body))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                with open(html_path, "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", len(body))
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.send_header("Pragma", "no-cache")
                self.send_header("Access-Control-Allow-Origin", self._cors_origin(self.headers.get("Origin", "")))
                self.end_headers()
                self.wfile.write(body)
                return

            if path == "/status":
                validators = db.get_validators() if db else []
                total_burned = db.get_total_burned() if db else 0
                total_supply = db.get_total_supply() if db and hasattr(db, "get_total_supply") else 0
                bridge_locks = (
                    db.get_bridge_locks(limit=1000)
                    if db and hasattr(db, "get_bridge_locks")
                    else []
                )
                bridge_pending = sum(1 for l in bridge_locks if l.get("status") == "pending")
                mp_stats = mp.get_stats()
                sh = self.__class__.sharding
                sharding_info = {"enabled": False}
                if sh and hasattr(sh, "get_stats"):
                    sh_st = sh.get_stats()
                    sharding_info = {
                        "enabled": True,
                        "total_shards": sh_st.get("total_shards", 0),
                        "pending_cross_shard_txs": sh_st.get("pending_cross_shard_txs", 0),
                        "total_cross_shard_txs": sh_st.get("total_cross_shard_txs", 0),
                    }
                peer_heights = []
                peer_gap = 0
                if p2p and hasattr(p2p, "get_peers_info"):
                    local_h = bc.get_height()
                    for peer in p2p.get_peers_info():
                        ph = int(peer.get("height", 0) or 0)
                        peer_heights.append({
                            "id": peer.get("id", "")[:12],
                            "height": ph,
                            "head": (peer.get("head") or "")[:16],
                            "gap": abs(ph - local_h),
                        })
                    if peer_heights:
                        peer_gap = max(p["gap"] for p in peer_heights)
                from crypto import native
                native_crypto = native.native_crypto_status(
                    required=bool(getattr(cfg, "require_native_crypto", False))
                )
                bridge_health = _rust_bridge_health(cfg)
                last_blk = bc.get_last_block() if bc else None
                head_hash = (last_blk or {}).get("hash", "")
                consensus_info = {
                    "mode": cfg.resolved_consensus_mode(),
                    "unified_path": cfg.resolved_consensus_mode() == "unified",
                    "lmd_ghost_enabled": False,
                    "canonical_head": None,
                    "attestation_count": 0,
                }
                ca = self.__class__.consensus_adapter
                if ca and hasattr(ca, "get_stats"):
                    try:
                        cstats = ca.get_stats()
                        consensus_info.update({
                            "mode": cstats.get("consensus_mode", consensus_info["mode"]),
                            "unified_path": bool(cstats.get("unified_consensus_path")),
                            "lmd_ghost_enabled": bool(cstats.get("lmd_ghost_enabled")),
                            "canonical_head": cstats.get("canonical_head"),
                            "attestation_count": int(cstats.get("attestation_count", 0) or 0),
                        })
                    except Exception:
                        pass
                self._json({
                    "status": "running",
                    "node_version": cfg.node_version,
                    "network_name": cfg.network_name,
                    "chain_name": cfg.network_name,
                    "chain_id": cfg.chain_id,
                    "height": bc.get_height(),
                    "head_hash": head_hash,
                    "peers": p2p.peer_count() if p2p else 0,
                    "mempool_size": mp.get_size(),
                    "mempool_stats": mp_stats,
                    "sharding": sharding_info,
                    "coin": cfg.coin_symbol,
                    "coin_symbol": cfg.coin_symbol,
                    "max_supply": getattr(cfg, "max_supply", 221_000_000),
                    "total_supply": total_supply,
                    "founder_initials": getattr(cfg, "founder_initials", "D.U.P."),
                    "founder_percent": getattr(cfg, "founder_percent", 17.4),
                    "founder_address": getattr(cfg, "founder_address", ""),
                    "miner_address": getattr(cfg, "miner_address", ""),
                    "rpc_port": cfg.rpc_port,
                    "http_port": cfg.http_port,
                    "ws_port": getattr(cfg, "ws_port", 8766),
                    "state_root": bc.get_state_root() if hasattr(bc, "get_state_root") else "",
                    "validator_count": len(validators),
                    "total_burned": total_burned,
                    "evm_enabled": cfg.evm_enabled,
                    "bridge_enabled": cfg.bridge_enabled,
                    "bridge_mode": getattr(cfg, "bridge_mode", "unknown"),
                    "bridge_pending": bridge_pending,
                    "bridge_locks_total": len(bridge_locks),
                    "deployment_mode": getattr(cfg, "deployment_mode", "dev"),
                    "consensus": consensus_info,
                    "state_root_strict_p2p": bool(
                        getattr(cfg, "state_root_strict_p2p", True)
                    ),
                    "jwt_enforce_admin": getattr(cfg, "jwt_enforce_admin", False),
                    "rpc_api_key_required": getattr(cfg, "rpc_api_key_required", False),
                    "bridge_oracle_enabled": bool(
                        getattr(cfg, "bridge_oracle_secret", "")
                        or os.environ.get("BRIDGE_ORACLE_SECRET", "")
                    ),
                    "bridge_l1_queue_path": getattr(cfg, "bridge_l1_queue_path", "data/bridge_l1_queue.json"),
                    "native_crypto": native_crypto,
                    "rust_bridge": bridge_health,
                    "oracle_registry_enabled": self.__class__.oracle_registry is not None,
                    "api_wave": 61,
                    "core_real": {
                        "deterministic_proposer": True,
                        "finality_quorum_live": True,
                        "reorg_finality_guard": True,
                        "mev_mempool_analysis": True,
                        "bridge_production_path": getattr(cfg, "bridge_mode", "unknown") == "rust",
                        "bridge_l1_queue": True,
                        "bridge2_rust_path": bool(getattr(self.__class__, "bridge", None)),
                        "bridge_relayer_live": True,
                        "bridge_ci_l1_rpc": True,
                        "native_crypto": native_crypto,
                    },
                    "lightning_enabled": self.__class__.lightning is not None,
                    "plasma_enabled": self.__class__.plasma is not None,
                    "crypto_will_enabled": self.__class__.crypto_will is not None,
                    "wasm_enabled": self.__class__.wasm_vm is not None,
                    "ai_agents_enabled": self.__class__.ai_manager is not None,
                    "mev_enabled": self.__class__.mev_simulator is not None,
                    "reorg_predictor_enabled": self.__class__.reorg_predictor is not None,
                    "core_receipts_enabled": bool(
                        db and hasattr(db, "get_tx_receipt")
                    ),
                    "l2_persisted": bool(
                        getattr(self.__class__.lightning, "db", None)
                        or getattr(self.__class__.plasma, "db", None)
                    ),
                    "bridge_l1_rpc_configured": bool(
                        os.environ.get("ETH_RPC_URL", "")
                        or os.environ.get("ETHEREUM_RPC_URL", "")
                    ),
                    "node_id": getattr(cfg, "node_id", "node-1"),
                    "peer_sync_gap": peer_gap,
                    "peer_heights": peer_heights,
                    "state_consistent": getattr(p2p, "_state_consistent", True) if p2p else True,
                    "health": {
                        "live": "/health/live",
                        "ready": "/health/ready",
                        "metrics": "/metrics",
                    },
                    "api_docs": "/docs",
                    "openapi": "/openapi.json",
                    "middleware": {
                        "rate_limit": _RATE_LIMIT_AVAILABLE,
                        "input_validation": _INPUT_VALIDATORS_AVAILABLE,
                        "jwt_auth": _JWT_AVAILABLE,
                    },
                })

            elif path == "/tokenomics":
                try:
                    from runtime.tokenomics import get_tokenomics_summary, resolve_founder_address
                    founder = resolve_founder_address(
                        getattr(cfg, "founder_address", ""),
                        getattr(cfg, "miner_address", ""),
                    )
                    stored = db.get_meta("tokenomics") if db and hasattr(db, "get_meta") else None
                    summary = get_tokenomics_summary(founder or None)
                    if stored:
                        summary["stored_genesis"] = stored
                    summary["live_supply"] = db.get_total_supply() if db else 0
                    self._json(summary)
                except Exception as e:
                    self._json({"error": str(e), "max_supply": 221_000_000})

            elif path == "/founder":
                try:
                    from runtime.tokenomics import founder_balance_lookup
                    info = founder_balance_lookup(
                        db,
                        getattr(cfg, "founder_address", ""),
                        getattr(cfg, "miner_address", ""),
                    )
                    founder = info["summary"]["founder"]
                    self._json({
                        **founder,
                        "balance_abs": info["balance_abs"],
                        "balance_address": info["balance_address"],
                        "conditions": info["summary"]["conditions"],
                    })
                except Exception as e:
                    self._json({"error": str(e)})

            elif path == "/allocation":
                try:
                    from runtime.tokenomics import get_tokenomics_summary, resolve_founder_address
                    founder = resolve_founder_address(
                        getattr(cfg, "founder_address", ""),
                        getattr(cfg, "miner_address", ""),
                    )
                    t = get_tokenomics_summary(founder or None)
                    allocations = [dict(a) for a in t["allocations"]]
                    pl = self.__class__.pool_locks
                    if pl and hasattr(pl, "get_status"):
                        live_map = {p["id"]: p for p in pl.get_status().get("pools", [])}
                        for row in allocations:
                            live = live_map.get(row["id"])
                            if live:
                                row["live_spendable"] = live.get("spendable", 0.0)
                                row["live_locked"] = live.get("locked", row.get("locked", False))
                                row["dao_unlocked"] = live.get("dao_unlocked", False)
                                row["dao_votes"] = live.get("dao_votes", 0)
                    self._json({
                        "max_supply": t["max_supply"],
                        "allocations": allocations,
                        "genesis_minted": t["genesis_minted"],
                        "mining_reserve": t["mining_reserve"],
                    })
                except Exception as e:
                    self._json({"error": str(e)})

            elif path == "/blocks":
                limit = int(qs.get("limit", ["20"])[0])
                blocks = db.get_latest_blocks(min(limit, 100))
                att_map = _attestation_count_map(self.__class__.consensus_adapter)
                if att_map:
                    for blk in blocks:
                        h = str(blk.get("hash", blk.get("block_hash", ""))).lower()
                        blk["attestation_count"] = att_map.get(h, 0)
                self._json({"blocks": blocks, "count": len(blocks)})

            elif path.startswith("/blocks/"):
                param = path.split("/blocks/")[1]
                if param.startswith("0x") or len(param) == 64:
                    blk = db.get_block_by_hash(param)
                else:
                    blk = bc.get_block(int(param))
                if blk:
                    self._json(blk)
                else:
                    self._error(404, "Block not found")

            elif path.startswith("/transactions/"):
                tx_hash = path.split("/transactions/")[1]
                if tx_hash == "recent":
                    limit = int(qs.get("limit", ["30"])[0])
                    txs = _collect_recent_activity(
                        db,
                        cross_bridge=self.__class__.cross_bridge,
                        limit=min(limit, 100),
                    )
                    self._json({"transactions": txs, "count": len(txs)})
                    return
                tx = bc.get_transaction(tx_hash)
                if tx:
                    self._json(tx)
                else:
                    self._error(404, "Transaction not found")

            elif path.startswith("/address/"):
                remainder = path[len("/address/"):]
                parts = remainder.split("/")
                addr = parts[0]
                sub = parts[1] if len(parts) > 1 else ""
                if not addr:
                    self._error(400, "address required"); return
                limit = min(max(int(qs.get("limit", ["50"])[0]), 1), 200)
                offset = max(int(qs.get("offset", ["0"])[0]), 0)
                direction = qs.get("direction", ["all"])[0]
                if direction not in ("all", "sent", "received"):
                    self._error(400, "direction must be all, sent, or received"); return
                if sub == "txs":
                    if not hasattr(db, "count_address_transactions"):
                        self._error(503, "address index not available"); return
                    total = db.count_address_transactions(addr, direction=direction)
                    txs = db.get_transactions_by_address(
                        addr, limit=limit, offset=offset, direction=direction
                    )
                    self._json({
                        "address": addr,
                        "direction": direction,
                        "limit": limit,
                        "offset": offset,
                        "total": total,
                        "transactions": txs,
                    })
                elif sub == "activity":
                    if not hasattr(db, "get_address_activity"):
                        self._error(503, "address index not available"); return
                    act = db.get_address_activity(addr)
                    act["balance_formatted"] = (
                        f"{act['balance']:.6f} {cfg.coin_symbol}"
                    )
                    self._json(act)
                else:
                    if hasattr(db, "get_address_activity"):
                        act = db.get_address_activity(addr)
                        txs = db.get_transactions_by_address(addr, limit=20, offset=0)
                        self._json({
                            **act,
                            "balance_formatted": (
                                f"{act['balance']:.6f} {cfg.coin_symbol}"
                            ),
                            "transactions": txs,
                        })
                    else:
                        balance = bc.get_balance(addr)
                        nonce = db.get_nonce(addr)
                        txs = db.get_transactions_by_address(addr, limit=50)
                        account = db.get_account(addr)
                        self._json({
                            "address": addr,
                            "balance": balance,
                            "balance_formatted": f"{balance:.6f} {cfg.coin_symbol}",
                            "nonce": nonce,
                            "is_contract": bool(account and account.get("code")),
                            "tx_count": len(txs),
                            "transactions": txs[:20],
                        })

            elif path == "/mempool":
                txs = mp.get(limit=50)
                stats = mp.get_stats()
                sh = self.__class__.sharding
                tx_rows = []
                for tx in txs:
                    row = {
                        "hash": tx.tx_hash,
                        "from": tx.from_addr,
                        "to": tx.to_addr,
                        "value": tx.amount,
                        "fee": tx.fee,
                        "nonce": tx.nonce,
                    }
                    if sh and hasattr(sh, "get_shard_for_address"):
                        row["from_shard"] = sh.get_shard_for_address(tx.from_addr)
                        row["to_shard"] = sh.get_shard_for_address(tx.to_addr)
                        row["cross_shard"] = row["from_shard"] != row["to_shard"]
                    tx_rows.append(row)
                payload = {
                    "stats": stats,
                    "transactions": tx_rows,
                    "min_fee": getattr(mp, "min_fee", 0),
                    "require_signatures": getattr(mp, "require_signatures", False),
                }
                if sh and hasattr(sh, "get_stats"):
                    sh_st = sh.get_stats()
                    payload["sharding"] = {
                        "enabled": True,
                        "pending_cross_shard_txs": sh_st.get("pending_cross_shard_txs", 0),
                        "total_shards": sh_st.get("total_shards", 0),
                    }
                self._json(payload)

            elif path == "/mempool/audit":
                stats = mp.get_stats()
                top = mp.get(limit=10)
                self._json({
                    "stats": stats,
                    "top_fees": [
                        {"hash": t.tx_hash, "fee": t.fee, "from": t.from_addr, "to": t.to_addr}
                        for t in top
                    ],
                    "min_fee": getattr(mp, "min_fee", 0),
                    "max_size": getattr(mp, "max_size", 0),
                    "require_signatures": getattr(mp, "require_signatures", False),
                })

            elif path == "/burn-stats":
                burn = db.get_burn_stats()
                self._json({
                    **burn,
                    "burn_rate_pct": cfg.burn_rate * 100,
                    "burn_address": cfg.burn_address,
                    "burn_address_balance": bc.get_balance(cfg.burn_address),
                })

            elif path == "/validators":
                from consensus.adapter import ConsensusAdapter
                # Получаем из БД
                validators = db.get_validators()
                self._json({
                    "validators": validators,
                    "count": len(validators),
                    "min_stake": cfg.min_stake,
                })

            elif path in ("/network/peers", "/peers"):
                peers_info = p2p.get_peers_info() if p2p else []
                self._json({
                    "peers": peers_info,
                    "count": len(peers_info),
                    "p2p_port": cfg.p2p_port,
                    "solo_mode": len(peers_info) == 0,
                    "bootstrap_peers": getattr(cfg, "bootstrap_peers", []),
                })

            elif path in ("/p2p/topology", "/p2p/peer-score"):
                if p2p and hasattr(p2p, "get_topology"):
                    self._json(p2p.get_topology())
                else:
                    self._json({
                        "node_id": getattr(cfg, "node_id", ""),
                        "running": False,
                        "peer_count": 0,
                        "topology_healthy": False,
                        "peers": [],
                    })

            elif path == "/network/stats":
                self._json(p2p.get_stats() if p2p else {})

            elif path == "/consensus/stats":
                ca = self.__class__.consensus_adapter
                if ca and hasattr(ca, "get_stats"):
                    try:
                        stats = dict(ca.get_stats())
                    except Exception as e:
                        stats = {
                            "enabled": True,
                            "error": str(e),
                            "lmd_ghost_enabled": getattr(ca, "slashing_engine", None) is not None,
                            "casper_ffg": (
                                getattr(ca, "casper_engine", None) is not None
                                or getattr(ca, "finality", None) is not None
                            ),
                            "slashing_enabled": getattr(ca, "slashing_engine", None) is not None,
                            "pbs_enabled": getattr(ca, "pbs_market", None) is not None,
                            "validator_registry": getattr(ca, "validator_registry", None) is not None,
                        }
                    validators = db.get_validators()
                    stats["validators"] = len(validators)
                    checkpoints = db.get_checkpoints() if hasattr(db, "get_checkpoints") else []
                    stats["checkpoints"] = len(checkpoints) if isinstance(checkpoints, list) else 0
                    self._json(stats)
                else:
                    validators = db.get_validators()
                    checkpoints = db.get_checkpoints() if hasattr(db, "get_checkpoints") else []
                    self._json({
                        "validators": len(validators),
                        "checkpoints": len(checkpoints) if isinstance(checkpoints, list) else 0,
                        "enabled": False,
                        "error": "consensus adapter not loaded",
                    })

            elif path == "/features":
                from features import FeatureFlags
                cfg = self.__class__.config
                flags = FeatureFlags.from_config(cfg) if cfg else FeatureFlags()
                instances = {
                    "evm": self.__class__.evm,
                    "bridge": getattr(self.__class__, "bridge", None) or self.__class__.cross_bridge,
                    "nft": self.__class__.nft,
                    "zk": self.__class__.zk,
                    "sharding": self.__class__.sharding,
                    "oracles": self.__class__.oracles,
                    "wasm": self.__class__.wasm_vm,
                    "plasma": self.__class__.plasma,
                    "lightning": self.__class__.lightning,
                    "pq": self.__class__.pq_manager,
                    "mev": self.__class__.mev_simulator,
                    "ai_agents": self.__class__.ai_manager,
                }
                payload = flags.to_api_dict(instances, cfg)
                payload["api_wave"] = 58
                rp = self.__class__.reorg_predictor
                if rp and hasattr(rp, "get_stats"):
                    payload["reorg_predictor"] = rp.get_stats()
                for name, mod in (
                    ("lightning", self.__class__.lightning),
                    ("plasma", self.__class__.plasma),
                    ("crypto_will", self.__class__.crypto_will),
                    ("wasm", self.__class__.wasm_vm),
                    ("ai_agents", self.__class__.ai_manager),
                    ("nft", self.__class__.nft),
                    ("mev", self.__class__.mev_simulator),
                ):
                    if mod and hasattr(mod, "get_stats"):
                        payload.setdefault("l2_modules", {})[name] = mod.get_stats()
                payload["bridge_dev_confirm"] = (
                    "POST /bridge/confirm-pending"
                    if getattr(cfg, "deployment_mode", "dev") != "prod"
                    else None
                )
                self._json(payload)

            elif path == "/evm/supported-opcodes":
                try:
                    from execution.evm_bytecode_validator import supported_opcodes_summary
                    self._json(supported_opcodes_summary())
                except Exception as e:
                    self._json({"error": str(e)})

            elif path == "/evm/logs" or path.startswith("/evm/logs/"):
                db = self.__class__.db
                if not db or not hasattr(db, "get_evm_logs"):
                    self._error(503, "EVM logs not available"); return
                contract = ""
                if path.startswith("/evm/logs/"):
                    contract = path.split("/evm/logs/", 1)[1].strip("/")
                limit = 100
                if contract:
                    logs = db.get_evm_logs(contract_address=contract, limit=limit)
                else:
                    logs = db.get_evm_logs(limit=limit)
                self._json({"count": len(logs), "logs": logs, "contract": contract or None})

            elif path == "/consensus/attestations/by-block":
                ca = self.__class__.consensus_adapter
                if ca and hasattr(ca, "get_attestations_by_block"):
                    rows = ca.get_attestations_by_block()
                    self._json({"count": len(rows), "blocks": rows})
                else:
                    self._json({"count": 0, "blocks": [], "enabled": False})

            elif path.startswith("/consensus/attestations/block/"):
                block_hash = path.split("/consensus/attestations/block/", 1)[1]
                ca = self.__class__.consensus_adapter
                if ca and hasattr(ca, "get_attestations_for_block"):
                    votes = ca.get_attestations_for_block(block_hash)
                    self._json({
                        "block_hash": block_hash,
                        "count": len(votes),
                        "attestations": votes,
                    })
                else:
                    self._json({"block_hash": block_hash, "count": 0, "attestations": []})

            elif path == "/consensus/attestations":
                ca = self.__class__.consensus_adapter
                if ca and hasattr(ca, "get_attestations"):
                    votes = ca.get_attestations()
                    self._json({
                        "count": len(votes),
                        "attestations": votes,
                        "head": ca.get_canonical_head() if hasattr(ca, "get_canonical_head") else None,
                    })
                else:
                    self._json({"count": 0, "attestations": [], "enabled": False})

            elif path == "/auth/token":
                if getattr(cfg, "deployment_mode", "dev") == "prod":
                    self._error(403, "GET /auth/token disabled in production")
                    return
                addr = qs.get("address", [""])[0]
                if _JWT_AVAILABLE and jwt_auth and addr:
                    token = jwt_auth.generate_token(addr)
                    self._json({"token": token, "address": addr, "expires_in": 86400})
                elif not addr:
                    self._error(400, "address parameter required")
                else:
                    self._error(503, "JWT auth not available (install PyJWT)")

            elif path.startswith("/contract/"):
                addr = path.split("/contract/")[1]
                if evm_adapter:
                    self._json(evm_adapter.get_contract_info(addr))
                else:
                    self._error(503, "EVM not enabled")

            elif path == "/stats":
                self._json(bc.get_stats())

            elif path == "/chain/metrics":
                db = self.__class__.db
                if db and hasattr(db, "get_chain_metrics"):
                    window = int(qs.get("window", ["32"])[0])
                    self._json(db.get_chain_metrics(window=window))
                else:
                    self._json({"error": "chain metrics not available"})

            elif path == "/chain/proposers/stats":
                db = self.__class__.db
                if not db or not hasattr(db, "get_proposer_stats"):
                    self._error(503, "proposer audit not available"); return
                limit = min(max(int(qs.get("limit", ["20"])[0]), 1), 100)
                rows = db.get_proposer_stats(limit=limit)
                self._json({
                    "count": len(rows),
                    "proposers": rows,
                    "audit_total": db.count_proposer_audit(),
                })

            elif path == "/chain/proposers/history":
                db = self.__class__.db
                if not db or not hasattr(db, "get_proposer_audit_log"):
                    self._error(503, "proposer audit not available"); return
                limit = min(max(int(qs.get("limit", ["50"])[0]), 1), 200)
                offset = max(int(qs.get("offset", ["0"])[0]), 0)
                proposer = qs.get("proposer", [""])[0]
                total = db.count_proposer_audit(proposer=proposer)
                rows = db.get_proposer_audit_log(
                    limit=limit, offset=offset, proposer=proposer
                )
                self._json({
                    "limit": limit,
                    "offset": offset,
                    "total": total,
                    "proposer": proposer or None,
                    "entries": rows,
                })

            elif path.startswith("/chain/proposer/"):
                addr = path[len("/chain/proposer/"):].split("/")[0]
                if not addr:
                    self._error(400, "proposer address required"); return
                db = self.__class__.db
                if not db or not hasattr(db, "get_proposer_detail"):
                    self._error(503, "proposer audit not available"); return
                recent = min(max(int(qs.get("recent", ["10"])[0]), 1), 50)
                detail = db.get_proposer_detail(addr, recent_limit=recent)
                if detail["blocks_proposed"] == 0:
                    self._error(404, "proposer not found in audit log"); return
                self._json(detail)

            elif path == "/chain/state-root/status":
                p2p = self.__class__.p2p
                db = self.__class__.db
                local_root = bc.get_state_root() if hasattr(bc, "get_state_root") else ""
                height = bc.get_height() if hasattr(bc, "get_height") else 0
                policy = (
                    bc.get_state_root_policy()
                    if hasattr(bc, "get_state_root_policy")
                    else {}
                )
                peers = []
                if p2p and hasattr(p2p, "request_peer_state_roots_sync"):
                    try:
                        for entry in p2p.request_peer_state_roots_sync(timeout=8):
                            pr = entry.get("state_root", "")
                            peers.append({
                                "peer_id": entry.get("peer_id", ""),
                                "height": entry.get("height", 0),
                                "state_root": pr,
                                "match": (pr == local_root) if pr else None,
                            })
                    except Exception:
                        pass
                mismatches = []
                if db and hasattr(db, "get_state_root_mismatches"):
                    mismatches = db.get_state_root_mismatches(limit=10)
                self._json({
                    "height": height,
                    "state_root": local_root,
                    "state_consistent": (
                        getattr(p2p, "_state_consistent", True) if p2p else True
                    ),
                    "peers": peers,
                    "recent_mismatches": mismatches,
                    **policy,
                })

            elif path in ("/chain/consistency/harness", "/testnet/state-consistency"):
                db = self.__class__.db
                self._json(_build_state_consistency_harness(p2p, bc, cfg, db))

            elif path == "/testnet/validators":
                db = self.__class__.db
                self._json(_build_testnet_validators_status(db, cfg, bc))

            elif path == "/testnet/multi-node-proof":
                db = self.__class__.db
                ca = self.__class__.consensus_adapter
                self._json(_build_testnet_multi_node_proof(p2p, bc, cfg, db, ca))

            elif path == "/testnet/bridge-relayer-proof":
                db = self.__class__.db
                br = getattr(self.__class__, "bridge", None)
                self._json(_build_testnet_bridge_relayer_proof(cfg, db, br))

            elif path == "/tx/propagation/recent":
                db = self.__class__.db
                if not db or not hasattr(db, "get_recent_tx_propagation"):
                    self._error(503, "tx propagation trace not available"); return
                limit = min(max(int(qs.get("limit", ["20"])[0]), 1), 50)
                rows = db.get_recent_tx_propagation(limit=limit)
                self._json({"count": len(rows), "traces": rows})

            elif path.startswith("/tx/trace/"):
                tx_hash = path[len("/tx/trace/"):].split("/")[0]
                if not tx_hash:
                    self._error(400, "tx hash required"); return
                db = self.__class__.db
                if not db or not hasattr(db, "get_tx_propagation_trace"):
                    self._error(503, "tx propagation trace not available"); return
                trace = db.get_tx_propagation_trace(tx_hash)
                if not trace.get("events") and not trace.get("receipt"):
                    mp = self.__class__.mempool
                    if mp and hasattr(mp, "has_transaction") and mp.has_transaction(tx_hash):
                        trace["status"] = "mempool_local_only"
                    else:
                        self._error(404, "tx trace not found"); return
                self._json(trace)

            elif path.startswith("/tx/receipt/") or path.startswith("/receipts/tx/"):
                tx_hash = path.split("/")[-1]
                db = self.__class__.db
                if not db or not hasattr(db, "get_tx_receipt"):
                    self._error(503, "receipts not available"); return
                rcpt = db.get_tx_receipt(tx_hash)
                if rcpt:
                    self._json(rcpt)
                else:
                    self._error(404, "receipt not found")

            elif path.startswith("/receipts/block/"):
                try:
                    height = int(path.split("/receipts/block/")[-1])
                except ValueError:
                    self._error(400, "invalid block height"); return
                db = self.__class__.db
                if not db or not hasattr(db, "get_receipts_by_block"):
                    self._error(503, "receipts not available"); return
                rows = db.get_receipts_by_block(height)
                self._json({"block_height": height, "count": len(rows), "receipts": rows})

            # ── NFT ──────────────────────────────────────────────────────────
            elif path == "/nft":
                nft = self.__class__.nft
                if not nft:
                    self._error(503, "NFT module not enabled")
                    return
                self._json({"tokens": nft.get_all(), "stats": nft.get_stats()})

            elif path == "/nft/sale":
                nft = self.__class__.nft
                if not nft:
                    self._error(503, "NFT module not enabled"); return
                self._json(nft.get_on_sale())

            elif path.startswith("/nft/token/"):
                token_id = path.split("/nft/token/")[1]
                nft = self.__class__.nft
                if not nft:
                    self._error(503, "NFT module not enabled"); return
                t = nft.get_token(token_id)
                if t:
                    self._json(t)
                else:
                    self._error(404, "NFT not found")

            elif path.startswith("/nft/owner/"):
                owner = path.split("/nft/owner/")[1]
                nft = self.__class__.nft
                if not nft:
                    self._error(503, "NFT module not enabled"); return
                self._json(nft.get_by_owner(owner))

            # ── ZK Proofs ─────────────────────────────────────────────────────
            elif path == "/zk/info":
                zk = self.__class__.zk
                if not zk:
                    self._error(503, "ZK module not enabled"); return
                self._json(zk.get_system_info())

            # ── Sharding ──────────────────────────────────────────────────────
            elif path in ("/sharding/stats", "/sharding"):
                sharding = self.__class__.sharding
                if sharding:
                    st = sharding.get_stats()
                    st["enabled"] = True
                    self._json(st)
                else:
                    self._json({"error": "sharding not enabled", "enabled": False})

            elif path == "/sharding/pending":
                sharding = self.__class__.sharding
                if not sharding:
                    self._json({"enabled": False, "pending": []})
                    return
                pending = []
                for tx_id in getattr(sharding, "pending_cross_txs", []):
                    tx = sharding.cross_shard_txs.get(tx_id)
                    if tx:
                        row = {
                            "tx_id": tx.tx_id,
                            "from_shard": tx.from_shard,
                            "to_shard": tx.to_shard,
                            "from_addr": tx.from_addr,
                            "to_addr": tx.to_addr,
                            "amount": tx.amount,
                            "status": tx.status,
                        }
                        if hasattr(sharding, "cross_shard_quorum_status"):
                            row["quorum"] = sharding.cross_shard_quorum_status(tx.tx_id)
                        pending.append(row)
                self._json({
                    "enabled": True,
                    "count": len(pending),
                    "pending": pending,
                })

            elif path.startswith("/sharding/cross-shard/quorum/"):
                sharding = self.__class__.sharding
                tx_id = path.rsplit("/", 1)[-1]
                if not sharding or not tx_id:
                    self._error(400, "tx_id required")
                    return
                if not hasattr(sharding, "cross_shard_quorum_status"):
                    self._error(503, "cross-shard quorum not available")
                    return
                status = sharding.cross_shard_quorum_status(tx_id)
                if not status:
                    self._error(404, "quorum session not found")
                    return
                self._json({"enabled": True, "quorum": status})

            elif path == "/sharding/reshard/status":
                sharding = self.__class__.sharding
                if not sharding or not getattr(sharding, "coordinator", None):
                    self._json({"enabled": False, "coordinator": None})
                    return
                coord = sharding.coordinator
                self._json({
                    "enabled": True,
                    "coordinator": coord.status(),
                    "migrations": coord.migrations_view(),
                })

            # ── Oracles ───────────────────────────────────────────────────────
            elif path in ("/oracles/prices", "/oracles"):
                oracles = self.__class__.oracles
                registry = self.__class__.oracle_registry
                if registry and oracles and hasattr(registry, "sync_from_manager"):
                    try:
                        registry.sync_from_manager(oracles)
                    except Exception:
                        pass
                if registry and hasattr(registry, "list_feeds"):
                    feeds = registry.list_feeds(limit=20)
                    if feeds:
                        self._json({
                            "prices": [
                                {
                                    "symbol": f["symbol"],
                                    "price": f["value"],
                                    "source": f["source"],
                                    "submitted_at": f.get("submitted_at"),
                                    "feed_id": f.get("feed_id"),
                                }
                                for f in feeds
                            ],
                            "count": len(feeds),
                            "registry": True,
                        })
                        return
                if not oracles:
                    self._json({"error": "oracles not enabled", "prices": []})
                    return
                try:
                    result = []
                    for sym in ["bitcoin", "ethereum", "solana"]:
                        p = oracles.get_crypto_price(sym)
                        if p:
                            result.append({
                                "symbol": sym, "price": p.price,
                                "change_24h": p.change_24h, "volume": p.volume,
                                "source": getattr(p, "source", "coingecko"),
                            })
                    abs_p = oracles.get_abs_reference_price()
                    result.append({
                        "symbol": "absolute",
                        "price": abs_p.price,
                        "change_24h": abs_p.change_24h,
                        "source": abs_p.source,
                    })
                    self._json({"prices": result, "count": len(result)})
                except Exception as e:
                    self._json({"prices": [], "error": str(e)})

            elif path == "/oracles/feeds" or path.startswith("/oracles/feeds/"):
                registry = self.__class__.oracle_registry
                if not registry:
                    self._json({"feeds": [], "error": "oracle registry not enabled"})
                    return
                symbol = ""
                if path.startswith("/oracles/feeds/"):
                    part = path.split("/oracles/feeds/", 1)[1].strip("/")
                    if part and part != "submit":
                        symbol = part
                feeds = registry.list_feeds(symbol=symbol, limit=100)
                self._json({"count": len(feeds), "symbol": symbol or None, "feeds": feeds})
                return

            elif path in ("/oracles/l1-queue", "/bridge/l1-queue"):
                self._json(_build_l1_queue_payload(cfg))
                return

            elif path == "/bridge/relayer/status":
                self._json(_build_bridge_relayer_status(cfg, db))
                return

            # ── Short URL aliases ─────────────────────────────────────────────
            elif path.startswith("/block/"):
                param = path.split("/block/")[1]
                try:
                    blk = bc.get_block(int(param))
                    if blk:
                        ca = self.__class__.consensus_adapter
                        if ca and hasattr(ca, "get_attestations_for_block"):
                            votes = ca.get_attestations_for_block(blk.get("hash", ""))
                            blk["attestation_count"] = len(votes)
                            blk["attestations"] = votes
                        self._json(blk)
                    else:
                        self._error(404, "Block not found")
                except Exception:
                    self._error(400, "Invalid block number")

            elif path.startswith("/tx/"):
                tx_hash = path.split("/tx/")[1]
                tx = bc.get_transaction(tx_hash)
                if tx:
                    self._json(tx)
                elif mp and hasattr(mp, "has_transaction") and mp.has_transaction(tx_hash):
                    pending = mp.transactions.get(tx_hash) if hasattr(mp, "transactions") else None
                    self._json({
                        "hash": tx_hash,
                        "status": "pending",
                        "mempool": True,
                        "from_addr": getattr(pending, "from_addr", ""),
                        "to_addr": getattr(pending, "to_addr", ""),
                        "data": getattr(pending, "data", ""),
                    })
                else:
                    self._error(404, "Transaction not found")

            # ── MiniVM contracts ──────────────────────────────────────────────
            elif path == "/minivm/contracts":
                cm = self.__class__.contract_manager
                if cm:
                    self._json({"contracts": cm.get_stats()})
                else:
                    self._json({"contracts": {}, "enabled": False})

            elif path.startswith("/minivm/storage/"):
                cm = self.__class__.contract_manager
                parts = path.split("/")
                if cm and len(parts) >= 5:
                    addr, key = parts[3], int(parts[4]) if parts[4].isdigit() else 0
                    self._json({"address": addr, "key": key,
                                "value": cm.get_storage(addr, key)})
                else:
                    self._error(400, "Usage: /minivm/storage/{address}/{key}")

            # ── Post-Quantum crypto ───────────────────────────────────────────
            elif path == "/pq/status":
                pqm = self.__class__.pq_manager
                if pqm:
                    try:
                        stats = pqm.get_stats() if hasattr(pqm, "get_stats") else {"enabled": True}
                        self._json({"post_quantum": "enabled", "stats": stats})
                    except Exception as e:
                        self._json({"post_quantum": "enabled", "error": str(e)})
                else:
                    self._json({"post_quantum": "disabled"})

            # ── Smart Accounts ────────────────────────────────────────────────
            elif path == "/smart-account/list":
                sa = self.__class__.smart_accounts
                if sa:
                    try:
                        accounts = sa.list_accounts() if hasattr(sa, "list_accounts") else []
                        self._json({"smart_accounts": accounts,
                                    "count": len(accounts) if isinstance(accounts, list) else 0})
                    except Exception as e:
                        self._json({"smart_accounts": [], "error": str(e)})
                else:
                    self._json({"smart_accounts": [], "enabled": False})

            # ── Multisig wallets ──────────────────────────────────────────────
            elif path == "/multisig/list":
                ms = self.__class__.multisig
                if ms:
                    try:
                        wallets = ms.list_wallets() if hasattr(ms, "list_wallets") else []
                        self._json({"multisig_wallets": wallets})
                    except Exception as e:
                        self._json({"multisig_wallets": [], "error": str(e)})
                else:
                    self._json({"multisig_wallets": [], "enabled": False})

            # ── Chain storage (JSON file backup) ──────────────────────────────
            elif path.startswith("/chain/block/"):
                parts = path.split("/")
                try:
                    n = int(parts[-1])
                    blk = bc.get_block(n) if hasattr(bc, "get_block") else None
                    if blk:
                        self._json(blk)
                    else:
                        self._error(404, "Block not found")
                except Exception:
                    self._error(400, "Invalid block number")

            # ── AI Validator ──────────────────────────────────────────────────
            elif path == "/ai/validators":
                ai = self.__class__.ai_validator
                if ai:
                    self._json({"stats": ai.get_stats(),
                                "validators": {addr: {"performance": v.performance,
                                                       "reliability": v.reliability,
                                                       "stake": v.stake,
                                                       "rewards": v.rewards}
                                               for addr, v in ai.validators.items()}})
                else:
                    self._json({"enabled": False})

            elif path == "/ai/proposer":
                ai = self.__class__.ai_validator
                if ai:
                    proposer = ai.select_proposer()
                    self._json({"proposer": proposer,
                                "stats": ai.get_stats()})
                else:
                    self._json({"enabled": False})

            elif path == "/ai/mev-scan":
                ai = self.__class__.ai_validator
                mp = self.__class__.mempool
                if ai and mp:
                    pending = mp.get(limit=50)
                    mev_data = ai.detect_mev_opportunity(pending)
                    self._json(mev_data)
                else:
                    self._json({"enabled": False})

            # ── Reorg Predictor ───────────────────────────────────────────────
            elif path == "/consensus/casper":
                bc_obj = self.__class__.blockchain
                cons = getattr(bc_obj, "_consensus", None) or getattr(bc_obj, "consensus", None)
                if cons and hasattr(cons, "get_casper_status"):
                    self._json(cons.get_casper_status())
                else:
                    try:
                        from consensus.finality_casper import CasperFinality
                        self._json({"enabled": True, "note": "CasperFinality available"})
                    except Exception:
                        self._json({"enabled": False})

            elif path == "/consensus/beacon":
                bc_obj = self.__class__.blockchain
                cons = getattr(bc_obj, "_consensus", None) or getattr(bc_obj, "consensus", None)
                if cons and hasattr(cons, "get_beacon_status"):
                    self._json(cons.get_beacon_status())
                else:
                    try:
                        from consensus.engine_beacon import ConsensusEngineBeacon
                        self._json({"enabled": True, "note": "BeaconEngine available"})
                    except Exception:
                        self._json({"enabled": False})

            # ── Immutable State (satoshi balances) ────────────────────────────
            elif path == "/state/stats":
                ist = self.__class__.immutable_state
                if ist:
                    self._json(ist.get_stats())
                else:
                    self._json({"enabled": False})

            elif path.startswith("/state/balance/"):
                ist = self.__class__.immutable_state
                addr = path.split("/state/balance/")[-1]
                if ist:
                    sat = ist.get_balance_satoshi(addr)
                    self._json({"address": addr,
                                "balance_satoshi": sat,
                                "balance_abs": sat / 1_000_000})
                else:
                    # fallback to blockchain balance
                    bal = bc.get_balance(addr) if hasattr(bc, "get_balance") else 0
                    self._json({"address": addr, "balance": bal})

            elif path == "/state/all":
                ist = self.__class__.immutable_state
                if ist:
                    self._json(ist.to_dict())
                else:
                    self._json({"enabled": False})

            # ── Extended oracle endpoints (from extended_api_server) ──────────
            elif path == "/oracles/news":
                oracles = self.__class__.oracles
                if oracles and hasattr(oracles, "get_news"):
                    try:
                        news = oracles.get_news()
                        self._json({"news": news if isinstance(news, list) else []})
                    except Exception as e:
                        self._json({"news": [], "error": str(e)})
                else:
                    self._json({"news": [], "enabled": False})

            elif path == "/oracles/stats":
                oracles = self.__class__.oracles
                if oracles and hasattr(oracles, "get_stats"):
                    try:
                        self._json(oracles.get_stats())
                    except Exception as e:
                        self._json({"error": str(e)})
                else:
                    self._json({"enabled": False})

            # ── Extended sharding (from extended_api_server) ──────────────────
            elif path == "/sharding/shards":
                sharding = self.__class__.sharding
                if sharding and hasattr(sharding, "shards"):
                    try:
                        shards_data = {}
                        for sid, shard in sharding.shards.items():
                            shards_data[str(sid)] = shard.get_stats() if hasattr(shard, "get_stats") else str(shard)
                        self._json({"shards": shards_data, "count": len(shards_data)})
                    except Exception as e:
                        self._json({"error": str(e)})
                else:
                    self._json({"enabled": False})

            elif path.startswith("/sharding/shard/"):
                sharding = self.__class__.sharding
                try:
                    shard_id = int(path.split("/")[-1])
                    if sharding and hasattr(sharding, "shards") and shard_id in sharding.shards:
                        shard = sharding.shards[shard_id]
                        self._json(shard.get_stats() if hasattr(shard, "get_stats") else {"id": shard_id})
                    else:
                        self._error(404, f"Shard {shard_id} not found")
                except Exception as e:
                    self._error(400, str(e))

            # ── NFT listings/auctions (from extended_api_server) ─────────────
            elif path == "/nft/listings":
                nft = self.__class__.nft
                if nft and hasattr(nft, "get_listings"):
                    try:
                        self._json({"listings": nft.get_listings()})
                    except Exception as e:
                        self._json({"listings": [], "error": str(e)})
                else:
                    # Basic: return all tokens for sale
                    if nft and hasattr(nft, "tokens"):
                        tokens = [t.__dict__ if hasattr(t, "__dict__") else t
                                  for t in list(nft.tokens.values())[:50]]
                        self._json({"listings": tokens, "count": len(tokens)})
                    else:
                        self._json({"listings": [], "enabled": False})

            elif path == "/nft/auctions":
                nft = self.__class__.nft
                if nft and hasattr(nft, "auctions"):
                    try:
                        auctions = {k: (v.__dict__ if hasattr(v, "__dict__") else v)
                                    for k, v in nft.auctions.items()}
                        self._json({"auctions": auctions, "count": len(auctions)})
                    except Exception as e:
                        self._json({"auctions": {}, "error": str(e)})
                else:
                    self._json({"auctions": {}, "enabled": False})

            # ── Ethereum-style keygen (keccak256 address) ─────────────────────
            elif path == "/crypto/eth-address":
                try:
                    from crypto.crypto import Crypto
                    priv, pub, addr = Crypto.generate_keypair()
                    self._json({"address": addr, "public_key": pub, "private_key": priv,
                                "type": "secp256k1/keccak256"})
                except Exception as e:
                    self._error(500, str(e))

            elif path.startswith("/consensus/reorg-risk"):
                rp = self.__class__.reorg_predictor
                if rp:
                    confirmations = int(qs.get("confirmations", ["6"])[0])
                    risk = rp.calculate_risk(confirmations)
                    confidence = rp.get_confidence(confirmations)
                    self._json({
                        "confirmations": confirmations,
                        "risk": risk,
                        "risk_percent": f"{risk*100:.1f}%",
                        "confidence": confidence,
                    })
                else:
                    self._json({"enabled": False})

            # ── MEV Analyzer ─────────────────────────────────────────────────
            elif path == "/mev/stats":
                mev = self.__class__.mev_simulator
                if mev:
                    self._json(mev.get_statistics())
                else:
                    self._json({"enabled": False})

            elif path == "/mev/history":
                mev = self.__class__.mev_simulator
                limit = int(qs.get("limit", ["50"])[0])
                if mev and hasattr(mev, "get_history"):
                    hist = mev.get_history(limit)
                    self._json({"count": len(hist), "history": hist})
                else:
                    self._json({"count": 0, "history": [], "enabled": False})

            # ── Merkle proofs / Light client SPV ─────────────────────────────
            elif path.startswith("/merkle/root/"):
                block_n = path.split("/")[-1]
                try:
                    from crypto.merkle import merkle_root
                    blk = bc.get_block(int(block_n)) if hasattr(bc, "get_block") else None
                    if blk:
                        tx_hashes = [t.get("hash", t) for t in (blk.get("transactions") or [])]
                        root = blk.get("tx_root") or (merkle_root(tx_hashes) if tx_hashes else merkle_root(["empty"]))
                        self._json({"block": int(block_n), "merkle_root": root,
                                    "tx_count": len(tx_hashes)})
                    else:
                        self._error(404, "Block not found")
                except Exception as e:
                    self._error(400, str(e))

            elif path.startswith("/merkle/proof/"):
                parts = path.strip("/").split("/")
                if len(parts) < 4:
                    self._error(400, "Use /merkle/proof/{block}/{tx_index}")
                    return
                try:
                    from crypto.merkle import merkle_root, generate_proof
                    block_n = int(parts[2])
                    tx_index = int(parts[3])
                    blk = bc.get_block(block_n) if bc and hasattr(bc, "get_block") else None
                    if not blk:
                        self._error(404, "Block not found")
                        return
                    txs = blk.get("transactions") or []
                    tx_hashes = [t.get("hash", str(t)) for t in txs]
                    if tx_index < 0 or tx_index >= len(tx_hashes):
                        self._error(404, "Tx index out of range")
                        return
                    root = blk.get("tx_root") or merkle_root(tx_hashes)
                    proof = generate_proof(tx_hashes, tx_index)
                    self._json({
                        "block": block_n,
                        "tx_index": tx_index,
                        "tx_hash": tx_hashes[tx_index],
                        "merkle_root": root,
                        "proof": proof,
                    })
                except Exception as e:
                    self._error(400, str(e))

            elif path == "/light/stats":
                lc = self.__class__.light_client
                if lc and hasattr(lc, "get_stats"):
                    self._json(lc.get_stats())
                else:
                    self._json({"enabled": False})

            elif path == "/light/headers":
                lc = self.__class__.light_client
                from_n = int(qs.get("from", ["0"])[0])
                limit = int(qs.get("limit", ["50"])[0])
                if lc and hasattr(lc, "get_headers"):
                    self._json({"headers": lc.get_headers(from_n, limit)})
                else:
                    self._json({"headers": [], "enabled": False})

            elif path.startswith("/light/header/"):
                block_n = path.split("/light/header/")[-1]
                lc = self.__class__.light_client
                if lc and hasattr(lc, "get_header"):
                    hdr = lc.get_header(int(block_n))
                    if hdr:
                        self._json(hdr.to_dict())
                    else:
                        self._error(404, "Header not found")
                else:
                    self._error(503, "Light client not enabled")

            elif path == "/light/sync":
                lc = self.__class__.light_client
                if lc and hasattr(lc, "sync_from_blockchain") and bc:
                    added = lc.sync_from_blockchain(bc)
                    self._json({"synced": added, "stats": lc.get_stats()})
                else:
                    self._error(503, "Light client not enabled")

            elif path == "/pools/locks":
                pl = self.__class__.pool_locks
                if pl and hasattr(pl, "get_status"):
                    self._json(pl.get_status())
                else:
                    self._json({"enabled": False})

            elif path == "/pools/dao/status":
                pl = self.__class__.pool_locks
                if pl:
                    st = pl.get_status()
                    dao = [p for p in st.get("pools", []) if p["id"] in ("ecosystem", "treasury")]
                    self._json({"pools": dao, "threshold": st.get("dao_threshold", 0.51)})
                else:
                    self._json({"enabled": False})

            # ── MiniVM examples ───────────────────────────────────────────────
            elif path == "/minivm/examples":
                try:
                    from compiler.examples import counter_contract, loop_contract, fibonacci_contract
                    self._json({
                        "examples": {
                            "counter":   {"bytecode": counter_contract(),   "description": "Simple counter with increment"},
                            "loop":      {"bytecode": loop_contract(),      "description": "Loop incrementing counter 10 times"},
                            "fibonacci": {"bytecode": fibonacci_contract(), "description": "Fibonacci sequence"},
                        }
                    })
                except Exception as e:
                    self._error(500, str(e))

            # ── Extended sharding endpoints ───────────────────────────────────
            elif path == "/sharding/route":
                sharding = self.__class__.sharding
                if sharding:
                    addr = qs.get("address", [""])[0]
                    try:
                        shard_id = sharding.get_shard_for_address(addr) if hasattr(sharding, "get_shard_for_address") else 0
                        self._json({"address": addr, "shard_id": shard_id})
                    except Exception as e:
                        self._error(500, str(e))
                else:
                    self._json({"enabled": False})

            elif path == "/sharding/all":
                sharding = self.__class__.sharding
                if sharding:
                    try:
                        state = sharding.get_all_shards_state() if hasattr(sharding, "get_all_shards_state") else {}
                        self._json({"shards": state})
                    except Exception as e:
                        self._error(500, str(e))
                else:
                    self._json({"enabled": False})

            # ── Extended oracle endpoints ─────────────────────────────────────
            elif path == "/oracles/all":
                oracles = self.__class__.oracles
                if not oracles:
                    self._json({"prices": [], "weather": None, "enabled": False}); return
                result = {}
                try:
                    prices = []
                    for sym in ["bitcoin", "ethereum", "absolute"]:
                        p = oracles.get_crypto_price(sym) if hasattr(oracles, "get_crypto_price") else None
                        if p:
                            prices.append({"symbol": sym, "price": p.price,
                                           "change_24h": p.change_24h})
                    result["prices"] = prices
                except Exception:
                    result["prices"] = []
                try:
                    weather = oracles.get_weather("London") if hasattr(oracles, "get_weather") else None
                    if weather:
                        result["weather"] = {"city": "London",
                                             "temp": getattr(weather, "temperature", None),
                                             "condition": getattr(weather, "condition", None)}
                except Exception:
                    result["weather"] = None
                self._json(result)

            elif path.startswith("/oracles/weather"):
                oracles = self.__class__.oracles
                city = qs.get("city", ["London"])[0]
                if oracles and hasattr(oracles, "get_weather"):
                    try:
                        w = oracles.get_weather(city)
                        if w:
                            self._json({
                                "city": city,
                                "temperature": getattr(w, "temperature", None),
                                "condition": getattr(w, "condition", None),
                                "humidity": getattr(w, "humidity", None),
                                "source": getattr(w, "source", "api"),
                            })
                        else:
                            self._json({
                                "city": city,
                                "error": "no data — set OPENWEATHER_API_KEY or WEATHERAPI_KEY in .env",
                            })
                    except Exception as e:
                        self._json({"city": city, "error": str(e)})
                else:
                    self._json({"enabled": False})

            # ── Wallet balance ────────────────────────────────────────────────
            elif path.startswith("/wallet/balance"):
                addr = qs.get("address", [""])[0]
                if not addr and "/" in path[16:]:
                    addr = path.split("/wallet/balance/")[-1]
                if addr and bc:
                    balance = bc.get_balance(addr) if hasattr(bc, "get_balance") else 0
                    self._json({"address": addr, "balance": balance,
                                "symbol": cfg.coin_symbol if cfg else "ABS"})
                else:
                    self._error(400, "address parameter required")

            # ── NFT Offers & Auctions (extended) ─────────────────────────────
            elif path == "/nft/offers":
                nft = self.__class__.nft
                token_id = qs.get("token_id", [""])[0] or None
                offers = nft.get_offers(token_id) if nft and hasattr(nft, "get_offers") else []
                self._json({"offers": offers})

            elif path == "/nft/sales":
                nft = self.__class__.nft
                token_id = qs.get("token_id", [""])[0] or None
                limit = int(qs.get("limit", ["50"])[0])
                sales = nft.get_sales_history(token_id, limit) if nft and hasattr(nft, "get_sales_history") else []
                self._json({"sales": sales})

            elif path == "/nft/marketplace":
                nft = self.__class__.nft
                stats = nft.get_stats() if nft else {}
                auctions = nft.get_auctions() if nft and hasattr(nft, "get_auctions") else []
                offers = list(getattr(nft, "offers", {}).values())[:20] if nft else []
                self._json({"stats": stats, "active_auctions": len([a for a in auctions if a.get("status")=="active"]),
                            "active_offers": len(offers), "total_auctions": len(auctions)})

            elif path == "/nft/stats":
                nft = self.__class__.nft
                if not nft:
                    self._json({"enabled": False}); return
                self._json(nft.get_stats())

            # ── Lightning Network ─────────────────────────────────────────────
            elif path == "/l2/status":
                self._json(_build_l2_status(self.__class__))

            elif path == "/lightning/stats":
                ln = self.__class__.lightning
                self._json(ln.get_stats() if ln else {"enabled": False})

            elif path == "/lightning/channels":
                ln = self.__class__.lightning
                self._json({"channels": ln.get_all_channels() if ln else []})

            elif path == "/lightning/payments":
                ln = self.__class__.lightning
                limit = int(qs.get("limit", ["50"])[0])
                self._json({"payments": ln.get_payment_history(limit) if ln else []})

            # ── Crypto Will ───────────────────────────────────────────────────
            elif path == "/will/stats":
                cw = self.__class__.crypto_will
                self._json(cw.get_stats() if cw else {"enabled": False})

            elif path.startswith("/will/list"):
                cw = self.__class__.crypto_will
                addr = qs.get("address", [""])[0]
                if cw and addr:
                    self._json({"wills": cw.get_user_wills(addr)})
                elif cw:
                    self._json({"wills": list(cw.wills.keys())[:50]})
                else:
                    self._json({"enabled": False})

            # ── Plasma Chain ──────────────────────────────────────────────────
            elif path == "/plasma/stats":
                pl = self.__class__.plasma
                self._json(pl.get_stats() if pl else {"enabled": False})

            elif path == "/plasma/blocks":
                pl = self.__class__.plasma
                limit = int(qs.get("limit", ["20"])[0])
                self._json({"blocks": pl.get_blocks(limit) if pl else []})

            elif path == "/plasma/deposits":
                pl = self.__class__.plasma
                limit = int(qs.get("limit", ["50"])[0])
                if pl and hasattr(pl, "get_deposits"):
                    self._json({"count": len(pl.get_deposits(limit)), "deposits": pl.get_deposits(limit)})
                else:
                    self._json({"deposits": [], "enabled": False})

            # ── WASM VM ───────────────────────────────────────────────────────
            elif path == "/wasm/stats":
                vm = self.__class__.wasm_vm
                self._json(vm.get_stats() if vm else {"enabled": False})

            elif path == "/wasm/contracts":
                vm = self.__class__.wasm_vm
                self._json({"contracts": vm.get_all_contracts() if vm else []})

            elif path.startswith("/wasm/contract/"):
                addr = path[len("/wasm/contract/"):]
                vm = self.__class__.wasm_vm
                c = vm.get_contract(addr) if vm else None
                self._json(c or {"error": "not found"})

            elif path.startswith("/wasm/storage/"):
                addr = path[len("/wasm/storage/"):]
                vm = self.__class__.wasm_vm
                self._json(vm.get_storage(addr) if vm else {})

            elif path == "/wasm/events":
                vm = self.__class__.wasm_vm
                limit = int(qs.get("limit", ["50"])[0])
                self._json({"events": vm.get_events(limit) if vm else []})

            # ── AI Agent Manager ──────────────────────────────────────────────
            elif path == "/ai-agent/stats":
                am = self.__class__.ai_manager
                self._json(am.get_stats() if am else {"enabled": False})

            elif path == "/ai-agent/list":
                am = self.__class__.ai_manager
                owner = qs.get("owner", [""])[0]
                if am and owner:
                    self._json({"agents": am.get_user_agents(owner)})
                else:
                    self._json({"agents": am.get_all_agents() if am else []})

            # ── Cross-Chain Bridge ────────────────────────────────────────────
            elif path == "/bridge":
                self._json(_build_bridge_overview(
                    self.__class__.bridge,
                    self.__class__.cross_bridge,
                    cfg,
                    db,
                ))

            elif path == "/wallet/status":
                w = self.__class__.wallet
                addr = w.address if w else None
                balance = bc.get_balance(addr) if addr else 0.0
                self._json({
                    "signing_enabled": w is not None,
                    "address": addr,
                    "signing_address": getattr(cfg, "signing_address", "") or addr,
                    "founder_address": getattr(cfg, "founder_address", ""),
                    "miner_address": cfg.miner_address,
                    "balance": balance,
                    "balance_formatted": f"{balance:.6f} {cfg.coin_symbol}",
                    "hint": (
                        "Set WALLET_PRIVATE_KEY in .env — this wallet mines blocks and signs txs. "
                        "Rewards accrue here after restart if operational wallet is the proposer."
                    ),
                })

            elif path == "/docs":
                routes_html = "".join(
                    f"<li><code>{r['method']}</code> <a href='{r['path']}'>{r['path']}</a> — {r['summary']}</li>"
                    for r in _PUBLIC_API_ROUTES
                )
                body = (
                    "<!DOCTYPE html><html><head><meta charset='utf-8'>"
                    "<title>Absolute Blockchain API</title></head><body>"
                    "<h1>Absolute Blockchain REST API</h1>"
                    f"<p>OpenAPI: <a href='/openapi.json'>/openapi.json</a> | "
                    f"Explorer: <a href='/'>/</a></p><ul>{routes_html}</ul></body></html>"
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", len(body))
                self.send_header("Access-Control-Allow-Origin", self._cors_origin(self.headers.get("Origin", "")))
                self.end_headers()
                self.wfile.write(body)
                return

            elif path == "/openapi.json":
                self._json(_build_openapi_spec(cfg))

            elif path == "/bridge2/stats":
                rb = getattr(self.__class__, "bridge", None)
                cb = self.__class__.cross_bridge
                overview = _build_bridge_overview(rb, cb, cfg, db)
                stats = cb.get_bridge_stats() if cb else {}
                locks = overview.get("locks") or {}
                stats.update({
                    "enabled": overview.get("enabled", False),
                    "mode": overview.get("mode", "unknown"),
                    "tier": overview.get("tier", "dev-only"),
                    "auto_confirm_sec": overview.get("auto_confirm_sec", 0),
                    "supported_chains": overview.get("supported_chains", stats.get("supported_chains", [])),
                    "total_transactions": locks.get("total", stats.get("total_transactions", 0)),
                    "confirmed": locks.get("confirmed", stats.get("confirmed", 0)),
                    "pending": locks.get("pending", stats.get("pending", 0)),
                    "rust_version": overview.get("rust_version"),
                    "l1_rpc": overview.get("l1_rpc"),
                })
                self._json(stats)

            elif path == "/bridge2/fee":
                cb = self.__class__.cross_bridge
                chain = qs.get("chain", ["ethereum"])[0]
                amount = float(qs.get("amount", ["100"])[0])
                fee = cb.estimate_fee(chain, amount) if cb else 0
                self._json({"chain": chain, "amount": amount, "fee": fee})

            # ── Standalone Consensus Engine ───────────────────────────────────
            elif path == "/consensus/engine":
                ce = self.__class__.consensus_engine_standalone
                self._json(ce.get_stats() if ce else {"enabled": False})

            # ── Finality Engine ───────────────────────────────────────────────
            elif path == "/finality/stats":
                fe = self.__class__.finality_engine
                self._json(fe.get_stats() if fe else {"enabled": False})

            elif path.startswith("/finality/block/"):
                blk_num = int(path[len("/finality/block/"):])
                fe = self.__class__.finality_engine
                self._json(fe.get_finality_status(blk_num) if fe else {"enabled": False})

            # ── Sync Engine ───────────────────────────────────────────────────
            elif path == "/testnet/mesh":
                self._json(_build_testnet_mesh(p2p, bc, cfg))

            elif path == "/testnet/fork-status":
                db = self.__class__.db
                self._json(_build_testnet_fork_status(p2p, bc, cfg, db))

            elif path == "/testnet/fork-exercise":
                db = self.__class__.db
                self._json(_build_testnet_fork_exercise(p2p, bc, cfg, db, run_reconcile=False))

            elif path == "/slashing/events":
                db = self.__class__.db
                limit = min(200, max(1, int(qs.get("limit", ["50"])[0] or 50)))
                events = (
                    db.get_slash_events(limit)
                    if db and hasattr(db, "get_slash_events")
                    else []
                )
                self._json({
                    "count": len(events),
                    "events": events,
                    "api_wave": 61,
                })

            elif path == "/sync/status":
                se = self.__class__.sync_engine
                self._json(_build_sync_status(se, p2p, bc, cfg))

            # ── StateEngine ───────────────────────────────────────────────────
            elif path == "/state/supply":
                ims = self.__class__.immutable_state
                se  = self.__class__.state_engine
                supply = None
                if ims and hasattr(ims, "get_total_supply_abs"):
                    supply = ims.get_total_supply_abs()
                elif se and hasattr(se, "get_total_supply"):
                    supply = se.get_total_supply()
                self._json({"total_supply": supply, "symbol": "ABS",
                            "source": "immutable_state" if ims else "state_engine"})

            elif path == "/state/engine":
                se = self.__class__.state_engine
                if not se:
                    self._json({"enabled": False}); return
                info = {}
                for attr in ("block_number","state_root","account_count","enabled"):
                    if hasattr(se, attr): info[attr] = getattr(se, attr)
                info["enabled"] = True
                self._json(info)

            # ── Lightning channel info ────────────────────────────────────────
            elif path.startswith("/lightning/channel/"):
                channel_id = path.split("/lightning/channel/")[-1]
                ln = self.__class__.lightning
                if ln and channel_id and hasattr(ln, "get_channel_info"):
                    ch = ln.get_channel_info(channel_id)
                    self._json(ch if ch else {"error": "Channel not found"})
                elif ln and hasattr(ln, "channels"):
                    ch = ln.channels.get(channel_id)
                    self._json(ch.__dict__ if ch else {"error": "Channel not found"})
                else:
                    self._error(404, "Channel not found")

            # ── Plasma finalize exit ──────────────────────────────────────────
            elif path == "/plasma/exits":
                plasma = self.__class__.plasma
                exits = list(getattr(plasma, "exit_requests", {}).values()) if plasma else []
                self._json({"exits": exits})

            # ── Crypto Will get single will ───────────────────────────────────
            elif path.startswith("/will/get/"):
                will_id = path.split("/will/get/")[-1]
                cw = self.__class__.crypto_will
                if cw and hasattr(cw, "get_will"):
                    w = cw.get_will(will_id)
                    self._json(w if w else {"error": "Will not found"})
                elif cw and hasattr(cw, "wills"):
                    w = cw.wills.get(will_id)
                    self._json(w.__dict__ if w else {"error": "Not found"})
                else:
                    self._error(404, "Will not found")

            # ── AI Agent single ───────────────────────────────────────────────
            elif path.startswith("/ai-agent/get/"):
                agent_id = path.split("/ai-agent/get/")[-1]
                am = self.__class__.ai_manager
                if am and hasattr(am, "get_agent"):
                    ag = am.get_agent(agent_id)
                    self._json(ag if ag else {"error": "Agent not found"})
                elif am and hasattr(am, "agents"):
                    ag = am.agents.get(agent_id)
                    self._json(ag.__dict__ if ag else {"error": "Not found"})
                else:
                    self._error(404, "Agent not found")

            # ── PQ encapsulate/decapsulate ────────────────────────────────────
            elif path.startswith("/pq/encapsulate/"):
                pubkey = path.split("/pq/encapsulate/")[-1]
                algo = qs.get("algo", ["kyber"])[0]
                pq = self.__class__.pq_manager
                if pq and hasattr(pq, "encapsulate"):
                    try:
                        algorithm = pq._parse_algorithm(algo) if hasattr(pq, "_parse_algorithm") else algo
                        result = pq.encapsulate(algorithm, bytes.fromhex(pubkey.replace("0x", "")))
                    except NotImplementedError as e:
                        self._error(501, str(e)); return
                    except ValueError as e:
                        self._error(400, str(e)); return
                    self._json({"ciphertext": result.ciphertext.hex(), "algorithm": algo})
                else:
                    self._error(501, "encapsulate not available")

            # ── Smart account info and accounts by owner ──────────────────────
            elif path == "/smart-account/all":
                sa = self.__class__.smart_accounts
                owner = qs.get("owner", [""])[0]
                if sa and owner and hasattr(sa, "get_accounts_by_owner"):
                    accounts = sa.get_accounts_by_owner(owner)
                    self._json({"accounts": accounts})
                elif sa and hasattr(sa, "accounts"):
                    self._json({"accounts": list(sa.accounts.keys())})
                else:
                    self._json({"accounts": []})

            elif path.startswith("/smart-account/info/"):
                addr = path.split("/smart-account/info/")[-1]
                sa = self.__class__.smart_accounts
                if sa and hasattr(sa, "get_info"):
                    info = sa.get_info(addr)
                    self._json(info if info else {"address": addr, "exists": False})
                elif sa and hasattr(sa, "get_account"):
                    acc = sa.get_account(addr)
                    self._json(acc.__dict__ if acc and hasattr(acc,'__dict__') else {"address": addr, "exists": bool(acc)})
                else:
                    self._json({"address": addr, "enabled": bool(sa)})

            elif path.startswith("/smart-account/settings/"):
                addr = path.split("/smart-account/settings/")[-1]
                sa = self.__class__.smart_accounts
                if sa and hasattr(sa, "get_settings"):
                    settings = sa.get_settings(addr)
                    self._json(settings if settings else {"address": addr})
                else:
                    self._json({"address": addr, "enabled": bool(sa)})

            # ── Sharding: get shard for transaction ───────────────────────────
            elif path == "/sharding/classify":
                sh = self.__class__.sharding
                tx_hash = qs.get("tx_hash", [""])[0]
                from_addr = qs.get("from", [""])[0]
                if sh and hasattr(sh, "get_shard_for_transaction"):
                    shard_id = sh.get_shard_for_transaction({"hash": tx_hash, "from": from_addr})
                    self._json({"shard_id": shard_id, "tx_hash": tx_hash})
                elif sh and from_addr:
                    shard_id = int(from_addr[-1], 16) % sh.num_shards if hasattr(sh, "num_shards") else 0
                    self._json({"shard_id": shard_id, "method": "hash_modulo"})
                else:
                    self._json({"shard_id": 0, "enabled": bool(sh)})

            # ── PQ keypair & signature ────────────────────────────────────────
            elif path.startswith("/pq/keypair/"):
                algo = path.split("/pq/keypair/")[-1]
                pq = self.__class__.pq_manager
                if pq and hasattr(pq, "get_keypair"):
                    kp = pq.get_keypair(algo)
                    self._json({"algorithm": algo, "keypair": str(kp)})
                else:
                    self._json({"algorithm": algo, "enabled": bool(pq)})

            elif path.startswith("/pq/signature/"):
                msg = path.split("/pq/signature/")[-1]
                pq = self.__class__.pq_manager
                algo = qs.get("algo", ["dilithium"])[0]
                if pq and hasattr(pq, "get_signature"):
                    sig = pq.get_signature(msg, algo)
                    self._json({"signature": str(sig), "algorithm": algo})
                else:
                    self._json({"enabled": bool(pq), "error": "get_signature not available"})

            # ── Sync peer management & fast sync ──────────────────────────────
            elif path == "/sync/peers":
                se = self.__class__.sync_engine
                if se and hasattr(se, "peers"):
                    peers = list(se.peers.keys()) if isinstance(se.peers, dict) else se.peers
                    self._json({"peers": peers, "count": len(peers)})
                else:
                    self._json({"peers": [], "enabled": bool(se)})

            # ── Consensus committee ───────────────────────────────────────────
            elif path == "/consensus/committee":
                ce = self.__class__.consensus_engine_standalone
                if ce and hasattr(ce, "get_committee"):
                    self._json({"committee": ce.get_committee()})
                elif ce and hasattr(ce, "validators"):
                    vals = list(ce.validators.values())
                    self._json({"committee": [v.__dict__ if hasattr(v,'__dict__') else str(v) for v in vals[:10]]})
                else:
                    self._json({"committee": [], "enabled": False})

            # ── Finality epoch ────────────────────────────────────────────────
            elif path == "/finality/epoch":
                fe = self.__class__.finality_engine
                if fe and hasattr(fe, "get_epoch"):
                    self._json(fe.get_epoch())
                elif fe:
                    ep = getattr(fe, "current_epoch", None) or getattr(fe, "epoch", 0)
                    self._json({"epoch": ep})
                else:
                    self._json({"epoch": 0, "enabled": False})

            # ── Sharding: balance and state ───────────────────────────────────
            elif path.startswith("/sharding/balance/"):
                addr = path.split("/sharding/balance/")[-1]
                sh = self.__class__.sharding
                bc = self.__class__.blockchain
                shard_id = sh.get_shard_for_address(addr) if sh and hasattr(sh, "get_shard_for_address") else None
                if bc and hasattr(bc, "get_balance"):
                    balance = float(bc.get_balance(addr))
                elif sh and hasattr(sh, "get_shard_balance"):
                    balance = float(sh.get_shard_balance(addr))
                else:
                    balance = 0.0
                self._json({
                    "address": addr,
                    "shard_id": shard_id,
                    "balance": balance,
                    "source": "chain_state",
                })

            elif path.startswith("/sharding/state/"):
                shard_id_str = path.split("/sharding/state/")[-1]
                sh = self.__class__.sharding
                try:
                    sid = int(shard_id_str)
                except ValueError:
                    self._error(400, "Invalid shard_id"); return
                if sh and hasattr(sh, "get_shard_state"):
                    self._json(sh.get_shard_state(sid))
                elif sh and hasattr(sh, "shards") and sid in sh.shards:
                    shard = sh.shards[sid]
                    self._json(shard.get_stats() if hasattr(shard,'get_stats') else {"shard_id": sid})
                else:
                    self._error(404, "Shard not found")

            # ── Bridge: lock details, pending ─────────────────────────────────
            elif path == "/bridge/locks":
                locks = []
                if db and hasattr(db, "get_bridge_locks"):
                    locks = db.get_bridge_locks(limit=500)
                self._json({"locks": locks, "count": len(locks)})

            elif path == "/bridge/l1-proofs":
                proofs = []
                if db and hasattr(db, "get_meta"):
                    raw = db.get_meta("bridge_l1_proofs", [])
                    if isinstance(raw, list):
                        proofs = raw[-100:]
                self._json({"count": len(proofs), "proofs": proofs})

            # ── ZK verify range ───────────────────────────────────────────────
            elif path == "/zk/verify/range":
                zk = self.__class__.zk
                if not zk:
                    self._error(503, "ZK module not enabled")
                    return
                from features.zk import ZKProof
                value = int(qs.get("value", ["42"])[0])
                min_v = int(qs.get("min", ["0"])[0])
                max_v = int(qs.get("max", ["100"])[0])
                proof_raw = qs.get("proof", [""])[0]
                try:
                    if proof_raw.startswith("{"):
                        proof = ZKProof.from_dict(json.loads(proof_raw))
                    else:
                        proof = ZKProof(
                            commitment=proof_raw,
                            response=int(qs.get("response", ["0"])[0]),
                            challenge=int(qs.get("challenge", ["0"])[0]),
                            proof_type="range",
                        )
                except (json.JSONDecodeError, ValueError, TypeError) as e:
                    self._error(400, f"invalid proof: {e}")
                    return
                ok = zk.verify_range(proof, min_v, max_v)
                self._json({"valid": bool(ok), "value_checked": value})

            # ── Slashing engine ───────────────────────────────────────────────
            elif path == "/slashing/status":
                se = self.__class__.slashing_engine
                if se:
                    info = {}
                    for attr in ("slashes","active_validators","total_stake","enabled"):
                        if hasattr(se, attr): info[attr] = getattr(se, attr)
                    info["enabled"] = True
                    info["total_active_stake"] = se.get_total_active_stake() if hasattr(se,"get_total_active_stake") else None
                    self._json(info)
                else:
                    self._json({"enabled": False})

            elif path == "/slashing/validators":
                se = self.__class__.slashing_engine
                if se and hasattr(se, "validators"):
                    vals = se.validators
                    self._json({"validators": {k: v.__dict__ if hasattr(v,'__dict__') else str(v)
                                               for k,v in vals.items()}})
                else:
                    self._json({"validators": {}, "enabled": bool(se)})

            # ── Validator Registry ────────────────────────────────────────────
            elif path == "/chain/genesis/ceremony":
                cfg = self.__class__.config
                manifest_path = (
                    getattr(cfg, "validators_manifest_path", "")
                    or getattr(self.__class__, "validators_manifest_path", "")
                    or ""
                )
                if not manifest_path or not os.path.isfile(manifest_path):
                    self._json({
                        "enabled": False,
                        "ready": False,
                        "error": "validators_manifest_missing",
                    })
                    return
                try:
                    from runtime.genesis_ceremony import build_ceremony_artifact, load_manifest
                    manifest = load_manifest(manifest_path)
                    config_dict = {
                        "network_name": getattr(cfg, "network_name", "Absolute"),
                        "chain_id": int(getattr(cfg, "chain_id", 0) or 0),
                        "deployment_mode": getattr(cfg, "deployment_mode", "dev"),
                        "founder_address": getattr(cfg, "founder_address", ""),
                    }
                    artifact = build_ceremony_artifact(
                        config_dict,
                        manifest,
                        manifest_path,
                        config_dict.get("founder_address", ""),
                    )
                    bc = self.__class__.blockchain
                    if bc and hasattr(bc, "get_height"):
                        artifact["live_height"] = bc.get_height()
                        if hasattr(bc, "get_state_root"):
                            artifact["live_state_root"] = bc.get_state_root()
                    self._json({"enabled": True, "ceremony": artifact})
                except Exception as exc:
                    self._json({"enabled": False, "ready": False, "error": str(exc)})

            elif path == "/validators/registry":
                vr = self.__class__.validator_registry
                db = self.__class__.db
                manifest_rows = getattr(self.__class__, "public_validator_set", None)
                manifest_path = getattr(self.__class__, "validators_manifest_path", "") or ""
                if db:
                    try:
                        from runtime.validator_loader import merged_registry_view_from_parts
                        self._json(
                            merged_registry_view_from_parts(
                                db, vr, manifest_rows, manifest_path
                            )
                        )
                        return
                    except Exception:
                        pass
                if vr and hasattr(vr, "validators"):
                    vals = vr.validators
                    self._json({"validators": {k: v.to_dict() if hasattr(v,'to_dict') else str(v)
                                               for k,v in vals.items()},
                                "count": len(vals)})
                else:
                    self._json({"validators": {}, "enabled": bool(vr)})

            elif path.startswith("/validators/info/"):
                addr = path.split("/validators/info/")[-1]
                vr = self.__class__.validator_registry
                if vr and hasattr(vr, "get"):
                    v = vr.get(addr)
                    self._json(v.to_dict() if v and hasattr(v,'to_dict') else {"address": addr, "found": v is not None})
                elif vr and hasattr(vr, "validators") and addr in vr.validators:
                    v = vr.validators[addr]
                    self._json(v.to_dict() if hasattr(v,'to_dict') else str(v))
                else:
                    self._error(404, "Validator not found")

            # ── Epoch Manager ─────────────────────────────────────────────────
            elif path == "/epoch/current":
                em = self.__class__.epoch_manager
                bc = self.__class__.blockchain
                height = bc.get_height() if bc and hasattr(bc,"get_height") else 0
                if em and hasattr(em, "get_epoch"):
                    ep = em.get_epoch(height)
                    self._json({"epoch": ep, "block_height": height,
                                "epoch_start": em.get_epoch_start(ep) if hasattr(em,"get_epoch_start") else None,
                                "epoch_end":   em.get_epoch_end(ep)   if hasattr(em,"get_epoch_end")   else None})
                else:
                    self._json({"epoch": height // 32 if height else 0, "enabled": bool(em)})

            # ── Beacon Finality ───────────────────────────────────────────────
            elif path == "/beacon/finality":
                bf = self.__class__.beacon_finality
                if bf and hasattr(bf, "get_stats"):
                    self._json(bf.get_stats())
                elif bf and hasattr(bf, "get_state"):
                    self._json(bf.get_state())
                else:
                    self._json({"enabled": bool(bf)})

            # ── LMD-GHOST Table ───────────────────────────────────────────────
            elif path == "/lmd/stats":
                lmd = self.__class__.lmd_table
                if lmd and hasattr(lmd, "get_stats"):
                    self._json(lmd.get_stats())
                elif lmd and hasattr(lmd, "get_weights"):
                    self._json({"weights": lmd.get_weights()})
                else:
                    self._json({"enabled": bool(lmd)})

            elif path == "/lmd/weights":
                lmd = self.__class__.lmd_table
                if lmd and hasattr(lmd, "get_weights"):
                    self._json({"weights": lmd.get_weights()})
                else:
                    self._json({"weights": {}, "enabled": bool(lmd)})

            # ── Casper Engine ─────────────────────────────────────────────────
            elif path == "/consensus/casper/head":
                cc = self.__class__.consensus_casper
                if cc and hasattr(cc, "get_head"):
                    self._json({"head": cc.get_head()})
                else:
                    self._json({"head": None, "enabled": bool(cc)})

            elif path == "/consensus/casper/status":
                cc = self.__class__.consensus_casper
                if cc:
                    info = {}
                    for attr in ("validators","blocks","attestations","head"):
                        if hasattr(cc, attr):
                            val = getattr(cc, attr)
                            info[attr] = len(val) if isinstance(val, dict) else val
                    info["enabled"] = True
                    self._json(info)
                else:
                    self._json({"enabled": False})

            # ── Block Validator ───────────────────────────────────────────────
            elif path == "/block/validate":
                bv = self.__class__.block_validator
                block_num = int(qs.get("height", [0])[0])
                bc = self.__class__.blockchain
                if bv and bc:
                    block = bc.get_block(block_num) if hasattr(bc,"get_block") else None
                    if block:
                        result = bv.validate_block(block)
                        self._json({"valid": bool(result), "block_height": block_num})
                    else:
                        self._json({"valid": None, "error": "Block not found"})
                else:
                    self._json({"enabled": bool(bv)})

            # ── SPHINCS+ ──────────────────────────────────────────────────────
            elif path == "/pq/sphincs/keygen":
                sph = self.__class__.sphincs
                if sph and hasattr(sph, "generate_keypair"):
                    try:
                        private_key, public_key = sph.generate_keypair()
                    except NotImplementedError as e:
                        self._error(501, str(e)); return
                    self._json({"public_key": public_key.hex(),
                                "private_key": private_key.hex(),
                                "algorithm": "SPHINCS+"})
                else:
                    self._error(503, "SPHINCS+ not available")

            # ── Canonical Serializer ──────────────────────────────────────────
            elif path.startswith("/block/canonical-hash/"):
                block_num = int(path.split("/block/canonical-hash/")[-1] or "0")
                cs = self.__class__.canonical_serializer
                bc = self.__class__.blockchain
                block = bc.get_block(block_num) if bc and hasattr(bc,"get_block") else None
                if cs and block and hasattr(cs, "compute_hash"):
                    h = cs.compute_hash(block)
                    self._json({"canonical_hash": h, "block_height": block_num})
                elif block:
                    h = getattr(block, 'hash', getattr(block, 'block_hash', None))
                    self._json({"canonical_hash": h, "block_height": block_num})
                else:
                    self._error(404, "Block not found")

            # ── Beacon consensus engine ──────────────────────────────────────
            elif path == "/consensus/beacon":
                cb = self.__class__.consensus_beacon
                if cb:
                    info = {}
                    for attr in ("validators","head","height","slot","epoch"):
                        if hasattr(cb, attr):
                            v = getattr(cb, attr)
                            info[attr] = len(v) if isinstance(v, dict) else v
                    info["enabled"] = True
                    if hasattr(cb, "get_head"): info["head_hash"] = cb.get_head()
                    self._json(info)
                else:
                    self._json({"enabled": False})

            elif path == "/consensus/slashing-engine":
                cs = self.__class__.consensus_engine_slashing
                if cs:
                    info = {"enabled": True}
                    for attr in ("validators","slashes","head"):
                        if hasattr(cs, attr):
                            v = getattr(cs, attr)
                            info[attr] = len(v) if isinstance(v, dict) else v
                    self._json(info)
                else:
                    self._json({"enabled": False})

            elif path == "/consensus/casper-finality":
                cf = self.__class__.casper_finality
                if cf:
                    info = {"enabled": True}
                    for attr in ("justified","finalized","current_epoch","total_stake"):
                        if hasattr(cf, attr): info[attr] = getattr(cf, attr)
                    self._json(info)
                else:
                    self._json({"enabled": False})

            # ── Consensus total stake ─────────────────────────────────────────
            elif path == "/consensus/stake":
                ce = self.__class__.consensus_engine_standalone
                if ce and hasattr(ce, "get_total_stake"):
                    self._json({"total_stake": ce.get_total_stake()})
                elif ce and hasattr(ce, "validators"):
                    total = sum(getattr(v,"stake",0) for v in ce.validators.values())
                    self._json({"total_stake": total, "validator_count": len(ce.validators)})
                else:
                    self._json({"total_stake": 0, "enabled": False})

            # ── MEV frontrun analysis ─────────────────────────────────────────
            elif path == "/mev/frontrun":
                cfg = self.__class__.config
                if getattr(cfg, "is_production", False):
                    self._json({"enabled": False, "dev_only": True, "error": "MEV disabled in production"})
                    return
                mev = self.__class__.mev_simulator
                mp = self.__class__.mempool
                tx_hash = qs.get("tx_hash", [""])[0]
                target = None
                if mp and tx_hash:
                    for tx in mp.get(limit=500):
                        if tx.tx_hash == tx_hash:
                            from features.mev_analyzer import Transaction as MevTx
                            target = MevTx(
                                hash=tx.tx_hash,
                                from_addr=tx.from_addr,
                                to_addr=tx.to_addr,
                                value=float(tx.amount),
                                gas_price=int(tx.fee * 1e9) if tx.fee else 1,
                                timestamp=0,
                            )
                            break
                if mev and target and hasattr(mev, "simulate_frontrun"):
                    result = mev.simulate_frontrun(target, bot_balance=1000.0)
                    result["dev_only"] = True
                    result["tx_hash"] = tx_hash
                    self._json(result)
                else:
                    self._json({
                        "success": False,
                        "feasible": False,
                        "dev_only": True,
                        "enabled": bool(mev),
                        "error": "tx not in mempool" if tx_hash else "tx_hash required",
                    })

            # ── Reorg depth & fork analysis ───────────────────────────────────
            elif path == "/reorg/depth":
                rp = self.__class__.reorg_predictor
                if rp and hasattr(rp, "predict_reorg_depth"):
                    network_hr = float(qs.get("network_hashrate", ["100"])[0])
                    attacker_hr = float(qs.get("attacker_hashrate", ["10"])[0])
                    depth = rp.predict_reorg_depth(network_hr, attacker_hr)
                    self._json({
                        "predicted_depth": depth,
                        "network_hashrate": network_hr,
                        "attacker_hashrate": attacker_hr,
                        "enabled": True,
                    })
                else:
                    self._json({"predicted_depth": 0, "enabled": bool(rp)})

            elif path == "/reorg/fork":
                rp = self.__class__.reorg_predictor
                if not rp:
                    self._json({"fork_detected": False, "enabled": False}); return
                main_raw = qs.get("main_chain", [""])[0]
                fork_raw = qs.get("fork_chain", [""])[0]
                if main_raw and fork_raw:
                    try:
                        main_chain = json.loads(main_raw)
                        fork_chain = json.loads(fork_raw)
                    except Exception as e:
                        self._error(400, f"invalid chain JSON: {e}"); return
                    analysis = rp.analyze_fork(main_chain, fork_chain)
                    self._json(analysis if isinstance(analysis, dict) else {"analysis": str(analysis)})
                else:
                    local_h = bc.get_height() if bc else 0
                    heights = []
                    if p2p and hasattr(p2p, "get_peers_info"):
                        for peer in p2p.get_peers_info():
                            heights.append(int(peer.get("height", 0) or 0))
                    self._json(rp.analyze_live_peers(local_h, heights))

            elif path == "/reorg/history":
                rp = self.__class__.reorg_predictor
                if not rp:
                    self._json({"count": 0, "assessments": [], "enabled": False}); return
                limit = int(qs.get("limit", ["50"])[0])
                hist = rp.get_history(limit) if hasattr(rp, "get_history") else []
                stats = rp.get_stats() if hasattr(rp, "get_stats") else {}
                self._json({"count": len(hist), "assessments": hist, "stats": stats, "enabled": True})

            # ── Immutable state ABS balance ───────────────────────────────────
            elif path.startswith("/state/abs-balance/"):
                addr = path.split("/state/abs-balance/")[-1]
                ims = self.__class__.immutable_state
                if ims and hasattr(ims, "get_balance_abs"):
                    self._json({"address": addr, "balance_abs": ims.get_balance_abs(addr)})
                elif ims and hasattr(ims, "get_balance"):
                    self._json({"address": addr, "balance_abs": ims.get_balance(addr)})
                else:
                    bc = self.__class__.blockchain
                    bal = bc.get_balance(addr) if bc and hasattr(bc,"get_balance") else 0
                    self._json({"address": addr, "balance_abs": bal})

            # ── Sharding: register node, mine block ───────────────────────────
            elif path == "/sharding/nodes":
                sh = self.__class__.sharding
                if sh and hasattr(sh, "list_nodes"):
                    self._json({"nodes": sh.list_nodes(), "enabled": True})
                else:
                    self._json({"nodes": [], "enabled": bool(sh)})

            # ── ZK range proof ────────────────────────────────────────────────
            elif path == "/zk/prove/range":
                zk = self.__class__.zk
                value = int(qs.get("value", ["42"])[0])
                min_v  = int(qs.get("min", ["0"])[0])
                max_v  = int(qs.get("max", ["100"])[0])
                if zk and hasattr(zk, "prove_range"):
                    proof = zk.prove_range(value, min_v, max_v)
                    self._json({"proof": proof.__dict__ if hasattr(proof,'__dict__') else str(proof),
                                "valid": True, "range": f"[{min_v}, {max_v}]"})
                else:
                    self._json({"valid": value >= min_v and value <= max_v,
                                "range": f"[{min_v}, {max_v}]", "value": value})

            elif path == "/zk/transaction":
                zk = self.__class__.zk
                if zk and hasattr(zk, "create_zk_transaction"):
                    tx = zk.create_zk_transaction(
                        sender=qs.get("sender",[""])[0],
                        amount=int(qs.get("amount",["1"])[0]))
                    self._json({"tx": tx.__dict__ if hasattr(tx,'__dict__') else str(tx)})
                else:
                    self._json({"error": "ZK transactions not available"})

            # ── Contracts list ────────────────────────────────────────────────
            elif path == "/contracts":
                cm = self.__class__.contract_manager
                if cm and hasattr(cm, "get_contracts"):
                    self._json({"contracts": cm.get_contracts()})
                elif cm and hasattr(cm, "contracts"):
                    self._json({"contracts": list(cm.contracts.keys())})
                else:
                    self._json({"contracts": []})

            # ── Immutable state total supply ──────────────────────────────────
            elif path == "/state/total-supply":
                ims = self.__class__.immutable_state
                if ims and hasattr(ims, "get_total_supply_abs"):
                    self._json({"total_supply_abs": ims.get_total_supply_abs(),
                                "total_supply_satoshi": ims.get_total_supply_satoshi()
                                if hasattr(ims,"get_total_supply_satoshi") else None})
                else:
                    self._json({"total_supply_abs": None, "enabled": False})

            else:
                self._error(404, "Endpoint not found")

        except Exception as e:
            logger.exception(f"REST error: {e}")
            self._error(500, str(e))

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        cfg = self.__class__.config
        if not _check_rate_limit(self, parsed.path):
            return

        self._track_request()
        length = int(self.headers.get("Content-Length", 0))
        raw_bytes = self.rfile.read(length) if length else b""
        if _is_prod_blocked_path(path, cfg):
            self._error(403, "dev/testnet endpoint disabled in production")
            return
        if path in _BRIDGE_ORACLE_PATHS:
            if not self._verify_bridge_oracle(path, raw_bytes):
                return
        elif not self._require_jwt_admin(path):
            return
        body = {}
        if raw_bytes:
            try:
                raw_body = json.loads(raw_bytes.decode("utf-8"))
                body = sanitize_input(raw_body) if _INPUT_VALIDATORS_AVAILABLE else raw_body
            except json.JSONDecodeError:
                self._error(400, "Invalid JSON")
                return

        bc = self.__class__.blockchain
        mp = self.__class__.mempool
        db = self.__class__.db
        evm_adapter = self.__class__.evm

        try:
            if path in ("/transactions", "/tx/send"):
                wallet = self.__class__.wallet
                result = _handle_send_tx_with_wallet(body, bc, mp, cfg, wallet)
                resp = {
                    "tx_hash": result,
                    "status": "pending",
                    "trace_url": f"/tx/trace/{result}",
                }
                sh = self.__class__.sharding
                if sh and hasattr(sh, "add_transaction"):
                    from_addr = body.get("from", body.get("from_addr", ""))
                    to_addr = body.get("to", body.get("to_addr", ""))
                    value = body.get("value", body.get("amount", 0))
                    shard_from, cross_id = sh.add_transaction({
                        "from": from_addr,
                        "to": to_addr,
                        "value": value,
                        "hash": result,
                    })
                    resp["from_shard"] = shard_from
                    resp["to_shard"] = sh.get_shard_for_address(to_addr) if hasattr(sh, "get_shard_for_address") else None
                    resp["cross_shard"] = bool(cross_id)
                    if cross_id:
                        resp["cross_shard_tx_id"] = cross_id
                self._json(resp)

            elif path == "/evm/validate-bytecode":
                raw = body.get("bytecode", body.get("data", ""))
                try:
                    from execution.evm_bytecode_validator import validate_bytecode_hex
                    self._json(validate_bytecode_hex(str(raw)))
                except Exception as e:
                    self._json({"valid": False, "error": str(e)})

            elif path == "/contract/deploy":
                if not evm_adapter:
                    self._error(503, "EVM not enabled")
                    return
                bc_hex = body.get("bytecode", body.get("data", ""))
                from execution.evm_bytecode_validator import validate_bytecode_hex
                v = validate_bytecode_hex(str(bc_hex))
                if not v.get("valid"):
                    self._error(400, f"unsupported EVM bytecode: {(v.get('unsupported') or [{}])[0].get('name', v.get('error'))}")
                    return
                if body.get("via_mempool", body.get("mempool", False)):
                    _reject_deploy_without_salt_in_prod(body, cfg)
                    tx_hash = _handle_deploy_tx(body, bc, mp, cfg, self.__class__.wallet, evm_adapter)
                    self._json({"tx_hash": tx_hash, "status": "pending", "via_mempool": True})
                    return
                _reject_deploy_without_salt_in_prod(body, cfg)
                result = evm_adapter.deploy_contract(
                    deployer=body.get("from", body.get("from_address", "")),
                    bytecode_hex=body.get("bytecode", body.get("data", "")),
                    value=float(body.get("value", 0)),
                    salt=body.get("salt"),
                )
                self._json(result.to_dict())

            elif path == "/tx/deploy":
                if not evm_adapter:
                    self._error(503, "EVM not enabled")
                    return
                _reject_deploy_without_salt_in_prod(body, cfg)
                tx_hash = _handle_deploy_tx(body, bc, mp, cfg, self.__class__.wallet, evm_adapter)
                self._json({"tx_hash": tx_hash, "status": "pending", "via_mempool": True})

            elif path == "/tx/call":
                if not evm_adapter:
                    self._error(503, "EVM not enabled")
                    return
                tx_hash = _handle_call_tx(body, bc, mp, cfg, self.__class__.wallet)
                self._json({"tx_hash": tx_hash, "status": "pending", "via_mempool": True})

            elif path == "/contract/call":
                if not evm_adapter:
                    self._error(503, "EVM not enabled")
                    return
                result = evm_adapter.call_contract(
                    caller=body.get("from", ""),
                    contract_addr=body.get("to", ""),
                    calldata_hex=body.get("data", ""),
                    value=float(body.get("value", 0)),
                )
                self._json(result.to_dict())

            elif path == "/validators/register":
                address = body.get("address", "")
                stake = float(body.get("stake", 0))
                if stake < cfg.min_stake:
                    self._error(400, f"Stake must be >= {cfg.min_stake}")
                    return
                ca = self.__class__.consensus_adapter
                if ca and hasattr(ca, "add_validator"):
                    ok = ca.add_validator(address, stake)
                    self._json({"registered": bool(ok), "address": address, "stake": stake})
                else:
                    bc.db.save_validator(address, stake)
                    self._json({"registered": True, "address": address, "stake": stake})

            # ── NFT POST ─────────────────────────────────────────────────────
            elif path == "/nft/mint":
                nft = self.__class__.nft
                if not nft:
                    self._error(503, "NFT module not enabled"); return
                result = nft.mint(
                    token_id=body.get("token_id", ""),
                    name=body.get("name", ""),
                    description=body.get("description", ""),
                    image_url=body.get("image_url", ""),
                    creator=body.get("creator", ""),
                    price=float(body.get("price", 0)),
                )
                self._json(result)

            elif path == "/nft/buy":
                nft = self.__class__.nft
                if not nft:
                    self._error(503, "NFT module not enabled"); return
                result = nft.buy(
                    token_id=body.get("token_id", ""),
                    buyer=body.get("buyer", ""),
                )
                self._json(result)

            elif path == "/nft/list":
                nft = self.__class__.nft
                if not nft:
                    self._error(503, "NFT module not enabled"); return
                result = nft.list_for_sale(
                    token_id=body.get("token_id", ""),
                    owner=body.get("owner", ""),
                    price=float(body.get("price", 0)),
                )
                self._json(result)

            elif path == "/nft/transfer":
                nft = self.__class__.nft
                if not nft:
                    self._error(503, "NFT module not enabled"); return
                result = nft.transfer(
                    token_id=body.get("token_id", ""),
                    from_addr=body.get("from", ""),
                    to_addr=body.get("to", ""),
                )
                self._json(result)

            # ── ZK Proofs POST ────────────────────────────────────────────────
            elif path == "/zk/prove/knowledge":
                zk = self.__class__.zk
                if not zk:
                    self._error(503, "ZK module not enabled"); return
                secret = int(body.get("secret", 0))
                proof = zk.prove_knowledge(secret)
                self._json(proof.to_dict())

            elif path == "/zk/verify/knowledge":
                zk = self.__class__.zk
                if not zk:
                    self._error(503, "ZK module not enabled"); return
                from features.zk import ZKProof
                proof = ZKProof.from_dict(body.get("proof", {}))
                pub = int(body.get("public_value", 0))
                ok = zk.verify_knowledge(proof, pub)
                self._json({"verified": ok})

            elif path == "/zk/prove/balance":
                zk = self.__class__.zk
                if not zk:
                    self._error(503, "ZK module not enabled"); return
                balance = int(body.get("balance", 0))
                amount = int(body.get("amount", 0))
                try:
                    proof = zk.prove_balance(balance, amount)
                    self._json(proof.to_dict())
                except ValueError as e:
                    self._error(400, str(e))

            elif path == "/zk/verify/balance":
                zk = self.__class__.zk
                if not zk:
                    self._error(503, "ZK module not enabled"); return
                from features.zk import ZKProof
                proof = ZKProof.from_dict(body.get("proof", {}))
                amount = int(body.get("amount", 0))
                ok = zk.verify_balance(proof, amount)
                self._json({"verified": ok})

            elif path == "/zk/prove":
                zk = self.__class__.zk
                if not zk:
                    self._error(503, "ZK module not enabled"); return
                proof_type = body.get("type", "knowledge")
                secret = int(body.get("secret", body.get("value", 42)))
                try:
                    if proof_type == "knowledge":
                        proof = zk.prove_knowledge(secret)
                    elif proof_type == "range":
                        lo = int(body.get("min", 0))
                        hi = int(body.get("max", 100))
                        proof = zk.prove_range(secret, lo, hi)
                    elif proof_type == "balance":
                        threshold = int(body.get("threshold", 0))
                        proof = zk.prove_balance(secret, threshold)
                    else:
                        self._error(400, "Unknown proof type"); return
                    pd = proof.to_dict() if hasattr(proof, "to_dict") else {"valid": getattr(proof, "valid", True)}
                    self._json({"proof_type": proof_type, "valid": True, **pd})
                except Exception as e:
                    self._json({"proof_type": proof_type, "valid": False, "error": str(e)})

            # ── Wallet create ─────────────────────────────────────────────────
            elif path == "/wallet/create":
                try:
                    from crypto.wallet import Wallet
                    w = Wallet.create_new()
                    self._json({
                        "address": w.address,
                        "public_key": getattr(w, "public_key_hex", ""),
                    })
                except Exception as e:
                    import hashlib as _hl, time as _t
                    addr = "0x" + _hl.sha256(str(_t.time()).encode()).hexdigest()[:40]
                    self._json({"address": addr, "note": "ecdsa not available"})

            # ── Multisig create ───────────────────────────────────────────────
            elif path == "/multisig/create":
                owners = body.get("owners", [])
                required = int(body.get("required", 2))
                to = body.get("to", "")
                value = float(body.get("value", 0))
                try:
                    from features.multisig import MultiSigWallet
                    ms = MultiSigWallet(owners, required)
                    result = ms.create_transaction(to, value)
                    if isinstance(result, dict) and result.get("success") is False:
                        self._error(400, result.get("error", "multisig transaction failed"))
                        return
                    self._json({**result, "owners": owners, "required": required})
                except ValueError as e:
                    self._error(400, str(e))
                except Exception as e:
                    self._error(500, str(e))

            # ── NFT mint ──────────────────────────────────────────────────────
            elif path == "/nft/mint":
                nft = self.__class__.nft
                if not nft:
                    self._error(503, "NFT module not enabled"); return
                name  = body.get("name", "Unnamed NFT")
                owner = body.get("owner", "")
                price = float(body.get("price", 1.0))
                desc  = body.get("description", "")
                if not owner:
                    self._error(400, "owner is required"); return
                token = nft.mint(owner=owner, name=name, description=desc, price=price)
                if token:
                    self._json({"token_id": getattr(token, "token_id", str(token)), "name": name})
                else:
                    self._error(500, "Mint failed")

            # ── MiniVM contract deploy ─────────────────────────────────────────
            elif path == "/minivm/compile":
                asm = self.__class__.assembler
                if not asm:
                    self._error(503, "MiniVM assembler not enabled"); return
                source = body.get("source", "")
                if not source:
                    self._error(400, "source field required"); return
                try:
                    bytecode = asm.assemble(source)
                    self._json({"success": True, "bytecode": bytecode,
                                "instructions": len(bytecode)})
                except Exception as e:
                    self._error(400, str(e))

            elif path == "/minivm/deploy":
                cm = self.__class__.contract_manager
                asm = self.__class__.assembler
                if not cm:
                    self._error(503, "ContractManager not enabled"); return
                source = body.get("source", "")
                address = body.get("address", "")
                if not address:
                    self._error(400, "address field required"); return
                try:
                    if source and asm:
                        bytecode = asm.assemble(source)
                    else:
                        bytecode = body.get("bytecode", [])
                    if not bytecode:
                        self._error(400, "source or bytecode required"); return
                    ok = cm.deploy(bytecode, address,
                                   initial_storage=body.get("initial_storage"))
                    if ok:
                        self._json({"success": True, "address": address,
                                    "instructions": len(bytecode)})
                    else:
                        self._error(409, f"Contract already deployed at {address}")
                except Exception as e:
                    self._error(400, str(e))

            elif path == "/minivm/call":
                cm = self.__class__.contract_manager
                if not cm:
                    self._error(503, "ContractManager not enabled"); return
                address = body.get("address", "")
                method  = body.get("method", "main")
                args    = body.get("args", [])
                if not address:
                    self._error(400, "address required"); return
                result = cm.call(address, method, args)
                if result is None:
                    self._error(404, f"No contract at {address}")
                else:
                    self._json(result)

            # ── Post-Quantum crypto ───────────────────────────────────────────
            elif path == "/pq/keygen":
                pqm = self.__class__.pq_manager
                if not pqm:
                    self._error(503, "PostQuantumManager not enabled"); return
                algo = body.get("algorithm", "dilithium")
                try:
                    if hasattr(pqm, "generate_keypair"):
                        algorithm = pqm._parse_algorithm(algo) if hasattr(pqm, "_parse_algorithm") else algo
                        kp = pqm.generate_keypair(algorithm)
                        keys = {
                            "key_id": kp.key_id,
                            "public_key": kp.public_key.hex(),
                            "private_key": kp.private_key.hex(),
                        }
                    elif hasattr(pqm, "generate_keys"):
                        keys = pqm.generate_keys(algo)
                    elif hasattr(pqm, "keygen"):
                        keys = pqm.keygen(algo)
                    else:
                        self._error(501, "keygen not available"); return
                    self._json({"algorithm": algo, "keys": keys})
                except NotImplementedError as e:
                    self._error(501, str(e))
                except ValueError as e:
                    self._error(400, str(e))
                except Exception as e:
                    self._error(500, str(e))

            elif path == "/pq/sign":
                pqm = self.__class__.pq_manager
                if not pqm:
                    self._error(503, "PostQuantumManager not enabled"); return
                message = body.get("message", "")
                algo = body.get("algorithm", "dilithium")
                key_id = body.get("key_id", "")
                try:
                    if hasattr(pqm, "sign_text"):
                        result = pqm.sign_text(message, algorithm=algo, key_id=key_id or None)
                        self._json(result)
                    else:
                        self._error(501, "sign not implemented in PQ manager")
                except NotImplementedError as e:
                    self._error(501, str(e))
                except Exception as e:
                    self._error(500, str(e))

            elif path == "/pq/verify":
                pqm = self.__class__.pq_manager
                if not pqm:
                    self._error(503, "PostQuantumManager not enabled"); return
                message = body.get("message", "")
                signature = body.get("signature", body.get("signature_payload", {}))
                algo = body.get("algorithm", "dilithium")
                public_key = body.get("public_key", "")
                try:
                    if hasattr(pqm, "verify_text"):
                        ok = pqm.verify_text(message, signature, algorithm=algo, public_key_hex=public_key)
                        self._json({"algorithm": algo, "valid": bool(ok)})
                    else:
                        self._error(501, "verify not implemented in PQ manager")
                except Exception as e:
                    self._error(500, str(e))

            # ── Smart Accounts ────────────────────────────────────────────────
            elif path == "/smart-account/create":
                sa = self.__class__.smart_accounts
                if not sa:
                    self._error(503, "SmartAccountManager not enabled"); return
                owner  = body.get("owner", "")
                method = body.get("method", "basic")
                if not owner:
                    self._error(400, "owner required"); return
                try:
                    if hasattr(sa, "create_account"):
                        acc = sa.create_account(owner, method)
                    elif hasattr(sa, "create"):
                        acc = sa.create(owner)
                    else:
                        self._error(501, "smart account create not supported")
                        return
                    if isinstance(acc, dict) and acc.get("success") is False:
                        self._error(400, acc.get("error", "smart account create failed"))
                        return
                    self._json({"success": True, "account": acc})
                except Exception as e:
                    self._error(500, str(e))

            elif path == "/smart-account/session-key":
                sa = self.__class__.smart_accounts
                if not sa:
                    self._error(503, "SmartAccountManager not enabled"); return
                account = body.get("account", "")
                try:
                    if hasattr(sa, "create_session_key"):
                        key = sa.create_session_key(account)
                    else:
                        self._error(501, "session keys not supported")
                        return
                    if isinstance(key, dict) and key.get("success") is False:
                        self._error(400, key.get("error", "session key create failed"))
                        return
                    self._json(key if isinstance(key, dict) else {"account": account, "session_key": key})
                except Exception as e:
                    self._error(500, str(e))

            elif path == "/smart-account/recover":
                sa = self.__class__.smart_accounts
                if not sa:
                    self._error(503, "SmartAccountManager not enabled"); return
                account   = body.get("account", "")
                new_owner = body.get("new_owner", "")
                guardians = body.get("guardians", [])
                try:
                    if hasattr(sa, "recover_account"):
                        ok = sa.recover_account(account, new_owner, guardians)
                        if ok:
                            self._json({"success": True, "account": account, "new_owner": new_owner})
                        else:
                            self._error(400, "recovery not approved")
                    elif hasattr(sa, "get_account"):
                        acc = sa.get_account(account)
                        if not acc:
                            self._error(404, "account not found"); return
                        if not guardians:
                            self._error(400, "guardians required"); return
                        req_id = None
                        for g in guardians:
                            req_id = acc.request_recovery(g) or req_id
                            if req_id:
                                acc.approve_recovery(req_id, g)
                        if req_id and acc.execute_recovery(req_id, new_owner):
                            self._json({"success": True, "account": account, "new_owner": new_owner, "request_id": req_id})
                        else:
                            self._error(400, "recovery not approved")
                    else:
                        self._error(501, "recovery not implemented")
                except Exception as e:
                    self._error(500, str(e))

            # ── AI Validator: register / update ───────────────────────────────
            elif path == "/ai/register-validator":
                ai = self.__class__.ai_validator
                if not ai:
                    self._error(503, "AI validator not enabled"); return
                address = body.get("address", "")
                stake   = float(body.get("stake", 100))
                if not address:
                    self._error(400, "address required"); return
                ai.add_validator(address, stake)
                self._json({"registered": address, "stake": stake,
                            "total_validators": len(ai.validators)})

            # ── MEV: analyze mempool ───────────────────────────────────────────
            elif path == "/mev/analyze":
                mev = self.__class__.mev_simulator
                if not mev:
                    self._error(503, "MEV analyzer not enabled"); return
                txs_raw = body.get("transactions", [])
                try:
                    from features.mev_analyzer import Transaction as MevTx
                    txs = [MevTx(
                        hash=t.get("hash", "0x0"),
                        from_addr=t.get("from", ""),
                        to_addr=t.get("to", ""),
                        value=float(t.get("value", 0)),
                        gas_price=int(t.get("gas_price", 1)),
                        timestamp=int(t.get("timestamp", 0)),
                    ) for t in txs_raw]
                    sandwich = mev.detect_sandwich_opportunity(txs)
                    arbitrage = mev.detect_arbitrage(txs_raw)
                    self._json({"sandwich": sandwich, "arbitrage": arbitrage,
                                "stats": mev.get_statistics()})
                except Exception as e:
                    self._error(500, str(e))

            # ── NFT: auction, listing, bid (from extended_api_server) ────────
            elif path == "/nft/auction":
                nft = self.__class__.nft
                if not nft:
                    self._error(503, "NFT not enabled"); return
                token_id    = body.get("token_id", "")
                seller      = body.get("seller", "")
                start_price = float(body.get("start_price", 1.0))
                reserve     = float(body.get("reserve_price", start_price))
                hours       = int(body.get("hours", 24))
                if not token_id or not seller:
                    self._error(400, "token_id and seller required"); return
                try:
                    if hasattr(nft, "create_auction"):
                        aid = nft.create_auction(token_id, seller, start_price, reserve, hours)
                        if aid:
                            self._json({"success": True, "auction_id": aid})
                        else:
                            self._error(400, "Could not create auction")
                    else:
                        self._error(501, "Auctions not supported by this NFT module")
                except Exception as e:
                    self._error(500, str(e))

            elif path == "/nft/bid":
                nft = self.__class__.nft
                if not nft:
                    self._error(503, "NFT not enabled"); return
                auction_id = body.get("auction_id", "")
                bidder     = body.get("bidder", "")
                amount     = float(body.get("amount", 0))
                if not auction_id or not bidder:
                    self._error(400, "auction_id and bidder required"); return
                try:
                    if hasattr(nft, "place_bid"):
                        result = nft.place_bid(auction_id, bidder, amount)
                        if isinstance(result, dict) and result.get("success"):
                            self._json({"success": True, "result": result})
                        else:
                            error = result.get("error", "Bid failed") if isinstance(result, dict) else "Bid failed"
                            self._error(400, error)
                    else:
                        self._error(501, "Bidding not supported")
                except Exception as e:
                    self._error(500, str(e))

            elif path == "/nft/list":
                nft = self.__class__.nft
                if not nft:
                    self._error(503, "NFT not enabled"); return
                token_id = body.get("token_id", "")
                seller   = body.get("seller", "")
                price    = float(body.get("price", 1.0))
                if not token_id or not seller:
                    self._error(400, "token_id and seller required"); return
                try:
                    if hasattr(nft, "create_listing"):
                        lid = nft.create_listing(token_id, seller, price)
                        if lid:
                            self._json({"success": True, "listing_id": lid})
                        else:
                            self._error(400, "Could not create listing")
                    elif hasattr(nft, "list_token"):
                        lid = nft.list_token(token_id, seller, price)
                        if lid:
                            self._json({"success": True, "listing_id": lid})
                        else:
                            self._error(400, "Could not create listing")
                    elif hasattr(nft, "list_for_sale"):
                        result = nft.list_for_sale(token_id, seller, price)
                        if isinstance(result, dict) and result.get("success"):
                            self._json(result)
                        else:
                            error = result.get("error", "Could not list token") if isinstance(result, dict) else "Could not list token"
                            self._error(400, error)
                    else:
                        self._error(501, "Listings not supported")
                except Exception as e:
                    self._error(500, str(e))

            # ── Immutable State: credit (for genesis / faucet) ────────────────
            elif path == "/state/credit":
                ist = self.__class__.immutable_state
                if not ist:
                    self._error(503, "ImmutableState not enabled"); return
                address = body.get("address", "")
                satoshi = int(body.get("satoshi", 0))
                if not address or satoshi <= 0:
                    self._error(400, "address and satoshi > 0 required"); return
                try:
                    acc = ist.get_account(address, create=True)
                    acc.balance_satoshi += satoshi
                    self._json({"success": True, "address": address,
                                "new_balance_satoshi": acc.balance_satoshi,
                                "new_balance_abs": acc.balance_satoshi / 1_000_000})
                except Exception as e:
                    self._error(500, str(e))

            # ── Crypto: sign, verify, keygen ──────────────────────────────────
            elif path == "/crypto/keygen":
                try:
                    from crypto.keys import KeyGenerator
                    kp = KeyGenerator.generate()
                    self._json({
                        "address":     kp.address,
                        "public_key":  kp.public_key.hex() if isinstance(kp.public_key, bytes) else kp.public_key,
                        "private_key": kp.private_key.hex() if isinstance(kp.private_key, bytes) else kp.private_key,
                    })
                except Exception as e:
                    self._error(500, str(e))

            elif path == "/crypto/sign":
                try:
                    from crypto.signing import Signer
                    from crypto.keys import KeyGenerator
                    private_key_hex = body.get("private_key", "")
                    tx_data         = body.get("transaction", {})
                    if not private_key_hex or not tx_data:
                        self._error(400, "private_key and transaction required"); return
                    private_key = bytes.fromhex(private_key_hex)
                    sig = Signer.sign_transaction(tx_data, private_key)
                    self._json({"signature": sig})
                except Exception as e:
                    self._error(500, str(e))

            elif path == "/crypto/verify":
                try:
                    from crypto.signing import Signer
                    tx_data   = body.get("transaction", {})
                    signature = body.get("signature", "")
                    pub_key   = body.get("public_key", "")
                    if not tx_data or not signature:
                        self._error(400, "transaction and signature required"); return
                    pub_bytes = bytes.fromhex(pub_key) if pub_key else None
                    ok = Signer.verify_transaction(tx_data, signature, pub_bytes)
                    self._json({"valid": ok})
                except Exception as e:
                    self._error(500, str(e))

            # ── NFT Extended: offers, auctions finalize ───────────────────────
            elif path == "/nft/offer":
                nft = self.__class__.nft
                if not nft:
                    self._error(503, "NFT not enabled"); return
                token_id = body.get("token_id", "")
                bidder = body.get("bidder", "")
                price = float(body.get("price", 0))
                hours = int(body.get("hours", 24))
                if not token_id or not bidder or price <= 0:
                    self._error(400, "token_id, bidder, price required"); return
                if hasattr(nft, "make_offer"):
                    oid = nft.make_offer(token_id, bidder, price, hours)
                    if oid:
                        self._json({"success": True, "offer_id": oid})
                    else:
                        self._error(400, "Could not create offer")
                else:
                    self._error(501, "Offers not supported")

            elif path == "/nft/accept-offer":
                nft = self.__class__.nft
                if not nft:
                    self._error(503, "NFT not enabled"); return
                offer_id = body.get("offer_id", "")
                seller = body.get("seller", "")
                if not offer_id or not seller:
                    self._error(400, "offer_id and seller required"); return
                if hasattr(nft, "accept_offer"):
                    result = nft.accept_offer(offer_id, seller)
                    if isinstance(result, dict) and result.get("success"):
                        self._json(result)
                    else:
                        error = result.get("error", "Could not accept offer") if isinstance(result, dict) else "Could not accept offer"
                        self._error(400, error)
                else:
                    self._error(501, "Offers not supported")

            elif path == "/nft/finalize-auction":
                nft = self.__class__.nft
                if not nft:
                    self._error(503, "NFT not enabled"); return
                auction_id = body.get("auction_id", "")
                if not auction_id:
                    self._error(400, "auction_id required"); return
                if hasattr(nft, "finalize_auction"):
                    result = nft.finalize_auction(auction_id)
                    if isinstance(result, dict) and result.get("success"):
                        self._json(result)
                    else:
                        error = result.get("error", "Could not finalize auction") if isinstance(result, dict) else "Could not finalize auction"
                        self._error(400, error)
                else:
                    self._error(501, "Auctions not supported")

            # ── Transaction Signing (TransactionSigner) ───────────────────────
            elif path == "/tx/sign":
                from_addr = body.get("from", "")
                to_addr = body.get("to", "")
                amount = float(body.get("amount", 0))
                nonce = int(body.get("nonce", 0))
                private_key = body.get("private_key", "")
                if not private_key:
                    self._error(400, "private_key required"); return
                try:
                    from crypto.tx_signer import TransactionSigner
                    from crypto.keys import KeyGenerator
                    tx_data = {"from": from_addr, "to": to_addr,
                               "amount": amount, "nonce": nonce,
                               "fee": float(body.get("fee", 0.001))}
                    keypair = KeyGenerator.from_private_key(private_key)
                    tx_data["public_key"] = keypair.public_key.hex()
                    tx_hash = TransactionSigner.hash_transaction(tx_data)
                    sig = TransactionSigner.sign_transaction(tx_data, private_key)
                    self._json({"tx_hash": tx_hash, "signature": sig,
                                "public_key": keypair.public_key.hex(),
                                "address": keypair.address,
                                "transaction": tx_data})
                except Exception as e:
                    self._error(500, str(e))

            elif path == "/tx/verify":
                tx_data = body.get("transaction", {})
                signature = body.get("signature", "")
                address = body.get("address", "")
                try:
                    from crypto.tx_signer import TransactionSigner
                    ok = TransactionSigner.verify_signature(tx_data, signature, address)
                    self._json({"valid": ok})
                except Exception as e:
                    self._error(500, str(e))

            # ── Pool DAO vote ───────────────────────────────────────────────
            elif path == "/pools/dao/vote":
                pl = self.__class__.pool_locks
                vr = self.__class__.validator_registry
                if not pl:
                    self._error(503, "Pool locks not enabled"); return
                pool_id = body.get("pool_id", body.get("pool", ""))
                voter = body.get("voter", body.get("address", ""))
                if not pool_id or not voter:
                    self._error(400, "pool_id and voter required"); return
                result = pl.dao_vote(pool_id, voter, validator_registry=vr)
                self._json(result)

            # ── Light client SPV verify ─────────────────────────────────────
            elif path == "/light/spv/verify":
                lc = self.__class__.light_client
                if not lc:
                    self._error(503, "Light client not enabled"); return
                block_n = int(body.get("block", body.get("block_number", -1)))
                tx = body.get("transaction", body.get("tx", {}))
                txs = body.get("transactions", [])
                if block_n < 0 or not tx:
                    self._error(400, "block and transaction required"); return
                if not txs and bc and hasattr(bc, "get_block"):
                    blk = bc.get_block(block_n)
                    txs = blk.get("transactions", []) if blk else []
                result = lc.verify_transaction_in_block(block_n, tx, txs)
                self._json(result)

            # ── Lightning Network ─────────────────────────────────────────────
            elif path == "/lightning/open":
                ln = self.__class__.lightning
                if not ln:
                    self._error(503, "Lightning not enabled"); return
                peer = body.get("peer_address", "")
                capacity = float(body.get("capacity", 0))
                if not peer or capacity <= 0:
                    self._error(400, "peer_address and capacity required"); return
                cid = ln.open_channel(peer, capacity)
                if cid:
                    self._json({"success": True, "channel_id": cid, "capacity": capacity})
                else:
                    self._error(400, "Could not open channel (capacity out of range or insufficient balance)")

            elif path == "/lightning/close":
                ln = self.__class__.lightning
                if not ln:
                    self._error(503, "Lightning not enabled"); return
                cid = body.get("channel_id", "")
                ok = ln.close_channel(cid) if cid else False
                if ok:
                    self._json({"success": True, "channel_id": cid})
                else:
                    self._error(400, "Could not close channel")

            elif path == "/lightning/pay":
                ln = self.__class__.lightning
                if not ln:
                    self._error(503, "Lightning not enabled"); return
                cid = body.get("channel_id", "")
                to_node = body.get("to", "")
                amount = float(body.get("amount", 0))
                if not cid or not to_node or amount <= 0:
                    self._error(400, "channel_id, to, amount required"); return
                pid = ln.send_payment(cid, to_node, amount)
                if pid:
                    self._json({"success": True, "payment_id": pid, "amount": amount})
                else:
                    self._error(400, "Payment failed (insufficient balance or invalid channel)")

            # ── Crypto Will ───────────────────────────────────────────────────
            elif path == "/will/create":
                cw = self.__class__.crypto_will
                if not cw:
                    self._error(503, "CryptoWill not enabled"); return
                owner = body.get("owner", "")
                heir = body.get("heir", "")
                amount = float(body.get("amount", 0))
                assets = body.get("assets", {})
                delay = int(body.get("execution_delay", 86400))
                witnesses = body.get("witnesses", [])
                if not owner or not heir or amount <= 0:
                    self._error(400, "owner, heir, amount required"); return
                wid = cw.create_will(owner, heir, amount, assets, delay, witnesses)
                if wid:
                    self._json({"success": True, "will_id": wid, "execution_delay_seconds": delay})
                else:
                    self._error(400, "Could not create will (insufficient balance?)")

            elif path == "/will/cancel":
                cw = self.__class__.crypto_will
                if not cw:
                    self._error(503, "CryptoWill not enabled"); return
                wid = body.get("will_id", "")
                owner = body.get("owner", "")
                ok = cw.cancel_will(wid, owner) if wid and owner else False
                if ok:
                    self._json({"success": True})
                else:
                    self._error(400, "Could not cancel will")

            elif path == "/will/execute":
                cw = self.__class__.crypto_will
                if not cw:
                    self._error(503, "CryptoWill not enabled"); return
                wid = body.get("will_id", "")
                force = bool(body.get("force", False))
                if not wid:
                    self._error(400, "will_id required"); return
                ok = cw.execute_will(wid, force=force) if hasattr(cw, "execute_will") else False
                if ok:
                    self._json({"success": True, "will_id": wid, "forced": force})
                else:
                    self._error(400, "Could not execute will")

            # ── Plasma Chain ──────────────────────────────────────────────────
            elif path == "/plasma/deposit":
                pl = self.__class__.plasma
                if not pl:
                    self._error(503, "Plasma not enabled"); return
                from_addr = body.get("from", "")
                amount = float(body.get("amount", 0))
                if not from_addr or amount <= 0:
                    self._error(400, "from and amount required"); return
                did = pl.deposit(from_addr, amount)
                if did:
                    self._json({"success": True, "deposit_id": did, "amount": amount})
                else:
                    self._error(400, "Deposit failed (insufficient L1 balance)")

            elif path == "/plasma/tx":
                pl = self.__class__.plasma
                if not pl:
                    self._error(503, "Plasma not enabled"); return
                from_addr = body.get("from", "")
                to_addr = body.get("to", "")
                amount = float(body.get("amount", 0))
                if not from_addr or not to_addr or amount <= 0:
                    self._error(400, "from, to, amount required"); return
                txh = pl.submit_transaction(from_addr, to_addr, amount)
                if txh:
                    self._json({"success": True, "tx_hash": txh})
                else:
                    self._error(400, "Transfer failed (insufficient L2 balance)")

            elif path == "/plasma/submit-block":
                pl = self.__class__.plasma
                if not pl:
                    self._error(503, "Plasma not enabled"); return
                proposer = body.get("proposer", "operator")
                result = pl.submit_block(proposer)
                if result:
                    self._json({"success": True, "block": result})
                else:
                    st = pl.get_stats() if hasattr(pl, "get_stats") else {}
                    self._error(400, (
                        "No pending transactions "
                        f"(pending={st.get('pending_transactions', 0)}, blocks={st.get('blocks', 0)})"
                    ))

            elif path == "/plasma/exit":
                pl = self.__class__.plasma
                if not pl:
                    self._error(503, "Plasma not enabled"); return
                deposit_id = body.get("deposit_id", "")
                user = body.get("user", "")
                if not deposit_id or not user:
                    self._error(400, "deposit_id and user required"); return
                eid = pl.request_exit(deposit_id, user)
                if eid:
                    self._json({"success": True, "exit_id": eid,
                                "message": "Exit requested. Challenge period: 7 days"})
                else:
                    self._error(400, "Exit failed (deposit not found or not confirmed)")

            # ── WASM VM ───────────────────────────────────────────────────────
            elif path == "/wasm/deploy":
                vm = self.__class__.wasm_vm
                if not vm:
                    self._error(503, "WASM VM not enabled"); return
                code = body.get("code", "")
                owner = body.get("owner", "")
                name = body.get("name", "")
                init_params = body.get("init_params", {})
                if not code or not owner:
                    self._error(400, "code and owner required"); return
                addr = vm.deploy(code, owner, name, init_params)
                if not addr:
                    self._error(400, "Deploy failed (insufficient balance for deploy fee?)"); return
                self._json({"success": True, "contract_address": addr, "name": name or f"Contract_{addr[:8]}"})

            elif path == "/wasm/call":
                vm = self.__class__.wasm_vm
                if not vm:
                    self._error(503, "WASM VM not enabled"); return
                contract_addr = body.get("contract", "")
                fn = body.get("function", "")
                params = body.get("params", {})
                caller = body.get("caller", "")
                value = float(body.get("value", 0))
                if not contract_addr or not fn:
                    self._error(400, "contract and function required"); return
                result = vm.call(contract_addr, fn, params, caller, value)
                self._json(result)

            # ── AI Agent Manager ──────────────────────────────────────────────
            elif path == "/ai-agent/create":
                am = self.__class__.ai_manager
                if not am:
                    self._error(503, "AI Manager not enabled"); return
                name = body.get("name", "")
                owner = body.get("owner", "")
                agent_type = body.get("type", "transformer")
                if not name or not owner:
                    self._error(400, "name and owner required"); return
                aid = am.create_agent(name, owner, agent_type)
                if not aid:
                    self._error(400, "Could not create agent (insufficient balance for create fee?)"); return
                self._json({"success": True, "agent_id": aid, "name": name, "type": agent_type})

            elif path == "/ai-agent/predict":
                am = self.__class__.ai_manager
                if not am:
                    self._error(503, "AI Manager not enabled"); return
                agent_id = body.get("agent_id", "")
                market_data = body.get("market_data", {})
                if not agent_id:
                    self._error(400, "agent_id required"); return
                result = am.predict(agent_id, market_data)
                if isinstance(result, dict) and result.get("error"):
                    self._error(404, result.get("error", "Agent not found")); return
                self._json(result)

            elif path == "/ai-agent/analyze":
                am = self.__class__.ai_manager
                if not am:
                    self._error(503, "AI Manager not enabled"); return
                agent_id = body.get("agent_id", "")
                price_history = body.get("price_history", [])
                if not agent_id:
                    self._error(400, "agent_id required"); return
                result = am.analyze(agent_id, price_history)
                if isinstance(result, dict) and result.get("error"):
                    self._error(404, result.get("error", "Agent not found")); return
                self._json(result)

            elif path == "/ai-agent/trade":
                am = self.__class__.ai_manager
                if not am:
                    self._error(503, "AI Manager not enabled"); return
                agent_id = body.get("agent_id", "")
                trade_type = body.get("type", "buy")
                amount = float(body.get("amount", 0))
                price = float(body.get("price", 0))
                if not agent_id or amount <= 0:
                    self._error(400, "agent_id, amount, price required"); return
                result = am.trade(agent_id, trade_type, amount, price)
                if isinstance(result, dict) and result.get("error") == "Trade execution backend not configured":
                    self._error(503, result["error"])
                    return
                if isinstance(result, dict) and result.get("success") is False:
                    status = 404 if result.get("error") == "Agent not found" else 400
                    self._error(status, result.get("error", "Trade failed"))
                    return
                self._json(result)

            # ── Cross-Chain Bridge ────────────────────────────────────────────
            elif path == "/bridge2/transfer":
                rust_br = getattr(self.__class__, "bridge", None)
                cb = self.__class__.cross_bridge
                from_chain = body.get("from_chain", "ethereum")
                to_chain = body.get("to_chain", "absolute")
                from_addr = body.get("from_address", "")
                to_addr = body.get("to_address", "")
                amount = float(body.get("amount", 0))
                l1_tx = (body.get("l1_tx_hash") or "").strip()
                if not from_addr or not to_addr or amount <= 0:
                    self._error(400, "from_address, to_address, amount required"); return
                if _is_production_cfg(cfg) and not (
                    rust_br and getattr(rust_br, "_mode", "") == "rust"
                ):
                    self._error(503, "production bridge requires RustBridge runtime")
                    return
                if rust_br and hasattr(rust_br, "lock_and_bridge"):
                    if to_chain.lower() in ("absolute", "abs"):
                        tx_id = body.get("tx_id") or l1_tx or (
                            "0x" + hashlib.sha256(
                                f"{from_chain}:{from_addr}:{to_addr}:{amount}".encode()
                            ).hexdigest()
                        )
                        result = rust_br.confirm_incoming(
                            tx_id, to_addr, amount, from_chain, l1_tx_hash=l1_tx
                        )
                        self._json({
                            **(result if isinstance(result, dict) else {"success": bool(result)}),
                            "bridge_path": "rust",
                            "direction": "incoming",
                        })
                    else:
                        result = rust_br.lock_and_bridge(
                            from_addr, to_chain, to_addr, amount, l1_tx_hash=l1_tx
                        )
                        self._json({
                            **(result if isinstance(result, dict) else {"success": bool(result)}),
                            "bridge_path": "rust",
                            "direction": "outbound",
                            "hint": "Confirm via POST /bridge/confirm-lock or bridge relayer",
                        })
                    return
                self._error(503, "RustBridge runtime required for bridge transfer")
                return

            # ── Standalone Consensus Engine ───────────────────────────────────
            elif path == "/consensus/engine/attest":
                ce = self.__class__.consensus_engine_standalone
                if not ce:
                    self._error(503, "ConsensusEngine not enabled"); return
                validator_addr = body.get("validator", "")
                slot = int(body.get("slot", 0))
                block_hash = body.get("block_hash", "")
                ok = ce.attest(validator_addr, slot, block_hash) if validator_addr else False
                self._json({"success": ok})

            elif path == "/consensus/engine/advance":
                ce = self.__class__.consensus_engine_standalone
                if not ce:
                    self._error(503, "ConsensusEngine not enabled"); return
                slot = ce.advance_slot()
                self._json({"success": True, "current_slot": slot,
                            "current_epoch": ce.current_epoch})

            # ── Finality Engine ───────────────────────────────────────────────
            elif path == "/finality/process-block":
                fe = self.__class__.finality_engine
                if not fe:
                    self._error(503, "FinalityEngine not enabled"); return
                block_num = int(body.get("block_number", 0))
                block_hash = body.get("block_hash", "")
                validator = body.get("validator", body.get("proposer", ""))
                if not block_hash:
                    self._error(400, "block_number, block_hash required"); return
                result = fe.process_block(block_num, block_hash, validator)
                self._json(result)

            # ── Finality: create checkpoint & attestation ─────────────────────
            elif path == "/finality/checkpoint":
                fe = self.__class__.finality_engine
                if not fe:
                    self._error(503, "FinalityEngine not enabled"); return
                epoch = int(body.get("epoch", 0))
                block_hash = body.get("block_hash", "")
                if hasattr(fe, "create_checkpoint"):
                    result = fe.create_checkpoint(epoch, block_hash)
                    self._json({"success": True, "checkpoint": str(result)})
                else:
                    self._json({"success": False, "error": "not supported"})

            elif path == "/finality/attest":
                fe = self.__class__.finality_engine
                if not fe:
                    self._error(503, "FinalityEngine not enabled"); return
                source = body.get("source_hash", "")
                target = body.get("target_hash", "")
                validator = body.get("validator", "")
                if hasattr(fe, "add_attestation"):
                    ok = fe.add_attestation(source, target, validator)
                    self._json({"success": bool(ok)})
                else:
                    self._json({"success": False, "error": "not supported"})

            # ── Plasma finalize exit ──────────────────────────────────────────
            elif path == "/plasma/finalize-exit":
                plasma = self.__class__.plasma
                if not plasma:
                    self._error(503, "Plasma not enabled"); return
                exit_id = body.get("exit_id", body.get("tx_id", ""))
                force = bool(body.get("force", False))
                if hasattr(plasma, "finalize_exit"):
                    ok = plasma.finalize_exit(exit_id, force=force)
                    if ok:
                        self._json({"success": True, "exit_id": exit_id, "forced": force})
                    else:
                        self._error(400, "Could not finalize exit")
                else:
                    self._json({"success": False, "error": "finalize_exit not available"})

            # ── Devnet faucet (ABS credit for testing) ───────────────────────
            elif path == "/devnet/faucet":
                if getattr(cfg, "deployment_mode", "dev") == "prod":
                    self._error(403, "faucet disabled in production"); return
                db = self.__class__.db
                if not db:
                    self._error(503, "database unavailable"); return
                address = (body.get("address", "") or "").strip()
                amount = float(body.get("amount", 100))
                if not address:
                    self._error(400, "address required"); return
                if amount <= 0 or amount > 1000:
                    self._error(400, "amount must be 0 < amount <= 1000"); return
                db.update_balance(address, amount)
                self._json({
                    "success": True,
                    "address": address,
                    "credited": amount,
                    "balance": db.get_balance(address),
                })

            elif path == "/devnet/pool-spend":
                if getattr(cfg, "deployment_mode", "dev") == "prod":
                    self._error(403, "pool-spend disabled in production"); return
                pl = self.__class__.pool_locks
                db = self.__class__.db
                if not pl or not db or not bc:
                    self._error(503, "pool locks or database unavailable"); return
                try:
                    result = _handle_devnet_pool_spend(body, bc, db, cfg, pl)
                    self._json(result)
                except ValueError as exc:
                    self._error(400, str(exc))

            elif path == "/pools/spend":
                if getattr(cfg, "deployment_mode", "dev") == "prod":
                    pl = self.__class__.pool_locks
                    db = self.__class__.db
                    if not pl or not db or not bc:
                        self._error(503, "pool locks or database unavailable"); return
                    try:
                        result = _handle_devnet_pool_spend(body, bc, db, cfg, pl)
                        self._json(result)
                    except ValueError as exc:
                        self._error(400, str(exc))
                else:
                    self._error(403, "use /devnet/pool-spend in dev mode")

            elif path == "/oracles/feeds/submit":
                registry = self.__class__.oracle_registry
                if not registry:
                    self._error(503, "Oracle registry not enabled"); return
                symbol = body.get("symbol", "")
                value = float(body.get("value", 0))
                source = body.get("source", "reporter")
                reporter = body.get("reporter", body.get("from", ""))
                sig = self.headers.get("X-Bridge-Oracle-Signature", body.get("signature", ""))
                result = registry.submit_feed(
                    symbol=symbol,
                    value=value,
                    source=source,
                    reporter=reporter,
                    signature=sig,
                    payload=body if isinstance(body, dict) else None,
                    require_signature=True,
                )
                if not result.get("ok"):
                    self._error(400, result.get("error", "submit failed")); return
                self._json(result)

            elif path == "/bridge/oracle/confirm-lock":
                br = _bridge_for_request(self.__class__, cfg)
                if not br:
                    self._error(503, "Bridge not enabled"); return
                tx_hash = body.get("tx_hash", body.get("tx_id", ""))
                if hasattr(br, "confirm_lock"):
                    self._json(br.confirm_lock(tx_hash))
                else:
                    self._error(501, "confirm_lock not available")

            elif path == "/bridge/oracle/incoming":
                br = _bridge_for_request(self.__class__, cfg)
                if not br:
                    self._error(503, "Bridge not enabled"); return
                tx_id = body.get("tx_id", body.get("tx_hash", ""))
                recipient = body.get("recipient", body.get("to_address", ""))
                amount = float(body.get("amount", 0))
                from_chain = body.get("from_chain", body.get("source_chain", "ethereum"))
                if hasattr(br, "confirm_incoming"):
                    l1_tx = body.get("l1_tx_hash", "").strip()
                    result = br.confirm_incoming(
                        tx_id, recipient, amount, from_chain, l1_tx_hash=l1_tx
                    )
                    self._json(result if isinstance(result, dict) else {"success": bool(result)})
                else:
                    self._json({"success": False, "error": "confirm not available"})

            elif path == "/bridge/oracle/l1-register":
                if _is_production_cfg(cfg) and not _bridge_for_request(self.__class__, cfg):
                    self._error(503, "production bridge requires RustBridge runtime")
                    return
                l1_tx = body.get("l1_tx_hash", body.get("tx_hash", "")).strip()
                abs_lock = body.get("abs_lock_tx", body.get("lock_tx_hash", "")).strip()
                chain = body.get("chain", body.get("from_chain", "ethereum"))
                if not l1_tx:
                    self._error(400, "l1_tx_hash required"); return
                if not db or not hasattr(db, "get_meta"):
                    self._error(503, "Database not available"); return
                proofs = db.get_meta("bridge_l1_proofs", [])
                if not isinstance(proofs, list):
                    proofs = []
                entry = {
                    "l1_tx_hash": l1_tx,
                    "abs_lock_tx": abs_lock,
                    "chain": chain,
                    "contract": body.get("contract", body.get("l1_contract", "")),
                    "amount": body.get("amount"),
                    "registered_at": int(time.time()),
                }
                proofs = [p for p in proofs if p.get("l1_tx_hash") != l1_tx]
                proofs.append(entry)
                db.set_meta("bridge_l1_proofs", proofs[-500:])
                br = getattr(self.__class__, "bridge", None)
                recipient = (body.get("recipient") or body.get("to_address") or "").strip()
                amount = float(body.get("amount", 0) or 0)
                if br and hasattr(br, "enqueue_l1_incoming") and recipient and amount > 0:
                    br.enqueue_l1_incoming(
                        l1_tx,
                        recipient,
                        amount,
                        chain,
                        tx_id=body.get("tx_id", l1_tx),
                    )
                    entry["queued_incoming"] = True
                elif br and abs_lock and hasattr(br, "_enqueue_l1_outbound"):
                    br._enqueue_l1_outbound(abs_lock, l1_tx, chain)
                    entry["queued_outbound"] = True
                self._json({"success": True, "registered": entry, "count": len(proofs)})

            elif path == "/bridge/oracle/l1-queue-sync":
                if _is_production_cfg(cfg) and not _bridge_for_request(self.__class__, cfg):
                    self._error(503, "production bridge requires RustBridge runtime")
                    return
                from bridge.l1_rpc import save_l1_queue

                qpath = getattr(cfg, "bridge_l1_queue_path", "data/bridge_l1_queue.json")
                outbound = body.get("outbound", [])
                incoming = body.get("incoming", [])
                if not isinstance(outbound, list) or not isinstance(incoming, list):
                    self._error(400, "outbound/incoming must be lists")
                    return
                queue = {
                    "outbound": list(outbound)[-500:],
                    "incoming": list(incoming)[-500:],
                }
                save_l1_queue(qpath, queue)
                self._json({
                    "success": True,
                    "path": qpath,
                    "outbound": len(queue["outbound"]),
                    "incoming": len(queue["incoming"]),
                })

            # ── Bridge: lock, confirm, refund ─────────────────────────────────
            elif path == "/bridge/lock":
                br = _bridge_for_request(self.__class__, cfg)
                if not br:
                    self._error(503, "Bridge not enabled"); return
                amount = float(body.get("amount", 0))
                from_addr = body.get("from_address", body.get("from", ""))
                to_addr = body.get("to_address", body.get("to", ""))
                target_chain = body.get("target_chain", body.get("to_chain", "ethereum"))
                l1_tx = (body.get("l1_tx_hash") or "").strip()
                if hasattr(br, "lock_and_bridge"):
                    result = br.lock_and_bridge(
                        from_addr, target_chain, to_addr, amount, l1_tx_hash=l1_tx
                    )
                    self._json(result if isinstance(result, dict) else {"success": bool(result)})
                elif hasattr(br, "transfer"):
                    result = br.transfer(from_addr, body.get("to_address",""), amount, target_chain)
                    self._json(result if isinstance(result, dict) else {"success": bool(result)})
                else:
                    self._json({"success": False, "error": "lock not available"})

            elif path == "/bridge/confirm":
                br = _bridge_for_request(self.__class__, cfg)
                if not br:
                    self._error(503, "Bridge not enabled"); return
                tx_id = body.get("tx_id", body.get("tx_hash", ""))
                recipient = body.get("recipient", body.get("to_address", ""))
                amount = float(body.get("amount", 0))
                from_chain = body.get("from_chain", body.get("source_chain", "ethereum"))
                if hasattr(br, "confirm_incoming"):
                    l1_tx = body.get("l1_tx_hash", "").strip()
                    result = br.confirm_incoming(
                        tx_id, recipient, amount, from_chain, l1_tx_hash=l1_tx
                    )
                    self._json(result if isinstance(result, dict) else {"success": bool(result)})
                else:
                    self._json({"success": False, "error": "confirm not available"})

            elif path == "/bridge/confirm-lock":
                br = _bridge_for_request(self.__class__, cfg)
                if not br:
                    self._error(503, "Bridge not enabled"); return
                tx_hash = body.get("tx_hash", body.get("tx_id", ""))
                if hasattr(br, "confirm_lock"):
                    self._json(br.confirm_lock(tx_hash))
                else:
                    self._error(501, "confirm_lock not available")

            elif path == "/bridge/confirm-pending" or path == "/bridge/dev-confirm-pending":
                if getattr(cfg, "deployment_mode", "dev") == "prod":
                    self._error(403, "batch confirm disabled in production"); return
                br = _bridge_for_request(self.__class__, cfg)
                if not br:
                    self._error(503, "Bridge not enabled"); return
                if hasattr(br, "confirm_pending_locks"):
                    self._json(br.confirm_pending_locks())
                else:
                    self._error(501, "confirm_pending not available")

            elif path == "/bridge/refund":
                br = _bridge_for_request(self.__class__, cfg)
                if not br:
                    self._error(503, "Bridge not enabled"); return
                tx_id = body.get("tx_id", "")
                if hasattr(br, "refund"):
                    result = br.refund(tx_id)
                    self._json(result if isinstance(result, dict) else {"success": bool(result)})
                else:
                    self._json({"success": False, "error": "refund not available"})

            # ── AI Agent: deactivate ──────────────────────────────────────────
            elif path == "/ai-agent/deactivate":
                am = self.__class__.ai_manager
                if not am:
                    self._error(503, "AI Manager not enabled"); return
                agent_id = body.get("agent_id", "")
                if not agent_id:
                    self._error(400, "agent_id required"); return
                if hasattr(am, "deactivate"):
                    ok = am.deactivate(agent_id)
                    self._json({"success": bool(ok), "agent_id": agent_id})
                elif hasattr(am, "agents") and agent_id in am.agents:
                    am.agents[agent_id].active = False
                    self._json({"success": True, "agent_id": agent_id})
                else:
                    self._json({"success": False, "error": "Agent not found"})

            # ── Smart Account: session keys & guardians ───────────────────────
            elif path == "/smart-account/session-keys":
                sa = self.__class__.smart_accounts
                account_address = body.get("account_address", "")
                if sa and hasattr(sa, "get_session_keys"):
                    keys = sa.get_session_keys(account_address)
                    self._json({"session_keys": keys})
                else:
                    self._json({"session_keys": []})

            elif path == "/smart-account/add-guardian":
                sa = self.__class__.smart_accounts
                if not sa:
                    self._error(503, "SmartAccounts not enabled"); return
                account_address = body.get("account_address", "")
                guardian = body.get("guardian_address", "")
                if hasattr(sa, "add_guardian"):
                    result = sa.add_guardian(account_address, guardian)
                    self._json({"success": bool(result)})
                else:
                    self._json({"success": False, "error": "not supported"})

            elif path == "/smart-account/revoke-session-key":
                sa = self.__class__.smart_accounts
                if not sa:
                    self._error(503, "SmartAccounts not enabled"); return
                account_address = body.get("account_address", "")
                key = body.get("session_key", "")
                if hasattr(sa, "revoke_session_key"):
                    result = sa.revoke_session_key(account_address, key)
                    self._json({"success": bool(result)})
                else:
                    self._json({"success": False, "error": "not supported"})

            # ── Slashing: record vote / add validator ─────────────────────────
            elif path == "/slashing/record-vote":
                se = self.__class__.slashing_engine
                if not se:
                    self._error(503, "SlashingEngine not enabled"); return
                validator = body.get("validator", "")
                block_hash = body.get("block_hash", "")
                epoch = int(body.get("epoch", 0))
                if hasattr(se, "record_vote"):
                    result = se.record_vote(validator, epoch, block_hash)
                    self._json({"success": True, "slashed": bool(result) if result else False})
                else:
                    self._json({"success": False, "error": "record_vote not available"})

            elif path == "/slashing/add-validator":
                se = self.__class__.slashing_engine
                if not se:
                    self._error(503, "SlashingEngine not enabled"); return
                validator = body.get("validator_address", body.get("validator", ""))
                stake = float(body.get("stake", 32.0))
                if not validator:
                    self._error(400, "validator_address required"); return
                if hasattr(se, "register_validator"):
                    se.register_validator(validator, stake)
                    self._json({"success": True, "validator": validator, "stake": stake})
                elif hasattr(se, "add_validator"):
                    se.add_validator(validator, stake)
                    self._json({"success": True, "validator": validator})
                else:
                    self._json({"success": False, "error": "add_validator not available"})

            # ── Validator Registry: register ──────────────────────────────────
            elif path == "/validators/register":
                vr = self.__class__.validator_registry
                if not vr:
                    self._error(503, "ValidatorRegistry not enabled"); return
                address = body.get("address", body.get("validator_address", ""))
                stake = float(body.get("stake", 32.0))
                if not address:
                    self._error(400, "address required"); return
                if hasattr(vr, "register"):
                    vr.register(address, stake)
                    self._json({"success": True, "address": address, "stake": stake})
                elif hasattr(vr, "add"):
                    vr.add(address, stake)
                    self._json({"success": True, "address": address})
                else:
                    self._json({"success": False, "error": "register not available"})

            # ── Beacon Finality: vote ─────────────────────────────────────────
            elif path == "/beacon/vote":
                bf = self.__class__.beacon_finality
                if not bf:
                    self._error(503, "BeaconFinality not enabled"); return
                validator = body.get("validator", "")
                source = body.get("source", 0)
                target = body.get("target", 0)
                if hasattr(bf, "add_vote"):
                    result = bf.add_vote(validator, source, target)
                    self._json({"success": bool(result), "validator": validator})
                else:
                    self._json({"success": False, "error": "add_vote not available"})

            # ── LMD-GHOST: update ─────────────────────────────────────────────
            elif path == "/lmd/update":
                lmd = self.__class__.lmd_table
                if not lmd:
                    self._error(503, "LMDTable not enabled"); return
                validator = body.get("validator", "")
                block_hash = body.get("block_hash", "")
                slot = int(body.get("slot", 0))
                if hasattr(lmd, "update"):
                    lmd.update(validator, slot, block_hash)
                    self._json({"success": True})
                else:
                    self._json({"success": False, "error": "update not available"})

            # ── SPHINCS+ sign/verify ──────────────────────────────────────────
            elif path == "/pq/sphincs/sign":
                sph = self.__class__.sphincs
                if not sph:
                    self._error(503, "SPHINCS+ not enabled"); return
                message = body.get("message", "")
                private_key = body.get("private_key", "")
                if hasattr(sph, "sign"):
                    try:
                        private_key_bytes = bytes.fromhex(private_key.replace("0x", ""))
                    except ValueError:
                        self._error(400, "private_key must be hex"); return
                    try:
                        sig = sph.sign(message.encode() if isinstance(message,str) else message,
                                       private_key_bytes)
                    except NotImplementedError as e:
                        self._error(501, str(e)); return
                    signature_hex = sig.hex() if isinstance(sig, bytes) else str(sig)
                    self._json({"signature": signature_hex, "algorithm": "SPHINCS+"})
                else:
                    self._error(501, "sign not available")

            elif path == "/pq/sphincs/verify":
                sph = self.__class__.sphincs
                if not sph:
                    self._error(503, "SPHINCS+ not enabled"); return
                message = body.get("message", "")
                signature = body.get("signature", "")
                public_key = body.get("public_key", "")
                if hasattr(sph, "verify"):
                    try:
                        sig_bytes = bytes.fromhex(signature.replace("0x", ""))
                        pub_bytes = bytes.fromhex(public_key.replace("0x", ""))
                    except ValueError:
                        self._error(400, "signature and public_key must be hex"); return
                    ok = sph.verify(message.encode() if isinstance(message,str) else message,
                                    sig_bytes, pub_bytes)
                    self._json({"valid": bool(ok), "algorithm": "SPHINCS+"})
                else:
                    self._error(501, "verify not available")

            # ── Finality finalize checkpoint ─────────────────────────────────
            elif path == "/finality/finalize":
                fe = self.__class__.finality_engine
                if not fe:
                    self._error(503, "FinalityEngine not enabled"); return
                checkpoint_id = body.get("checkpoint_id", "")
                if hasattr(fe, "finalize_checkpoint"):
                    result = fe.finalize_checkpoint(checkpoint_id)
                    self._json({"success": bool(result), "checkpoint_id": checkpoint_id})
                else:
                    self._json({"success": False, "error": "finalize_checkpoint not available"})

            # ── P2P operational reconnect (Wave 61) ──────────────────────────
            elif path == "/p2p/reconnect":
                p2p = self.__class__.p2p
                if not p2p or not hasattr(p2p, "reconnect_known_peers_sync"):
                    self._error(503, "P2P reconnect not available"); return
                timeout = max(5.0, min(60.0, float(body.get("timeout", 20) or 20)))
                detail = p2p.reconnect_known_peers_sync(timeout=timeout)
                topology = p2p.get_topology() if hasattr(p2p, "get_topology") else {}
                self._json({
                    "success": bool(detail.get("ok")),
                    "message": "P2P reconnect finished",
                    "detail": detail,
                    "topology": topology,
                })

            # ── Sync: fast sync, add/remove peer ─────────────────────────────
            elif path == "/sync/fast-sync":
                p2p = self.__class__.p2p
                sync_timeout = max(30.0, min(600.0, float(body.get("timeout", 90) or 90)))
                if p2p and hasattr(p2p, "catch_up_sync"):
                    result = p2p.catch_up_sync(timeout=sync_timeout)
                    self._json({
                        "success": bool(result.get("ok")),
                        "local_height": self.__class__.blockchain.get_height(),
                        "message": "P2P catch-up finished",
                        "detail": result,
                    })
                    return
                if p2p and hasattr(p2p, "trigger_catch_up"):
                    p2p.trigger_catch_up()
                    self._json({
                        "success": True,
                        "local_height": self.__class__.blockchain.get_height(),
                        "message": "P2P catch-up scheduled",
                    })
                    return
                se = self.__class__.sync_engine
                if not se:
                    self._error(503, "SyncEngine not enabled"); return
                target_block = int(body.get("target_block", 0))
                if hasattr(se, "fast_sync"):
                    result = se.fast_sync(target_block)
                    self._json({"success": bool(result), "target_block": target_block})
                else:
                    self._json({"success": False, "error": "fast_sync not available"})

            elif path == "/sync/reconcile":
                p2p = self.__class__.p2p
                if not p2p or not hasattr(p2p, "trigger_reconcile"):
                    self._error(503, "P2P reconcile not available"); return
                sync_timeout = max(30.0, min(600.0, float(body.get("timeout", 90) or 90)))
                if hasattr(p2p, "reconcile_peers_sync"):
                    detail = p2p.reconcile_peers_sync(timeout=sync_timeout)
                else:
                    p2p.trigger_reconcile()
                    time.sleep(2)
                    detail = {"ok": True, "message": "scheduled"}
                sync = _build_sync_status(
                    self.__class__.sync_engine, p2p,
                    self.__class__.blockchain, cfg,
                )
                self._json({
                    "success": bool(detail.get("ok", True)),
                    "message": "P2P reconcile finished",
                    "detail": detail,
                    "sync": sync,
                })

            elif path == "/chain/consistency/repair":
                if not bc or not hasattr(bc, "ensure_state_at_tip"):
                    self._error(503, "state repair not available"); return
                repaired = bc.ensure_state_at_tip()
                harness = _build_state_consistency_harness(
                    self.__class__.p2p, bc, cfg, self.__class__.db
                )
                self._json({
                    "success": bool(repaired),
                    "repaired": bool(repaired),
                    "height": bc.get_height() if hasattr(bc, "get_height") else 0,
                    "harness": harness,
                })

            elif path == "/testnet/reorg-exercise":
                if getattr(cfg, "deployment_mode", "dev") == "prod":
                    self._error(403, "reorg-exercise is dev-only"); return
                if not bc or not hasattr(bc, "ensure_state_at_tip"):
                    self._error(503, "blockchain not available"); return
                before_root = bc.get_state_root() if hasattr(bc, "get_state_root") else ""
                before_h = bc.get_height() if hasattr(bc, "get_height") else 0
                replay_ok = bc.ensure_state_at_tip()
                after_root = bc.get_state_root() if hasattr(bc, "get_state_root") else ""
                harness = _build_state_consistency_harness(
                    self.__class__.p2p, bc, cfg, self.__class__.db
                )
                self._json({
                    "action": "canonical_replay_drill",
                    "height": before_h,
                    "state_root_before": before_root,
                    "state_root_after": after_root,
                    "roots_match": bool(before_root and before_root == after_root),
                    "replay_ok": bool(replay_ok),
                    "harness_healthy": bool(harness.get("harness_healthy")),
                    "reorg_safe": bool(
                        before_root == after_root and harness.get("harness_healthy")
                    ),
                    "api_wave": 61,
                })

            elif path == "/testnet/fork-exercise":
                if getattr(cfg, "deployment_mode", "dev") == "prod":
                    self._error(403, "fork-exercise is dev-only"); return
                p2p = self.__class__.p2p
                db = self.__class__.db
                self._json(_build_testnet_fork_exercise(p2p, bc, cfg, db, run_reconcile=True))

            elif path == "/sync/add-peer":
                se = self.__class__.sync_engine
                if not se:
                    self._error(503, "SyncEngine not enabled"); return
                peer_id = body.get("peer_id", "")
                peer_addr = body.get("address", "")
                if hasattr(se, "add_peer"):
                    se.add_peer(peer_id, peer_addr)
                    self._json({"success": True, "peer_id": peer_id})
                else:
                    self._json({"success": False, "error": "add_peer not available"})

            elif path == "/sync/remove-peer":
                se = self.__class__.sync_engine
                if not se:
                    self._error(503, "SyncEngine not enabled"); return
                peer_id = body.get("peer_id", "")
                if hasattr(se, "remove_peer"):
                    se.remove_peer(peer_id)
                    self._json({"success": True, "peer_id": peer_id})
                else:
                    self._json({"success": False, "error": "remove_peer not available"})

            # ── Sharding: add transaction ─────────────────────────────────────
            elif path == "/sharding/add-tx":
                sh = self.__class__.sharding
                if not sh:
                    self._error(503, "Sharding not enabled"); return
                tx = body.get("transaction", body)
                if hasattr(sh, "add_transaction"):
                    result = sh.add_transaction(tx)
                    self._json(result if isinstance(result, dict) else {"success": bool(result)})
                else:
                    self._json({"success": False, "error": "add_transaction not available"})

            elif path == "/sharding/process-cross":
                sh = self.__class__.sharding
                if not sh:
                    self._error(503, "Sharding not enabled"); return
                if hasattr(sh, "process_cross_shard_transactions"):
                    result = sh.process_cross_shard_transactions()
                    self._json(result if isinstance(result, dict) else {"processed": result, "success": True})
                else:
                    self._json({"success": False, "error": "process_cross_shard_transactions not available"})

            elif path == "/sharding/reshard/plan":
                sh = self.__class__.sharding
                if not sh or not hasattr(sh, "plan_reshard"):
                    self._error(503, "Sharding coordinator not enabled"); return
                new_shards = int(body.get("new_num_shards", body.get("to_shards", 0)) or 0)
                epoch = int(body.get("effective_epoch", 0) or 0)
                plan = sh.plan_reshard(new_shards, epoch)
                self._json({"success": True, "plan": plan})

            elif path == "/sharding/reshard/discover":
                sh = self.__class__.sharding
                if not sh or not hasattr(sh, "discover_reshard_migrations"):
                    self._error(503, "Sharding coordinator not enabled"); return
                count = sh.discover_reshard_migrations()
                self._json({"success": True, "queued": count})

            elif path == "/sharding/reshard/apply":
                sh = self.__class__.sharding
                if not sh or not hasattr(sh, "apply_reshard"):
                    self._error(503, "Sharding coordinator not enabled"); return
                ok = sh.apply_reshard()
                self._json({"success": ok, "num_shards": getattr(sh, "num_shards", 0)})

            elif path == "/sharding/reshard/process-migrations":
                sh = self.__class__.sharding
                if not sh or not hasattr(sh, "process_reshard_migrations"):
                    self._error(503, "Sharding coordinator not enabled"); return
                limit = int(body.get("limit", 20) or 20)
                result = sh.process_reshard_migrations(limit=limit)
                self._json({"success": True, **result})

            elif path == "/sharding/cross-shard/ack":
                sh = self.__class__.sharding
                if not sh or not hasattr(sh, "submit_cross_shard_validator_ack"):
                    self._error(503, "Sharding coordinator not enabled"); return
                tx_id = str(body.get("tx_id", "") or "").strip()
                shard_id = int(body.get("shard_id", body.get("to_shard", -1)) or -1)
                validator_id = str(body.get("validator_id", "") or "").strip()
                if not tx_id or shard_id < 0:
                    self._error(400, "tx_id and shard_id required"); return
                ok = sh.submit_cross_shard_validator_ack(tx_id, shard_id, validator_id)
                quorum = sh.cross_shard_quorum_status(tx_id) if hasattr(sh, "cross_shard_quorum_status") else None
                self._json({"success": ok, "quorum": quorum})

            elif path == "/sharding/committees/load":
                sh = self.__class__.sharding
                if not sh or not hasattr(sh, "load_shard_committees"):
                    self._error(503, "Sharding coordinator not enabled"); return
                manifest = body.get("manifest")
                committees = body.get("committees")
                loaded = 0
                if isinstance(manifest, dict) and hasattr(sh, "load_validators_from_manifest"):
                    loaded = sh.load_validators_from_manifest(manifest)
                elif isinstance(committees, dict):
                    parsed = {
                        int(k): [str(v) for v in vals]
                        for k, vals in committees.items()
                        if isinstance(vals, list)
                    }
                    loaded = sh.load_shard_committees(parsed)
                else:
                    self._error(400, "committees or manifest object required"); return
                coord = getattr(sh, "coordinator", None)
                self._json({
                    "success": True,
                    "loaded": loaded,
                    "coordinator": coord.status() if coord and hasattr(coord, "status") else None,
                })

            # ── Smart account: request/approve recovery ───────────────────────
            elif path == "/smart-account/request-recovery":
                sa = self.__class__.smart_accounts
                if not sa:
                    self._error(503, "SmartAccounts not enabled"); return
                account_address = body.get("account_address", "")
                new_owner = body.get("new_owner", "")
                if hasattr(sa, "request_recovery"):
                    result = sa.request_recovery(account_address, new_owner)
                    self._json({"success": bool(result)})
                else:
                    self._json({"success": False, "error": "request_recovery not available"})

            elif path == "/smart-account/approve-recovery":
                sa = self.__class__.smart_accounts
                if not sa:
                    self._error(503, "SmartAccounts not enabled"); return
                account_address = body.get("account_address", "")
                guardian = body.get("guardian_address", "")
                if hasattr(sa, "approve_recovery"):
                    result = sa.approve_recovery(account_address, guardian)
                    self._json({"success": bool(result)})
                else:
                    self._json({"success": False, "error": "approve_recovery not available"})

            elif path == "/smart-account/execute-recovery":
                sa = self.__class__.smart_accounts
                if not sa:
                    self._error(503, "SmartAccounts not enabled"); return
                account_address = body.get("account_address", "")
                if hasattr(sa, "execute_recovery"):
                    result = sa.execute_recovery(account_address)
                    self._json({"success": bool(result)})
                else:
                    self._json({"success": False, "error": "execute_recovery not available"})

            # ── Smart account: remove guardian, approve guardian, unlink, delete ─
            elif path == "/smart-account/remove-guardian":
                sa = self.__class__.smart_accounts
                if not sa:
                    self._error(503, "SmartAccounts not enabled"); return
                account_address = body.get("account_address", "")
                guardian_address = body.get("guardian_address", "")
                if hasattr(sa, "remove_guardian"):
                    result = sa.remove_guardian(account_address, guardian_address)
                    self._json({"success": bool(result)})
                else:
                    self._json({"success": False, "error": "remove_guardian not available"})

            elif path == "/smart-account/approve-guardian":
                sa = self.__class__.smart_accounts
                if not sa:
                    self._error(503, "SmartAccounts not enabled"); return
                account_address = body.get("account_address", "")
                guardian_address = body.get("guardian_address", "")
                if hasattr(sa, "approve_guardian"):
                    result = sa.approve_guardian(account_address, guardian_address)
                    self._json({"success": bool(result)})
                else:
                    self._json({"success": False, "error": "approve_guardian not available"})

            elif path == "/smart-account/unlink-social":
                sa = self.__class__.smart_accounts
                if not sa:
                    self._error(503, "SmartAccounts not enabled"); return
                account_address = body.get("account_address", "")
                provider = body.get("provider", "")
                if hasattr(sa, "unlink_social_account"):
                    result = sa.unlink_social_account(account_address, provider)
                    self._json({"success": bool(result)})
                else:
                    self._json({"success": False, "error": "unlink_social_account not available"})

            elif path == "/smart-account/delete":
                sa = self.__class__.smart_accounts
                if not sa:
                    self._error(503, "SmartAccounts not enabled"); return
                account_address = body.get("account_address", "")
                if not account_address:
                    self._error(400, "account_address required"); return
                if hasattr(sa, "delete_account"):
                    result = sa.delete_account(account_address)
                    self._json({"success": bool(result)})
                elif hasattr(sa, "accounts") and account_address in sa.accounts:
                    del sa.accounts[account_address]
                    self._json({"success": True, "deleted": account_address})
                else:
                    self._json({"success": False, "error": "Account not found"})

            # ── Smart account: get social logins ──────────────────────────────
            elif path == "/smart-account/social-logins":
                sa = self.__class__.smart_accounts
                account_address = body.get("account_address", "")
                if sa and hasattr(sa, "get_social_logins"):
                    logins = sa.get_social_logins(account_address)
                    self._json({"social_logins": logins})
                else:
                    self._json({"social_logins": []})

            # ── Sharding: register node, mine shard ──────────────────────────
            elif path == "/sharding/register-node":
                sh = self.__class__.sharding
                if not sh:
                    self._error(503, "Sharding not enabled"); return
                node_id = body.get("node_id", "")
                shard_id = int(body.get("shard_id", 0))
                if hasattr(sh, "register_node"):
                    ok = sh.register_node(node_id, shard_id)
                    self._json({"success": bool(ok), "node_id": node_id, "shard_id": shard_id})
                else:
                    self._json({"success": False, "error": "register_node not available"})

            elif path == "/sharding/mine":
                sh = self.__class__.sharding
                if not sh:
                    self._error(503, "Sharding not enabled"); return
                shard_id = int(body.get("shard_id", 0))
                miner = body.get("miner", "")
                if hasattr(sh, "mine_shard_block"):
                    result = sh.mine_shard_block(shard_id, miner)
                    self._json(result if isinstance(result, dict) else {"success": bool(result)})
                else:
                    self._json({"success": False, "error": "mine_shard_block not available"})

            # ── PQ hybrid operations ──────────────────────────────────────────
            elif path == "/pq/hybrid-sign":
                pq = self.__class__.pq_manager
                if not pq:
                    self._error(503, "PQ not enabled"); return
                message = body.get("message", "")
                private_key = body.get("private_key", "")
                if hasattr(pq, "hybrid_sign"):
                    try:
                        sig = pq.hybrid_sign(message, private_key)
                    except NotImplementedError as e:
                        self._error(501, str(e)); return
                    self._json({"signature": str(sig), "algorithm": "hybrid"})
                else:
                    self._error(501, "hybrid_sign not available in PQ manager")

            elif path == "/pq/hybrid-encrypt":
                pq = self.__class__.pq_manager
                if not pq:
                    self._error(503, "PQ not enabled"); return
                message = body.get("message", "")
                public_key = body.get("public_key", "")
                if hasattr(pq, "hybrid_encrypt"):
                    try:
                        ciphertext = pq.hybrid_encrypt(message, public_key)
                    except NotImplementedError as e:
                        self._error(501, str(e)); return
                    self._json({"ciphertext": str(ciphertext), "algorithm": "kyber_hybrid"})
                else:
                    self._error(501, "hybrid_encrypt not available")

            # ── PQ hybrid decrypt ─────────────────────────────────────────────
            elif path == "/pq/hybrid-decrypt":
                pq = self.__class__.pq_manager
                ciphertext = body.get("ciphertext", "")
                private_key = body.get("private_key", "")
                if pq and hasattr(pq, "hybrid_decrypt"):
                    try:
                        plaintext = pq.hybrid_decrypt(ciphertext, private_key)
                    except NotImplementedError as e:
                        self._error(501, str(e)); return
                    self._json({"plaintext": str(plaintext)})
                else:
                    self._error(501, "hybrid_decrypt not available")

            # ── Smart account: register, add/remove auth, settings ───────────
            elif path == "/smart-account/register":
                sa = self.__class__.smart_accounts
                if not sa:
                    self._error(503, "SmartAccounts not enabled"); return
                owner = body.get("owner_address", body.get("owner", ""))
                if not owner:
                    self._error(400, "owner_address required"); return
                if hasattr(sa, "register_account"):
                    result = sa.register_account(owner)
                    self._json(result if isinstance(result, dict) else {"success": bool(result), "owner": owner})
                elif hasattr(sa, "create_account"):
                    result = sa.create_account(owner, body.get("auth_method","basic"))
                    self._json(result if isinstance(result, dict) else {"success": bool(result)})
                else:
                    self._json({"success": False, "error": "register not available"})

            elif path == "/smart-account/add-auth":
                sa = self.__class__.smart_accounts
                if not sa:
                    self._error(503, "SmartAccounts not enabled"); return
                account_address = body.get("account_address", "")
                auth_method = body.get("auth_method", "")
                credential = body.get("credential", "")
                if hasattr(sa, "add_auth_method"):
                    result = sa.add_auth_method(account_address, auth_method, credential)
                    self._json({"success": bool(result)})
                else:
                    self._json({"success": False, "error": "add_auth_method not available"})

            elif path == "/smart-account/remove-auth":
                sa = self.__class__.smart_accounts
                if not sa:
                    self._error(503, "SmartAccounts not enabled"); return
                account_address = body.get("account_address", "")
                auth_method = body.get("auth_method", "")
                if hasattr(sa, "remove_auth_method"):
                    result = sa.remove_auth_method(account_address, auth_method)
                    self._json({"success": bool(result)})
                else:
                    self._json({"success": False, "error": "remove_auth_method not available"})

            elif path == "/smart-account/update-settings":
                sa = self.__class__.smart_accounts
                if not sa:
                    self._error(503, "SmartAccounts not enabled"); return
                account_address = body.get("account_address", "")
                settings = body.get("settings", {})
                if hasattr(sa, "update_settings"):
                    result = sa.update_settings(account_address, settings)
                    self._json({"success": bool(result)})
                else:
                    self._json({"success": False, "error": "update_settings not available"})

            # ── PQ decapsulate ────────────────────────────────────────────────
            elif path == "/pq/decapsulate":
                pq = self.__class__.pq_manager
                ciphertext = body.get("ciphertext", "")
                private_key = body.get("private_key", "")
                algo = body.get("algo", "kyber")
                if pq and hasattr(pq, "decapsulate"):
                    result = pq.decapsulate(ciphertext, private_key, algo)
                    self._json({"shared_secret": str(result), "algorithm": algo})
                else:
                    self._json({"enabled": bool(pq), "error": "decapsulate not available"})

            # ── Smart account authenticate ────────────────────────────────────
            elif path == "/smart-account/authenticate":
                sa = self.__class__.smart_accounts
                account_address = body.get("account_address", "")
                credential = body.get("credential", "")
                auth_method = body.get("auth_method", "basic")
                if sa and hasattr(sa, "authenticate"):
                    ok = sa.authenticate(account_address, credential, auth_method)
                    self._json({"authenticated": bool(ok)})
                else:
                    self._json({"authenticated": False, "error": "not supported"})

            # ── Smart account verify ──────────────────────────────────────────
            elif path == "/smart-account/verify":
                sa = self.__class__.smart_accounts
                account_address = body.get("account_address", "")
                credential = body.get("credential", "")
                if sa and hasattr(sa, "is_valid"):
                    ok = sa.is_valid(account_address)
                    self._json({"valid": bool(ok)})
                elif sa and hasattr(sa, "get_account"):
                    acc = sa.get_account(account_address)
                    self._json({"valid": acc is not None, "account": acc})
                else:
                    self._json({"valid": False, "error": "not supported"})

            # ── MEV frontrun analysis ─────────────────────────────────────────
            elif path == "/mev/frontrun":
                cfg = self.__class__.config
                if getattr(cfg, "is_production", False):
                    self._json({"enabled": False, "dev_only": True, "error": "MEV disabled in production"})
                    return
                mev = self.__class__.mev_simulator
                mp = self.__class__.mempool
                tx_data = body.get("transaction", {})
                tx_hash = body.get("tx_hash", tx_data.get("hash", ""))
                target = None
                if tx_data:
                    from features.mev_analyzer import Transaction as MevTx
                    target = MevTx(
                        hash=tx_data.get("hash", tx_hash or "0x0"),
                        from_addr=tx_data.get("from", ""),
                        to_addr=tx_data.get("to", ""),
                        value=float(tx_data.get("value", tx_data.get("amount", 0))),
                        gas_price=int(tx_data.get("gas_price", 1)),
                        timestamp=0,
                    )
                elif mp and tx_hash:
                    for tx in mp.get(limit=500):
                        if tx.tx_hash == tx_hash:
                            from features.mev_analyzer import Transaction as MevTx
                            target = MevTx(
                                hash=tx.tx_hash,
                                from_addr=tx.from_addr,
                                to_addr=tx.to_addr,
                                value=float(tx.amount),
                                gas_price=int(tx.fee * 1e9) if tx.fee else 1,
                                timestamp=0,
                            )
                            break
                if mev and target and hasattr(mev, "simulate_frontrun"):
                    result = mev.simulate_frontrun(target, bot_balance=1000.0)
                    result["dev_only"] = True
                    self._json(result)
                else:
                    self._json({
                        "success": False,
                        "feasible": False,
                        "dev_only": True,
                        "enabled": bool(mev),
                        "error": "transaction or tx_hash required",
                    })

            # ── ZK: range proof & transaction ─────────────────────────────────
            elif path == "/zk/prove/range":
                zk = self.__class__.zk
                value = int(body.get("value", 42))
                min_v = int(body.get("min_value", 0))
                max_v = int(body.get("max_value", 100))
                if zk and hasattr(zk, "prove_range"):
                    proof = zk.prove_range(value, min_v, max_v)
                    self._json({"proof": str(proof), "valid": True})
                else:
                    self._error(503, "ZK range proofs not available")

            elif path == "/zk/create-tx":
                zk = self.__class__.zk
                if zk and hasattr(zk, "create_zk_transaction"):
                    tx = zk.create_zk_transaction(
                        sender=body.get("sender",""),
                        amount=int(body.get("amount", 1)))
                    self._json({"tx": str(tx), "success": True})
                else:
                    self._json({"success": False, "error": "ZK transactions not available"})

            else:
                self._error(404, "Endpoint not found")

        except Exception as e:
            logger.exception(f"REST POST error: {e}")
            self._error(500, str(e))

    def _json(self, data: Any):
        body = json.dumps(data, default=str).encode()
        origin = self._cors_origin(self.headers.get("Origin", ""))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code: int, message: str):
        mc = self.__class__.metrics_collector
        if mc:
            mc.inc_error()
        body = json.dumps({"error": message}).encode()
        origin = self._cors_origin(self.headers.get("Origin", ""))
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        origin = self._cors_origin(self.headers.get("Origin", ""))
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()


# ═══════════════════════════════════════════════════════════════════════════════
#  Вспомогательные форматтеры
# ═══════════════════════════════════════════════════════════════════════════════

def _format_block(blk: Optional[Dict], full_tx: bool = False) -> Optional[Dict]:
    if not blk:
        return None
    state_root = blk.get("state_root", "") or ""
    if state_root and not str(state_root).startswith("0x"):
        state_root = "0x" + str(state_root)
    txs = blk.get("transactions", [])
    tx_hashes = [
        tx.get("hash", "") if isinstance(tx, dict) else str(tx)
        for tx in (txs if isinstance(txs, list) else [])
    ]
    return {
        "number": hex(blk.get("height", 0)),
        "hash": blk.get("hash", blk.get("block_hash", "")),
        "parentHash": blk.get("parent_hash", ""),
        "nonce": "0x0000000000000000",
        "sha3Uncles": "0x" + "0" * 64,
        "logsBloom": "0x" + "0" * 512,
        "transactionsRoot": "0x" + "0" * 64,
        "stateRoot": state_root or ("0x" + "0" * 64),
        "receiptsRoot": "0x" + "0" * 64,
        "miner": blk.get("miner", blk.get("proposer", "")),
        "difficulty": "0x0",
        "totalDifficulty": "0x0",
        "extraData": "0x",
        "size": hex(256 + len(tx_hashes) * 32),
        "gasLimit": hex(30_000_000),
        "gasUsed": hex(blk.get("gas_used", 0)),
        "timestamp": hex(blk.get("timestamp", 0)),
        "uncles": [],
        "transactions": txs if full_tx else tx_hashes,
        "totalBurned": blk.get("total_burned", 0.0),
        "txCount": blk.get("tx_count", len(tx_hashes)),
    }


def _format_tx(tx: Optional[Dict]) -> Optional[Dict]:
    if not tx:
        return None
    return {
        "hash": tx.get("hash", tx.get("tx_hash", "")),
        "blockNumber": hex(tx.get("block_height", 0)),
        "from": tx.get("from_addr", tx.get("from", "")),
        "to": tx.get("to_addr", tx.get("to", "")),
        "value": hex(int(float(tx.get("value", tx.get("amount", 0))) * 10**18)),
        "gas": hex(tx.get("gas", 21000)),
        "gasUsed": hex(tx.get("gas_used", tx.get("gas", 21000))),
        "nonce": hex(tx.get("nonce", 0)),
        "input": tx.get("data", tx.get("tx_data", "0x")),
        "burned": tx.get("burned", 0.0),
    }


def _format_receipt(tx: Optional[Dict], bc=None) -> Optional[Dict]:
    if not tx:
        return None
    tx_hash = tx.get("hash", tx.get("tx_hash", ""))
    logs: List[Dict] = []
    if bc and hasattr(bc, "db") and hasattr(bc.db, "get_evm_logs_by_tx"):
        logs = [
            _format_eth_log(row, bc)
            for row in bc.db.get_evm_logs_by_tx(tx_hash)
        ]
    return {
        "transactionHash": tx_hash,
        "blockNumber": hex(tx.get("block_height", 0)),
        "from": tx.get("from_addr", tx.get("from", "")),
        "to": tx.get("to_addr", tx.get("to", "")),
        "status": hex(tx.get("status", 1)),
        "gasUsed": hex(tx.get("gas_used", tx.get("gas", 21000))),
        "logs": logs,
        "burned": tx.get("burned", 0.0),
    }


def _resolve_block_tag_to_height(bc, tag) -> int:
    if tag in (None, "", "earliest"):
        return 0
    if tag in ("latest", "pending"):
        return int(bc.get_height()) if bc else 0
    try:
        return int(tag, 16) if str(tag).startswith("0x") else int(tag)
    except (TypeError, ValueError):
        return 0


def _normalize_log_data(data) -> str:
    raw = str(data or "")
    if not raw or raw == "0x":
        return "0x"
    return raw if raw.startswith("0x") else "0x" + raw


def _tx_index_in_block(bc, block_height: int, tx_hash: str) -> int:
    if not bc or not tx_hash:
        return 0
    blk = bc.get_block(int(block_height))
    if not blk:
        return 0
    txs = blk.get("transactions", [])
    if not isinstance(txs, list):
        return 0
    target = tx_hash.lower()
    for idx, entry in enumerate(txs):
        if isinstance(entry, dict):
            h = str(entry.get("hash", entry.get("tx_hash", ""))).lower()
        else:
            h = str(entry).lower()
        if h == target:
            return idx
    return 0


def _format_eth_log(row: Dict, bc=None) -> Dict:
    block_height = int(row.get("block_height", 0))
    block_hash = ""
    if bc:
        blk = bc.get_block(block_height)
        if blk:
            block_hash = blk.get("hash", blk.get("block_hash", ""))
    tx_hash = row.get("tx_hash", "")
    topics = row.get("topics", [])
    if not isinstance(topics, list):
        topics = []
    return {
        "removed": False,
        "logIndex": hex(int(row.get("log_index", 0))),
        "transactionIndex": hex(_tx_index_in_block(bc, block_height, tx_hash)),
        "transactionHash": tx_hash,
        "blockHash": block_hash,
        "blockNumber": hex(block_height),
        "address": row.get("contract_address", ""),
        "data": _normalize_log_data(row.get("data", "")),
        "topics": topics,
    }


def _handle_eth_get_logs(filt: Dict, bc) -> List[Dict]:
    if not bc or not hasattr(bc, "db") or not hasattr(bc.db, "query_evm_logs"):
        return []
    from_block = _resolve_block_tag_to_height(bc, filt.get("fromBlock", "0x0"))
    to_block = _resolve_block_tag_to_height(bc, filt.get("toBlock", "latest"))
    if to_block < from_block:
        return []
    address = filt.get("address")
    addresses = None
    if address:
        addresses = address if isinstance(address, list) else [address]
    topics = filt.get("topics")
    rows = bc.db.query_evm_logs(
        from_block=from_block,
        to_block=to_block,
        addresses=addresses,
        topics=topics,
    )
    return [_format_eth_log(row, bc) for row in rows]


def _resolve_block_by_tag(bc, tag: str) -> Optional[Dict]:
    """Resolve eth block tag (latest/pending/hex/decimal) to block dict."""
    if not bc:
        return None
    if tag in ("latest", "pending"):
        return bc.get_last_block()
    try:
        height = int(tag, 16) if str(tag).startswith("0x") else int(tag)
        return bc.get_block(height)
    except (TypeError, ValueError):
        return None


def _tx_at_block_index(bc, blk: Optional[Dict], index: int) -> Optional[Dict]:
    if not bc or not blk or index < 0:
        return None
    txs = blk.get("transactions", [])
    if not isinstance(txs, list) or index >= len(txs):
        return None
    entry = txs[index]
    if isinstance(entry, dict):
        return entry
    tx_hash = str(entry)
    if hasattr(bc, "get_transaction"):
        return bc.get_transaction(tx_hash)
    return None


def _parse_tx_value(value_raw) -> float:
    """ABS amount: plain float, or 0x wei when value looks like Ethereum wei."""
    if isinstance(value_raw, str):
        if value_raw.startswith("0x"):
            wei = int(value_raw, 16)
            return wei / 10**18 if wei >= 10**15 else float(wei)
        return float(value_raw)
    return float(value_raw)


def _build_testnet_mesh(p2p, bc, cfg) -> Dict:
    """Live P2P mesh view for multi-node devnet (Wave 52)."""
    local_h = bc.get_height() if bc and hasattr(bc, "get_height") else 0
    state_root = bc.get_state_root() if bc and hasattr(bc, "get_state_root") else ""
    peers_info = p2p.get_peers_info() if p2p else []
    peers = []
    max_gap = 0
    for p in peers_info:
        ph = int(p.get("height", 0) or 0)
        gap = abs(ph - local_h)
        max_gap = max(max_gap, gap)
        peers.append({
            "peer_id": p.get("id", ""),
            "host": p.get("host", ""),
            "port": p.get("port", 0),
            "height": ph,
            "head": p.get("head", ""),
            "height_gap": gap,
            "connected_for_sec": p.get("connected_for", 0),
        })
    peer_count = len(peers)
    expected_peers = max(1, int(getattr(cfg, "testnet_expected_peers", 1) or 1))
    state_consistent = getattr(p2p, "_state_consistent", True) if p2p else True
    height_aligned = max_gap <= 2
    mesh_healthy = peer_count >= expected_peers and height_aligned and state_consistent
    return {
        "node_id": getattr(cfg, "node_id", ""),
        "chain_id": getattr(cfg, "chain_id", 0),
        "local_height": local_h,
        "state_root": state_root,
        "peer_count": peer_count,
        "expected_peers": expected_peers,
        "max_peer_height_gap": max_gap,
        "state_consistent": state_consistent,
        "mesh_healthy": mesh_healthy,
        "height_aligned": height_aligned,
        "bootstrap_peers": getattr(cfg, "bootstrap_peers", []),
        "peers": peers,
        "testnet_mode": "3-node" if expected_peers >= 2 else "multi",
        "api_wave": 61,
    }


def _build_testnet_fork_status(p2p, bc, cfg, db=None) -> Dict:
    """Fork / partition view for adversarial testnet CI (Wave 53)."""
    local_h = bc.get_height() if bc and hasattr(bc, "get_height") else 0
    last = bc.get_last_block() if bc and hasattr(bc, "get_last_block") else None
    local_head = (last or {}).get("hash", "")
    local_root = bc.get_state_root() if bc and hasattr(bc, "get_state_root") else ""
    peers_info = p2p.get_peers_info() if p2p else []
    peers = []
    max_gap = 0
    heads_by_height: Dict[int, set] = {}
    if local_head:
        heads_by_height.setdefault(local_h, set()).add(local_head)
    for p in peers_info:
        ph = int(p.get("height", 0) or 0)
        head = p.get("head", "") or ""
        gap = abs(ph - local_h)
        max_gap = max(max_gap, gap)
        if head:
            heads_by_height.setdefault(ph, set()).add(head)
        peers.append({
            "peer_id": p.get("id", ""),
            "host": p.get("host", ""),
            "port": p.get("port", 0),
            "height": ph,
            "head": head,
            "height_gap": gap,
        })
    same_height_fork = any(len(heads) > 1 for heads in heads_by_height.values())
    peer_count = len(peers)
    expected_peers = max(1, int(getattr(cfg, "testnet_expected_peers", 1) or 1))
    state_consistent = getattr(p2p, "_state_consistent", True) if p2p else True
    slash_events = (
        db.get_slash_events(100) if db and hasattr(db, "get_slash_events") else []
    )
    fork_detected = same_height_fork or max_gap > 2 or not state_consistent
    consensus_healthy = (
        peer_count >= expected_peers
        and max_gap <= 2
        and not same_height_fork
        and state_consistent
    )
    return {
        "node_id": getattr(cfg, "node_id", ""),
        "chain_id": getattr(cfg, "chain_id", 0),
        "local_height": local_h,
        "local_head": local_head,
        "local_state_root": local_root,
        "peer_count": peer_count,
        "expected_peers": expected_peers,
        "max_peer_height_gap": max_gap,
        "same_height_divergent_heads": same_height_fork,
        "state_consistent": state_consistent,
        "fork_detected": fork_detected,
        "consensus_healthy": consensus_healthy,
        "slash_events_count": len(slash_events),
        "recent_slash_events": slash_events[:5],
        "peers": peers,
        "api_wave": 61,
    }


def _build_testnet_fork_exercise(p2p, bc, cfg, db=None, run_reconcile: bool = False) -> Dict:
    """Fork recovery drill: reconcile peers + repair state (Wave 58)."""
    before = _build_testnet_fork_status(p2p, bc, cfg, db)
    reconcile_detail: Dict = {}
    repaired = False

    if run_reconcile:
        if p2p and hasattr(p2p, "reconcile_peers_sync"):
            try:
                reconcile_detail = p2p.reconcile_peers_sync(timeout=90)
            except Exception as exc:
                reconcile_detail = {"ok": False, "error": str(exc)}
        elif p2p and hasattr(p2p, "trigger_reconcile"):
            p2p.trigger_reconcile()
            time.sleep(3)
            reconcile_detail = {"ok": True, "message": "scheduled"}

        if bc and hasattr(bc, "ensure_state_at_tip"):
            try:
                repaired = bool(bc.ensure_state_at_tip())
            except Exception:
                repaired = False

    after = _build_testnet_fork_status(p2p, bc, cfg, db)
    harness = _build_state_consistency_harness(p2p, bc, cfg, db)
    state_consistent = bool(
        reconcile_detail.get("state_consistent", after.get("state_consistent", True))
    )
    fork_recovered = bool(
        after.get("consensus_healthy")
        and harness.get("harness_healthy")
        and not after.get("same_height_divergent_heads")
        and state_consistent
    )

    return {
        "action": "fork_recovery_drill" if run_reconcile else "fork_recovery_status",
        "run_reconcile": bool(run_reconcile),
        "before": {
            "consensus_healthy": before.get("consensus_healthy"),
            "fork_detected": before.get("fork_detected"),
            "max_peer_height_gap": before.get("max_peer_height_gap"),
            "same_height_divergent_heads": before.get("same_height_divergent_heads"),
        },
        "after": {
            "consensus_healthy": after.get("consensus_healthy"),
            "fork_detected": after.get("fork_detected"),
            "max_peer_height_gap": after.get("max_peer_height_gap"),
            "same_height_divergent_heads": after.get("same_height_divergent_heads"),
            "local_height": after.get("local_height"),
            "local_state_root": after.get("local_state_root"),
        },
        "reconcile": reconcile_detail,
        "state_repaired": repaired,
        "harness_healthy": bool(harness.get("harness_healthy")),
        "fork_recovered": fork_recovered if run_reconcile else None,
        "needs_recovery": not before.get("consensus_healthy") or before.get("fork_detected"),
        "api_wave": 61,
    }


def _build_state_consistency_harness(p2p, bc, cfg, db=None) -> Dict:
    """Multi-check state integrity harness for testnet CI (Wave 54)."""
    height = bc.get_height() if bc and hasattr(bc, "get_height") else 0
    live_root = bc.get_state_root() if bc and hasattr(bc, "get_state_root") else ""
    tip_blk = bc.get_last_block() if bc and hasattr(bc, "get_last_block") else None
    tip_root = str((tip_blk or {}).get("state_root") or "")
    live_norm = (live_root or "").strip().lower()
    tip_norm = tip_root.strip().lower()
    tip_aligned = (live_norm == tip_norm) if tip_norm and live_norm else True

    peers = []
    peer_roots_aligned = True
    if p2p and hasattr(p2p, "request_peer_state_roots_sync"):
        try:
            for entry in p2p.request_peer_state_roots_sync(timeout=8):
                pr = str(entry.get("state_root") or "")
                pr_norm = pr.strip().lower()
                match = (pr_norm == live_norm) if pr_norm and live_norm else None
                if match is False:
                    peer_roots_aligned = False
                peers.append({
                    "peer_id": entry.get("peer_id", ""),
                    "height": int(entry.get("height", 0) or 0),
                    "state_root": pr,
                    "match": match,
                })
        except Exception:
            peer_roots_aligned = False

    # Long Docker chains: tip block metadata may lag while mesh agrees on live root
    tip_metadata_drift = not tip_aligned
    if (
        tip_metadata_drift
        and peer_roots_aligned
        and peers
        and live_norm
        and all(p.get("match") is True for p in peers)
    ):
        tip_aligned = True

    mismatches = (
        db.get_state_root_mismatches(limit=20)
        if db and hasattr(db, "get_state_root_mismatches")
        else []
    )
    account_count = (
        len(db.get_all_accounts())
        if db and hasattr(db, "get_all_accounts")
        else 0
    )
    total_supply = (
        float(db.get_total_supply())
        if db and hasattr(db, "get_total_supply")
        else 0.0
    )
    max_supply = float(getattr(cfg, "max_supply", 221_000_000) or 221_000_000)
    state_consistent = getattr(p2p, "_state_consistent", True) if p2p else True

    checks = [
        {
            "id": "tip_state_aligned",
            "ok": tip_aligned,
            "detail": "live state_root matches canonical tip block",
        },
        {
            "id": "peer_state_roots",
            "ok": peer_roots_aligned or not peers,
            "detail": "P2P peer state_roots match local",
        },
        {
            "id": "p2p_state_consistent",
            "ok": bool(state_consistent),
            "detail": "P2P wire state consistency flag",
        },
        {
            "id": "no_recent_mismatches",
            "ok": len(mismatches) == 0,
            "detail": "no state_root_mismatches in SQLite audit",
        },
        {
            "id": "accounts_present",
            "ok": account_count > 0 or height <= 0,
            "detail": "SQLite accounts table populated",
        },
        {
            "id": "supply_within_cap",
            "ok": total_supply <= max_supply * 1.001,
            "detail": f"total_supply {total_supply:,.0f} <= max {max_supply:,.0f}",
        },
    ]
    harness_healthy = all(c["ok"] for c in checks)
    policy = bc.get_state_root_policy() if bc and hasattr(bc, "get_state_root_policy") else {}

    return {
        "node_id": getattr(cfg, "node_id", ""),
        "chain_id": getattr(cfg, "chain_id", 0),
        "height": height,
        "live_state_root": live_root,
        "tip_block_state_root": tip_root,
        "tip_state_aligned": tip_aligned,
        "tip_metadata_drift": tip_metadata_drift and tip_aligned,
        "account_count": account_count,
        "total_supply_abs": total_supply,
        "max_supply_abs": max_supply,
        "peer_count": len(peers),
        "peers": peers,
        "recent_mismatch_count": len(mismatches),
        "recent_mismatches": mismatches[:5],
        "checks": checks,
        "harness_healthy": harness_healthy,
        "canonical_state_root_source": "blockchain.database",
        "failed_checks": [c["id"] for c in checks if not c["ok"]],
        "policy": policy,
        "api_wave": 61,
    }


def _build_testnet_validators_status(db, cfg, bc) -> Dict:
    """Validator set + proposer rotation view (Wave 55)."""
    validators = db.get_validators() if db and hasattr(db, "get_validators") else []
    active = [
        v for v in validators
        if v.get("active", True) and not v.get("slashed")
    ]
    stats = (
        db.get_proposer_stats(limit=15)
        if db and hasattr(db, "get_proposer_stats")
        else []
    )
    height = bc.get_height() if bc and hasattr(bc, "get_height") else 0
    expected = max(1, int(getattr(cfg, "testnet_expected_validators", 5) or 5))
    distinct_proposers = len({s.get("proposer", "") for s in stats if s.get("proposer")})
    min_height = 12 if expected >= 3 else 8
    rotation_needed = min(3, expected) if expected >= 3 else 2
    rotation_ok = distinct_proposers >= rotation_needed or height < min_height
    manifest_path = getattr(cfg, "testnet_validators_manifest", "") or ""
    slashed = {str(v.get("address", "")).lower() for v in validators if v.get("slashed")}
    observed = {
        str(v.get("address", "")).lower()
        for v in active
        if str(v.get("address", "")).startswith("0x")
    }
    observed.update(
        str(s.get("proposer", "")).lower()
        for s in stats
        if str(s.get("proposer", "")).startswith("0x")
    )
    observed = {addr for addr in observed if addr and addr not in slashed}
    manifest_count = 0
    if manifest_path:
        try:
            from runtime.devnet_validators import load_manifest, manifest_entries
            resolved_manifest = manifest_path
            if not os.path.isabs(resolved_manifest):
                resolved_manifest = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    resolved_manifest,
                )
            founder = getattr(cfg, "founder_address", "") or getattr(cfg, "miner_address", "") or ""
            manifest = load_manifest(resolved_manifest)
            manifest_rows = [
                row for row in manifest_entries(manifest, founder)
                if row.get("mines", True) and row.get("address")
            ]
            manifest_count = len(manifest_rows)
        except Exception:
            manifest_count = 0
    effective_active = max(len(active), len(observed))
    validators_healthy = len(active) >= expected
    if manifest_count >= expected:
        validators_healthy = effective_active >= expected
    return {
        "node_id": getattr(cfg, "node_id", ""),
        "chain_id": getattr(cfg, "chain_id", 0),
        "height": height,
        "expected_validators": expected,
        "registered_count": len(validators),
        "active_count": len(active),
        "observed_validator_count": len(observed),
        "effective_active_count": effective_active,
        "validators_healthy": validators_healthy,
        "distinct_proposers": distinct_proposers,
        "rotation_observed": rotation_ok,
        "proposer_stats": stats,
        "validators": validators,
        "manifest": manifest_path,
        "manifest_validator_count": manifest_count,
        "validator_index": int(getattr(cfg, "testnet_validator_index", 0) or 0),
        "api_wave": 61,
    }


def _build_testnet_multi_node_proof(p2p, bc, cfg, db, consensus_adapter) -> Dict:
    """Unified multi-node proof dashboard (Wave 56)."""
    mesh = _build_testnet_mesh(p2p, bc, cfg)
    harness = _build_state_consistency_harness(p2p, bc, cfg, db)
    validators = _build_testnet_validators_status(db, cfg, bc)
    fork = _build_testnet_fork_status(p2p, bc, cfg, db)

    attestations: List[Dict] = []
    att_count = 0
    att_enabled = False
    if consensus_adapter and hasattr(consensus_adapter, "get_attestations"):
        attestations = consensus_adapter.get_attestations() or []
        att_count = len(attestations)
        att_enabled = True

    att_by_block: List[Dict] = []
    if consensus_adapter and hasattr(consensus_adapter, "get_attestations_by_block"):
        att_by_block = consensus_adapter.get_attestations_by_block() or []

    height = int(mesh.get("local_height", 0) or 0)
    expected_val = int(validators.get("expected_validators", 3) or 3)
    expected_peers = int(mesh.get("expected_peers", 2) or 2)
    min_height = 12 if expected_val >= 3 else 8
    rotation_needed = min(3, expected_val) if expected_val >= 3 else 2
    distinct = int(validators.get("distinct_proposers", 0) or 0)
    rotation_ok = distinct >= rotation_needed or height < min_height
    attestations_ok = att_count > 0 or height < 4

    checks = [
        {"id": "mesh_healthy", "ok": bool(mesh.get("mesh_healthy"))},
        {"id": "harness_healthy", "ok": bool(harness.get("harness_healthy"))},
        {"id": "validators_healthy", "ok": bool(validators.get("validators_healthy"))},
        {"id": "rotation_observed", "ok": bool(rotation_ok)},
        {"id": "attestations_present", "ok": bool(attestations_ok)},
        {"id": "consensus_healthy", "ok": bool(fork.get("consensus_healthy"))},
        {"id": "height_sufficient", "ok": height >= min_height},
    ]
    ignored_low_height_checks = ("rotation_observed", "height_sufficient")
    if height < min_height:
        proof_ok = all(
            c["ok"] for c in checks
            if c["id"] not in ignored_low_height_checks
        )
    else:
        proof_ok = all(c["ok"] for c in checks)
    failed_checks = [
        c["id"] for c in checks
        if not c["ok"] and not (height < min_height and c["id"] in ignored_low_height_checks)
    ]
    pending_checks = [
        c["id"] for c in checks
        if not c["ok"] and height < min_height and c["id"] in ignored_low_height_checks
    ]

    return {
        "node_id": getattr(cfg, "node_id", ""),
        "chain_id": getattr(cfg, "chain_id", 0),
        "height": height,
        "min_proof_height": min_height,
        "expected_validators": expected_val,
        "expected_peers": expected_peers,
        "mesh": mesh,
        "harness": {
            "harness_healthy": harness.get("harness_healthy"),
            "live_state_root": harness.get("live_state_root"),
            "failed_checks": harness.get("failed_checks"),
            "checks": harness.get("checks"),
        },
        "validators": {
            "validators_healthy": validators.get("validators_healthy"),
            "active_count": validators.get("active_count"),
            "observed_validator_count": validators.get("observed_validator_count"),
            "effective_active_count": validators.get("effective_active_count"),
            "distinct_proposers": distinct,
            "rotation_observed": rotation_ok,
            "rotation_needed": rotation_needed,
        },
        "fork": {
            "consensus_healthy": fork.get("consensus_healthy"),
            "fork_detected": fork.get("fork_detected"),
            "max_peer_height_gap": fork.get("max_peer_height_gap"),
        },
        "attestations": {
            "enabled": att_enabled,
            "count": att_count,
            "by_block_count": len(att_by_block),
            "recent": attestations[:5],
        },
        "checks": checks,
        "proof_ok": proof_ok,
        "failed_checks": failed_checks,
        "pending_checks": pending_checks,
        "api_wave": 61,
    }


def _build_sync_status(se, p2p, bc, cfg) -> Dict:
    """Real sync view: SyncEngine when present, merged with live P2P peer heights."""
    local_h = bc.get_height() if bc and hasattr(bc, "get_height") else 0
    state_root = bc.get_state_root() if bc and hasattr(bc, "get_state_root") else ""
    peer_count = p2p.peer_count() if p2p else 0
    peers_info = p2p.get_peers_info() if p2p else []
    best_peer_height = max((p.get("height", 0) for p in peers_info), default=local_h)
    state_consistent = getattr(p2p, "_state_consistent", True) if p2p else True
    root_fields = {
        "state_root": state_root,
        "state_consistent": state_consistent,
        "state_root_strict_p2p": getattr(cfg, "state_root_strict_p2p", True),
    }
    if bc and hasattr(bc, "get_state_root_policy"):
        root_fields.update(bc.get_state_root_policy())

    if se and hasattr(se, "get_status"):
        status = dict(se.get_status())
        status["enabled"] = True
        status["source"] = "sync_engine"
        status["local_height"] = local_h
        status["p2p_peers"] = peer_count
        status["best_peer_height"] = best_peer_height
        status["behind"] = max(0, best_peer_height - local_h)
        status["solo_mode"] = peer_count == 0
        status.update(root_fields)
        if peer_count == 0:
            status["hint"] = (
                "Solo node is normal locally. Connect peers: "
                "python main.py --peers 127.0.0.1:5000 or .\\scripts\\start_two_nodes.ps1"
            )
        return status
    p2p_sync = {}
    if p2p and getattr(p2p, "sync_engine", None):
        try:
            p2p_sync = p2p.sync_engine.get_status()
        except Exception:
            p2p_sync = {}

    return {
        "enabled": True,
        "source": "p2p",
        "syncing": bool(p2p_sync.get("syncing", False)),
        "local_height": local_h,
        "best_peer_height": best_peer_height,
        "behind": max(0, best_peer_height - local_h),
        "peers": peer_count,
        "solo_mode": peer_count == 0,
        "bootstrap_peers": getattr(cfg, "bootstrap_peers", []) if cfg else [],
        **root_fields,
        "hint": (
            "Solo node is normal locally. Connect peers: "
            "python main.py --peers 127.0.0.1:5000 or bootstrap_peers in config"
            if peer_count == 0 else None
        ),
    }


def _collect_recent_activity(db, cross_bridge=None, limit: int = 30) -> List[Dict]:
    """Chain txs + bridge locks + in-memory cross-chain transfers for dashboard feed."""
    items: List[Dict] = []
    if db and hasattr(db, "get_recent_transactions"):
        for t in db.get_recent_transactions(limit):
            items.append({
                "hash": t.get("hash", t.get("tx_hash", "")),
                "from": t.get("from_addr", t.get("from", "")),
                "to": t.get("to_addr", t.get("to", "")),
                "value": t.get("value", t.get("amount", 0)),
                "block_height": t.get("block_height", t.get("height")),
                "fee": t.get("fee", 0),
                "type": "transfer",
                "status": t.get("status", "confirmed"),
                "timestamp": int(t.get("timestamp", 0) or 0),
            })
    if db and hasattr(db, "get_bridge_locks"):
        for lock in db.get_bridge_locks(limit):
            items.append({
                "hash": lock.get("tx_hash", ""),
                "from": lock.get("from_addr", ""),
                "to": f"lock:{lock.get('to_chain', '?')}",
                "to_addr": lock.get("to_addr", ""),
                "value": lock.get("amount", 0),
                "block_height": None,
                "fee": 0,
                "type": "bridge_lock",
                "status": lock.get("status", "pending"),
                "timestamp": int(lock.get("created_at", 0) or 0),
            })
    if cross_bridge and hasattr(cross_bridge, "transactions"):
        for tx in cross_bridge.transactions.values():
            items.append({
                "hash": tx.tx_hash,
                "from": tx.from_addr,
                "to": f"{tx.from_chain}→{tx.to_chain}",
                "to_addr": tx.to_addr,
                "value": tx.amount,
                "block_height": None,
                "fee": 0,
                "type": "bridge_transfer",
                "status": tx.status,
                "timestamp": int(tx.timestamp or 0),
            })
    items.sort(
        key=lambda x: (
            x.get("timestamp") or 0,
            x.get("block_height") or 0,
        ),
        reverse=True,
    )
    return items[:limit]


def _build_l2_status(handler_cls) -> Dict:
    """Unified dashboard for Waves 40-43 L2/dev-test modules."""
    modules = {}
    ln = handler_cls.lightning
    pl = handler_cls.plasma
    cw = handler_cls.crypto_will
    wasm = handler_cls.wasm_vm
    ai = handler_cls.ai_manager
    nft = getattr(handler_cls, "nft", None)
    if ln and hasattr(ln, "get_stats"):
        modules["lightning"] = ln.get_stats()
    if pl and hasattr(pl, "get_stats"):
        modules["plasma"] = pl.get_stats()
    if cw and hasattr(cw, "get_stats"):
        modules["crypto_will"] = cw.get_stats()
    if wasm and hasattr(wasm, "get_stats"):
        modules["wasm"] = wasm.get_stats()
    if ai and hasattr(ai, "get_stats"):
        modules["ai_agents"] = ai.get_stats()
    nft_persisted = False
    if nft and hasattr(nft, "get_stats"):
        modules["nft"] = nft.get_stats()
        nft_persisted = bool(modules["nft"].get("persisted"))
    persisted = any(
        m.get("persisted") for m in modules.values() if isinstance(m, dict)
    )
    return {
        "api_wave": 61,
        "l2_persisted": persisted,
        "nft_persisted": nft_persisted,
        "core": {
            "receipts_enabled": bool(
                getattr(handler_cls, "db", None)
                and hasattr(getattr(handler_cls, "db", None), "get_tx_receipt")
            ),
            "address_index_enabled": bool(
                getattr(handler_cls, "db", None)
                and hasattr(getattr(handler_cls, "db", None), "get_address_activity")
            ),
            "proposer_audit_enabled": bool(
                getattr(handler_cls, "db", None)
                and hasattr(getattr(handler_cls, "db", None), "get_proposer_audit_log")
            ),
            "state_root_strict_p2p": bool(
                getattr(handler_cls, "blockchain", None)
                and getattr(
                    getattr(handler_cls, "blockchain", None),
                    "config",
                    None,
                )
                and getattr(
                    getattr(handler_cls, "blockchain", None).config,
                    "state_root_strict_p2p",
                    True,
                )
            ),
            "endpoints": {
                "metrics": "GET /chain/metrics",
                "receipt": "GET /tx/receipt/{hash}",
                "block_receipts": "GET /receipts/block/{height}",
                "address_activity": "GET /address/{addr}/activity",
                "address_txs": "GET /address/{addr}/txs?limit=&offset=&direction=",
                "proposer_stats": "GET /chain/proposers/stats",
                "proposer_history": "GET /chain/proposers/history?limit=&offset=&proposer=",
                "proposer_detail": "GET /chain/proposer/{addr}",
                "state_root_status": "GET /chain/state-root/status",
                "tx_trace": "GET /tx/trace/{hash}",
                "tx_propagation": "GET /tx/propagation/recent",
            },
        },
        "modules_enabled": list(modules.keys()),
        "modules": modules,
        "endpoints": {
            "lightning": "GET /lightning/stats",
            "plasma": "GET /plasma/stats",
            "will": "GET /will/stats",
            "wasm": "GET /wasm/stats",
            "ai": "GET /ai-agent/stats",
            "mev": "GET /mev/stats",
            "nft": "GET /nft/stats",
        },
    }


def _build_l1_queue_payload(cfg) -> Dict:
    """Shared JSON for GET /bridge/l1-queue and GET /oracles/l1-queue."""
    try:
        from bridge.l1_rpc import load_l1_queue, chain_rpc_url, min_confirmations
        qpath = getattr(cfg, "bridge_l1_queue_path", "data/bridge_l1_queue.json")
        queue = load_l1_queue(qpath)
        return {
            "path": qpath,
            "min_confirmations": min_confirmations(),
            "eth_rpc_configured": bool(chain_rpc_url("ethereum")),
            "outbound": len(queue.get("outbound", [])),
            "incoming": len(queue.get("incoming", [])),
            "queue": queue,
        }
    except Exception as e:
        return {"error": str(e), "outbound": 0, "incoming": 0, "queue": {}}


def _build_bridge_relayer_status(cfg, db) -> Dict:
    """Summary for scripts/bridge_relayer.py operators."""
    try:
        from bridge.l1_rpc import load_l1_queue, min_confirmations
        from bridge.relayer import check_relayer_readiness, relayer_require_l1_proof

        qpath = getattr(cfg, "bridge_l1_queue_path", "data/bridge_l1_queue.json")
        queue = load_l1_queue(qpath)
        locks = db.get_bridge_locks(limit=1000) if db and hasattr(db, "get_bridge_locks") else []
        pending_locks = [l for l in locks if (l.get("status") or "pending") == "pending"]
        oracle_on = bool(
            getattr(cfg, "bridge_oracle_secret", "")
            or __import__("os").environ.get("BRIDGE_ORACLE_SECRET", "")
        )
        api_url = f"http://127.0.0.1:{getattr(cfg, 'http_port', 8080)}"
        secret = getattr(cfg, "bridge_oracle_secret", "") or __import__("os").environ.get(
            "BRIDGE_ORACLE_SECRET", ""
        )
        readiness = (
            check_relayer_readiness(api_url, secret, probe_l1=False)
            if oracle_on
            else {"ok": False, "errors": ["oracle secret not configured"], "require_l1_proof": relayer_require_l1_proof()}
        )
        return {
            "relayer_script": "python scripts/bridge_relayer.py --once --watch-l1",
            "preflight_script": "python scripts/bridge_relayer.py --preflight",
            "oracle_hmac_configured": oracle_on,
            "require_l1_proof": relayer_require_l1_proof(),
            "blind_pending_confirm_allowed": not relayer_require_l1_proof(),
            "readiness": readiness,
            "min_confirmations": min_confirmations(),
            "queue_path": qpath,
            "l1_outbound": len(queue.get("outbound", [])),
            "l1_incoming": len(queue.get("incoming", [])),
            "pending_locks": len(pending_locks),
            "pending_lock_txs": [l.get("tx_hash", "")[:24] for l in pending_locks[:10]],
            "endpoints": {
                "confirm_lock": "POST /bridge/oracle/confirm-lock",
                "incoming": "POST /bridge/oracle/incoming",
                "l1_queue": "GET /bridge/l1-queue",
            },
        }
    except Exception as e:
        return {"error": str(e), "pending_locks": 0, "l1_outbound": 0, "l1_incoming": 0}


def _build_testnet_bridge_relayer_proof(cfg, db, bridge) -> Dict:
    """Wave 60: relayer readiness + L1 queue + mock RPC hint."""
    relayer = _build_bridge_relayer_status(cfg, db)
    from bridge.l1_rpc import chain_rpc_url

    bridge_on = bool(getattr(cfg, "bridge_enabled", False))
    oracle_on = bool(relayer.get("oracle_hmac_configured"))
    rpc_on = bool(chain_rpc_url("ethereum"))
    queue_in = int(relayer.get("l1_incoming", 0) or 0)
    queue_out = int(relayer.get("l1_outbound", 0) or 0)
    rust_path = bridge is not None and hasattr(bridge, "lock_and_bridge")
    proof_ok = bridge_on and oracle_on and rust_path

    return {
        "api_wave": 61,
        "bridge_enabled": bridge_on,
        "bridge_mode": getattr(cfg, "bridge_mode", "unknown"),
        "oracle_hmac_configured": oracle_on,
        "eth_rpc_configured": rpc_on,
        "l1_incoming": queue_in,
        "l1_outbound": queue_out,
        "pending_locks": int(relayer.get("pending_locks", 0) or 0),
        "relayer": relayer,
        "ci_l1_rpc_hint": "bridge.mock_l1_rpc.start_mock_l1_rpc + ETH_RPC_URL for CI",
        "ci_mode": "python scripts/verify_p2p_ci.py --mode ci-bridge-relayer",
        "proof_ok": proof_ok,
    }


def _build_bridge_overview(rb, cb, cfg, db) -> Dict:
    """Unified GET /bridge summary (RustBridge + CrossChainBridge + DB locks)."""
    overview = {
        "enabled": bool(getattr(cfg, "bridge_enabled", False)),
        "mode": getattr(cfg, "bridge_mode", "unknown"),
        "dev_only": getattr(cfg, "bridge_mode", "unknown") == "simulator",
        "tier": "production" if getattr(cfg, "bridge_mode", "") == "rust" else "dev-only",
        "auto_confirm_sec": int(getattr(cfg, "bridge_auto_confirm_sec", 0) or 0),
        "deployment_note": (
            "Manual confirm mode — use POST /bridge/confirm-lock"
            if int(getattr(cfg, "bridge_auto_confirm_sec", 0) or 0) <= 0
            else "Devnet-only auto-confirm after bridge_auto_confirm_sec"
        ),
        "supported_chains": ["ethereum", "bsc", "solana", "absolute"],
        "endpoints": {
            "locks": "GET /bridge/locks",
            "l1_queue": "GET /bridge/l1-queue",
            "oracle_feeds": "GET /oracles/feeds",
            "relayer_status": "GET /bridge/relayer/status",
            "oracle_prices": "GET /oracles/prices",
            "lock": "POST /bridge/lock",
            "confirm": "POST /bridge/confirm",
            "confirm_lock": "POST /bridge/confirm-lock",
            "stats_detail": "GET /bridge2/stats",
            "fee": "GET /bridge2/fee",
        },
    }
    locks = db.get_bridge_locks(limit=1000) if db and hasattr(db, "get_bridge_locks") else []
    overview["locks"] = {
        "total": len(locks),
        "pending": sum(1 for l in locks if l.get("status") == "pending"),
        "confirmed": sum(1 for l in locks if l.get("status") == "confirmed"),
    }
    try:
        from bridge.health import check_l1_rpc_health
        from bridge.l1_rpc import min_confirmations

        l1_health = check_l1_rpc_health(cfg, timeout=1.5)
        overview["l1_rpc"] = {
            "eth_configured": "ETH_RPC_URL" in l1_health.get("endpoints", []),
            "min_confirmations": min_confirmations(),
            "queue_path": getattr(cfg, "bridge_l1_queue_path", "data/bridge_l1_queue.json"),
            "required": bool(l1_health.get("required")),
            "ok": bool(l1_health.get("ok")),
            "endpoints": l1_health.get("endpoints", []),
            "error": l1_health.get("error", ""),
        }
    except Exception:
        overview["l1_rpc"] = {"eth_configured": False}
    overview["rust_bridge_health"] = _rust_bridge_health(cfg)
    if rb and hasattr(rb, "get_stats"):
        overview["rust_bridge"] = rb.get_stats()
        overview["bridge_fees"] = overview["rust_bridge"].get("bridge_fees", {})
        if overview.get("mode") == "rust":
            resolve = getattr(cfg, "resolve_rust_bridge_path", None)
            overview["rust_binary"] = resolve() if callable(resolve) else getattr(
                cfg, "rust_bridge_path", ""
            )
            overview["rust_version"] = overview["rust_bridge"].get("version", "v4")
    if cb and hasattr(cb, "get_bridge_stats"):
        overview["cross_chain"] = cb.get_bridge_stats()
    overview["status"] = "dev-test-simulator" if overview.get("mode") == "simulator" else overview.get("mode")
    return overview


def _build_openapi_spec(cfg) -> Dict:
    http_port = getattr(cfg, "http_port", 8080) if cfg else 8080
    paths = {}
    for route in _PUBLIC_API_ROUTES:
        paths.setdefault(route["path"], {})[route["method"].lower()] = {
            "summary": route["summary"],
            "responses": {"200": {"description": "OK"}},
        }
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Absolute Blockchain REST API",
            "version": getattr(cfg, "node_version", "1.2.0") if cfg else "1.2.0",
            "description": "Production-hardened ABS node API. See /docs for quick reference.",
        },
        "servers": [{"url": f"http://localhost:{http_port}"}],
        "paths": paths,
    }


def _handle_deploy_tx(body: Dict, bc, mp, cfg, wallet=None, evm=None) -> str:
    """Queue EVM contract deploy as a signed mempool transaction."""
    from core.blockchain import Transaction

    bytecode = body.get("bytecode", body.get("data", ""))
    if not bytecode:
        raise ValueError("bytecode required")
    if not str(bytecode).replace("0x", "").strip():
        raise ValueError("empty_bytecode")
    from execution.evm_bytecode_validator import validate_bytecode_hex
    v = validate_bytecode_hex(str(bytecode))
    if not v.get("valid"):
        unsup = v.get("unsupported") or []
        detail = unsup[0]["name"] if unsup else v.get("error", "invalid_bytecode")
        raise ValueError(f"unsupported_evm_bytecode: {detail}")

    zero_addr = "0x0000000000000000000000000000000000000000"
    from_addr = body.get("from", body.get("from_address", ""))
    value = _parse_tx_value(body.get("value", body.get("amount", 0)))
    gas = int(body.get("gas", getattr(cfg, "evm_gas_limit", 8_000_000)))

    tx_body = dict(body or {})
    _reject_auto_sign_in_prod(tx_body, cfg)
    if wallet and (body.get("auto_sign") or not from_addr):
        nonce = bc.db.get_nonce(wallet.address)
        signed = wallet.sign_transaction(
            zero_addr,
            int(value) if value == int(value) else value,
            nonce,
            getattr(cfg, "chain_id", 1),
            data=bytecode,
            gas_limit=gas,
        )
        tx_body.update(signed)
        from_addr = wallet.address

    if not from_addr:
        raise ValueError("from address required (or auto_sign with wallet)")

    nonce = int(tx_body.get("nonce", bc.db.get_nonce(from_addr)))
    tx = Transaction(
        from_addr=from_addr,
        to_addr=zero_addr,
        value=value,
        nonce=nonce,
        gas=gas,
        data=bytecode,
        signature=tx_body.get("signature", ""),
        public_key=tx_body.get("public_key", ""),
    )
    tx_body = {
        "from": from_addr,
        "to": zero_addr,
        "value": value,
        "nonce": nonce,
        "gas": gas,
        "data": tx.data,
        "signature": tx.signature,
        "public_key": tx.public_key,
        "hash": tx.hash,
    }
    return _handle_send_tx_obj(tx_body, bc, mp, cfg)


def _handle_call_tx(body: Dict, bc, mp, cfg, wallet=None) -> str:
    """Queue EVM contract call as a signed mempool transaction."""
    to_addr = body.get("to", body.get("contract", body.get("to_addr", "")))
    data = body.get("data", body.get("input", body.get("calldata", "")))
    if not to_addr:
        raise ValueError("contract address (to) required")
    if not str(data).replace("0x", "").strip():
        raise ValueError("calldata required")

    from_addr = body.get("from", body.get("from_address", ""))
    value = _parse_tx_value(body.get("value", body.get("amount", 0)))
    gas = int(body.get("gas", getattr(cfg, "evm_gas_limit", 500_000)))

    tx_body = dict(body or {})
    _reject_auto_sign_in_prod(tx_body, cfg)
    if wallet and (body.get("auto_sign") or not from_addr):
        nonce = bc.db.get_nonce(wallet.address)
        signed = wallet.sign_transaction(
            to_addr,
            int(value) if value == int(value) else value,
            nonce,
            getattr(cfg, "chain_id", 1),
            data=data,
            gas_limit=gas,
        )
        tx_body.update(signed)
        from_addr = wallet.address

    if not from_addr:
        raise ValueError("from address required (or auto_sign with wallet)")

    nonce = int(tx_body.get("nonce", bc.db.get_nonce(from_addr)))
    tx_body = {
        "from": from_addr,
        "to": to_addr,
        "value": value,
        "nonce": nonce,
        "gas": gas,
        "data": data,
        "signature": tx_body.get("signature", ""),
        "public_key": tx_body.get("public_key", ""),
    }
    return _handle_send_tx_obj(tx_body, bc, mp, cfg)


def _handle_devnet_pool_spend(body: Dict, bc, db, cfg, pool_locks) -> Dict:
    """Devnet-only transfer from unlocked ecosystem/treasury/staking pool."""
    import hashlib
    import time as _time

    pool_id = (body.get("pool_id", body.get("pool", "ecosystem")) or "").strip().lower()
    to_addr = (body.get("to", body.get("recipient", "")) or "").strip()
    amount = float(body.get("amount", 0))
    if pool_id not in ("ecosystem", "treasury", "staking"):
        raise ValueError("pool_id must be ecosystem, treasury, or staking")
    if not to_addr:
        raise ValueError("to address required")
    if amount <= 0:
        raise ValueError("amount must be positive")

    from runtime.tokenomics import build_allocations, resolve_founder_address

    founder = resolve_founder_address(
        getattr(cfg, "founder_address", ""),
        getattr(cfg, "miner_address", ""),
    )
    pool_addrs = {p.id: p.address_key for p in build_allocations(founder or None)}
    from_addr = pool_addrs.get(pool_id)
    if not from_addr:
        raise ValueError("pool address not found")

    balance = float(db.get_balance(from_addr))
    allowed, reason = pool_locks.is_outgoing_allowed(from_addr, amount, balance)
    if not allowed:
        raise ValueError(reason)

    db.update_balance(from_addr, -amount)
    db.update_balance(to_addr, amount)
    pool_locks.record_outgoing(from_addr, amount)

    tx_hash = hashlib.sha256(
        f"pool-spend|{from_addr}|{to_addr}|{amount}|{_time.time()}".encode()
    ).hexdigest()[:16]
    height = bc.get_height() if bc and hasattr(bc, "get_height") else 0
    db.save_transaction({
        "hash": tx_hash,
        "from_addr": from_addr,
        "to_addr": to_addr,
        "value": amount,
        "block_height": height,
        "fee": 0.0,
        "status": 1,
        "timestamp": int(_time.time()),
    })

    return {
        "success": True,
        "tx_hash": tx_hash,
        "pool_id": pool_id,
        "from": from_addr,
        "to": to_addr,
        "amount": amount,
        "pool_balance": db.get_balance(from_addr),
        "recipient_balance": db.get_balance(to_addr),
        "spendable_remaining": pool_locks.spendable_balance(from_addr, db.get_balance(from_addr)),
    }


def _handle_send_tx_with_wallet(tx_obj: Dict, bc, mp, cfg, wallet=None) -> str:
    """Submit tx; optional auto_sign fills from/nonce/signature from operational wallet."""
    body = dict(tx_obj or {})
    _reject_auto_sign_in_prod(body, cfg)
    if body.get("auto_sign"):
        if not wallet:
            raise ValueError(
                "auto_sign requires signing wallet "
                "(WALLET_PRIVATE_KEY, private_key in wallet.json, or dev_signer.json)"
            )
        to_addr = body.get("to", body.get("to_addr", ""))
        if not to_addr:
            raise ValueError("auto_sign requires 'to' address")
        value = _parse_tx_value(body.get("value", body.get("amount", 0)))
        nonce_raw = body.get("nonce")
        if nonce_raw is None:
            nonce = bc.db.get_nonce(wallet.address)
        elif isinstance(nonce_raw, str) and nonce_raw.startswith("0x"):
            nonce = int(nonce_raw, 16)
        else:
            nonce = int(nonce_raw)
        signed = wallet.sign_transaction(
            to_addr,
            int(value) if value == int(value) else value,
            nonce,
            getattr(cfg, "chain_id", 1),
            data=body.get("data", body.get("input", "")),
            gas_limit=int(body.get("gas", body.get("gas_limit", 21000))),
        )
        body.update(signed)
        if "gas_limit" in body and "gas" not in body:
            body["gas"] = body["gas_limit"]
    return _handle_send_tx_obj(body, bc, mp, cfg)


def _handle_send_tx(raw_hex: str, bc, mp, cfg) -> str:
    """Принимает raw hex транзакцию (Ethereum RLP или dev JSON) и добавляет в мемпул."""
    if not raw_hex:
        raise ValueError("empty_raw_transaction")
    raw = bytes.fromhex(str(raw_hex).replace("0x", ""))
    if not raw:
        raise ValueError("empty_raw_transaction")
    try:
        from crypto.eth_tx import decode_raw_transaction
        return _handle_send_tx_obj(decode_raw_transaction(raw), bc, mp, cfg)
    except (ValueError, RuntimeError):
        pass
    try:
        decoded = json.loads(raw.decode())
        if not isinstance(decoded, dict):
            raise ValueError("raw_tx_must_decode_to_object")
        return _handle_send_tx_obj(decoded, bc, mp, cfg)
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError) as e:
        raise ValueError(f"invalid_raw_transaction: {e}") from e


def _handle_send_tx_obj(tx_obj: Dict, bc, mp, cfg) -> str:
    """Принимает объект транзакции, валидирует, добавляет в мемпул."""
    from core.blockchain import Transaction
    from blockchain.mempool import MempoolTransaction

    from_addr = tx_obj.get("from", tx_obj.get("from_addr", ""))
    to_addr = tx_obj.get("to", tx_obj.get("to_addr", ""))
    value_raw = tx_obj.get("value", tx_obj.get("amount", 0))
    value = _parse_tx_value(value_raw)

    gas = int(tx_obj.get("gas", cfg.base_gas_price), 16) if isinstance(
        tx_obj.get("gas"), str) else int(tx_obj.get("gas", cfg.base_gas_price))
    nonce = int(tx_obj.get("nonce", 0), 16) if isinstance(
        tx_obj.get("nonce"), str) else int(tx_obj.get("nonce", 0))

    tx = Transaction(
        from_addr=from_addr,
        to_addr=to_addr,
        value=value,
        nonce=nonce,
        gas=gas,
        data=tx_obj.get("data", tx_obj.get("input", "")),
        signature=tx_obj.get("signature", ""),
        public_key=tx_obj.get("public_key", ""),
        tx_hash=tx_obj.get("hash", ""),
    )
    if tx_obj.get("blob_hashes"):
        tx.blob_hashes = list(tx_obj.get("blob_hashes") or [])
    if tx_obj.get("maxFeePerBlobGas") is not None:
        tx.max_fee_per_blob_gas = int(tx_obj.get("maxFeePerBlobGas", 0))
    if tx_obj.get("eth_tx_type"):
        tx.eth_tx_type = str(tx_obj.get("eth_tx_type"))

    validation = bc.validate_transaction(tx)
    if not validation["valid"]:
        raise ValueError(validation["error"])

    # Extra validation via TransactionValidator (Database-backed)
    try:
        from blockchain.tx_validator import TransactionValidator
        from blockchain.state_adapter import DatabaseStateAdapter
        adapter = DatabaseStateAdapter(bc.db)
        tx_dict = {
            "from": from_addr,
            "to": to_addr,
            "amount": value,
            "value": value,
            "nonce": nonce,
            "fee": gas * cfg.gas_price_wei,
            "signature": tx_obj.get("signature", ""),
            "public_key": tx_obj.get("public_key", ""),
            "hash": tx.hash,
            "data": tx_obj.get("data", tx_obj.get("input", "")),
            "gas": gas,
            "gas_limit": tx_obj.get("gas_limit", gas),
        }
        ok, reason = TransactionValidator.validate(
            tx_dict, adapter, mempool=mp, chain_id=getattr(cfg, "chain_id", 1),
            require_signature=bool(
                tx_obj.get("signature") or getattr(cfg, "require_signatures", False)
            ),
        )
        if not ok:
            raise ValueError(f"tx_validator: {reason}")
    except ImportError:
        pass
    except ValueError:
        raise

    fee = gas * cfg.gas_price_wei
    mp_tx = MempoolTransaction(
        tx_hash=tx.hash,
        from_addr=from_addr,
        to_addr=to_addr,
        amount=value,
        fee=fee,
        nonce=nonce,
        signature=tx_obj.get("signature", ""),
        public_key=tx_obj.get("public_key", ""),
        data=tx_obj.get("data", tx_obj.get("input", "")),
        gas=gas,
    )
    if not mp.add(mp_tx):
        raise ValueError("mempool_rejected")

    db = getattr(bc, "db", None)
    node_id = getattr(cfg, "node_id", "")
    if db and hasattr(db, "record_tx_propagation_event"):
        db.record_tx_propagation_event(
            tx.hash, "api_submit", node_id=node_id,
            detail={"from": from_addr, "to": to_addr, "value": value},
        )
        db.record_tx_propagation_event(
            tx.hash, "mempool_local", node_id=node_id,
            detail={"mempool_size": mp.get_size()},
        )

    bus = getattr(RESTHandler, "bus", None)
    if bus:
        from blockchain.mempool_wire import mempool_tx_to_wire
        bus.emit("tx.new", mempool_tx_to_wire(mp_tx))

    return tx.hash


# ═══════════════════════════════════════════════════════════════════════════════
#  Фабрики серверов
# ═══════════════════════════════════════════════════════════════════════════════

def create_rpc_server(blockchain, mempool, config, evm=None, p2p=None, wallet=None, sync_engine=None) -> HTTPServer:
    """Создаёт JSON-RPC сервер на config.rpc_port."""
    configure_rate_limiter(config)
    try:
        from middleware.rpc_auth import RPCApiKeyAuth
        JSONRPCHandler.rpc_auth = RPCApiKeyAuth.from_config(config)
        if JSONRPCHandler.rpc_auth.enabled:
            logger.info("RPC API key auth: enabled")
    except ImportError:
        JSONRPCHandler.rpc_auth = None
    JSONRPCHandler.blockchain = blockchain
    JSONRPCHandler.mempool = mempool
    JSONRPCHandler.config = config
    JSONRPCHandler.evm = evm
    JSONRPCHandler.p2p = p2p
    JSONRPCHandler.wallet = wallet
    JSONRPCHandler.sync_engine = sync_engine
    try:
        from api.eth_filters import EthFilterStore
        JSONRPCHandler.eth_filters = EthFilterStore()
    except ImportError:
        JSONRPCHandler.eth_filters = None
    server = ThreadedHTTPServer((config.rpc_host, config.rpc_port), JSONRPCHandler)
    return server


def create_http_server(blockchain, mempool, db, config,
                       p2p=None, evm=None, nft=None, zk=None,
                       sharding=None, oracles=None, oracle_registry=None,
                       contract_manager=None, assembler=None,
                       pq_manager=None, smart_accounts=None,
                       multisig=None,
                       ai_validator=None, reorg_predictor=None,
                       mev_simulator=None,
                       immutable_state=None,
                       lightning=None, crypto_will=None, plasma=None,
                       wasm_vm=None, ai_manager=None, cross_bridge=None,
                       consensus_engine_standalone=None,
                       consensus_adapter=None,
                       finality_engine=None, sync_engine=None,
                       state_engine=None,
                       slashing_engine=None, validator_registry=None,
                       epoch_manager=None, beacon_finality=None,
                       lmd_table=None, consensus_casper=None,
                       block_validator=None, sphincs=None,
                       canonical_serializer=None,
                       consensus_beacon=None,
                       consensus_engine_slashing=None,
                       casper_finality=None,
                       pool_locks=None,
                       light_client=None,
                       bridge=None,
                       wallet=None,
                       bus=None) -> ThreadedHTTPServer:
    """Создаёт REST API сервер на config.http_port."""
    configure_rate_limiter(config)
    RESTHandler.blockchain = blockchain
    RESTHandler.mempool = mempool
    RESTHandler.config = config
    RESTHandler.db = db
    RESTHandler.p2p = p2p
    RESTHandler.evm = evm
    RESTHandler.nft = nft
    RESTHandler.zk = zk
    RESTHandler.sharding = sharding
    RESTHandler.oracles = oracles
    RESTHandler.oracle_registry = oracle_registry
    RESTHandler.contract_manager = contract_manager
    RESTHandler.assembler = assembler
    RESTHandler.pq_manager = pq_manager
    RESTHandler.smart_accounts = smart_accounts
    RESTHandler.multisig = multisig
    RESTHandler.ai_validator = ai_validator
    RESTHandler.reorg_predictor = reorg_predictor
    RESTHandler.mev_simulator = mev_simulator
    RESTHandler.immutable_state = immutable_state
    RESTHandler.lightning = lightning
    RESTHandler.crypto_will = crypto_will
    RESTHandler.plasma = plasma
    RESTHandler.wasm_vm = wasm_vm
    RESTHandler.ai_manager = ai_manager
    RESTHandler.cross_bridge = cross_bridge
    RESTHandler.consensus_engine_standalone = consensus_engine_standalone
    RESTHandler.consensus_adapter = consensus_adapter
    RESTHandler.finality_engine = finality_engine
    RESTHandler.sync_engine = sync_engine
    RESTHandler.state_engine = state_engine
    RESTHandler.slashing_engine = slashing_engine
    RESTHandler.validator_registry = validator_registry
    RESTHandler.epoch_manager = epoch_manager
    RESTHandler.beacon_finality = beacon_finality
    RESTHandler.lmd_table = lmd_table
    RESTHandler.consensus_casper = consensus_casper
    RESTHandler.block_validator = block_validator
    RESTHandler.sphincs = sphincs
    RESTHandler.canonical_serializer = canonical_serializer
    RESTHandler.consensus_beacon = consensus_beacon
    RESTHandler.consensus_engine_slashing = consensus_engine_slashing
    RESTHandler.casper_finality = casper_finality
    RESTHandler.pool_locks = pool_locks
    RESTHandler.light_client = light_client
    RESTHandler.bridge = bridge
    RESTHandler.wallet = wallet
    RESTHandler.bus = bus
    RESTHandler.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _METRICS_AVAILABLE and RESTHandler.metrics_collector is None:
        RESTHandler.metrics_collector = MetricsCollector()
    server = ThreadedHTTPServer((config.http_host, config.http_port), RESTHandler)
    return server


def _attestation_count_map(consensus_adapter) -> Dict[str, int]:
    """Map block_hash -> attestation vote count from consensus adapter."""
    if not consensus_adapter or not hasattr(consensus_adapter, "get_attestations_by_block"):
        return {}
    out: Dict[str, int] = {}
    for row in consensus_adapter.get_attestations_by_block():
        h = str(row.get("block_hash", "")).lower()
        if h:
            out[h] = int(row.get("votes", 0))
    return out


def start_rpc_server_thread(blockchain, mempool, config, evm=None, p2p=None, wallet=None, sync_engine=None):
    """Запускает JSON-RPC в отдельном потоке. Возвращает (thread, server)."""
    server = create_rpc_server(blockchain, mempool, config, evm, p2p, wallet, sync_engine)
    t = threading.Thread(target=server.serve_forever, daemon=True,
                         name="JSONRPCServer")
    t.start()
    print(f"[RPC] JSON-RPC server started on {config.rpc_host}:{config.rpc_port}")
    return t, server


def start_http_server_thread(blockchain, mempool, db, config,
                              p2p=None, evm=None, nft=None, zk=None,
                              sharding=None, oracles=None, oracle_registry=None,
                              contract_manager=None, assembler=None,
                              pq_manager=None, smart_accounts=None,
                              multisig=None,
                              ai_validator=None, reorg_predictor=None,
                              mev_simulator=None,
                              immutable_state=None,
                              lightning=None, crypto_will=None, plasma=None,
                              wasm_vm=None, ai_manager=None,                               cross_bridge=None,
                              consensus_adapter=None,
                              consensus_engine_standalone=None,
                              finality_engine=None, sync_engine=None,
                              state_engine=None,
                              slashing_engine=None, validator_registry=None,
                              epoch_manager=None, beacon_finality=None,
                              lmd_table=None, consensus_casper=None,
                       block_validator=None, sphincs=None,
                       canonical_serializer=None,
                       consensus_beacon=None,
                       consensus_engine_slashing=None,
                       casper_finality=None,
                       pool_locks=None,
                       light_client=None,
                       bridge=None,
                       wallet=None,
                       bus=None):
    """Запускает REST API в отдельном потоке. Возвращает (thread, server)."""
    server = create_http_server(
        blockchain, mempool, db, config, p2p, evm, nft, zk,
        sharding=sharding, oracles=oracles, oracle_registry=oracle_registry,
        contract_manager=contract_manager, assembler=assembler,
        pq_manager=pq_manager, smart_accounts=smart_accounts,
        multisig=multisig,
        ai_validator=ai_validator, reorg_predictor=reorg_predictor,
        mev_simulator=mev_simulator, immutable_state=immutable_state,
        lightning=lightning, crypto_will=crypto_will, plasma=plasma,
        wasm_vm=wasm_vm, ai_manager=ai_manager,         cross_bridge=cross_bridge,
        consensus_adapter=consensus_adapter,
        consensus_engine_standalone=consensus_engine_standalone,
        finality_engine=finality_engine, sync_engine=sync_engine,
        state_engine=state_engine,
        slashing_engine=slashing_engine, validator_registry=validator_registry,
        epoch_manager=epoch_manager, beacon_finality=beacon_finality,
        lmd_table=lmd_table, consensus_casper=consensus_casper,
        block_validator=block_validator, sphincs=sphincs,
        canonical_serializer=canonical_serializer,
        consensus_beacon=consensus_beacon,
        consensus_engine_slashing=consensus_engine_slashing,
        casper_finality=casper_finality,
        pool_locks=pool_locks,
        light_client=light_client,
        bridge=bridge,
        wallet=wallet,
        bus=bus,
    )
    t = threading.Thread(target=server.serve_forever, daemon=True,
                         name="RESTServer")
    t.start()
    print(f"[HTTP] REST API server started on {config.http_host}:{config.http_port}")
    return t, server


def shutdown_http_server(server, name: str = "HTTP") -> None:
    """Корректно останавливает ThreadedHTTPServer (безопасно с другого потока)."""
    if not server:
        return
    try:
        threading.Thread(target=server.shutdown, daemon=True, name=f"{name}Shutdown").start()
        server.server_close()
        print(f"[{name}] Server shutdown initiated")
    except Exception as e:
        print(f"[{name}] Shutdown warning: {e}")
