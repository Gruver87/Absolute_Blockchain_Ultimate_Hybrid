#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔══════════════════════════════════════════════════════════╗
║         ABSOLUTE BLOCKCHAIN NODE — main.py               ║
║  Единственная точка запуска всего узла.                  ║
╚══════════════════════════════════════════════════════════╝

Использование:
    python main.py                         # полный узел (miner + validator)
    python main.py --mode miner            # только майнинг
    python main.py --mode validator        # только валидация
    python main.py --mode rpc-only         # только RPC/HTTP без майнинга
    python main.py --config node.json      # кастомный конфиг из файла
    python main.py --port 5001             # другой P2P-порт
    python main.py --peers 127.0.0.1:5000  # bootstrap-пиры
    python main.py --data-dir ./mydata     # кастомная директория данных
"""

import asyncio
import argparse
import signal
import sys
import os
import time
import threading
import logging


def _configure_stdio_utf8() -> None:
    """Windows cp1251 consoles crash on emoji in print when stdout is redirected."""
    if sys.platform != "win32":
        return
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


_configure_stdio_utf8()

# ── Настройка путей ──────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# ── Импорты всех модулей узла ────────────────────────────────────────────────
from runtime.config import Config
from storage.database import Database
from core.blockchain import Blockchain, Transaction
from blockchain.mempool import Mempool, MempoolTransaction
from kernel.event_bus import EventBus
from consensus.adapter import ConsensusAdapter
from execution.evm_adapter import EVMAdapter
from network.p2p_node import P2PNode
from api.http import start_rpc_server_thread, start_http_server_thread, shutdown_http_server
from network.websocket import WebSocketServer
from bridge.abs_bridge import RustBridge
from features.nft import NFTMarketplace
from features.zk import ZKProofSystem

# --- Wallet (ECDSA miner key generation) ---
try:
    from crypto.wallet import Wallet
    _WALLET_AVAILABLE = True
except ImportError:
    _WALLET_AVAILABLE = False

# --- Dynamic Sharding ---
try:
    from dynamic_sharding import ShardingManager
    _SHARDING_AVAILABLE = True
except Exception:
    _SHARDING_AVAILABLE = False

# --- Real World Oracles ---
try:
    from features.oracle_registry import OracleFeedRegistry
    _ORACLE_REGISTRY_AVAILABLE = True
except Exception:
    OracleFeedRegistry = None  # type: ignore
    _ORACLE_REGISTRY_AVAILABLE = False

try:
    from real_world_oracles import OracleManager
    _ORACLE_MANAGER_AVAILABLE = True
except Exception:
    _ORACLE_MANAGER_AVAILABLE = False

_ORACLES_AVAILABLE = _ORACLE_REGISTRY_AVAILABLE or _ORACLE_MANAGER_AVAILABLE

# --- Multisig Wallets ---
try:
    from features.multisig import MultiSigWallet
    _MULTISIG_AVAILABLE = True
except Exception:
    _MULTISIG_AVAILABLE = False

# --- Smart Accounts ---
try:
    from features.smart_accounts import SmartAccountManager
    _SMART_ACCOUNTS_AVAILABLE = True
except Exception:
    _SMART_ACCOUNTS_AVAILABLE = False

# --- Post-Quantum Crypto ---
try:
    from crypto.sphincs_plus import SPHINCSPLUS as SphincsPlus
    _POSTQUANTUM_AVAILABLE = True
except Exception:
    _POSTQUANTUM_AVAILABLE = False

# --- MiniVM Contract Manager + Assembler ---
try:
    from execution.contract_manager import ContractManager
    from compiler.assembler import Assembler, assemble
    _MINIVM_CONTRACTS_AVAILABLE = True
except Exception:
    _MINIVM_CONTRACTS_AVAILABLE = False

# --- BlockBuilder ---
try:
    from execution.block_builder import BlockBuilder
    _BLOCK_BUILDER_AVAILABLE = True
except Exception:
    _BLOCK_BUILDER_AVAILABLE = False

# --- ValidatorKeys ---
try:
    from crypto.validator_keys import ValidatorKeys
    _VALIDATOR_KEYS_AVAILABLE = True
except Exception:
    _VALIDATOR_KEYS_AVAILABLE = False

# --- Transaction Validator ---
try:
    from blockchain.tx_validator import TransactionValidator
    _TX_VALIDATOR_AVAILABLE = True
except Exception:
    _TX_VALIDATOR_AVAILABLE = False

# --- RANDAO Validator Selection ---
try:
    from consensus.validator_selection import ValidatorSelection
    _VALIDATOR_SELECTION_AVAILABLE = True
except Exception:
    _VALIDATOR_SELECTION_AVAILABLE = False

# --- Chain Storage (JSON file backup) ---
try:
    from storage.chain_storage import ChainStorage
    _CHAIN_STORAGE_AVAILABLE = True
except Exception:
    _CHAIN_STORAGE_AVAILABLE = False

# --- PostQuantum Manager (full suite) ---
try:
    from features.postquantum import PostQuantumManager
    _PQ_MANAGER_AVAILABLE = True
except Exception:
    _PQ_MANAGER_AVAILABLE = False

# --- AI Validator Engine ---
try:
    from features.ai_validator import AIValidatorEngine
    _AI_VALIDATOR_AVAILABLE = True
except Exception:
    _AI_VALIDATOR_AVAILABLE = False

# --- Reorg Predictor ---
try:
    from features.reorg_predictor import ReorgPredictor
    _REORG_PREDICTOR_AVAILABLE = True
except Exception:
    _REORG_PREDICTOR_AVAILABLE = False

# --- MEV Simulator ---
try:
    from features.mev_simulator import MEVSimulator
    _MEV_SIMULATOR_AVAILABLE = True
except Exception:
    _MEV_SIMULATOR_AVAILABLE = False

# --- Immutable State Manager (satoshi-precision balances) ---
try:
    from blockchain.immutable_state import ImmutableStateManager
    _IMMUTABLE_STATE_AVAILABLE = True
except Exception:
    _IMMUTABLE_STATE_AVAILABLE = False

# --- Lightning Network (payment channels) ---
try:
    from features.lightning import LightningNetwork
    _LIGHTNING_AVAILABLE = True
except Exception:
    _LIGHTNING_AVAILABLE = False

# --- Crypto Will (blockchain inheritance) ---
try:
    from features.crypto_will import CryptoWillManager
    _CRYPTO_WILL_AVAILABLE = True
except Exception:
    _CRYPTO_WILL_AVAILABLE = False

# --- Plasma Chain (L2 sidechain) ---
try:
    from features.plasma import PlasmaChain
    _PLASMA_AVAILABLE = True
except Exception:
    _PLASMA_AVAILABLE = False

# --- WASM VM (WebAssembly-style smart contracts) ---
try:
    from features.wasm_vm import WASMVirtualMachine
    _WASM_VM_AVAILABLE = True
except Exception:
    _WASM_VM_AVAILABLE = False

# --- AI Agent Manager (trading agents) ---
try:
    from features.ai_manager import AIAgentManager
    _AI_MANAGER_AVAILABLE = True
except Exception:
    _AI_MANAGER_AVAILABLE = False

# --- Cross-Chain Bridge Simulator ---
try:
    from cross_chain_bridge import CrossChainBridge
    _CROSS_BRIDGE_AVAILABLE = True
except Exception:
    _CROSS_BRIDGE_AVAILABLE = False

# --- Standalone Consensus Engine (PoS slots/epochs) ---
try:
    from consensus_engine import ConsensusEngine as StandaloneConsensusEngine
    _CONSENSUS_ENGINE_AVAILABLE = True
except Exception:
    _CONSENSUS_ENGINE_AVAILABLE = False

# --- Finality Engine (Casper FFG) ---
try:
    from finality_engine import FinalityEngine
    _FINALITY_ENGINE_AVAILABLE = True
except Exception:
    _FINALITY_ENGINE_AVAILABLE = False

# --- Sync Engine ---
try:
    from sync.sync_engine import SyncEngine
    _SYNC_ENGINE_AVAILABLE = True
except Exception:
    _SYNC_ENGINE_AVAILABLE = False


# ── Логирование ──────────────────────────────────────────────────────────────

def _setup_logging(config: Config):
    from observability.logging_setup import setup_logging as _obs_setup
    _obs_setup(
        log_level=config.log_level,
        log_file=config.log_file,
        log_json=getattr(config, "log_json", False),
        node_id=getattr(config, "node_id", "node-1"),
        deployment_mode=getattr(config, "deployment_mode", "dev"),
    )


_ACTIVE_NODE: "NodeOrchestrator | None" = None


def _handle_shutdown_signal(signum, frame):
    global _ACTIVE_NODE
    if _ACTIVE_NODE:
        _ACTIVE_NODE.stop()
    sys.exit(0)


# ═══════════════════════════════════════════════════════════════════════════════
#  NodeOrchestrator — центральный оркестратор
# ═══════════════════════════════════════════════════════════════════════════════

class NodeOrchestrator:
    """
    Собирает все компоненты в единый работающий узел.

    Порядок инициализации:
      1. EventBus      — шина событий (нет зависимостей)
      2. Database      — БД (нет зависимостей, кроме config.db_path)
      3. Mempool       — пул транзакций (нет зависимостей)
      4. Blockchain    — ядро (зависит от Database, EventBus)
      5. Consensus     — консенсус (зависит от Blockchain, Database, EventBus)
      6. EVM           — исполнитель (зависит от Database)
      7. P2PNode       — сеть (зависит от Blockchain, Mempool, EventBus)
      8. Bridge        — кросс-чейн мост (зависит от Database, EventBus)
      9. RPC Server    — JSON-RPC :8545 (зависит от Blockchain, Mempool)
     10. HTTP Server   — REST API :8080 (зависит от всего выше)
    """

    def __init__(self, config: Config):
        global _ACTIVE_NODE
        self.config = config
        self._running = False
        self._tasks = []
        self._rpc_server = None
        self._http_server = None
        _ACTIVE_NODE = self

        logging.getLogger("Node").info("Initializing components...")

        # 1. Шина событий
        self.bus = EventBus()

        # 2. База данных
        self.db = Database(config.db_path, synchronous=config.sqlite_synchronous)
        self.db.initialize()
        print(f"[Node] Database: {config.db_path}")

        # 3. Мемпул
        self.mempool = Mempool(max_size=10_000, min_fee=config.base_fee() * 0.5)

        # 4. Ядро блокчейна
        self.blockchain = Blockchain(config, self.db, self.bus)
        self.mempool.set_blockchain(self.blockchain)
        print(f"[Node] Blockchain height: {self.blockchain.get_height()}")
        if (
            config.verify_peer_state_root
            and not config.state_root_legacy_cutoff_height
            and self.blockchain.get_height() > 0
        ):
            config.state_root_legacy_cutoff_height = self.blockchain.get_height()
            print(
                f"[Node] state_root legacy cutoff: #{config.state_root_legacy_cutoff_height} "
                "(blocks above require strict match)"
            )
        # Сохраняем метаданные токеномики (genesis-аллокация — после загрузки wallet)
        try:
            from runtime.tokenomics import get_tokenomics_summary, resolve_founder_address
            founder = resolve_founder_address(
                getattr(config, "founder_address", ""),
                config.miner_address,
            )
            if not self.db.get_meta("tokenomics"):
                self.db.set_meta("tokenomics", get_tokenomics_summary(founder or None))
                print(f"[Node] Tokenomics saved: 221M ABS, founder D.U.P. 17.4%")
        except Exception as _tok_err:
            print(f"[Node] Tokenomics migration note: {_tok_err}")

        # 5. Консенсус
        self.consensus = ConsensusAdapter(config, self.db, self.bus)
        self.blockchain.consensus_adapter = self.consensus

        # Если miner_address не задан — загружаем wallet.json или генерируем ECDSA
        self.wallet = None
        _data_dir = os.path.dirname(config.db_path) if os.path.dirname(config.db_path) else "data"
        _wallet_path = os.path.join(_data_dir, "wallet.json")
        if os.path.exists(_wallet_path):
            try:
                import json as _json
                with open(_wallet_path, encoding="utf-8") as _wf:
                    _wdata = _json.load(_wf)
                _waddr = _wdata.get("address", "")
                if _waddr:
                    if not getattr(config, "founder_address", ""):
                        config.founder_address = _waddr
                    if not config.miner_address:
                        config.miner_address = _waddr
                    print(f"[Node] Founder wallet (D.U.P.): {_waddr}")
                if _WALLET_AVAILABLE:
                    if _wdata.get("private_key"):
                        self.wallet = Wallet.import_wallet(_wallet_path)
                        config.signing_address = self.wallet.address
                        if not config.miner_address:
                            config.miner_address = self.wallet.address
                        print(f"[Node] Wallet loaded from wallet.json (signing enabled): {self.wallet.address}")
                    else:
                        _pk_env = os.environ.get("WALLET_PRIVATE_KEY", "").strip()
                        if _pk_env:
                            try:
                                _w = Wallet.from_private_key(_pk_env)
                                self.wallet = _w
                                config.signing_address = _w.address
                                config.miner_address = _w.address
                                print(
                                    f"[Node] Operational wallet from WALLET_PRIVATE_KEY: "
                                    f"{_w.address} (mining + signing)"
                                )
                                if _waddr and _w.address.lower() != _waddr.lower():
                                    print(
                                        f"[Node] Founder in wallet.json is watch-only "
                                        f"(tokenomics): {_waddr}"
                                    )
                            except Exception as _pke:
                                print(f"[Node] WALLET_PRIVATE_KEY invalid ({_pke})")
            except Exception as _we:
                print(f"[Node] Wallet load warning ({_we})")
        elif _WALLET_AVAILABLE:
            _pk_env = os.environ.get("WALLET_PRIVATE_KEY", "").strip()
            if _pk_env:
                try:
                    _w = Wallet.from_private_key(_pk_env)
                    self.wallet = _w
                    config.signing_address = _w.address
                    config.miner_address = _w.address
                    print(f"[Node] Operational wallet from WALLET_PRIVATE_KEY: {_w.address}")
                except Exception as _pke:
                    print(f"[Node] WALLET_PRIVATE_KEY invalid ({_pke})")
        if config.require_wallet_file and self.wallet is None:
            raise RuntimeError(
                f"Production mode requires wallet with private_key at: {_wallet_path}"
            )
        if _WALLET_AVAILABLE and self.wallet is None and not config.require_wallet_file:
            if config.miner_address and os.path.exists(_wallet_path):
                print(
                    f"[Node] Wallet address loaded (no private_key in file — "
                    f"signing disabled): {config.miner_address}"
                )
            else:
                try:
                    self.wallet = Wallet.create_new()
                    if not config.miner_address:
                        config.miner_address = self.wallet.address
                    if not getattr(config, "founder_address", ""):
                        config.founder_address = self.wallet.address
                    print(f"[Node] ECDSA wallet generated. Address: {config.miner_address}")
                    try:
                        os.makedirs(_data_dir, exist_ok=True)
                        self.wallet.export(_wallet_path)
                        print(f"[Node] Wallet saved: {_wallet_path}")
                    except Exception as _save_err:
                        print(f"[Node] Wallet save warning: {_save_err}")
                except Exception as _we:
                    print(f"[Node] Wallet unavailable ({_we})")
        if not config.miner_address:
            import hashlib as _hl
            config.miner_address = "0x" + _hl.sha256(
                f"miner-{config.p2p_port}".encode()
            ).hexdigest()[:40]
            print(f"[Node] Auto-generated miner address: {config.miner_address}")

        self._apply_genesis_allocation()

        # Если нет валидаторов в БД — регистрируем текущий узел как валидатор
        if not self.db.get_validators():
            self.consensus.add_validator(config.miner_address, config.min_stake)
            print(f"[Node] Registered self as validator: {config.miner_address}")

        # Operational wallet (WALLET_PRIVATE_KEY) must mine + sign on solo devnet
        _op = getattr(config, "signing_address", "") or ""
        if _op and self.wallet:
            _vals = self.db.get_validators(active_only=True) or []
            if not any(v["address"].lower() == _op.lower() for v in _vals):
                self.consensus.add_validator(_op, config.min_stake)
            config.miner_address = _op
            print(f"[Node] Mining proposer locked to operational wallet: {_op}")

        # 4b. Pool locks (ecosystem/treasury/staking enforcement)
        try:
            from runtime.pool_locks import PoolLockManager
            founder = getattr(config, "founder_address", "") or config.miner_address
            self.pool_locks = PoolLockManager(
                self.db, founder, epoch_size=getattr(config, "epoch_size", 32)
            )
            self.blockchain.pool_locks = self.pool_locks
            h = self.blockchain.get_height()
            if h > 0:
                from consensus.epoch import EpochManager as _EpCatch
                _ep = _EpCatch(epoch_size=getattr(config, "epoch_size", 32))
                catch = self.pool_locks.catch_up_epochs(_ep.get_epoch(h))
                if catch.get("staking_released_total", 0) > 0:
                    print(f"[Node] Staking catch-up: +{catch['staking_released_total']:,.0f} ABS released")
            print("[Node] PoolLockManager: ecosystem/treasury/staking locks active")
        except Exception as _pl_err:
            self.pool_locks = None
            print(f"[Node] PoolLockManager: unavailable ({_pl_err})")

        # 4c. Light client (SPV headers)
        try:
            from light.light_client import LightClient
            self.light_client = LightClient()
            synced = self.light_client.sync_from_blockchain(self.blockchain)
            print(f"[Node] LightClient: enabled ({synced} headers synced)")
        except Exception as _lc_err:
            self.light_client = None
            print(f"[Node] LightClient: unavailable ({_lc_err})")

        # 6. EVM
        self.evm = EVMAdapter(self.db, config) if config.evm_enabled else None
        if self.evm:
            print("[Node] EVM: enabled")
        self.blockchain.evm = self.evm

        # 7. P2P
        self.p2p = P2PNode(config, self.blockchain, self.mempool, self.bus)

        # 8. Мост
        self.bridge = RustBridge(config, self.db, self.bus) if config.bridge_enabled else None

        # 9. NFT маркетплейс
        self.nft = NFTMarketplace(db=self.db, bus=self.bus)
        print(f"[Node] NFT Marketplace: {len(self.nft.tokens)} genesis tokens loaded")

        # 10. ZK Proof System
        self.zk = ZKProofSystem()
        print("[Node] ZK Proof System: ready")

        # 11. Dynamic Sharding (4 shards: Genesis, Finance, Governance, Identity)
        if _SHARDING_AVAILABLE:
            self.sharding = ShardingManager(num_shards=4, db=self.db)
            self.sharding.register_node(config.miner_address or "node-0")
            print(f"[Node] Sharding: {self.sharding.num_shards} shards active")
        else:
            self.sharding = None

        # 12. Real World Oracles (crypto prices, weather) + on-chain feed registry
        self.oracle_registry = None
        self.oracles = None
        if _ORACLE_REGISTRY_AVAILABLE:
            try:
                self.oracle_registry = OracleFeedRegistry(self.db)
                print("[Node] Oracle registry: SQLite feeds enabled")
            except Exception as e:
                self.oracle_registry = None
                print(f"[Node] Oracle registry: unavailable ({e})")
        if _ORACLE_MANAGER_AVAILABLE:
            try:
                self.oracles = OracleManager()
                print("[Node] Oracles: price feeds active (BTC/ETH/ABS)")
            except Exception as e:
                self.oracles = None
                print(f"[Node] Oracles: live feeds unavailable ({e})")

        # 13. Multisig support
        if _MULTISIG_AVAILABLE:
            self.multisig = MultiSigWallet  # pass class for API to instantiate
            print("[Node] Multisig: enabled")
        else:
            self.multisig = None

        # 14. Smart Accounts (Account Abstraction)
        if _SMART_ACCOUNTS_AVAILABLE:
            try:
                self.smart_accounts = SmartAccountManager()
                print("[Node] Smart Accounts: enabled (session keys, social recovery)")
            except Exception as e:
                self.smart_accounts = None
                print(f"[Node] Smart Accounts: unavailable ({e})")
        else:
            self.smart_accounts = None

        # 15. Post-Quantum Crypto
        if _POSTQUANTUM_AVAILABLE:
            print("[Node] Post-Quantum Crypto: SPHINCS+ enabled")

        # 16. WebSocket server (real-time browser events on :8546)
        self.ws_server = WebSocketServer(event_bus=self.bus,
                                         host="0.0.0.0",
                                         port=getattr(config, "ws_port", 8546))

        # 17. MiniVM Contract Manager + Assembler
        if _MINIVM_CONTRACTS_AVAILABLE:
            self.contract_manager = ContractManager(db=self.db)
            self.assembler = Assembler()
            print("[Node] MiniVM ContractManager: ready (deploy/call via /minivm/*)")
        else:
            self.contract_manager = None
            self.assembler = None

        # 18. RANDAO Validator Selection
        if _VALIDATOR_SELECTION_AVAILABLE:
            self.validator_selection = ValidatorSelection()
            last_blk = self.blockchain.get_last_block()
            if last_blk and last_blk.get("hash"):
                self.validator_selection.update_seed(last_blk["hash"])
            print("[Node] RANDAO ValidatorSelection: enabled")
        else:
            self.validator_selection = None

        # 19. Chain Storage (JSON file backup layer)
        if _CHAIN_STORAGE_AVAILABLE:
            self.chain_storage = ChainStorage(data_dir="data")
            print("[Node] ChainStorage: JSON backup layer ready")
        else:
            self.chain_storage = None

        # 20. Post-Quantum Manager (full suite: Kyber, Dilithium, Falcon)
        if _PQ_MANAGER_AVAILABLE:
            try:
                self.pq_manager = PostQuantumManager()
                print("[Node] PostQuantumManager: Kyber/Dilithium/Falcon enabled")
            except Exception as e:
                self.pq_manager = None
                print(f"[Node] PostQuantumManager: unavailable ({e})")
        else:
            self.pq_manager = None

        # 21. Transaction Validator
        if _TX_VALIDATOR_AVAILABLE:
            self.tx_validator = TransactionValidator()
            print("[Node] TransactionValidator: enabled (nonce/fee/balance checks)")
        else:
            self.tx_validator = None

        # 22. AI Validator Engine (performance-weighted proposer selection)
        if _AI_VALIDATOR_AVAILABLE:
            self.ai_validator = AIValidatorEngine()
            print("[Node] AIValidatorEngine: enabled (performance-weighted proposer selection)")
        else:
            self.ai_validator = None

        # 23. Reorg Predictor
        if _REORG_PREDICTOR_AVAILABLE:
            self.reorg_predictor = ReorgPredictor()
            print("[Node] ReorgPredictor: enabled (confirmation-depth risk)")
        else:
            self.reorg_predictor = None

        # 24. MEV Simulator
        if _MEV_SIMULATOR_AVAILABLE:
            self.mev_simulator = MEVSimulator(db=self.db)
            print("[Node] MEVSimulator: enabled (sandwich/arbitrage/frontrun analysis)")
        else:
            self.mev_simulator = None

        # 24b. StateEngine (deterministic state transitions)
        try:
            from execution.state_engine import StateEngine
            _se_candidate = getattr(self.blockchain, "state_engine", None)
            self.state_engine = _se_candidate if _se_candidate else StateEngine(db=self.db)
            print("[Node] StateEngine: enabled (deterministic state transitions)")
        except Exception as _se_err:
            self.state_engine = None
            print(f"[Node] StateEngine: unavailable ({_se_err})")

        # 25. BlockBuilder (deterministic block assembly)
        if _BLOCK_BUILDER_AVAILABLE:
            try:
                self.block_builder = BlockBuilder(self.mempool, self.state_engine) if self.state_engine else None
                if self.block_builder:
                    print("[Node] BlockBuilder: enabled (deterministic tx selection)")
            except Exception as e:
                self.block_builder = None
                print(f"[Node] BlockBuilder: unavailable ({e})")
        else:
            self.block_builder = None

        # 26. Immutable State Manager (satoshi-precision, replay-only state)
        if _IMMUTABLE_STATE_AVAILABLE:
            self.immutable_state = ImmutableStateManager()
            try:
                from runtime.tokenomics import genesis_balances
                founder = getattr(config, "founder_address", "") or config.miner_address
                alloc = genesis_balances(founder or None)
                self.immutable_state.seed_from_balances(alloc)
            except Exception:
                pass
            print("[Node] ImmutableStateManager: enabled (satoshi-precision balances)")
        else:
            self.immutable_state = None

        # 27. ValidatorKeys (block/attestation signing)
        if _VALIDATOR_KEYS_AVAILABLE:
            try:
                self.validator_keys = ValidatorKeys().initialize(self.wallet)
                print(f"[Node] ValidatorKeys: initialized ({self.validator_keys.get_address()[:16]}...)")
            except Exception as e:
                self.validator_keys = None
                print(f"[Node] ValidatorKeys: unavailable ({e})")
        else:
            self.validator_keys = None

        if self.p2p:
            self.p2p.set_consensus(self.consensus, self.validator_keys)

        # Register attestation validator (node2 gets its own key separate from miner)
        self._attestation_validator = None
        if self.validator_keys and self.wallet:
            _vaddr = self.validator_keys.get_address()
            _vals = self.db.get_validators(active_only=False) or []
            if not any(v["address"].lower() == _vaddr.lower() for v in _vals):
                self.consensus.add_validator(_vaddr, config.min_stake)
                print(f"[Node] Registered attestation validator: {_vaddr[:16]}…")
            self._attestation_validator = _vaddr

        # 28. Lightning Network (payment channels)
        if _LIGHTNING_AVAILABLE:
            try:
                self.lightning = LightningNetwork(
                    node_address=config.miner_address or "genesis",
                    db=self.db,
                )
                print("[Node] Lightning Network: payment channels ready")
            except Exception as e:
                self.lightning = None
                print(f"[Node] Lightning: unavailable ({e})")
        else:
            self.lightning = None

        # 29. Crypto Will (blockchain inheritance system)
        if _CRYPTO_WILL_AVAILABLE:
            try:
                self.crypto_will = CryptoWillManager(blockchain=self.blockchain, db=self.db)
                print("[Node] CryptoWill: inheritance system ready")
            except Exception as e:
                self.crypto_will = None
                print(f"[Node] CryptoWill: unavailable ({e})")
        else:
            self.crypto_will = None

        # 30. Plasma Chain (L2 sidechain)
        if _PLASMA_AVAILABLE:
            try:
                self.plasma = PlasmaChain(
                    chain_id="plasma_abs",
                    root_chain=self.blockchain,
                    db=self.db,
                )
                print("[Node] Plasma Chain: L2 sidechain ready")
            except Exception as e:
                self.plasma = None
                print(f"[Node] Plasma: unavailable ({e})")
        else:
            self.plasma = None

        # 31. WASM VM (WebAssembly-style contracts)
        if _WASM_VM_AVAILABLE:
            try:
                self.wasm_vm = WASMVirtualMachine(db=self.db)
                print("[Node] WASM VM: WebAssembly-style VM ready")
            except Exception as e:
                self.wasm_vm = None
                print(f"[Node] WASM VM: unavailable ({e})")
        else:
            self.wasm_vm = None

        # 32. AI Agent Manager (trading agents)
        if _AI_MANAGER_AVAILABLE:
            try:
                self.ai_manager = AIAgentManager(db=self.db)
                print("[Node] AI Agent Manager: trading agents ready")
            except Exception as e:
                self.ai_manager = None
                print(f"[Node] AI Manager: unavailable ({e})")
        else:
            self.ai_manager = None

        # 33. Cross-Chain Bridge Simulator (ETH/BSC/Solana/ABS)
        if _CROSS_BRIDGE_AVAILABLE:
            try:
                self.cross_bridge = CrossChainBridge()
                print("[Node] Cross-Chain Bridge: ETH/BSC/Solana/ABS ready")
            except Exception as e:
                self.cross_bridge = None
                print(f"[Node] Cross-Bridge: unavailable ({e})")
        else:
            self.cross_bridge = None

        # 34. Standalone Consensus Engine (PoS slots/epochs/attestations)
        if _CONSENSUS_ENGINE_AVAILABLE:
            try:
                self.consensus_engine_standalone = StandaloneConsensusEngine()
                if config.miner_address:
                    self.consensus_engine_standalone.add_validator(config.miner_address, config.min_stake)
                print("[Node] Standalone ConsensusEngine: PoS slots/attestations ready")
            except Exception as e:
                self.consensus_engine_standalone = None
                print(f"[Node] Standalone ConsensusEngine: unavailable ({e})")
        else:
            self.consensus_engine_standalone = None

        # 34b. Consensus Sub-Engines (LMD-GHOST, Casper, Slashing, Registry, Epoch, Beacon)
        try:
            from consensus.slashing import SlashingEngine as _SlashingEng
            self.slashing_engine = _SlashingEng()
            if config.miner_address:
                self.slashing_engine.register_validator(config.miner_address, config.min_stake)
            if self.db and hasattr(self.db, "save_slash_event"):
                self.slashing_engine.register_slash_callback(
                    lambda v, r, e, p: self.db.save_slash_event(v, r, e, p)
                )
            print("[Node] SlashingEngine: double-vote detection ready")
        except Exception as _e:
            self.slashing_engine = None
            print(f"[Node] SlashingEngine: unavailable ({_e})")

        try:
            from consensus.validator_registry import ValidatorRegistry as _ValReg
            self.validator_registry = _ValReg()
            if config.miner_address:
                self.validator_registry.register_validator(
                    config.miner_address, int(config.min_stake)
                )
            print("[Node] ValidatorRegistry: ready")
        except Exception as _e:
            self.validator_registry = None
            print(f"[Node] ValidatorRegistry: unavailable ({_e})")

        try:
            from consensus.epoch import EpochManager as _EpMgr
            self.epoch_manager = _EpMgr(epoch_size=getattr(config, "epoch_size", 32))
            print(f"[Node] EpochManager: {self.epoch_manager.epoch_size} blocks/epoch")
        except Exception as _e:
            self.epoch_manager = None
            print(f"[Node] EpochManager: unavailable ({_e})")

        try:
            from consensus.finality_beacon import BeaconFinality as _BF
            self.beacon_finality = _BF()
            print("[Node] BeaconFinality: beacon chain finality ready")
        except Exception as _e:
            self.beacon_finality = None
            print(f"[Node] BeaconFinality: unavailable ({_e})")

        try:
            from consensus.lmd import LMDTable as _LMD
            self.lmd_table = _LMD()
            if config.miner_address:
                self.lmd_table.add_validator(config.miner_address)
            print("[Node] LMDTable: LMD-GHOST fork choice ready")
        except Exception as _e:
            self.lmd_table = None
            print(f"[Node] LMDTable: unavailable ({_e})")

        try:
            from consensus.engine_casper import ConsensusEngineCasper as _CECasper
            self.consensus_casper = _CECasper()
            print("[Node] ConsensusEngineCasper: Casper FFG engine ready")
        except Exception as _e:
            self.consensus_casper = None
            print(f"[Node] ConsensusEngineCasper: unavailable ({_e})")

        try:
            from consensus.engine_beacon import ConsensusEngineBeacon as _CEBeacon
            self.consensus_beacon = _CEBeacon()
            print("[Node] ConsensusEngineBeacon: Beacon consensus ready")
        except Exception as _e:
            self.consensus_beacon = None
            print(f"[Node] ConsensusEngineBeacon: unavailable ({_e})")

        try:
            from consensus.engine_slashing import ConsensusEngineSlashing as _CESl
            self.consensus_engine_slashing = _CESl()
            print("[Node] ConsensusEngineSlashing: slashing-aware consensus ready")
        except Exception as _e:
            self.consensus_engine_slashing = None
            print(f"[Node] ConsensusEngineSlashing: unavailable ({_e})")

        try:
            from consensus.finality_casper import CasperFinality as _CasperFin
            self.casper_finality = _CasperFin()
            print("[Node] CasperFinality: Casper finality engine ready")
        except Exception as _e:
            self.casper_finality = None
            print(f"[Node] CasperFinality: unavailable ({_e})")

        try:
            from execution.block_validator import BlockValidator as _BV
            _se = getattr(self.blockchain, "state_engine", None) or self.state_engine
            self.block_validator = _BV(_se, self.mempool)
            print("[Node] BlockValidator: block pre-validation ready")
        except Exception as _e:
            self.block_validator = None
            print(f"[Node] BlockValidator: unavailable ({_e})")

        try:
            from crypto.sphincs_plus import SPHINCSPLUS as _SPHINCS
            self.sphincs = _SPHINCS()
            print("[Node] SPHINCS+: post-quantum hash-based signatures ready")
        except Exception as _e:
            self.sphincs = None
            print(f"[Node] SPHINCS+: unavailable ({_e})")

        try:
            from blockchain.canonical_serializer import CanonicalSerializer as _CS
            self.canonical_serializer = _CS()
            print("[Node] CanonicalSerializer: deterministic block hashing ready")
        except Exception as _e:
            self.canonical_serializer = None
            print(f"[Node] CanonicalSerializer: unavailable ({_e})")

        # 34c. Crypto Utilities (Hasher, KeyPair, Signer, TransactionSigner)
        try:
            from crypto.hashing import Hasher as _Hasher
            self.hasher = _Hasher()
            print("[Node] Hasher: crypto hashing utility ready")
        except Exception as _e:
            self.hasher = None
            print(f"[Node] Hasher: unavailable ({_e})")

        try:
            from crypto.keys import KeyGenerator as _KeyGen
            self.key_generator = _KeyGen()
            print("[Node] KeyGenerator: key pair generation ready")
        except Exception as _e:
            self.key_generator = None
            print(f"[Node] KeyGenerator: unavailable ({_e})")

        try:
            from crypto.signing import Signer as _Signer
            self.signer = _Signer()
            print("[Node] Signer: transaction signing utility ready")
        except Exception as _e:
            self.signer = None
            print(f"[Node] Signer: unavailable ({_e})")

        try:
            from crypto.tx_signer import TransactionSigner as _TxSigner
            self.tx_signer = _TxSigner()
            print("[Node] TransactionSigner: advanced TX signing ready")
        except Exception as _e:
            self.tx_signer = None
            print(f"[Node] TransactionSigner: unavailable ({_e})")

        # 35. Finality Engine (Casper FFG)
        if _FINALITY_ENGINE_AVAILABLE:
            try:
                self.finality_engine = FinalityEngine()
                print("[Node] FinalityEngine: Casper FFG ready")
            except Exception as e:
                self.finality_engine = None
                print(f"[Node] FinalityEngine: unavailable ({e})")
        else:
            self.finality_engine = None

        # 36. Sync Engine (fast-sync for P2P)
        if _SYNC_ENGINE_AVAILABLE:
            try:
                self.sync_engine = SyncEngine(node=self)
                print("[Node] SyncEngine: fast-sync ready")
            except Exception as e:
                self.sync_engine = None
                print(f"[Node] SyncEngine: unavailable ({e})")
        else:
            self.sync_engine = None

        print("[Node] All components initialized.")

    # ── SyncEngine node interface ─────────────────────────────────────────────

    def get_block(self, block_hash: str):
        """Resolve block locally or via P2P peers (for SyncEngine.download_chain)."""
        blk = self.blockchain.get_block_by_hash(block_hash)
        if blk:
            return blk
        if self.p2p and hasattr(self.p2p, "fetch_block_from_peers_sync"):
            return self.p2p.fetch_block_from_peers_sync(block_hash)
        return None

    def import_block(self, block_data: dict) -> bool:
        return self.blockchain.import_block(block_data)

    def get_height(self) -> int:
        return self.blockchain.get_height()

    def request_peer_state_roots_sync(self, timeout: float = 15):
        if self.p2p and hasattr(self.p2p, "request_peer_state_roots_sync"):
            return self.p2p.request_peer_state_roots_sync(timeout)
        return []

    # ── Запуск ───────────────────────────────────────────────────────────────

    async def start(self):
        self._running = True

        # Запускаем API-серверы в отдельных потоках (не блокируют event loop)
        _, self._rpc_server = start_rpc_server_thread(
            self.blockchain, self.mempool, self.config, self.evm,
            p2p=self.p2p, wallet=self.wallet, sync_engine=self.sync_engine,
        )
        # Aliases for audit compatibility
        self.websocket_server = self.ws_server
        self.bot = getattr(self, '_bot_instance', None)

        _, self._http_server = start_http_server_thread(
            self.blockchain, self.mempool, self.db, self.config,
            self.p2p, self.evm, self.nft, self.zk,
            sharding=self.sharding, oracles=self.oracles,
            oracle_registry=self.oracle_registry,
            contract_manager=self.contract_manager,
            assembler=self.assembler,
            pq_manager=self.pq_manager,
            smart_accounts=self.smart_accounts,
            multisig=self.multisig,
            ai_validator=self.ai_validator,
            reorg_predictor=self.reorg_predictor,
            mev_simulator=self.mev_simulator,
            immutable_state=self.immutable_state,
            lightning=self.lightning,
            crypto_will=self.crypto_will,
            plasma=self.plasma,
            wasm_vm=self.wasm_vm,
            ai_manager=self.ai_manager,
            cross_bridge=self.cross_bridge,
            consensus_adapter=self.consensus,
            consensus_engine_standalone=self.consensus_engine_standalone,
            finality_engine=self.finality_engine,
            sync_engine=self.sync_engine,
            state_engine=self.state_engine,
            slashing_engine=self.slashing_engine,
            validator_registry=self.validator_registry,
            epoch_manager=self.epoch_manager,
            beacon_finality=self.beacon_finality,
            lmd_table=self.lmd_table,
            consensus_casper=self.consensus_casper,
            block_validator=self.block_validator,
            sphincs=self.sphincs,
            canonical_serializer=self.canonical_serializer,
            consensus_beacon=self.consensus_beacon,
            consensus_engine_slashing=self.consensus_engine_slashing,
            casper_finality=self.casper_finality,
            pool_locks=self.pool_locks,
            light_client=self.light_client,
            bridge=self.bridge,
            wallet=self.wallet,
            bus=self.bus,
        )

        self._print_banner()

        # Asyncio задачи
        tasks = []

        # P2P сервер
        tasks.append(asyncio.create_task(self.p2p.start(), name="P2PServer"))
        if self._attestation_validator and self.p2p:
            tasks.append(asyncio.create_task(
                self._announce_validator_loop(), name="ValidatorAnnounce"
            ))

        # Цикл майнинга (если включён)
        if self.config.mining_enabled:
            tasks.append(asyncio.create_task(self._mining_loop(), name="MiningLoop"))

        # Мост (если включён)
        if self.bridge:
            tasks.append(asyncio.create_task(self.bridge.start(), name="BridgeLoop"))

        # WebSocket сервер (порт 8546)
        tasks.append(asyncio.create_task(self.ws_server.start(), name="WebSocketServer"))

        # Blockchain Monitor — per-node port (8092 node1, 8093 node2)
        self.monitor = None
        if self.config.monitor_enabled:
            try:
                from monitor import MonitorServer
                _mon_port = self.config.resolved_monitor_port()
                _api_url = f"http://127.0.0.1:{self.config.http_port}"
                self.monitor = MonitorServer(
                    api_url=_api_url,
                    port=_mon_port,
                    node_id=self.config.node_id,
                )
                self.monitor.start()
                print(f"[Monitor] Health monitor started: http://localhost:{_mon_port}")
            except Exception:
                self.monitor = None

        # RPC CORS Proxy — per-node port (8082 node1, 8083 node2)
        if self.config.enable_cors_rpc_proxy:
            try:
                import threading as _threading
                from http.server import HTTPServer as _HTTPServer, BaseHTTPRequestHandler as _BH
                import json as _json_mod
                _rpc_port = self.config.rpc_port
                _proxy_port = self.config.resolved_rpc_proxy_port()
                class _CORSProxy(_BH):
                    def do_OPTIONS(self):
                        self.send_response(200)
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
                        self.send_header("Access-Control-Allow-Headers", "Content-Type")
                        self.end_headers()
                    def do_POST(self):
                        import requests as _req
                        cl = int(self.headers.get("Content-Length", 0))
                        body = self.rfile.read(cl)
                        try:
                            resp = _req.post(
                                f"http://localhost:{_rpc_port}", data=body,
                                headers={"Content-Type": "application/json"}, timeout=5,
                            )
                            data = resp.content
                        except Exception as e:
                            data = _json_mod.dumps({"error": str(e)}).encode()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Access-Control-Allow-Origin", "*")
                        self.send_header("Content-Length", len(data))
                        self.end_headers()
                        try:
                            self.wfile.write(data)
                        except Exception:
                            pass
                    def log_message(self, *a):
                        pass
                _proxy = _HTTPServer(("0.0.0.0", _proxy_port), _CORSProxy)
                _threading.Thread(target=_proxy.serve_forever, daemon=True, name="RPCProxy").start()
                print(f"[RPC Proxy] CORS proxy started: http://localhost:{_proxy_port}/rpc -> :{_rpc_port}")
            except Exception:
                pass  # proxy is optional
        else:
            print("[RPC Proxy] Disabled (ENABLE_CORS_RPC_PROXY=false or prod mode)")

        # Telegram Bot — автозапуск если TELEGRAM_BOT_TOKEN установлен
        import os as _os
        _tg_token = _os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        try:
            from runtime.secret_utils import is_placeholder_secret
            _tg_placeholder = is_placeholder_secret(_tg_token)
        except ImportError:
            _tg_placeholder = _tg_token.lower().startswith("your_")
        if _tg_token and not _tg_placeholder:
            try:
                import threading as _threading
                # BOT_TOKEN is read at module import time from env — already set above
                from telegram_super_bot import AbsoluteBot as _TGBot
                _bot = _TGBot()
                _tg_t = _threading.Thread(target=_bot.run, daemon=True, name="TelegramBot")
                _tg_t.start()
                print(f"[Telegram] Bot started (token: {_tg_token[:8]}...)")
            except Exception as _te:
                print(f"[Telegram] Bot unavailable: {_te}")
        elif _tg_token and _tg_placeholder:
            print("[Telegram] Skipped — TELEGRAM_BOT_TOKEN is placeholder in .env")
        else:
            print("[Telegram] Bot ready — set TELEGRAM_BOT_TOKEN in .env to activate")

        # Обработка tx из мемпула (периодическое включение в блок)
        tasks.append(asyncio.create_task(self._mempool_monitor(), name="MempoolMonitor"))

        self._tasks = tasks

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass

    async def _announce_validator_loop(self):
        """Gossip attestation validator to peers once P2P is up."""
        await asyncio.sleep(8)
        while self._running:
            if self.p2p and self._attestation_validator:
                self.p2p.announce_validator(
                    self._attestation_validator, self.config.min_stake
                )
            await asyncio.sleep(60)

    def _apply_genesis_allocation(self) -> None:
        """Credit genesis pools after wallet/config founder address is known."""
        try:
            from runtime.tokenomics import (
                FOUNDER_AMOUNT_ABS,
                genesis_balances,
                get_tokenomics_summary,
                resolve_founder_address,
            )
            founder = resolve_founder_address(
                getattr(self.config, "founder_address", ""),
                self.config.miner_address,
            )
            if not self.db.get_meta("genesis_alloc_applied"):
                alloc = genesis_balances(founder or None)
                for addr, amount in alloc.items():
                    cur = self.db.get_balance(addr)
                    if cur < amount * 0.99:
                        self.db.set_balance(addr, float(amount))
                self.db.set_meta("genesis_alloc_applied", True)
                self.db.set_meta("tokenomics", get_tokenomics_summary(founder or None))
                print(
                    f"[Node] Genesis allocation applied "
                    f"(founder {FOUNDER_AMOUNT_ABS:,.0f} ABS -> {founder})"
                )
                return
            expected = int(genesis_balances(founder or None).get(founder, FOUNDER_AMOUNT_ABS))
            cur = self.db.get_balance(founder)
            if cur < expected * 0.99:
                self.db.set_balance(founder, float(expected))
                print(f"[Node] Founder wallet synced: {expected:,.0f} ABS -> {founder}")
        except Exception as exc:
            print(f"[Node] Genesis allocation note: {exc}")

    # ── Остановка ────────────────────────────────────────────────────────────

    def stop(self):
        if not self._running:
            return
        self._running = False
        print("\n[Node] Shutting down...")
        shutdown_http_server(getattr(self, "_http_server", None), "HTTP")
        shutdown_http_server(getattr(self, "_rpc_server", None), "RPC")
        # Отменяем asyncio-задачи
        for task in self._tasks:
            if not task.done():
                task.cancel()
        # Останавливаем синхронные компоненты
        self.p2p.stop()
        if self.bridge:
            self.bridge.stop()
        try:
            self.db.close()
        except Exception:
            pass
        print("[Node] Goodbye.")

    # ── Цикл майнинга ────────────────────────────────────────────────────────

    async def _mining_loop(self):
        """
        Каждые block_time секунд форжит новый блок если:
          1. Наступил нужный момент (consensus.should_produce_block)
          2. Есть транзакции в мемпуле ИЛИ прошло > block_time с последнего блока
        """
        print(f"[Mining] Loop started. Block time: {self.config.block_time}s")

        while self._running:
            await asyncio.sleep(1)  # проверяем каждую секунду

            if not self.consensus.should_produce_block():
                continue

            # ── Proposer: solo operational wallet OR RANDAO when multiple validators ──
            proposer = None
            _signing = getattr(self.config, "signing_address", "")
            _active_vals = self.db.get_validators(active_only=True) if self.db else []
            if _signing and self.wallet and len(_active_vals) <= 1:
                proposer = _signing

            # 1) RANDAO-style selection if validators registered
            if not proposer and self.validator_selection and self.db:
                try:
                    validators_dict = {v["address"]: v.get("stake", 100)
                                       for v in (self.db.get_validators() or [])}
                    if validators_dict:
                        slot = getattr(self.consensus, "engine", None)
                        slot_n = getattr(slot, "current_slot", 0) if slot else 0
                        proposer = self.validator_selection.select_proposer(validators_dict, slot_n)
                except Exception:
                    pass

            # 2) AI-weighted selection fallback
            if not proposer and self.ai_validator and self.ai_validator.validators:
                try:
                    proposer = self.ai_validator.select_proposer()
                except Exception:
                    pass

            # 3) Consensus adapter fallback
            if not proposer:
                proposer = self.consensus.select_proposer()
            if not proposer:
                proposer = self.config.miner_address or "genesis"

            # ── PBS auction (MEV protection) ──────────────────────────────────
            pbs_tx_order = None
            try:
                pending_dicts = [{"hash": t.tx_hash, "from": t.from_addr, "to": t.to_addr,
                                  "value": t.amount, "gasPrice": int(t.fee * 1e9),
                                  "gas": int(getattr(t, "gas", 0) or 21000),
                                  "nonce": t.nonce,
                                  "data": getattr(t, "data", "") or "",
                                  "timestamp": t.timestamp}
                                 for t in self.mempool.get(limit=self.config.max_tx_per_block)]
                pbs_result = self.consensus.run_pbs_auction(pending_dicts)
                if pbs_result and pbs_result.get("transactions"):
                    pbs_tx_order = {tx["hash"] for tx in pbs_result["transactions"]}
            except Exception:
                pass

            # ── Get mempool transactions ──────────────────────────────────────
            pending = self.mempool.get(limit=self.config.max_tx_per_block)

            # Re-order by PBS if auction ran
            if pbs_tx_order:
                pending = sorted(pending, key=lambda t: 0 if t.tx_hash in pbs_tx_order else 1)

            # ── MEV scan (monitoring, PBS handles protection) ─────────────────
            if self.mev_simulator and len(pending) >= 2:
                try:
                    from features.mev_simulator import Transaction as MevTx
                    mev_txs = [MevTx(mp_tx.tx_hash, mp_tx.from_addr, mp_tx.to_addr,
                                     mp_tx.amount, int(mp_tx.fee * 1e9), int(mp_tx.timestamp))
                               for mp_tx in pending[:10]]
                    self.mev_simulator.detect_sandwich_opportunity(mev_txs)
                except Exception:
                    pass

            # ── Конвертируем MempoolTransaction → Transaction ─────────────────
            txs = []
            for mp_tx in pending:
                tx_gas = int(getattr(mp_tx, "gas", 0) or 0)
                if not tx_gas:
                    tx_gas = (
                        self.config.evm_gas_limit
                        if getattr(mp_tx, "data", "")
                        else self.config.base_gas_price
                    )
                txs.append(Transaction(
                    from_addr=mp_tx.from_addr,
                    to_addr=mp_tx.to_addr,
                    value=mp_tx.amount,
                    nonce=mp_tx.nonce,
                    gas=tx_gas,
                    data=getattr(mp_tx, "data", "") or "",
                    timestamp=int(mp_tx.timestamp),
                    tx_hash=mp_tx.tx_hash,
                    signature=mp_tx.signature,
                    public_key=mp_tx.public_key,
                ))

            # Обновляем miner_address в конфиге если задан
            if proposer != "genesis":
                self.config.miner_address = proposer

            # ── Создаём и добавляем блок ──────────────────────────────────────
            block = self.blockchain.create_block(txs, proposer)

            # Sign block with ValidatorKeys if available
            if self.validator_keys:
                try:
                    block_dict = {"hash": block.hash, "number": block.height,
                                  "proposer": proposer, "timestamp": block.timestamp}
                    block.signature = self.validator_keys.sign_block(block_dict)
                except Exception:
                    pass

            success = self.blockchain.add_block(block)

            if success:
                # Удаляем включённые транзакции из мемпула
                for tx in block.transactions:
                    self.mempool.remove(tx.hash)

                # LMD-GHOST: attest at current slot, then advance for next block
                try:
                    self.consensus.attest(proposer, block.hash)
                except Exception:
                    pass

                self.consensus.mark_block_produced(proposer=proposer)

                self._log_block(block)

                # RANDAO: обновляем seed случайности после каждого блока
                if self.validator_selection:
                    self.validator_selection.update_seed(block.hash)

                # AI Validator: обновляем performance proposer'а
                if self.ai_validator:
                    self.ai_validator.update_performance(proposer, success=True)

                # ImmutableState: синхронизируем satoshi-балансы по транзакциям блока
                if self.immutable_state:
                    try:
                        for tx in block.transactions:
                            self.immutable_state.apply_transaction({
                                "from": tx.from_addr,
                                "to":   tx.to_addr,
                                "amount": tx.value,
                                "fee":  getattr(tx, "gas", 0) * self.config.gas_price_wei,
                            })
                    except Exception:
                        pass

                # Light client: новый заголовок
                if self.light_client:
                    try:
                        from core.block_header import BlockHeader
                        self.light_client.add_header(BlockHeader.from_block_dict(block.to_dict()))
                    except Exception:
                        pass

                # Epoch boundary: разблокировка staking-пула
                if self.epoch_manager and self.pool_locks:
                    try:
                        if self.epoch_manager.is_epoch_boundary(block.height):
                            ep = self.epoch_manager.get_epoch(block.height)
                            rel = self.pool_locks.on_epoch_boundary(ep)
                            delta = rel.get("staking_released_delta", 0)
                            if delta > 0:
                                print(f"[Epoch] #{ep}: staking +{delta:,.0f} ABS released")
                    except Exception:
                        pass

                # ChainStorage: сохраняем блок в JSON backup
                if self.chain_storage:
                    try:
                        block_dict = {
                            "number": block.height,
                            "hash": block.hash,
                            "parent_hash": block.parent_hash,
                            "timestamp": block.timestamp,
                            "proposer": proposer,
                            "tx_count": len(block.transactions),
                        }
                        self.chain_storage.save_block(block.height, block_dict)
                    except Exception:
                        pass

    async def _mempool_monitor(self):
        """Периодически логирует статус мемпула."""
        while self._running:
            await asyncio.sleep(60)
            stats = self.mempool.get_stats()
            if stats["size"] > 0:
                print(f"[Mempool] size={stats['size']} "
                      f"avg_fee={stats['avg_fee']:.6f} ABS")

    # ── Вывод ─────────────────────────────────────────────────────────────────

    def _print_banner(self):
        tip = self.db.get_chain_tip()
        burned = self.db.get_total_burned()
        validators = len(self.db.get_validators())
        state_root = self.blockchain.get_state_root() if hasattr(self.blockchain, "get_state_root") else ""
        consensus_stats = self.consensus.get_stats()
        sep = "-" * 62
        shards_str = f"{self.sharding.num_shards} shards" if self.sharding else "off"
        oracles_str = "on" if self.oracles else "off"
        pq_str = "SPHINCS+" if _POSTQUANTUM_AVAILABLE else "off"
        multisig_str = "on" if _MULTISIG_AVAILABLE else "off"
        sa_str = "on" if self.smart_accounts else "off"
        ln_str = "on" if self.lightning else "off"
        plasma_str = "on" if self.plasma else "off"
        wasm_str = "on" if self.wasm_vm else "off"
        will_str = "on" if self.crypto_will else "off"
        lines = [
            "",
            "+" + sep + "+",
            f"|  ABSOLUTE BLOCKCHAIN NODE  v{self.config.node_version:<10}                      |",
            "+" + sep + "+",
            f"|  Chain      : {self.config.network_name:<16}  Chain ID : {self.config.chain_id:<10}      |",
            f"|  Supply     : max={self.config.max_supply:,} ABS  founder={getattr(self.config,'founder_initials','D.U.P.')} {getattr(self.config,'founder_percent',17.4)}% |",
            f"|  Founder    : {getattr(self.config,'founder_name','Uladzimir Dabranski'):<45} |",
            f"|  Height     : {str(tip):<45} |",
            f"|  Burned     : {f'{burned:.4f} {self.config.coin_symbol}':<45} |",
            f"|  Validators : {str(validators):<45} |",
            f"|  State Root : {(state_root[:32] + '...' if len(state_root) > 32 else state_root or 'n/a'):<45} |",
            "+" + sep + "+",
            f"|  Consensus  : LMD-GHOST={consensus_stats.get('lmd_ghost_enabled', False)}  PBS={consensus_stats.get('pbs_enabled', False)}  Slashing=yes  |",
            f"|  Features   : Sharding={shards_str}  Oracles={oracles_str}  PQ={pq_str}       |",
            f"|  Wallets    : Multisig={multisig_str}  SmartAccounts={sa_str}                  |",
            f"|  L2/Bridge  : Lightning={ln_str}  Plasma={plasma_str}  WASM={wasm_str}  Will={will_str}  |",
            "+" + sep + "+",
            f"|  JSON-RPC  ->  http://localhost:{self.config.rpc_port:<30}|",
            f"|  Explorer  ->  http://localhost:{self.config.http_port:<30}|",
            f"|  WebSocket ->  ws://localhost:{getattr(self.config,'ws_port',8546):<31}|",
            f"|  P2P       ->  0.0.0.0:{self.config.p2p_port:<38}|",
            "+" + sep + "+",
            "",
        ]
        print("\n".join(lines))

    def _log_block(self, block):
        burned_str = f"{block.total_burned:.4f}" if block.total_burned > 0 else "0"
        print(
            f"[BLOCK #{block.height:>6}] "
            f"hash={block.hash[:12]}... "
            f"txs={len(block.transactions):>3}  "
            f"burned={burned_str} ABS"
        )


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI аргументы
# ═══════════════════════════════════════════════════════════════════════════════

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Absolute Blockchain Node",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["full", "miner", "validator", "rpc-only"],
        default="full",
        help="Режим работы узла (default: full)",
    )
    parser.add_argument(
        "--config",
        default=None,
        metavar="FILE",
        help="Путь к JSON-файлу конфигурации",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        metavar="PORT",
        help="P2P-порт (переопределяет конфиг)",
    )
    parser.add_argument(
        "--rpc-port",
        type=int,
        default=None,
        metavar="PORT",
        help="JSON-RPC порт (default: 8545)",
    )
    parser.add_argument(
        "--http-port",
        type=int,
        default=None,
        metavar="PORT",
        help="REST API порт (default: 8080)",
    )
    parser.add_argument(
        "--peers",
        nargs="+",
        default=[],
        metavar="HOST:PORT",
        help="Список bootstrap-пиров",
    )
    parser.add_argument(
        "--miner",
        default=None,
        metavar="ADDRESS",
        help="Адрес кошелька для получения наград",
    )
    parser.add_argument(
        "--data-dir",
        default=None,
        metavar="DIR",
        help="Директория для данных (БД, логи)",
    )
    parser.add_argument(
        "--no-bridge",
        action="store_true",
        help="Отключить кросс-чейн мост",
    )
    parser.add_argument(
        "--no-evm",
        action="store_true",
        help="Отключить EVM",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Уровень логирования",
    )
    return parser.parse_args()


def build_config(args: argparse.Namespace) -> Config:
    """Строит Config: .env → JSON-файл → CLI (последний побеждает)."""
    config = Config()

    # 1) Глобальные значения из .env / окружения
    try:
        from runtime.env_loader import load_dotenv_file
        load_dotenv_file(os.path.join(BASE_DIR, ".env"))
    except Exception:
        pass
    config.apply_env()

    # 2) JSON-файл узла (перекрывает .env — важно для node2 на других портах)
    if args.config and os.path.exists(args.config):
        file_cfg = Config.from_json(args.config)
        for key, value in file_cfg.__dict__.items():
            if not key.startswith("_"):
                setattr(config, key, value)
        print(f"[Config] Loaded from: {args.config}")

    # 3) CLI — высший приоритет
    if args.port:
        config.p2p_port = args.port
    if args.rpc_port:
        config.rpc_port = args.rpc_port
    if args.http_port:
        config.http_port = args.http_port
    if args.peers:
        config.bootstrap_peers = args.peers
    if args.miner:
        config.miner_address = args.miner
    if args.data_dir:
        config.db_path = os.path.join(args.data_dir, "blockchain.db")
        config.log_file = os.path.join(args.data_dir, "node.log")
    if args.no_bridge:
        config.bridge_enabled = False
    if args.no_evm:
        config.evm_enabled = False
    if args.log_level:
        config.log_level = args.log_level

    errors = config.validate()
    if errors and config.is_production:
        for e in errors:
            print(f"[Config] ERROR: {e}")
        raise SystemExit(1)
    elif errors:
        for e in errors:
            print(f"[Config] WARN: {e}")

    # Режимы работы
    if args.mode == "rpc-only":
        config.mining_enabled = False
    elif args.mode == "validator":
        config.mining_enabled = False  # валидатор не майнит, только аттестует

    return config


# ═══════════════════════════════════════════════════════════════════════════════
#  Точка входа
# ═══════════════════════════════════════════════════════════════════════════════

async def _run_node(config: Config):
    """Корутина верхнего уровня: создаёт узел и запускает его."""
    node = NodeOrchestrator(config)

    # Graceful shutdown: Unix (asyncio) + Windows/Linux (signal)
    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, node.stop)
    else:
        signal.signal(signal.SIGINT, _handle_shutdown_signal)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _handle_shutdown_signal)

    try:
        await node.start()
    except asyncio.CancelledError:
        pass
    finally:
        node.stop()


def main():
    args = parse_args()
    config = build_config(args)
    _setup_logging(config)

    try:
        asyncio.run(_run_node(config))
    except KeyboardInterrupt:
        print("\n[Node] Interrupted.")


if __name__ == "__main__":
    main()
