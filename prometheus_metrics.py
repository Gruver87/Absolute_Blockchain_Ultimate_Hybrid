#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import threading
import requests
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST
from http.server import HTTPServer, BaseHTTPRequestHandler

blocks_total = Counter('blockchain_blocks_total', 'Total number of blocks')
transactions_total = Counter('blockchain_transactions_total', 'Total number of transactions')
pending_transactions = Gauge('blockchain_pending_transactions', 'Number of pending transactions')
current_difficulty = Gauge('blockchain_difficulty', 'Current mining difficulty')
total_supply = Gauge('blockchain_total_supply', 'Total ABS supply')
peers_count = Gauge('blockchain_peers_count', 'Number of P2P peers')

class MetricsServer:
    def __init__(self, api_url: str = "http://localhost:8080", port: int = 9090):
        self.api_url = api_url
        self.port = port
        self._running = True
        self._start_collector()
        print(f"📊 Prometheus Metrics initialized on port {self.port}")
    
    def _start_collector(self):
        def collect():
            while self._running:
                try:
                    r = requests.get(f"{self.api_url}/api/stats", timeout=30)
                    if r.status_code == 200:
                        stats = r.json()
                        blocks_total.inc(stats.get('blocks', 0) - blocks_total._value.get())
                        pending_transactions.set(stats.get('pending_transactions', 0))
                        current_difficulty.set(stats.get('difficulty', 1))
                        total_supply.set(stats.get('total_supply', 0))
                    
                    r = requests.get(f"{self.api_url}/api/peers", timeout=30)
                    if r.status_code == 200:
                        peers = r.json()
                        peers_count.set(len(peers.get('peers', [])))
                    
                except Exception as e:
                    print(f"   Metrics collection error: {e}")
                
                time.sleep(30)
        
        threading.Thread(target=collect, daemon=True).start()
    
    def start(self):
        class MetricsHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass
            
            def do_GET(self):
                if self.path == '/metrics':
                    self.send_response(200)
                    self.send_header('Content-Type', CONTENT_TYPE_LATEST)
                    self.end_headers()
                    self.wfile.write(generate_latest())
                else:
                    self.send_response(404)
                    self.end_headers()
        
        server = HTTPServer(('0.0.0.0', self.port), MetricsHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"   Metrics endpoint: http://localhost:{self.port}/metrics")
        return server


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  ABSOLUTE BLOCKCHAIN - PROMETHEUS METRICS (FIXED)")
    print("="*60)
    
    metrics = MetricsServer()
    metrics.start()
    
    print("\n✅ Prometheus метрики активны!")
    print(f"   curl http://localhost:9090/metrics")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Metrics server stopped")
