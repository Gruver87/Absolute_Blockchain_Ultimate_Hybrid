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
from typing import Optional, Any, Dict
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

# POST без JWT даже в prod (публичные операции)
_PUBLIC_POST_PATHS = frozenset({"/transactions"})

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

    def log_message(self, fmt, *args):
        logger.debug(fmt % args)

    def do_OPTIONS(self):
        self._send_cors()

    def do_GET(self):
        """Redirect browser GET requests to the Explorer UI on http_port."""
        http_port = self.__class__.config.http_port if self.__class__.config else 8080
        self.send_response(302)
        self.send_header("Location", f"http://localhost:{http_port}/")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

    def do_POST(self):
        # Rate limiting
        if _RATE_LIMIT_AVAILABLE and _rate_limiter:
            client_ip = self.client_address[0]
            allowed, remaining = _rate_limiter.allow_request(client_ip)
            if not allowed:
                self.send_response(429)
                self.send_header("Content-Type", "application/json")
                self.send_header("Retry-After", "60")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "rate_limit_exceeded"}).encode())
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

        # ── net / web3 ─────────────────────────────────────────────────────
        if method == "net_version":
            return str(cfg.chain_id)

        if method == "web3_clientVersion":
            return f"Absolute/{cfg.node_version}/python"

        if method == "net_peerCount":
            return hex(0)

        if method == "eth_chainId":
            return hex(cfg.chain_id)

        # ── Блоки ─────────────────────────────────────────────────────────
        if method == "eth_blockNumber":
            return hex(bc.get_height())

        if method == "eth_getBlockByNumber":
            tag = params[0] if params else "latest"
            full_tx = params[1] if len(params) > 1 else False
            if tag in ("latest", "pending"):
                blk = bc.get_last_block()
            else:
                try:
                    h = int(tag, 16) if tag.startswith("0x") else int(tag)
                    blk = bc.get_block(h)
                except ValueError:
                    blk = None
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
            tx_obj = params[0] if params else {}
            return _handle_send_tx_obj(tx_obj, bc, mp, cfg)

        if method == "eth_getTransactionByHash":
            tx_hash = params[0] if params else ""
            tx = bc.get_transaction(tx_hash)
            return _format_tx(tx)

        if method == "eth_getTransactionReceipt":
            tx_hash = params[0] if params else ""
            tx = bc.get_transaction(tx_hash)
            return _format_receipt(tx)

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
            data = tx_obj.get("data", "")
            if evm_adapter and to_addr:
                gas = evm_adapter.estimate_gas(to_addr, data)
                return hex(gas)
            return hex(cfg.base_gas_price)

        if method == "eth_gasPrice":
            return hex(int(cfg.gas_price_wei * 10**18))

        # ── Мемпул ────────────────────────────────────────────────────────
        if method == "eth_getBlockTransactionCountByNumber":
            return hex(mp.get_size())

        raise ValueError(f"Method not supported: {method}")

    def _send_cors(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _send_json(self, data: Any):
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
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
    contract_manager = None          # MiniVM ContractManager
    assembler = None                 # MiniVM Assembler
    pq_manager = None                # PostQuantumManager
    smart_accounts = None            # SmartAccountManager
    multisig = None                  # MultiSigWallet class
    ai_validator = None              # AIValidatorEngine
    reorg_predictor = None           # ReorgPredictor
    mev_simulator = None             # MEVSimulator
    immutable_state = None           # ImmutableStateManager
    # ── NEW features ───────────────────────────────────────────────────────────
    lightning = None                 # LightningNetwork
    crypto_will = None               # CryptoWillManager
    plasma = None                    # PlasmaChain
    wasm_vm = None                   # WASMVirtualMachine
    ai_manager = None                # AIAgentManager
    cross_bridge = None              # CrossChainBridge
    consensus_engine_standalone = None  # Standalone ConsensusEngine
    finality_engine = None           # FinalityEngine
    sync_engine = None               # SyncEngine
    state_engine = None              # StateEngine
    slashing_engine = None           # SlashingEngine
    validator_registry = None        # ValidatorRegistry
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
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    metrics_collector = None

    def log_message(self, fmt, *args):
        logger.debug(fmt % args)

    @classmethod
    def _cors_origin(cls, request_origin: str = "") -> str:
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
        if path in _PUBLIC_POST_PATHS:
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

    def do_OPTIONS(self):
        self._cors()

    def do_GET(self):
        # Rate limiting
        if _RATE_LIMIT_AVAILABLE and _rate_limiter:
            client_ip = self.client_address[0]
            allowed, remaining = _rate_limiter.allow_request(client_ip)
            if not allowed:
                self.send_response(429)
                self.send_header("Content-Type", "application/json")
                self.send_header("Retry-After", "60")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "rate_limit_exceeded"}).encode())
                return

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
                checks = {
                    "blockchain": bc is not None,
                    "database": db is not None,
                    "mempool": mp is not None,
                }
                ready = all(checks.values())
                payload = {
                    "status": "ready" if ready else "not_ready",
                    "checks": checks,
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
                text = mc.render_prometheus(
                    height=bc.get_height() if bc else 0,
                    peers=p2p.peer_count() if p2p else 0,
                    mempool=mp.get_size() if mp else 0,
                    validators=len(validators),
                    deployment_mode=getattr(cfg, "deployment_mode", "dev"),
                    node_id=getattr(cfg, "node_id", "node-1"),
                )
                body = text.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
                self.send_header("Content-Length", len(body))
                self.end_headers()
                self.wfile.write(body)
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
                self.send_header("Access-Control-Allow-Origin", self._cors_origin(self.headers.get("Origin", "")))
                self.end_headers()
                self.wfile.write(body)
                return

            if path == "/status":
                validators = db.get_validators() if db else []
                total_burned = db.get_total_burned() if db else 0
                total_supply = db.get_total_supply() if db and hasattr(db, "get_total_supply") else 0
                self._json({
                    "status": "running",
                    "node_version": cfg.node_version,
                    "network_name": cfg.network_name,
                    "chain_name": cfg.network_name,
                    "chain_id": cfg.chain_id,
                    "height": bc.get_height(),
                    "peers": p2p.peer_count() if p2p else 0,
                    "mempool_size": mp.get_size(),
                    "coin": cfg.coin_symbol,
                    "coin_symbol": cfg.coin_symbol,
                    "max_supply": getattr(cfg, "max_supply", 221_000_000),
                    "total_supply": total_supply,
                    "founder_initials": getattr(cfg, "founder_initials", "D.U.P."),
                    "founder_percent": getattr(cfg, "founder_percent", 17.4),
                    "founder_address": getattr(cfg, "founder_address", ""),
                    "rpc_port": cfg.rpc_port,
                    "http_port": cfg.http_port,
                    "state_root": bc.get_state_root() if hasattr(bc, "get_state_root") else "",
                    "validator_count": len(validators),
                    "total_burned": total_burned,
                    "evm_enabled": cfg.evm_enabled,
                    "bridge_enabled": cfg.bridge_enabled,
                    "deployment_mode": getattr(cfg, "deployment_mode", "dev"),
                    "node_id": getattr(cfg, "node_id", "node-1"),
                    "health": {
                        "live": "/health/live",
                        "ready": "/health/ready",
                        "metrics": "/metrics",
                    },
                    "middleware": {
                        "rate_limit": _RATE_LIMIT_AVAILABLE,
                        "input_validation": _INPUT_VALIDATORS_AVAILABLE,
                        "jwt_auth": _JWT_AVAILABLE,
                    },
                })

            elif path == "/tokenomics":
                try:
                    from runtime.tokenomics import get_tokenomics_summary
                    founder = getattr(cfg, "founder_address", "") or ""
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
                    from runtime.tokenomics import get_tokenomics_summary
                    founder = getattr(cfg, "founder_address", "") or ""
                    t = get_tokenomics_summary(founder or None)
                    bal = db.get_balance(founder) if db and founder else 0
                    self._json({**t["founder"], "balance_abs": bal, "conditions": t["conditions"]})
                except Exception as e:
                    self._json({"error": str(e)})

            elif path == "/allocation":
                try:
                    from runtime.tokenomics import get_tokenomics_summary
                    founder = getattr(cfg, "founder_address", "") or ""
                    t = get_tokenomics_summary(founder or None)
                    self._json({
                        "max_supply": t["max_supply"],
                        "allocations": t["allocations"],
                        "genesis_minted": t["genesis_minted"],
                        "mining_reserve": t["mining_reserve"],
                    })
                except Exception as e:
                    self._json({"error": str(e)})

            elif path == "/blocks":
                limit = int(qs.get("limit", ["20"])[0])
                blocks = db.get_latest_blocks(min(limit, 100))
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
                tx = bc.get_transaction(tx_hash)
                if tx:
                    self._json(tx)
                else:
                    self._error(404, "Transaction not found")

            elif path.startswith("/address/"):
                addr = path.split("/address/")[1]
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
                self._json({
                    "stats": stats,
                    "transactions": [
                        {
                            "hash": tx.tx_hash,
                            "from": tx.from_addr,
                            "to": tx.to_addr,
                            "value": tx.amount,
                            "fee": tx.fee,
                            "nonce": tx.nonce,
                        }
                        for tx in txs
                    ],
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

            elif path == "/network/peers":
                peers_info = p2p.get_peers_info() if p2p else []
                self._json({
                    "peers": peers_info,
                    "count": len(peers_info),
                    "p2p_port": cfg.p2p_port,
                })

            elif path == "/network/stats":
                self._json(p2p.get_stats() if p2p else {})

            elif path == "/consensus/stats":
                # Full consensus stats including LMD-GHOST + slashing + PBS
                from consensus.adapter import ConsensusAdapter
                # We expose stats via the blockchain stats endpoint since we don't
                # hold a reference here — expose what's in DB
                validators = db.get_validators()
                checkpoints = db.get_checkpoints() if hasattr(db, "get_checkpoints") else []
                self._json({
                    "validators": len(validators),
                    "checkpoints": len(checkpoints) if isinstance(checkpoints, list) else 0,
                    "systems": {
                        "lmd_ghost": True,
                        "casper_ffg": True,
                        "slashing": True,
                        "pbs": True,
                        "validator_registry": True,
                    },
                    "description": "Unified consensus: LMD-GHOST + Casper FFG + Slashing + PBS",
                })

            elif path == "/auth/token":
                # JWT token generation endpoint
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
                    self._json(sharding.get_stats())
                else:
                    self._json({"error": "sharding not enabled", "enabled": False})

            # ── Oracles ───────────────────────────────────────────────────────
            elif path in ("/oracles/prices", "/oracles"):
                oracles = self.__class__.oracles
                if not oracles:
                    self._json({"error": "oracles not enabled", "prices": []})
                    return
                try:
                    result = []
                    for sym in ["bitcoin", "ethereum"]:
                        p = oracles.get_crypto_price(sym)
                        if p:
                            result.append({
                                "symbol": sym, "price": p.price,
                                "change_24h": p.change_24h, "volume": p.volume,
                            })
                    self._json({"prices": result, "count": len(result)})
                except Exception as e:
                    self._json({"prices": [], "error": str(e)})

            # ── Short URL aliases ─────────────────────────────────────────────
            elif path.startswith("/block/"):
                param = path.split("/block/")[1]
                try:
                    blk = bc.get_block(int(param))
                    if blk: self._json(blk)
                    else: self._error(404, "Block not found")
                except Exception:
                    self._error(400, "Invalid block number")

            elif path.startswith("/tx/"):
                tx_hash = path.split("/tx/")[1]
                tx = bc.get_transaction(tx_hash)
                if tx: self._json(tx)
                else: self._error(404, "Transaction not found")

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

            # ── MEV Simulator ─────────────────────────────────────────────────
            elif path == "/mev/stats":
                mev = self.__class__.mev_simulator
                if mev:
                    self._json(mev.get_statistics())
                else:
                    self._json({"enabled": False})

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
                            self._json({"city": city,
                                        "temperature": getattr(w, "temperature", None),
                                        "condition":   getattr(w, "condition", None),
                                        "humidity":    getattr(w, "humidity", None)})
                        else:
                            self._json({"city": city, "error": "no data"})
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

            # ── Lightning Network ─────────────────────────────────────────────
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
            elif path == "/bridge2/stats":
                cb = self.__class__.cross_bridge
                self._json(cb.get_bridge_stats() if cb else {"enabled": False})

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
            elif path == "/sync/status":
                se = self.__class__.sync_engine
                self._json(se.get_status() if se else {"enabled": False})

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
                    result = pq.encapsulate(pubkey, algo)
                    self._json({"ciphertext": str(result), "algorithm": algo})
                else:
                    self._json({"enabled": bool(pq), "error": "encapsulate not available"})

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
                if sh and hasattr(sh, "get_shard_balance"):
                    self._json({"address": addr, "balance": sh.get_shard_balance(addr)})
                elif sh and hasattr(sh, "shards"):
                    total = 0
                    for shard in sh.shards.values():
                        if hasattr(shard, "balances"):
                            total += shard.balances.get(addr, 0)
                    self._json({"address": addr, "total_shard_balance": total})
                else:
                    self._error(404, "Sharding not enabled")

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
                br = self.__class__.bridge if hasattr(self.__class__,'bridge') else None
                locks = list(getattr(br, "locks", {}).values()) if br else []
                self._json({"locks": locks, "count": len(locks)})

            # ── ZK verify range ───────────────────────────────────────────────
            elif path == "/zk/verify/range":
                zk = self.__class__.zk
                value = int(qs.get("value", ["42"])[0])
                min_v = int(qs.get("min", ["0"])[0])
                max_v = int(qs.get("max", ["100"])[0])
                proof = qs.get("proof", [""])[0]
                if zk and hasattr(zk, "verify_range"):
                    ok = zk.verify_range(proof, value, min_v, max_v)
                    self._json({"valid": bool(ok)})
                else:
                    self._json({"valid": value >= min_v and value <= max_v, "simulated": True})

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
            elif path == "/validators/registry":
                vr = self.__class__.validator_registry
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
                    kp = sph.generate_keypair()
                    self._json({"public_key": str(kp[0] if isinstance(kp,tuple) else kp),
                                "algorithm": "SPHINCS+"})
                else:
                    self._json({"enabled": bool(sph), "error": "SPHINCS+ not available"})

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

            # ── MEV frontrun simulation ───────────────────────────────────────
            elif path == "/mev/frontrun":
                mev = self.__class__.mev_simulator
                tx_hash = qs.get("tx_hash", ["sample_tx"])[0]
                if mev and hasattr(mev, "simulate_frontrun"):
                    result = mev.simulate_frontrun(tx_hash)
                    self._json(result if isinstance(result, dict) else {"result": str(result)})
                else:
                    self._json({"profit_potential": 0.0, "feasible": False, "enabled": bool(mev)})

            # ── Reorg depth & fork analysis ───────────────────────────────────
            elif path == "/reorg/depth":
                rp = self.__class__.reorg_predictor
                if rp and hasattr(rp, "predict_reorg_depth"):
                    depth = rp.predict_reorg_depth()
                    self._json({"predicted_depth": depth})
                else:
                    self._json({"predicted_depth": 0, "enabled": bool(rp)})

            elif path == "/reorg/fork":
                rp = self.__class__.reorg_predictor
                if rp and hasattr(rp, "analyze_fork"):
                    analysis = rp.analyze_fork()
                    self._json(analysis if isinstance(analysis, dict) else {"analysis": str(analysis)})
                else:
                    self._json({"fork_detected": False, "enabled": bool(rp)})

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
                if sh and hasattr(sh, "nodes"):
                    self._json({"nodes": list(sh.nodes.keys()) if isinstance(sh.nodes, dict) else sh.nodes})
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
        # Rate limiting
        if _RATE_LIMIT_AVAILABLE and _rate_limiter:
            client_ip = self.client_address[0]
            allowed, remaining = _rate_limiter.allow_request(client_ip)
            if not allowed:
                self.send_response(429)
                self.send_header("Content-Type", "application/json")
                self.send_header("Retry-After", "60")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "rate_limit_exceeded"}).encode())
                return

        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")

        self._track_request()
        if not self._require_jwt_admin(path):
            return
        length = int(self.headers.get("Content-Length", 0))
        body = {}
        if length:
            try:
                raw_body = json.loads(self.rfile.read(length))
                body = sanitize_input(raw_body) if _INPUT_VALIDATORS_AVAILABLE else raw_body
            except json.JSONDecodeError:
                self._error(400, "Invalid JSON")
                return

        bc = self.__class__.blockchain
        mp = self.__class__.mempool
        cfg = self.__class__.config
        evm_adapter = self.__class__.evm

        try:
            if path == "/transactions":
                result = _handle_send_tx_obj(body, bc, mp, cfg)
                self._json({"tx_hash": result, "status": "pending"})

            elif path == "/contract/deploy":
                if not evm_adapter:
                    self._error(503, "EVM not enabled")
                    return
                result = evm_adapter.deploy_contract(
                    deployer=body.get("from", ""),
                    bytecode_hex=body.get("bytecode", ""),
                    value=float(body.get("value", 0)),
                )
                self._json(result.to_dict())

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
                    self._json({**result, "owners": owners, "required": required})
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
                    if hasattr(pqm, "generate_keys"):
                        keys = pqm.generate_keys(algo)
                    elif hasattr(pqm, "keygen"):
                        keys = pqm.keygen(algo)
                    else:
                        keys = {"error": "keygen not available"}
                    self._json({"algorithm": algo, "keys": keys})
                except Exception as e:
                    self._error(500, str(e))

            elif path == "/pq/sign":
                pqm = self.__class__.pq_manager
                if not pqm:
                    self._error(503, "PostQuantumManager not enabled"); return
                message = body.get("message", "")
                algo    = body.get("algorithm", "dilithium")
                try:
                    if hasattr(pqm, "sign"):
                        sig = pqm.sign(message, algo)
                        self._json({"algorithm": algo, "signature": sig})
                    else:
                        self._error(501, "sign not implemented in PQ manager")
                except Exception as e:
                    self._error(500, str(e))

            elif path == "/pq/verify":
                pqm = self.__class__.pq_manager
                if not pqm:
                    self._error(503, "PostQuantumManager not enabled"); return
                message   = body.get("message", "")
                signature = body.get("signature", "")
                algo      = body.get("algorithm", "dilithium")
                try:
                    if hasattr(pqm, "verify"):
                        ok = pqm.verify(message, signature, algo)
                        self._json({"algorithm": algo, "valid": ok})
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
                        acc = {"error": "create not supported"}
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
                        key = {"error": "session_keys not supported"}
                    self._json({"account": account, "session_key": key})
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
                        self._json({"success": ok, "account": account, "new_owner": new_owner})
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
                    self._error(503, "MEV simulator not enabled"); return
                txs_raw = body.get("transactions", [])
                try:
                    from features.mev_simulator import Transaction as MevTx
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
                        self._json({"success": True, "auction_id": aid})
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
                        self._json({"success": bool(result), "result": result})
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
                        self._json({"success": True, "listing_id": lid})
                    elif hasattr(nft, "list_token"):
                        lid = nft.list_token(token_id, seller, price)
                        self._json({"success": True, "listing_id": lid})
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
                    self._json({"success": bool(oid), "offer_id": oid})
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
                    self._json(result)
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
                    self._json(result)
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
                    tx_data = {"from": from_addr, "to": to_addr,
                               "amount": amount, "nonce": nonce,
                               "fee": float(body.get("fee", 0.001))}
                    tx_hash = TransactionSigner.hash_transaction(tx_data)
                    sig = TransactionSigner.sign_transaction(tx_data, private_key)
                    self._json({"tx_hash": tx_hash, "signature": sig,
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
                self._json({"success": ok, "channel_id": cid})

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
                self._json({"success": ok})

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
                self._json({"success": bool(txh), "tx_hash": txh})

            elif path == "/plasma/submit-block":
                pl = self.__class__.plasma
                if not pl:
                    self._error(503, "Plasma not enabled"); return
                proposer = body.get("proposer", "operator")
                result = pl.submit_block(proposer)
                if result:
                    self._json({"success": True, "block": result})
                else:
                    self._json({"success": False, "message": "No pending transactions"})

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
                self._json(result)

            # ── Cross-Chain Bridge ────────────────────────────────────────────
            elif path == "/bridge2/transfer":
                cb = self.__class__.cross_bridge
                if not cb:
                    self._error(503, "Cross-chain bridge not enabled"); return
                from_chain = body.get("from_chain", "ethereum")
                to_chain = body.get("to_chain", "absolute")
                from_addr = body.get("from_address", "")
                to_addr = body.get("to_address", "")
                amount = float(body.get("amount", 0))
                if not from_addr or not to_addr or amount <= 0:
                    self._error(400, "from_address, to_address, amount required"); return
                tx_hash = cb.bridge(from_chain, to_chain, from_addr, to_addr, amount)
                cb.confirm_transaction(tx_hash)
                fee = cb.estimate_fee(from_chain, amount)
                self._json({"success": True, "tx_hash": tx_hash,
                            "from_chain": from_chain, "to_chain": to_chain,
                            "amount": amount - fee, "fee": fee, "status": "confirmed"})

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
                tx_id = body.get("tx_id", "")
                if hasattr(plasma, "finalize_exit"):
                    result = plasma.finalize_exit(tx_id)
                    self._json(result if isinstance(result, dict) else {"success": bool(result)})
                else:
                    self._json({"success": False, "error": "finalize_exit not available"})

            # ── Bridge: lock, confirm, refund ─────────────────────────────────
            elif path == "/bridge/lock":
                br = getattr(self.__class__, "bridge", None) or self.__class__.cross_bridge
                if not br:
                    self._error(503, "Bridge not enabled"); return
                amount = float(body.get("amount", 0))
                from_addr = body.get("from_address", body.get("from", ""))
                target_chain = body.get("target_chain", "ETH")
                if hasattr(br, "lock_and_bridge"):
                    result = br.lock_and_bridge(from_addr, amount, target_chain)
                    self._json(result if isinstance(result, dict) else {"success": bool(result)})
                elif hasattr(br, "transfer"):
                    result = br.transfer(from_addr, body.get("to_address",""), amount, target_chain)
                    self._json(result if isinstance(result, dict) else {"success": bool(result)})
                else:
                    self._json({"success": False, "error": "lock not available"})

            elif path == "/bridge/confirm":
                br = getattr(self.__class__, "bridge", None) or self.__class__.cross_bridge
                if not br:
                    self._error(503, "Bridge not enabled"); return
                tx_id = body.get("tx_id", "")
                if hasattr(br, "confirm_incoming"):
                    result = br.confirm_incoming(tx_id)
                    self._json(result if isinstance(result, dict) else {"success": bool(result)})
                else:
                    self._json({"success": False, "error": "confirm not available"})

            elif path == "/bridge/refund":
                br = getattr(self.__class__, "bridge", None) or self.__class__.cross_bridge
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
                    sig = sph.sign(message.encode() if isinstance(message,str) else message,
                                   private_key)
                    self._json({"signature": str(sig), "algorithm": "SPHINCS+"})
                else:
                    self._json({"success": False, "error": "sign not available"})

            elif path == "/pq/sphincs/verify":
                sph = self.__class__.sphincs
                if not sph:
                    self._error(503, "SPHINCS+ not enabled"); return
                message = body.get("message", "")
                signature = body.get("signature", "")
                public_key = body.get("public_key", "")
                if hasattr(sph, "verify"):
                    ok = sph.verify(message.encode() if isinstance(message,str) else message,
                                    signature, public_key)
                    self._json({"valid": bool(ok), "algorithm": "SPHINCS+"})
                else:
                    self._json({"valid": False, "error": "verify not available"})

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

            # ── Sync: fast sync, add/remove peer ─────────────────────────────
            elif path == "/sync/fast-sync":
                se = self.__class__.sync_engine
                if not se:
                    self._error(503, "SyncEngine not enabled"); return
                target_block = int(body.get("target_block", 0))
                if hasattr(se, "fast_sync"):
                    result = se.fast_sync(target_block)
                    self._json({"success": bool(result), "target_block": target_block})
                else:
                    self._json({"success": False, "error": "fast_sync not available"})

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
                    sig = pq.hybrid_sign(message, private_key)
                    self._json({"signature": str(sig), "algorithm": "hybrid"})
                else:
                    import hashlib
                    self._json({"signature": hashlib.sha256(message.encode()).hexdigest(),
                                "algorithm": "sha256_fallback"})

            elif path == "/pq/hybrid-encrypt":
                pq = self.__class__.pq_manager
                if not pq:
                    self._error(503, "PQ not enabled"); return
                message = body.get("message", "")
                public_key = body.get("public_key", "")
                if hasattr(pq, "hybrid_encrypt"):
                    ciphertext = pq.hybrid_encrypt(message, public_key)
                    self._json({"ciphertext": str(ciphertext), "algorithm": "kyber_hybrid"})
                else:
                    self._json({"ciphertext": None, "error": "hybrid_encrypt not available"})

            # ── PQ hybrid decrypt ─────────────────────────────────────────────
            elif path == "/pq/hybrid-decrypt":
                pq = self.__class__.pq_manager
                ciphertext = body.get("ciphertext", "")
                private_key = body.get("private_key", "")
                if pq and hasattr(pq, "hybrid_decrypt"):
                    plaintext = pq.hybrid_decrypt(ciphertext, private_key)
                    self._json({"plaintext": str(plaintext)})
                else:
                    self._json({"plaintext": None, "error": "hybrid_decrypt not available"})

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
                elif sa and hasattr(sa, "get_account"):
                    acc = sa.get_account(account_address)
                    self._json({"authenticated": acc is not None})
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
                mev = self.__class__.mev_simulator
                tx_data = body.get("transaction", {})
                tx_hash = body.get("tx_hash", "sample_tx")
                if mev and hasattr(mev, "simulate_frontrun"):
                    result = mev.simulate_frontrun(tx_hash)
                    self._json(result if isinstance(result, dict) else {"result": str(result)})
                else:
                    self._json({"profit_potential": 0.0, "feasible": False, "enabled": bool(mev)})

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
                    self._json({"valid": value >= min_v and value <= max_v, "simulated": True})

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
    return {
        "number": hex(blk.get("height", 0)),
        "hash": blk.get("hash", blk.get("block_hash", "")),
        "parentHash": blk.get("parent_hash", ""),
        "timestamp": hex(blk.get("timestamp", 0)),
        "miner": blk.get("miner", ""),
        "gasUsed": hex(blk.get("gas_used", 0)),
        "transactions": blk.get("transactions", []) if full_tx else
                        [tx.get("hash", "") if isinstance(tx, dict) else tx
                         for tx in blk.get("transactions", [])],
        "totalBurned": blk.get("total_burned", 0.0),
        "txCount": blk.get("tx_count", 0),
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


def _format_receipt(tx: Optional[Dict]) -> Optional[Dict]:
    if not tx:
        return None
    return {
        "transactionHash": tx.get("hash", tx.get("tx_hash", "")),
        "blockNumber": hex(tx.get("block_height", 0)),
        "from": tx.get("from_addr", tx.get("from", "")),
        "to": tx.get("to_addr", tx.get("to", "")),
        "status": hex(tx.get("status", 1)),
        "gasUsed": hex(tx.get("gas_used", tx.get("gas", 21000))),
        "logs": [],
        "burned": tx.get("burned", 0.0),
    }


def _handle_send_tx(raw_hex: str, bc, mp, cfg) -> str:
    """Принимает raw hex транзакцию и добавляет в мемпул."""
    try:
        raw = bytes.fromhex(raw_hex.replace("0x", ""))
        decoded = json.loads(raw.decode())
        return _handle_send_tx_obj(decoded, bc, mp, cfg)
    except Exception:
        tx_hash = "0x" + hashlib.sha256(raw_hex.encode()).hexdigest()
        return tx_hash


def _handle_send_tx_obj(tx_obj: Dict, bc, mp, cfg) -> str:
    """Принимает объект транзакции, валидирует, добавляет в мемпул."""
    from core.blockchain import Transaction
    from blockchain.mempool import MempoolTransaction

    from_addr = tx_obj.get("from", tx_obj.get("from_addr", ""))
    to_addr = tx_obj.get("to", tx_obj.get("to_addr", ""))
    value_raw = tx_obj.get("value", tx_obj.get("amount", 0))

    # Обрабатываем hex value (Ethereum-style)
    if isinstance(value_raw, str) and value_raw.startswith("0x"):
        value = int(value_raw, 16) / 10**18
    else:
        value = float(value_raw)

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
    )

    validation = bc.validate_transaction(tx)
    if not validation["valid"]:
        raise ValueError(validation["error"])

    # Extra validation via TransactionValidator (nonce/fee/balance/size caps)
    try:
        from blockchain.tx_validator import TransactionValidator
        _state = getattr(bc, "state_engine", None)
        if _state:
            tx_dict = {"from": from_addr, "to": to_addr, "amount": value, "nonce": nonce,
                       "fee": gas * cfg.gas_price_wei}
            ok, reason = TransactionValidator.validate(tx_dict, _state)
            if not ok:
                raise ValueError(f"tx_validator: {reason}")
    except ImportError:
        pass
    except ValueError:
        raise
    except Exception:
        pass  # tx_validator is best-effort

    fee = gas * cfg.gas_price_wei
    mp_tx = MempoolTransaction(
        tx_hash=tx.hash,
        from_addr=from_addr,
        to_addr=to_addr,
        amount=value,
        fee=fee,
        nonce=nonce,
    )
    mp.add(mp_tx)

    return tx.hash


# ═══════════════════════════════════════════════════════════════════════════════
#  Фабрики серверов
# ═══════════════════════════════════════════════════════════════════════════════

def create_rpc_server(blockchain, mempool, config, evm=None) -> HTTPServer:
    """Создаёт JSON-RPC сервер на config.rpc_port."""
    configure_rate_limiter(config)
    JSONRPCHandler.blockchain = blockchain
    JSONRPCHandler.mempool = mempool
    JSONRPCHandler.config = config
    JSONRPCHandler.evm = evm
    server = ThreadedHTTPServer((config.rpc_host, config.rpc_port), JSONRPCHandler)
    return server


def create_http_server(blockchain, mempool, db, config,
                       p2p=None, evm=None, nft=None, zk=None,
                       sharding=None, oracles=None,
                       contract_manager=None, assembler=None,
                       pq_manager=None, smart_accounts=None,
                       multisig=None,
                       ai_validator=None, reorg_predictor=None,
                       mev_simulator=None,
                       immutable_state=None,
                       lightning=None, crypto_will=None, plasma=None,
                       wasm_vm=None, ai_manager=None, cross_bridge=None,
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
                       light_client=None) -> ThreadedHTTPServer:
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
    RESTHandler.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _METRICS_AVAILABLE and RESTHandler.metrics_collector is None:
        RESTHandler.metrics_collector = MetricsCollector()
    server = ThreadedHTTPServer((config.http_host, config.http_port), RESTHandler)
    return server


def start_rpc_server_thread(blockchain, mempool, config, evm=None):
    """Запускает JSON-RPC в отдельном потоке. Возвращает (thread, server)."""
    server = create_rpc_server(blockchain, mempool, config, evm)
    t = threading.Thread(target=server.serve_forever, daemon=True,
                         name="JSONRPCServer")
    t.start()
    print(f"[RPC] JSON-RPC server started on {config.rpc_host}:{config.rpc_port}")
    return t, server


def start_http_server_thread(blockchain, mempool, db, config,
                              p2p=None, evm=None, nft=None, zk=None,
                              sharding=None, oracles=None,
                              contract_manager=None, assembler=None,
                              pq_manager=None, smart_accounts=None,
                              multisig=None,
                              ai_validator=None, reorg_predictor=None,
                              mev_simulator=None,
                              immutable_state=None,
                              lightning=None, crypto_will=None, plasma=None,
                              wasm_vm=None, ai_manager=None, cross_bridge=None,
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
                       light_client=None):
    """Запускает REST API в отдельном потоке. Возвращает (thread, server)."""
    server = create_http_server(
        blockchain, mempool, db, config, p2p, evm, nft, zk,
        sharding=sharding, oracles=oracles,
        contract_manager=contract_manager, assembler=assembler,
        pq_manager=pq_manager, smart_accounts=smart_accounts,
        multisig=multisig,
        ai_validator=ai_validator, reorg_predictor=reorg_predictor,
        mev_simulator=mev_simulator, immutable_state=immutable_state,
        lightning=lightning, crypto_will=crypto_will, plasma=plasma,
        wasm_vm=wasm_vm, ai_manager=ai_manager, cross_bridge=cross_bridge,
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
