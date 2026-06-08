# real_world_oracles.py - Оракулы реального мира (без API ключей в коде!)
import json
import time
import threading
import urllib.request
import random
import os
from typing import Dict, Any, Optional

class RealWorldOracles:
    """Оракулы реального мира"""
    
    def __init__(self):
        self.cache: Dict[str, Any] = {}
        self.cache_time: Dict[str, float] = {}
        self.cache_ttl = 60
        self.lock = threading.RLock()
        # API ключи берутся из переменных окружения
        self.openweather_api_key = os.getenv("OPENWEATHER_API_KEY", "")
        self.weatherapi_key = os.getenv("WEATHERAPI_KEY", "")
    
    def _get_cached(self, key: str) -> Optional[Any]:
        if key in self.cache and time.time() - self.cache_time.get(key, 0) < self.cache_ttl:
            return self.cache[key]
        return None
    
    def _set_cache(self, key: str, value: Any):
        self.cache[key] = value
        self.cache_time[key] = time.time()
    
    def get_eth_price(self) -> float:
        cached = self._get_cached('eth_price')
        if cached:
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
        if cached:
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
        if cached:
            return cached
        # Тестовые данные (без API ключа)
        weather = {
            'city': city,
            'temperature': round(random.uniform(-10, 35), 1),
            'condition': random.choice(['Sunny', 'Cloudy', 'Rainy', 'Snowy']),
            'humidity': random.randint(30, 90),
            'timestamp': time.time(),
            'note': 'Test data - add OPENWEATHER_API_KEY to .env for real data'
        }
        self._set_cache(f'weather_{city}', weather)
        return weather
    
    def get_all_prices(self) -> Dict:
        return {
            'eth_usd': self.get_eth_price(),
            'btc_usd': self.get_btc_price(),
            'timestamp': time.time()
        }

# Глобальный экземпляр
oracles = RealWorldOracles()
oracle_manager = oracles  # Для обратной совместимости
