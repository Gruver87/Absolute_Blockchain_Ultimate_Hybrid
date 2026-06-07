import os
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ABSOLUTE BLOCKCHAIN - REAL WORLD ORACLES (С РАБОЧИМИ API)
"""

import time
import json
import threading
import requests
from datetime import datetime
from typing import Dict, List, Optional

class OracleConfig:
    UPDATE_INTERVAL = 60
    CACHE_TTL = 300
    MIN_SOURCES = 1

class PriceOracle:
    def __init__(self):
        self.cache = {}
        self.lock = threading.RLock()
        print("?? Price Oracle initialized")
    
    def _fetch_coingecko(self, symbol):
        try:
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=usd"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data.get(symbol, {}).get('usd', 0)
        except:
            pass
        return None
    
    def _fetch_binance(self, symbol):
        try:
            symbol_map = {'bitcoin': 'BTCUSDT', 'ethereum': 'ETHUSDT', 'solana': 'SOLUSDT'}
            pair = symbol_map.get(symbol, f"{symbol.upper()}USDT")
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={pair}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return float(data.get('price', 0))
        except:
            pass
        return None
    
    def _fetch_kucoin(self, symbol):
        try:
            symbol_map = {'bitcoin': 'BTC-USDT', 'ethereum': 'ETH-USDT', 'solana': 'SOL-USDT'}
            pair = symbol_map.get(symbol, f"{symbol.upper()}-USDT")
            url = f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={pair}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return float(data.get('data', {}).get('price', 0))
        except:
            pass
        return None
    
    def get_price(self, symbol: str, vs_currency: str = 'usd') -> Dict:
        cache_key = f"{symbol}_{vs_currency}"
        
        with self.lock:
            if cache_key in self.cache:
                entry = self.cache[cache_key]
                if time.time() - entry['timestamp'] < OracleConfig.CACHE_TTL:
                    return entry['data']
        
        prices = []
        
        coingecko = self._fetch_coingecko(symbol)
        if coingecko:
            prices.append({'source': 'coingecko', 'price': coingecko})
        
        binance = self._fetch_binance(symbol)
        if binance:
            prices.append({'source': 'binance', 'price': binance})
        
        kucoin = self._fetch_kucoin(symbol)
        if kucoin:
            prices.append({'source': 'kucoin', 'price': kucoin})
        
        if len(prices) >= OracleConfig.MIN_SOURCES:
            price_values = [p['price'] for p in prices]
            price_values.sort()
            median_price = price_values[len(price_values) // 2]
            
            result = {
                'symbol': symbol,
                'price': round(median_price, 2),
                'currency': vs_currency,
                'sources': prices,
                'timestamp': int(time.time()),
                'confidence': len(prices) / 3 * 100
            }
            
            with self.lock:
                self.cache[cache_key] = {'data': result, 'timestamp': time.time()}
            
            return result
        
        return {'symbol': symbol, 'price': 0, 'error': 'No consensus reached'}

class WeatherOracle:
    def __init__(self):
        self.cache = {}
        self.lock = threading.RLock()
        # ТВОИ API КЛЮЧИ
        self.OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
        self.WEATHERAPI_KEY = os.getenv("WEATHERAPI_KEY", "")
        print("??? Weather Oracle initialized")
    
    def _fetch_openweather(self, city: str) -> Optional[Dict]:
        try:
            url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={self.OPENWEATHER_API_KEY}&units=metric"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return {
                    'temperature': data['main']['temp'],
                    'feels_like': data['main']['feels_like'],
                    'humidity': data['main']['humidity'],
                    'wind_speed': data['wind']['speed'],
                    'description': data['weather'][0]['description']
                }
        except Exception as e:
            print(f"OpenWeather error: {e}")
        return None
    
    def _fetch_weatherapi(self, city: str) -> Optional[Dict]:
        try:
            url = f"http://api.weatherapi.com/v1/current.json?key={self.WEATHERAPI_KEY}&q={city}"
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                current = data.get('current', {})
                return {
                    'temperature': current.get('temp_c', 0),
                    'feels_like': current.get('feelslike_c', 0),
                    'humidity': current.get('humidity', 0),
                    'wind_speed': current.get('wind_kph', 0),
                    'description': current.get('condition', {}).get('text', '')
                }
        except Exception as e:
            print(f"WeatherAPI error: {e}")
        return None
    
    def get_weather(self, city: str) -> Dict:
        cache_key = f"weather_{city}"
        
        with self.lock:
            if cache_key in self.cache:
                entry = self.cache[cache_key]
                if time.time() - entry['timestamp'] < OracleConfig.CACHE_TTL:
                    return entry['data']
        
        weather_data = []
        
        # OpenWeatherMap
        owm = self._fetch_openweather(city)
        if owm:
            weather_data.append({'source': 'openweathermap', 'data': owm})
        
        # WeatherAPI
        wapi = self._fetch_weatherapi(city)
        if wapi:
            weather_data.append({'source': 'weatherapi', 'data': wapi})
        
        if weather_data:
            avg_temp = sum(w['data']['temperature'] for w in weather_data) / len(weather_data)
            avg_humidity = sum(w['data']['humidity'] for w in weather_data) / len(weather_data)
            avg_wind = sum(w['data']['wind_speed'] for w in weather_data) / len(weather_data)
            
            result = {
                'city': city,
                'temperature': round(avg_temp, 1),
                'feels_like': round(avg_temp, 1),
                'humidity': round(avg_humidity, 0),
                'wind_speed': round(avg_wind, 1),
                'description': weather_data[0]['data'].get('description', 'Unknown'),
                'sources': len(weather_data),
                'timestamp': int(time.time()),
                'confidence': len(weather_data) * 50
            }
            
            with self.lock:
                self.cache[cache_key] = {'data': result, 'timestamp': time.time()}
            
            return result
        
        return {'city': city, 'temperature': 'N/A', 'error': 'Weather service unavailable', 'timestamp': int(time.time())}

class NewsOracle:
    def __init__(self):
        self.cache = {}
        self.lock = threading.RLock()
        print("?? News Oracle initialized")
    
    def get_news(self, currency=None, limit=10):
        return {'news': [], 'count': 0, 'timestamp': int(time.time())}

class OracleManager:
    def __init__(self):
        self.price_oracle = PriceOracle()
        self.weather_oracle = WeatherOracle()
        self.news_oracle = NewsOracle()
        self._running = False
        print("?? Oracle Manager initialized")
    
    def get_price(self, symbol='bitcoin'):
        return self.price_oracle.get_price(symbol)
    
    def get_weather(self, city='London'):
        return self.weather_oracle.get_weather(city)
    
    def get_news(self, currency=None, limit=10):
        return self.news_oracle.get_news(currency, limit)
    
    def get_all_data(self):
        return {
            'prices': {'bitcoin': self.get_price('bitcoin'), 'ethereum': self.get_price('ethereum')},
            'timestamp': int(time.time())
        }
    
    def get_stats(self):
        return {
            'price_cache': len(self.price_oracle.cache),
            'weather_cache': len(self.weather_oracle.cache),
            'news_cache': len(self.news_oracle.cache),
            'status': 'active'
        }
    
    def start_auto_update(self):
        self._running = True
        def update_loop():
            while self._running:
                try:
                    self.get_price('bitcoin')
                    print(f"?? Oracles data updated at {datetime.now()}")
                except:
                    pass
                time.sleep(OracleConfig.UPDATE_INTERVAL)
        threading.Thread(target=update_loop, daemon=True).start()
        print("?? Auto-update started")

oracle_manager = OracleManager()


