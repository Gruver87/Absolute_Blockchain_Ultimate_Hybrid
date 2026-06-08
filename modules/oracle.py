# modules/oracle.py
import json
import urllib.request
import time

class OracleModule:
    def __init__(self):
        self.cache = {}
        self.cache_time = {}
        print("   ✅ Oracle Module loaded")
    
    def _get_cached(self, key, ttl=60):
        if key in self.cache and time.time() - self.cache_time.get(key, 0) < ttl:
            return self.cache[key]
        return None
    
    def _set_cache(self, key, value):
        self.cache[key] = value
        self.cache_time[key] = time.time()
    
    def get_price(self, symbol='bitcoin'):
        cached = self._get_cached(f"price_{symbol}")
        if cached:
            return cached
        
        try:
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=usd"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                price = data.get(symbol, {}).get('usd', 0)
                result = {'symbol': symbol, 'price': price, 'currency': 'usd', 'timestamp': int(time.time())}
                self._set_cache(f"price_{symbol}", result)
                return result
        except:
            return {'symbol': symbol, 'price': 0, 'error': 'Failed to fetch', 'timestamp': int(time.time())}
    
    def get_weather(self, city='London'):
        cached = self._get_cached(f"weather_{city}")
        if cached:
            return cached
        
        try:
            # OpenWeatherMap API (требуется ключ)
            api_key = "REDACTED_OPENWEATHER_USE_ENV"
            url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode())
                result = {
                    'city': city,
                    'temperature': data['main']['temp'],
                    'humidity': data['main']['humidity'],
                    'description': data['weather'][0]['description'],
                    'timestamp': int(time.time())
                }
                self._set_cache(f"weather_{city}", result)
                return result
        except:
            return {'city': city, 'error': 'Failed to fetch', 'timestamp': int(time.time())}
    
    def stop(self):
        pass
