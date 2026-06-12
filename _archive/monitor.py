#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import time
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler

class BlockchainMonitor:
    def __init__(self, api_url: str = "http://localhost:8080"):
        self.api_url = api_url
        self.alerts = []
        self.metrics = {}
        self.is_running = True
        self._start_monitoring()
        print(f"📊 Blockchain Monitor initialized")
    
    def _get_stats(self):
        try:
            r = requests.get(f"{self.api_url}/api/stats", timeout=30)
            return r.json() if r.status_code == 200 else {}
        except:
            return {}
    
    def _get_peers(self):
        try:
            r = requests.get(f"{self.api_url}/api/peers", timeout=30)
            data = r.json() if r.status_code == 200 else {}
            return data.get('peers', [])
        except:
            return []
    
    def _check_health(self):
        stats = self._get_stats()
        peers = self._get_peers()
        
        self.metrics = {
            'timestamp': int(time.time()),
            'blocks': stats.get('blocks', 0),
            'pending': stats.get('pending_transactions', 0),
            'difficulty': stats.get('difficulty', 1),
            'peers_count': len(peers),
            'api_status': 'online' if stats else 'offline'
        }
        
        if not stats:
            self._add_alert('CRITICAL', 'API сервер не отвечает')
        elif self.metrics['pending'] > 100:
            self._add_alert('WARNING', f'Большая очередь: {self.metrics["pending"]}')
        elif self.metrics['peers_count'] == 0:
            self._add_alert('WARNING', 'Нет подключённых пиров')
    
    def _add_alert(self, level, message):
        alert = {'level': level, 'message': message, 'timestamp': int(time.time())}
        self.alerts.append(alert)
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        print(f"⚠️ [{level}] {message}")
    
    def _start_monitoring(self):
        def monitor():
            while self.is_running:
                self._check_health()
                time.sleep(30)
        threading.Thread(target=monitor, daemon=True).start()
    
    def get_metrics(self):
        return self.metrics
    
    def get_alerts(self, limit=20):
        return self.alerts[-limit:][::-1]


class MonitorServer:
    def __init__(self):
        self.monitor = BlockchainMonitor()
        self.port = 8092
    
    def start(self):
        class Handler(BaseHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                self.monitor = monitor
                super().__init__(*args, **kwargs)
            
            def log_message(self, format, *args):
                pass
            
            def do_GET(self):
                if self.path == '/':
                    self._send_html(self._get_html())
                elif self.path == '/api/monitor/metrics':
                    self._send_json(self.monitor.get_metrics())
                elif self.path == '/api/monitor/alerts':
                    self._send_json({'alerts': self.monitor.get_alerts()})
                else:
                    self._send_error(404)
            
            def _send_json(self, data):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode())
            
            def _send_html(self, html):
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(html.encode())
            
            def _send_error(self, code):
                self.send_response(code)
                self.end_headers()
            
            def _get_html(self):
                return '''
                <!DOCTYPE html>
                <html>
                <head><title>Monitor</title>
                <style>body{font-family:monospace;background:#0a0a2a;color:white;padding:20px}</style>
                </head>
                <body>
                <h1>📊 Blockchain Monitor</h1>
                <div id="metrics"></div>
                <div id="alerts"></div>
                <script>
                async function load(){const r=await fetch('/api/monitor/metrics');const d=await r.json();document.getElementById('metrics').innerHTML=JSON.stringify(d,null,2);const a=await fetch('/api/monitor/alerts');const al=await a.json();document.getElementById('alerts').innerHTML='<h2>⚠️ Alerts</h2>'+JSON.stringify(al,null,2);}
                load();setInterval(load,5000);
                </script>
                </body>
                </html>
                '''
        
        monitor = self.monitor
        server = HTTPServer(('0.0.0.0', self.port), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"📊 Monitor started on http://localhost:{self.port}")
        return server


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  ABSOLUTE BLOCKCHAIN - MONITOR (FIXED)")
    print("="*60)
    
    server = MonitorServer()
    server.start()
    
    print(f"\n✅ Мониторинг активен: http://localhost:8092")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Мониторинг остановлен")





