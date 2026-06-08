# real_world_oracles.py - Оракулы реального мира (без API ключей)
import json
import time
import threading
import urllib.request
import os
from typing import Dict, Any, Optional

class RealWorldOracles:
    """Оракулы для получения данных из реального мира"""
    
    def __init__(self):
        self.cache: Dict[str, Any] = {}
        self.cache_time: Dict[str, float] = {}
        self.cache_ttl = 60
        self.lock = threading.RLock()
        # API ключ берется из переменных окружения (не хранится в коде!)
        self.api_key = os.getenv("OPENWEATHER_API_KEY", "")
    
    def _get_cached(self, key: str) -> Optional[Any]:
        if key in self.cache and time.time() - self.cache_time.get(key, 0) < self.cache_ttl:
            return self.cache[key]
        return None
    
    def _set_cache(self, key: str, value: Any):
        self.cache[key] = value
        self.cache_time[key] = time.time()
    
    def get_eth_price(self) -> float:
        cached = self._get_cached('eth_price')
        if cached is not None:
            return cached
        try:
            url = "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                price = float(data['price'])
                self._set_cache('eth_price', price)
                return price
        except:
            return 3500.0
    
    def get_btc_price(self) -> float:
        cached = self._get_cached('btc_price')
        if cached is not None:
            return cached
        try:
            url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                price = float(data['price'])
                self._set_cache('btc_price', price)
                return price
        except:
            return 60000.0
    
    def get_weather(self, city: str = "London") -> Dict:
        cached = self._get_cached(f'weather_{city}')
        if cached is not None:
            return cached
        # Без API ключа возвращаем тестовые данные
        import random
        weather = {
            'city': city,
            'temperature': round(random.uniform(-10, 35), 1),
            'condition': random.choice(['Sunny', 'Cloudy', 'Rainy', 'Snowy']),
            'humidity': random.randint(30, 90),
            'timestamp': time.time()
        }
        self._set_cache(f'weather_{city}', weather)
        return weather
    
    def get_random_number(self, min_val: int = 1, max_val: int = 100) -> int:
        import random
        return random.randint(min_val, max_val)
    
    def get_all_prices(self) -> Dict:
        return {
            'eth_usd': self.get_eth_price(),
            'btc_usd': self.get_btc_price(),
            'timestamp': time.time()
        }

oracles = RealWorldOracles()
