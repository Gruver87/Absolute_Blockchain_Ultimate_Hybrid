#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  ABSOLUTE BLOCKCHAIN - MOBILE API (FIXED)
================================================================================
"""

import json
import time
import os
import threading
import requests
from http.server import HTTPServer, BaseHTTPRequestHandler

class MobileAPIHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        self.api_url = "http://localhost:8080"
        super().__init__(*args, **kwargs)
    
    def log_message(self, format, *args):
        pass
    
    def _send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_GET(self):
        if self.path == '/api/mobile/config':
            self._send_json({
                'app_name': 'Absolute Blockchain',
                'version': '1.0.0',
                'api_version': 'v1',
                'features': ['send', 'receive', 'staking', 'nft', 'swap']
            })
        
        elif self.path.startswith('/api/mobile/balance/'):
            address = self.path.split('/')[-1]
            if address:
                try:
                    r = requests.get(f"{self.api_url}/api/balance?address={address}", timeout=10)
                    data = r.json()
                    self._send_json({'success': True, 'balance': data.get('balance', 0), 'address': address})
                except:
                    self._send_json({'success': False, 'error': 'Network error'})
            else:
                self._send_json({'success': False, 'error': 'Address required'})
        
        elif self.path == '/api/mobile/stats':
            try:
                r = requests.get(f"{self.api_url}/api/stats", timeout=10)
                data = r.json()
                self._send_json({'success': True, 'blocks': data.get('blocks', 0), 'supply': data.get('total_supply', 0)})
            except:
                self._send_json({'success': False, 'error': 'Network error'})
        
        else:
            self._send_json({'error': 'Not found'})
    
    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length else b'{}'
        try:
            data = json.loads(body.decode())
        except:
            data = {}
        
        if self.path == '/api/mobile/send':
            from_addr = data.get('from')
            to_addr = data.get('to')
            amount = data.get('amount')
            private_key = data.get('private_key')
            
            if not all([from_addr, to_addr, amount, private_key]):
                self._send_json({'success': False, 'error': 'Missing fields'})
                return
            
            try:
                r = requests.post(f"{self.api_url}/api/transaction/send", json={
                    'from': from_addr, 'to': to_addr, 'amount': amount, 'private_key': private_key
                }, timeout=30)
                self._send_json(r.json())
            except:
                self._send_json({'success': False, 'error': 'Network error'})
        
        elif self.path == '/api/mobile/create_wallet':
            try:
                r = requests.post(f"{self.api_url}/api/wallet/create", timeout=30)
                self._send_json(r.json())
            except:
                self._send_json({'success': False, 'error': 'Network error'})
        
        elif self.path == '/api/mobile/register_device':
            device_token = data.get('device_token')
            platform = data.get('platform')
            user_id = data.get('user_id')
            
            devices_file = "data/devices.json"
            devices = {}
            if os.path.exists(devices_file):
                with open(devices_file, 'r') as f:
                    devices = json.load(f)
            
            if user_id not in devices:
                devices[user_id] = []
            
            devices[user_id].append({
                'token': device_token,
                'platform': platform,
                'registered_at': int(time.time())
            })
            
            os.makedirs("data", exist_ok=True)
            with open(devices_file, 'w') as f:
                json.dump(devices, f)
            
            self._send_json({'success': True})
        
        else:
            self._send_json({'error': 'Not found'})


class MobileAPIServer:
    def __init__(self, port: int = 8093):
        self.port = port
        self.server = None
    
    def start(self):
        self.server = HTTPServer(('0.0.0.0', self.port), MobileAPIHandler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        print(f"📱 Mobile API started on http://localhost:{self.port}")
        return self.server
    
    def stop(self):
        if self.server:
            self.server.shutdown()


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  ABSOLUTE BLOCKCHAIN - MOBILE API (FIXED)")
    print("="*60)
    
    server = MobileAPIServer()
    server.start()
    
    print(f"\n✅ Mobile API активен на порту 8093")
    print(f"   GET  /api/mobile/config")
    print(f"   GET  /api/mobile/balance/:address")
    print(f"   GET  /api/mobile/stats")
    print(f"   POST /api/mobile/send")
    print(f"   POST /api/mobile/create_wallet")
    print(f"   POST /api/mobile/register_device")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Mobile API остановлен")
