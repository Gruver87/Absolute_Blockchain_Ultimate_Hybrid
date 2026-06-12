# network/p2p/peer_manager.py - FIXED
class PeerManager:
    def __init__(self, node_id="default_node"):
        self.node_id = node_id
        self.peers = {}
        self.connected_peers = 0
    
    def get_peer_count(self):
        return len(self.peers)
    
    def add_peer(self, peer_id, address):
        self.peers[peer_id] = address
        self.connected_peers = len(self.peers)
    
    def remove_peer(self, peer_id):
        if peer_id in self.peers:
            del self.peers[peer_id]
        self.connected_peers = len(self.peers)
    
    def get_peers(self):
        return list(self.peers.keys())
