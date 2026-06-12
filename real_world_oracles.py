# real_world_oracles.py - COMPLETE ORACLES (FIXED)
import requests
import json
import time
import threading
from typing import Dict, Optional, List
from datetime import datetime
from dataclasses import dataclass

@dataclass
class PriceData:
    symbol: str
    price: float
    change_24h: float
    volume: float
    market_cap: float
    timestamp: float
    source: str = "coingecko"

@dataclass
class WeatherData:
    city: str
    temperature: float
    condition: str
    humidity: int
    wind_speed: float
    timestamp: float
    source: str = "openweather"

class OracleManager:
    """Complete oracle system with real API integration"""
    
    def __init__(self):
        # API keys только из переменных окружения (никогда не хардкодить в репозиторий)
        import os
        self.openweather_key = os.getenv("OPENWEATHER_API_KEY", "")
        self.weatherapi_key = os.getenv("WEATHERAPI_KEY", "")
        
        # Cache
        self.price_cache: Dict[str, PriceData] = {}
        self.weather_cache: Dict[str, WeatherData] = {}
        self.cache_ttl = 60  # seconds
        
        # Start update thread
        self.running = True
        self.update_thread = threading.Thread(target=self._auto_update, daemon=True)
        self.update_thread.start()
    
    def get_crypto_price(self, symbol: str) -> Optional[PriceData]:
        """Get real cryptocurrency price from API"""
        # Check cache first
        if symbol in self.price_cache:
            cached = self.price_cache[symbol]
            if time.time() - cached.timestamp < self.cache_ttl:
                return cached
        
        try:
            # Use CoinGecko API (free, no key required)
            url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=usd&include_24hr_change=true&include_volume=true&include_market_cap=true"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if symbol in data:
                    price_data = PriceData(
                        symbol=symbol,
                        price=data[symbol].get('usd', 0),
                        change_24h=data[symbol].get('usd_24h_change', 0),
                        volume=data[symbol].get('usd_24h_vol', 0),
                        market_cap=data[symbol].get('usd_market_cap', 0),
                        timestamp=time.time(),
                        source="coingecko",
                    )
                    self.price_cache[symbol] = price_data
                    return price_data
            
            return None

        except Exception as e:
            print(f"Price API error ({symbol}): {e}")
            return None

    def get_abs_reference_price(self) -> PriceData:
        """Educational ABS reference — derived from chain tokenomics, not a market feed."""
        try:
            from runtime.tokenomics import MAX_SUPPLY_ABS
            supply = float(MAX_SUPPLY_ABS)
        except ImportError:
            supply = 221_000_000.0
        return PriceData(
            symbol="absolute",
            price=round(1.0 / max(supply, 1), 8),
            change_24h=0.0,
            volume=0.0,
            market_cap=supply * round(1.0 / max(supply, 1), 8),
            timestamp=time.time(),
            source="tokenomics_reference",
        )
    
    def get_weather(self, city: str) -> Optional[WeatherData]:
        """Get real weather data from OpenWeatherMap API"""
        # Check cache
        if city in self.weather_cache:
            cached = self.weather_cache[city]
            if time.time() - cached.timestamp < self.cache_ttl:
                return cached
        
        if not self.openweather_key and not self.weatherapi_key:
            return None

        try:
            if self.openweather_key:
                url = (
                    f"https://api.openweathermap.org/data/2.5/weather"
                    f"?q={city}&appid={self.openweather_key}&units=metric"
                )
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    weather_data = WeatherData(
                        city=city,
                        temperature=data["main"]["temp"],
                        condition=data["weather"][0]["description"],
                        humidity=data["main"]["humidity"],
                        wind_speed=data["wind"]["speed"],
                        timestamp=time.time(),
                        source="openweather",
                    )
                    self.weather_cache[city] = weather_data
                    return weather_data

            if self.weatherapi_key:
                url = (
                    f"https://api.weatherapi.com/v1/current.json"
                    f"?key={self.weatherapi_key}&q={city}"
                )
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    weather_data = WeatherData(
                        city=city,
                        temperature=data["current"]["temp_c"],
                        condition=data["current"]["condition"]["text"],
                        humidity=data["current"]["humidity"],
                        wind_speed=data["current"]["wind_kph"],
                        timestamp=time.time(),
                        source="weatherapi",
                    )
                    self.weather_cache[city] = weather_data
                    return weather_data

            return None

        except Exception as e:
            print(f"Weather API error ({city}): {e}")
            return None
    
    def _auto_update(self):
        """Auto-update prices periodically"""
        while self.running:
            time.sleep(300)  # Update every 5 minutes
            for symbol in list(self.price_cache.keys()):
                self.get_crypto_price(symbol)
    
    def stop(self):
        """Stop oracle updates"""
        self.running = False
    
    def get_all_prices(self) -> Dict:
        """Get prices for major cryptocurrencies + ABS reference."""
        symbols = ["bitcoin", "ethereum", "solana", "dogecoin"]
        result = {}
        for symbol in symbols:
            price = self.get_crypto_price(symbol)
            if price:
                result[symbol] = {
                    "price": price.price,
                    "change_24h": price.change_24h,
                    "volume": price.volume,
                    "market_cap": price.market_cap,
                    "source": price.source,
                }
        abs_p = self.get_abs_reference_price()
        result["absolute"] = {
            "price": abs_p.price,
            "change_24h": abs_p.change_24h,
            "volume": abs_p.volume,
            "market_cap": abs_p.market_cap,
            "source": abs_p.source,
        }
        return result

    def get_stats(self) -> Dict:
        return {
            "enabled": True,
            "price_cache_size": len(self.price_cache),
            "weather_cache_size": len(self.weather_cache),
            "openweather_configured": bool(self.openweather_key),
            "weatherapi_configured": bool(self.weatherapi_key),
            "cache_ttl_sec": self.cache_ttl,
            "sources": {
                "crypto": "coingecko",
                "weather": "openweather|weatherapi",
                "abs": "tokenomics_reference",
            },
        }

    def get_news(self) -> List[Dict]:
        """Crypto headlines via free CoinGecko trending (no extra API key)."""
        try:
            r = requests.get(
                "https://api.coingecko.com/api/v3/search/trending",
                timeout=10,
            )
            if r.status_code != 200:
                return []
            coins = r.json().get("coins", [])
            out = []
            for item in coins[:8]:
                c = item.get("item", {})
                out.append({
                    "title": c.get("name", ""),
                    "symbol": (c.get("symbol") or "").upper(),
                    "rank": c.get("market_cap_rank"),
                    "source": "coingecko_trending",
                })
            return out
        except Exception as e:
            print(f"Oracle news error: {e}")
            return []

# Global oracle instance (single)
oracle = OracleManager()

# API endpoints for extended server
def register_oracle_routes(app):
    """Register oracle routes with FastAPI app"""
    
    @app.get("/api/oracle/price")
    async def get_price(symbol: str = "bitcoin"):
        price = oracle.get_crypto_price(symbol.lower())
        if price:
            return {
                "symbol": price.symbol,
                "price_usd": price.price,
                "change_24h": price.change_24h,
                "volume_24h": price.volume,
                "market_cap": price.market_cap,
                "timestamp": price.timestamp
            }
        return {"error": "Price not found"}
    
    @app.get("/api/oracle/weather")
    async def get_weather(city: str = "London"):
        weather = oracle.get_weather(city)
        if weather:
            return {
                "city": weather.city,
                "temperature_c": weather.temperature,
                "condition": weather.condition,
                "humidity": weather.humidity,
                "wind_speed_kph": weather.wind_speed,
                "timestamp": weather.timestamp
            }
        return {"error": "Weather not found"}
    
    @app.get("/api/oracle/all_prices")
    async def get_all_prices():
        return oracle.get_all_prices()

# Back-compat alias — one shared instance
oracle_manager = oracle

if __name__ == "__main__":
    print("Testing oracles...")
    btc = oracle.get_crypto_price("bitcoin")
    print(f"BTC: ${btc.price:,.2f}")
    
    weather = oracle.get_weather("London")
    print(f"London: {weather.temperature}°C, {weather.condition}")


