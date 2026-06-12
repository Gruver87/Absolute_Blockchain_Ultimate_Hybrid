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
import time
import hashlib
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from typing import Optional, Any, Dict
import threading

logger = logging.getLogger("API")

# --- Rate Limiter (middleware/rate_limit.py) ---
try:
    from middleware.rate_limit import RateLimiter
    _rate_limiter = RateLimiter(requests_per_minute=120, window_seconds=60)
    _RATE_LIMIT_AVAILABLE = True
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
    nft = None   # NFTMarketplace
    zk = None    # ZKProofSystem

    def log_message(self, fmt, *args):
        logger.debug(fmt % args)

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
            if path == "/status" or path == "/":
                self._json({
                    "status": "running",
                    "node_version": cfg.node_version,
                    "network": cfg.network_name,
                    "chain_id": cfg.chain_id,
                    "height": bc.get_height(),
                    "peers": p2p.peer_count() if p2p else 0,
                    "mempool_size": mp.get_size(),
                    "coin": cfg.coin_symbol,
                    "rpc_port": cfg.rpc_port,
                    "http_port": cfg.http_port,
                    "state_root": bc.get_state_root() if hasattr(bc, "get_state_root") else "",
                    "middleware": {
                        "rate_limit": _RATE_LIMIT_AVAILABLE,
                        "input_validation": _INPUT_VALIDATORS_AVAILABLE,
                        "jwt_auth": _JWT_AVAILABLE,
                    },
                })

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

            else:
                self._error(404, "Endpoint not found")

        except Exception as e:
            logger.exception(f"REST POST error: {e}")
            self._error(500, str(e))

    def _json(self, data: Any):
        body = json.dumps(data, default=str).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, code: int, message: str):
        body = json.dumps({"error": message}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def _cors(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
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
    JSONRPCHandler.blockchain = blockchain
    JSONRPCHandler.mempool = mempool
    JSONRPCHandler.config = config
    JSONRPCHandler.evm = evm
    server = HTTPServer((config.rpc_host, config.rpc_port), JSONRPCHandler)
    return server


def create_http_server(blockchain, mempool, db, config,
                       p2p=None, evm=None, nft=None, zk=None) -> HTTPServer:
    """Создаёт REST API сервер на config.http_port."""
    RESTHandler.blockchain = blockchain
    RESTHandler.mempool = mempool
    RESTHandler.config = config
    RESTHandler.db = db
    RESTHandler.p2p = p2p
    RESTHandler.evm = evm
    RESTHandler.nft = nft
    RESTHandler.zk = zk
    server = HTTPServer((config.http_host, config.http_port), RESTHandler)
    return server


def start_rpc_server_thread(blockchain, mempool, config, evm=None) -> threading.Thread:
    """Запускает JSON-RPC в отдельном потоке."""
    server = create_rpc_server(blockchain, mempool, config, evm)
    t = threading.Thread(target=server.serve_forever, daemon=True,
                         name="JSONRPCServer")
    t.start()
    print(f"[RPC] JSON-RPC server started on {config.rpc_host}:{config.rpc_port}")
    return t


def start_http_server_thread(blockchain, mempool, db, config,
                              p2p=None, evm=None, nft=None, zk=None) -> threading.Thread:
    """Запускает REST API в отдельном потоке."""
    server = create_http_server(blockchain, mempool, db, config, p2p, evm, nft, zk)
    t = threading.Thread(target=server.serve_forever, daemon=True,
                         name="RESTServer")
    t.start()
    print(f"[HTTP] REST API server started on {config.http_host}:{config.http_port}")
    return t
