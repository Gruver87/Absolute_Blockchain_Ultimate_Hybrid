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
from network.p2p import P2PNode
from api.http import start_rpc_server_thread, start_http_server_thread
from bridge.abs_bridge import RustBridge
from features.nft import NFTMarketplace
from features.zk import ZKProofSystem

# --- Wallet (ECDSA miner key generation) ---
try:
    from crypto.wallet import Wallet
    _WALLET_AVAILABLE = True
except ImportError:
    _WALLET_AVAILABLE = False


# ── Логирование ──────────────────────────────────────────────────────────────

def _setup_logging(config: Config):
    level = getattr(logging, config.log_level.upper(), logging.INFO)
    os.makedirs(os.path.dirname(config.log_file) if os.path.dirname(config.log_file) else ".", exist_ok=True)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(config.log_file, encoding="utf-8"),
        ],
    )


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
        self.config = config
        self._running = False
        self._tasks = []

        print("[Node] Initializing components...")

        # 1. Шина событий
        self.bus = EventBus()

        # 2. База данных
        self.db = Database(config.db_path)
        self.db.initialize()
        print(f"[Node] Database: {config.db_path}")

        # 3. Мемпул
        self.mempool = Mempool(max_size=10_000, min_fee=config.base_fee() * 0.5)

        # 4. Ядро блокчейна
        self.blockchain = Blockchain(config, self.db, self.bus)
        print(f"[Node] Blockchain height: {self.blockchain.get_height()}")

        # 5. Консенсус
        self.consensus = ConsensusAdapter(config, self.db, self.bus)

        # Если miner_address не задан — генерируем через ECDSA wallet (или fallback hash)
        if not config.miner_address:
            if _WALLET_AVAILABLE:
                wallet = Wallet.create_new()
                config.miner_address = wallet.address
                print(f"[Node] ECDSA wallet generated. Miner address: {config.miner_address}")
            else:
                import hashlib as _hl
                config.miner_address = "0x" + _hl.sha256(
                    f"miner-{config.p2p_port}".encode()
                ).hexdigest()[:40]
                print(f"[Node] Auto-generated miner address: {config.miner_address}")

        # Если нет валидаторов в БД — регистрируем текущий узел как валидатор
        if not self.db.get_validators():
            self.consensus.add_validator(config.miner_address, config.min_stake)
            print(f"[Node] Registered self as validator: {config.miner_address}")

        # 6. EVM
        self.evm = EVMAdapter(self.db, config) if config.evm_enabled else None
        if self.evm:
            print("[Node] EVM: enabled")

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

        print("[Node] All components initialized.")

    # ── Запуск ───────────────────────────────────────────────────────────────

    async def start(self):
        self._running = True

        # Запускаем API-серверы в отдельных потоках (не блокируют event loop)
        start_rpc_server_thread(
            self.blockchain, self.mempool, self.config, self.evm
        )
        start_http_server_thread(
            self.blockchain, self.mempool, self.db, self.config,
            self.p2p, self.evm, self.nft, self.zk
        )

        self._print_banner()

        # Asyncio задачи
        tasks = []

        # P2P сервер
        tasks.append(asyncio.create_task(self.p2p.start(), name="P2PServer"))

        # Цикл майнинга (если включён)
        if self.config.mining_enabled:
            tasks.append(asyncio.create_task(self._mining_loop(), name="MiningLoop"))

        # Мост (если включён)
        if self.bridge:
            tasks.append(asyncio.create_task(self.bridge.start(), name="BridgeLoop"))

        # Обработка tx из мемпула (периодическое включение в блок)
        tasks.append(asyncio.create_task(self._mempool_monitor(), name="MempoolMonitor"))

        self._tasks = tasks

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass

    # ── Остановка ────────────────────────────────────────────────────────────

    def stop(self):
        if not self._running:
            return
        self._running = False
        print("\n[Node] Shutting down...")
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

            proposer = self.consensus.select_proposer()
            if not proposer:
                proposer = self.config.miner_address or "genesis"

            # Берём транзакции из мемпула
            pending = self.mempool.get(limit=self.config.max_tx_per_block)

            # Конвертируем MempoolTransaction → Transaction
            txs = []
            for mp_tx in pending:
                txs.append(Transaction(
                    from_addr=mp_tx.from_addr,
                    to_addr=mp_tx.to_addr,
                    value=mp_tx.amount,
                    nonce=mp_tx.nonce,
                    gas=self.config.base_gas_price,
                    timestamp=int(mp_tx.timestamp),
                    tx_hash=mp_tx.tx_hash,
                ))

            # Обновляем miner_address в конфиге если задан
            if proposer != "genesis":
                self.config.miner_address = proposer

            # Создаём и добавляем блок
            block = self.blockchain.create_block(txs, proposer)
            success = self.blockchain.add_block(block)

            if success:
                # Удаляем включённые транзакции из мемпула
                for tx in block.transactions:
                    self.mempool.remove(tx.hash)

                self.consensus.mark_block_produced(proposer=proposer)
                self._log_block(block)

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
        lines = [
            "",
            "+" + sep + "+",
            f"|  ABSOLUTE BLOCKCHAIN NODE  v{self.config.node_version:<10}                      |",
            "+" + sep + "+",
            f"|  Chain      : {self.config.network_name:<16}  Chain ID : {self.config.chain_id:<10}      |",
            f"|  Height     : {str(tip):<45} |",
            f"|  Burned     : {f'{burned:.4f} {self.config.coin_symbol}':<45} |",
            f"|  Validators : {str(validators):<45} |",
            f"|  State Root : {(state_root[:32] + '...' if len(state_root) > 32 else state_root or 'n/a'):<45} |",
            "+" + sep + "+",
            f"|  Consensus  : LMD-GHOST={consensus_stats.get('lmd_ghost_enabled', False)}  PBS={consensus_stats.get('pbs_enabled', False)}  Slashing=yes  |",
            "+" + sep + "+",
            f"|  JSON-RPC  ->  http://localhost:{self.config.rpc_port:<30}|",
            f"|  REST API  ->  http://localhost:{self.config.http_port:<30}|",
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
    """Строит Config из файла + аргументов командной строки."""
    if args.config and os.path.exists(args.config):
        config = Config.from_json(args.config)
        print(f"[Config] Loaded from: {args.config}")
    else:
        config = Config()

    # Переопределяем из аргументов CLI
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

    # Graceful shutdown по сигналу (только Unix)
    loop = asyncio.get_running_loop()
    if sys.platform != "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, node.stop)

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
