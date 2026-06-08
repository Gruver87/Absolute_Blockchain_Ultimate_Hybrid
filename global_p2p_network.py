#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABSOLUTE BLOCKCHAIN - ГЛОБАЛЬНАЯ P2P СЕТЬ
Позволяет подключаться к узлам по всему миру
"""

import socket
import threading
import requests
import json
import time
import hashlib
import os
import sys

class GlobalP2PNetwork:
    def __init__(self, port=5000, blockchain=None):
        self.port = port
        self.blockchain = blockchain
        self.peers = set()
        self.running = False
        self.socket = None
        self.node_id = hashlib.sha256(f"{os.urandom(16)}".encode()).hexdigest()[:16]
        
        # Публичные трекеры (бесплатные)
        self.trackers = [
            "https://absolute-p2p-tracker.herokuapp.com",
            "https://p2p-tracker-absolute.cyclic.app",
            "https://absolute-tracker.onrender.com"
        ]
        
        # Bootstrap узлы (можно добавить свои)
        self.bootstrap_peers = [
            ("seed1.absolute-blockchain.com", 5000),
            ("seed2.absolute-blockchain.com", 5000),
        ]
        
        print(f"🌐 Global P2P Node: {self.node_id}")
    
    def get_public_ip(self):
        """Определение публичного IP"""
        services = [
            'https://api.ipify.org?format=json',
            'https://api.my-ip.io/ip.json',
            'https://ipapi.co/json/'
        ]
        for service in services:
            try:
                response = requests.get(service, timeout=5)
                data = response.json()
                if 'ip' in data:
                    return data['ip']
                elif isinstance(data, str):
                    return data
            except:
                continue
        return "127.0.0.1"
    
    def register_on_trackers(self):
        """Регистрация на всех трекерах"""
        public_ip = self.get_public_ip()
        data = {
            "ip": public_ip,
            "port": self.port,
            "node_id": self.node_id,
            "timestamp": int(time.time()),
            "height": len(self.blockchain.chain) if self.blockchain else 0
        }
        
        for tracker in self.trackers:
            try:
                response = requests.post(f"{tracker}/register", json=data, timeout=5)
                if response.status_code == 200:
                    print(f"   ✅ Зарегистрирован на {tracker.split('/')[2]}")
            except:
                pass
    
    def get_peers_from_trackers(self):
        """Получение пиров со всех трекеров"""
        all_peers = set()
        my_ip = self.get_public_ip()
        my_addr = f"{my_ip}:{self.port}"
        
        for tracker in self.trackers:
            try:
                response = requests.get(f"{tracker}/peers", timeout=5)
                if response.status_code == 200:
                    peers = response.json()
                    for peer in peers:
                        peer_addr = f"{peer['ip']}:{peer['port']}"
                        if peer_addr != my_addr:
                            all_peers.add(peer_addr)
            except:
                pass
        
        self.peers.update(all_peers)
        print(f"   ✅ Получено {len(self.peers)} пиров")
        return list(self.peers)
    
    def connect_to_bootstrap(self):
        """Подключение к bootstrap узлам"""
        for ip, port in self.bootstrap_peers:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((ip, port))
                self.peers.add(f"{ip}:{port}")
                sock.close()
                print(f"   ✅ Подключен к bootstrap: {ip}:{port}")
            except:
                pass
    
    def start_server(self):
        """Запуск P2P сервера"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(('0.0.0.0', self.port))
            self.socket.listen(50)
            self.running = True
            print(f"   ✅ P2P сервер запущен на порту {self.port}")
            
            while self.running:
                try:
                    client, addr = self.socket.accept()
                    threading.Thread(target=self._handle_client, args=(client, addr), daemon=True).start()
                except:
                    pass
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
    
    def _handle_client(self, client, addr):
        """Обработка клиентов"""
        try:
            data = client.recv(4096).decode()
            if data:
                message = json.loads(data)
                msg_type = message.get('type')
                
                if msg_type == 'handshake':
                    response = json.dumps({
                        'type': 'handshake_ack',
                        'node_id': self.node_id,
                        'height': len(self.blockchain.chain) if self.blockchain else 0
                    })
                    client.send(response.encode())
                    self.peers.add(f"{addr[0]}:{addr[1]}")
                    
                elif msg_type == 'get_chain':
                    if self.blockchain:
                        blocks = [b.to_dict() for b in self.blockchain.chain[-20:]]
                        response = json.dumps({'type': 'chain', 'blocks': blocks})
                        client.send(response.encode())
                        
                elif msg_type == 'get_peers':
                    response = json.dumps({'type': 'peers', 'peers': list(self.peers)})
                    client.send(response.encode())
                    
                elif msg_type == 'new_block':
                    if self.blockchain:
                        print(f"   📡 Новый блок от {addr[0]}:{addr[1]}")
                        
            client.close()
        except:
            pass
    
    def broadcast_new_block(self, block):
        """Рассылка нового блока"""
        message = json.dumps({
            'type': 'new_block',
            'block': block.to_dict(),
            'sender': self.node_id,
            'timestamp': int(time.time())
        })
        
        for peer in list(self.peers):
            try:
                ip, port = peer.split(':')
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(3)
                sock.connect((ip, int(port)))
                sock.send(message.encode())
                sock.close()
            except:
                pass
        
        print(f"   📡 Блок #{block.height} разослан {len(self.peers)} пирам")
    
    def start(self):
        """Запуск всего"""
        print("🚀 Запуск глобальной P2P сети...")
        
        threading.Thread(target=self.start_server, daemon=True).start()
        time.sleep(1)
        
        self.register_on_trackers()
        self.get_peers_from_trackers()
        self.connect_to_bootstrap()
        
        print(f"✅ Глобальная P2P сеть запущена. Пиров: {len(self.peers)}")
        return self.peers

if __name__ == "__main__":
    p2p = GlobalP2PNetwork()
    p2p.start()
    print(f"\n🌍 Global P2P Network Demo")
    print(f"🆔 Node ID: {p2p.node_id}")
    print(f"📡 IP: {p2p.get_public_ip()}:{p2p.port}")
    print(f"🔗 Peers: {list(p2p.peers)[:5]}")

