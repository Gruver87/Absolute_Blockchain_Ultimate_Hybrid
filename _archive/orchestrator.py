import threading, time
from runtime.config import Config
from core.blockchain import Blockchain
from network.p2p import P2PNode
from api.http import create_http_server

class Orchestrator:
    def __init__(self):
        print("\n" + "="*60)
        print("     ABSOLUTE BLOCKCHAIN - UNIFIED CLIENT")
        print("="*60 + "\n")
        self.config = Config()
        self.blockchain = Blockchain(self.config.DB_PATH)
        self.p2p = P2PNode(self.blockchain)
        self.http_app = create_http_server(self.blockchain)
        self._running = False
    
    def _mining_loop(self):
        while self._running:
            time.sleep(self.config.BLOCK_TIME)
            block = self.blockchain.create_block("miner")
            if self.blockchain.add_block(block):
                print(f"[Miner] Block #{block['height']}: {block['block_hash'][:16]}...")
    
    def start(self):
        self._running = True
        threading.Thread(target=self.p2p.start, daemon=True).start()
        threading.Thread(target=self._mining_loop, daemon=True).start()
        print(f"[API] Starting on http://localhost:{self.config.HTTP_PORT}")
        print(f"[Chain] Height: {self.blockchain.get_height()}")
        print(f"[Miner] Block time: {self.config.BLOCK_TIME} seconds")
        print("\nPress Ctrl+C to stop\n")
        self.http_app.run(host='0.0.0.0', port=self.config.HTTP_PORT, debug=False, use_reloader=False)
    
    def stop(self):
        self._running = False
        self.p2p.stop()
