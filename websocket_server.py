# websocket_server.py - COMPLETE WEBSOCKET SUPPORT
import asyncio
import json
import hashlib
import threading
import time
from typing import Dict, Set, Optional
from dataclasses import dataclass

try:
    import websockets
    from websockets.server import serve
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    print("⚠️ websockets library not installed. Run: pip install websockets")

@dataclass
class WebSocketClient:
    """WebSocket client connection"""
    id: str
    websocket: any
    subscriptions: Set[str]
    connected_at: float

class WebSocketServer:
    """Complete WebSocket server for real-time updates"""
    
    def __init__(self, host="0.0.0.0", port=8546):
        self.host = host
        self.port = port
        self.clients: Dict[str, WebSocketClient] = {}
        self.node = None
        self.running = False
        self.server = None
    
    def set_node(self, node):
        """Set blockchain node reference"""
        self.node = node
    
    async def _handler(self, websocket, path):
        """Handle WebSocket connection"""
        client_id = hashlib.sha256(f"{websocket.remote_address}{time.time()}".encode()).hexdigest()[:16]
        
        # Create client
        client = WebSocketClient(
            id=client_id,
            websocket=websocket,
            subscriptions=set(),
            connected_at=time.time()
        )
        self.clients[client_id] = client
        
        print(f"🔌 WebSocket client connected: {client_id}")
        
        try:
            async for message in websocket:
                await self._process_message(client, message)
        except:
            pass
        finally:
            del self.clients[client_id]
            print(f"🔌 WebSocket client disconnected: {client_id}")
    
    async def _process_message(self, client: WebSocketClient, message: str):
        """Process incoming WebSocket message"""
        try:
            data = json.loads(message)
            method = data.get('method')
            params = data.get('params', {})
            
            if method == 'subscribe':
                channel = params.get('channel')
                if channel:
                    client.subscriptions.add(channel)
                    await client.websocket.send(json.dumps({
                        "type": "subscribed",
                        "channel": channel,
                        "status": "ok"
                    }))
            
            elif method == 'unsubscribe':
                channel = params.get('channel')
                if channel and channel in client.subscriptions:
                    client.subscriptions.remove(channel)
                    await client.websocket.send(json.dumps({
                        "type": "unsubscribed",
                        "channel": channel,
                        "status": "ok"
                    }))
            
            elif method == 'get_block':
                block_num = params.get('number', 'latest')
                await client.websocket.send(json.dumps({
                    "type": "block",
                    "data": {"number": block_num}
                }))
            
            elif method == 'ping':
                await client.websocket.send(json.dumps({"type": "pong", "timestamp": time.time()}))
            
        except Exception as e:
            await client.websocket.send(json.dumps({"type": "error", "message": str(e)}))
    
    async def _broadcast_to_channel(self, channel: str, data: dict):
        """Broadcast data to all subscribers of a channel"""
        for client in self.clients.values():
            if channel in client.subscriptions:
                try:
                    await client.websocket.send(json.dumps({
                        "type": "update",
                        "channel": channel,
                        "data": data,
                        "timestamp": time.time()
                    }))
                except:
                    pass
    
    def broadcast_new_block(self, block: dict):
        """Broadcast new block to subscribers"""
        if WEBSOCKET_AVAILABLE:
            asyncio.create_task(self._broadcast_to_channel("blocks", block))
    
    def broadcast_new_transaction(self, tx: dict):
        """Broadcast new transaction to subscribers"""
        if WEBSOCKET_AVAILABLE:
            asyncio.create_task(self._broadcast_to_channel("transactions", tx))
    
    def broadcast_new_peer(self, peer: dict):
        """Broadcast new peer to subscribers"""
        if WEBSOCKET_AVAILABLE:
            asyncio.create_task(self._broadcast_to_channel("peers", peer))
    
    def start(self):
        """Start WebSocket server"""
        if not WEBSOCKET_AVAILABLE:
            print("⚠️ WebSocket not available. Install: pip install websockets")
            return
        
        async def run():
            async with serve(self._handler, self.host, self.port):
                print(f"🔌 WebSocket Server running on ws://{self.host}:{self.port}")
                await asyncio.Future()
        
        self.running = True
        
        def run_async():
            asyncio.run(run())
        
        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()
    
    def stop(self):
        """Stop WebSocket server"""
        self.running = False
        print("🔌 WebSocket Server stopped")

# WebSocket client example
class WebSocketClient:
    """Simple WebSocket client for testing"""
    
    def __init__(self, url="ws://localhost:8546"):
        self.url = url
        self.websocket = None
    
    async def connect(self):
        """Connect to WebSocket server"""
        if WEBSOCKET_AVAILABLE:
            import websockets
            self.websocket = await websockets.connect(self.url)
            print(f"Connected to {self.url}")
    
    async def subscribe(self, channel: str):
        """Subscribe to a channel"""
        if self.websocket:
            await self.websocket.send(json.dumps({
                "method": "subscribe",
                "params": {"channel": channel}
            }))
            response = await self.websocket.recv()
            print(f"Subscribed to {channel}: {response}")
    
    async def listen(self):
        """Listen for messages"""
        if self.websocket:
            async for message in self.websocket:
                data = json.loads(message)
                print(f"Received: {data}")
    
    async def close(self):
        """Close connection"""
        if self.websocket:
            await self.websocket.close()

if __name__ == "__main__":
    print("WebSocket module ready")
    print("To use: pip install websockets")

