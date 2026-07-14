"""
Dynamic city lookup — geocodes city names not in config.CITIES
using OpenStreetMap Nominatim (free, no API key).

Results are cached in city_cache.json so each city is only
looked up once. Timezone is derived from lat/lon using timezonefinder.
"""

import json
import os
import time
import requests
from typing import Optional

import config
from logger import bot_logger

CACHE_FILE = os.path.join(os.path.dirname(__file__), "city_cache.json")
NOMINATIM  = "https://nominatim.openstreetmap.org/search"
HEADERS    = {"User-Agent": "PolymarketTradingBot/1.0 (weather trading)"}

_cache: dict = {}
_cache_loaded = False


def _load_cache():
    global _cache, _cache_loaded
    if _cache_loaded:
        return
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE) as f:
                _cache = json.load(f)
    except Exception:
        _cache = {}
    _cache_loaded = True


def _save_cache():
    try:
        with open(CACHE_FILE, "w") as f:
            json.dump(_cache, f, indent=2)
    except Exception as e:
        bot_logger.warning(f"city_lookup: could not save cache: {e}")


def _geocode(city_name: str) -> Optional[dict]:
    """Look up lat/lon via OpenStreetMap Nominatim."""
    try:
        time.sleep(1.1)  # Nominatim rate limit: 1 req/sec
        r = requests.get(NOMINATIM, params={
            "q": city_name, "format": "json", "limit": 1,
        }, headers=HEADERS, timeout=10)
        r.raise_for_status()
        results = r.json()
        if results:
            return {"lat": float(results[0]["lat"]), "lon": float(results[0]["lon"])}
    except Exception as e:
        bot_logger.warning(f"city_lookup: geocode failed for '{city_name}': {e}")
    return None


def _get_timezone(lat: float, lon: float) -> str:
    """Look up IANA timezone from coordinates."""
    try:
        from timezonefinder import TimezoneFinder
        tf = TimezoneFinder()
        tz = tf.timezone_at(lat=lat, lng=lon)
        return tz or "UTC"
    except Exception:
        return "UTC"


def get_city_data(city_name: str) -> Optional[dict]:
    """
    Return city data dict with lat, lon, timezone, aliases.
    Checks config.CITIES first, then local cache, then geocodes.
    Returns None if the city cannot be found.
    """
    # 1. Check hardcoded config
    if city_name in config.CITIES:
        return config.CITIES[city_name]

    # Also check by alias
    name_lower = city_name.lower()
    for cname, cdata in config.CITIES.items():
        if any(alias == name_lower for alias in cdata["aliases"]):
            return cdata

    # 2. Check local cache
    _load_cache()
    if city_name in _cache:
        return _cache[city_name]

    # 3. Geocode via Nominatim
    bot_logger.info(f"city_lookup: geocoding new city '{city_name}'...")
    coords = _geocode(city_name)
    if not coords:
        bot_logger.warning(f"city_lookup: could not geocode '{city_name}' — skipping")
        return None

    tz = _get_timezone(coords["lat"], coords["lon"])
    entry = {
        "lat":      coords["lat"],
        "lon":      coords["lon"],
        "timezone": tz,
        "aliases":  [city_name.lower()],
    }

    _cache[city_name] = entry
    _save_cache()
    bot_logger.info(f"city_lookup: cached '{city_name}' → {coords['lat']:.2f},{coords['lon']:.2f} ({tz})")
    return entry
