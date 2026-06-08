# modules/p2p.py
import socket
import threading
import json
import time

class P2PModule:
    def __init__(self, core, port=5000):
        self.core = core
        self.port = port
        self.peers = set()
        self.running = False
        self.socket = None
        print(f"   ✅ P2P Module initialized (port {port})")
    
    def start(self):
        self.running = True
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('0.0.0.0', self.port))
        self.socket.listen(5)
        
        thread = threading.Thread(target=self._listen, daemon=True)
        thread.start()
        print(f"   ✅ P2P Server started on port {self.port}")
    
    def _listen(self):
        while self.running:
            try:
                client, addr = self.socket.accept()
                self.peers.add(addr[0])
                threading.Thread(target=self._handle_client, args=(client,), daemon=True).start()
            except:
                pass
    
    def _handle_client(self, client):
        try:
            data = client.recv(4096).decode()
            if data:
                message = json.loads(data)
                self._process_message(message)
            client.close()
        except:
            pass
    
    def _process_message(self, message):
        msg_type = message.get('type')
        if msg_type == 'GET_BLOCKS':
            pass
        elif msg_type == 'NEW_BLOCK':
            pass
    
    def broadcast(self, message):
        for peer in self.peers:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((peer, self.port))
                sock.send(json.dumps(message).encode())
                sock.close()
            except:
                pass
    
    def get_peers(self):
        return list(self.peers)
    
    def stop(self):
        self.running = False
        if self.socket:
            self.socket.close()
        print("   ✅ P2P stopped")
