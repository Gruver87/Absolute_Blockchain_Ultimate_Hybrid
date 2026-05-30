# core/node.py
"""
Absolute Node — полный клиент с синхронизацией
"""

import time
import threading
from typing import Optional, Dict, Any

from state.state import State
from core.priority_mempool import PriorityMempool
from core.canonical_chain import CanonicalChain
from core.block_importer import BlockImporter
from core.reorg_manager import ReorgManager
from sync.sync_engine import SyncEngine
from rpc.rpc_server import RPCServer
from network.p2p_server import P2PServer
from network.sync_engine import SyncEngine as NetworkSyncEngine


class AbsoluteNode:
    """
    Главный класс ноды с P2P и синхронизацией
    """

    def __init__(self, node_id: str = "node1", rpc_port: int = 8545, p2p_port: int = 30303):
        self.node_id = node_id
        self.rpc_port = rpc_port
        self.p2p_port = p2p_port

        # Core components
        self.state = State()
        self.mempool = PriorityMempool()
        self.chain = CanonicalChain()
        self.importer = BlockImporter()
        self.reorg_manager = ReorgManager()

        # Sync engine (network sync)
        self.network_sync = NetworkSyncEngine(self)

        # RPC server
        self.rpc_server = None

        # P2P server
        self.p2p_server = P2PServer(self, p2p_port, node_id)

        # Runtime state
        self.running = False
        self._thread = None

        # Initialize genesis
        self._init_genesis()

    def _init_genesis(self):
        """Создаёт генезис блок"""
        genesis_block = {
            "block_number": 0,
            "block_hash": "0xgenesis",
            "parent_hash": "0x0",
            "timestamp": 0,
            "transactions": [],
            "gas_used": 0,
            "gas_limit": 30_000_000,
            "state_root": self.state.root()
        }
        self.chain.add_block(genesis_block)

    def start(self):
        """Запускает ноду"""
        print(f"🚀 Starting Absolute Node: {self.node_id}")
        print(f"   RPC endpoint: http://localhost:{self.rpc_port}")
        print(f"   P2P endpoint: port {self.p2p_port}")

        # Start RPC server
        self.rpc_server = RPCServer(self.chain, self.state, self.mempool, port=self.rpc_port)
        self._rpc_thread = threading.Thread(target=self._run_rpc, daemon=True)
        self._rpc_thread.start()

        # Start P2P server
        self.p2p_server.start()

        # Start main loop
        self.running = True
        self._run_main_loop()

    def _run_rpc(self):
        """Запускает RPC сервер"""
        if self.rpc_server:
            self.rpc_server.start()

    def _run_main_loop(self):
        """Главный цикл ноды с синхронизацией"""
        print(f"🔄 Node {self.node_id} main loop started")

        last_proposal_time = time.time()
        PROPOSAL_INTERVAL = 10

        try:
            while self.running:
                # 1. Sync with network
                self.network_sync.sync_step()

                # 2. Propose block periodically
                if time.time() - last_proposal_time > PROPOSAL_INTERVAL:
                    self._propose_block()
                    last_proposal_time = time.time()

                time.sleep(1)

        except KeyboardInterrupt:
            self.stop()

    def _propose_block(self):
        """Предлагает новый блок"""
        # Simplified for now
        pass

    def add_peer(self, host: str, port: int):
        """Добавляет пира"""
        self.p2p_server.add_peer(host, port)

    def get_status(self) -> Dict[str, Any]:
        """Возвращает статус ноды"""
        sync_status = self.network_sync.get_status()
        return {
            "node_id": self.node_id,
            "running": self.running,
            "chain_height": self.chain.get_head_height(),
            "mempool_size": self.mempool.size(),
            "peers": len(self.p2p_server.peers),
            "syncing": sync_status["syncing"],
            "best_peer_height": sync_status["best_peer_height"],
            "rpc_port": self.rpc_port,
            "p2p_port": self.p2p_port
        }

    def stop(self):
        """Останавливает ноду"""
        print(f"🛑 Stopping node: {self.node_id}")
        self.running = False
        if self.rpc_server:
            self.rpc_server.stop()
        if self.p2p_server:
            self.p2p_server.stop()
