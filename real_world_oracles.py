# real_world_oracles.py - исправленная версия
import json, time, threading, urllib.request, os, random

class RealWorldOracles:
    def __init__(self):
        self.cache = {}
        self.cache_time = {}
        self.cache_ttl = 60
        self.lock = threading.RLock()
    
    def _get_cached(self, key):
        if key in self.cache and time.time() - self.cache_time.get(key, 0) < self.cache_ttl:
            return self.cache[key]
        return None
    
    def _set_cache(self, key, value):
        self.cache[key] = value
        self.cache_time[key] = time.time()
    
    def get_eth_price(self):
        cached = self._get_cached('eth_price')
        if cached: return cached
        try:
            with urllib.request.urlopen("https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT", timeout=5) as r:
                price = float(json.loads(r.read().decode())['price'])
                self._set_cache('eth_price', price)
                return price
        except:
            return 3500.0
    
    def get_btc_price(self):
        cached = self._get_cached('btc_price')
        if cached: return cached
        try:
            with urllib.request.urlopen("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5) as r:
                price = float(json.loads(r.read().decode())['price'])
                self._set_cache('btc_price', price)
                return price
        except:
            return 60000.0
    
    def get_all_prices(self):
        return {'eth_usd': self.get_eth_price(), 'btc_usd': self.get_btc_price(), 'timestamp': time.time()}

oracles = RealWorldOracles()
