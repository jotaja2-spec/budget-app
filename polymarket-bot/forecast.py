"""
Pulls 31-member GFS ensemble data from Open-Meteo and calculates the
probability that the daily high temperature will be above or below a
given threshold (in °F) on a specific date.
"""

import requests
from datetime import date, datetime, timedelta
from typing import Optional
from functools import lru_cache

import config
from logger import bot_logger

# Cache forecasts for 30 minutes (key = city + date string) to avoid hammering the API
_forecast_cache: dict = {}
_cache_timestamps: dict = {}
CACHE_TTL_SECONDS = 1800


def _cache_key(city: str, target_date: date) -> str:
    return f"{city}:{target_date.isoformat()}"


def _is_cache_valid(key: str) -> bool:
    import time
    ts = _cache_timestamps.get(key)
    return ts is not None and (time.time() - ts) < CACHE_TTL_SECONDS


def fetch_ensemble_highs(city: str, target_date: date) -> Optional[list[float]]:
    """
    Returns a list of 31 ensemble daily-high temperature values in °F
    for the given city and date. Returns None on failure.
    """
    key = _cache_key(city, target_date)
    if _is_cache_valid(key):
        return _forecast_cache[key]

    from city_lookup import get_city_data
    city_data = get_city_data(city)
    if not city_data:
        bot_logger.warning(f"forecast: unknown city '{city}'")
        return None

    today = date.today()
    days_ahead = (target_date - today).days
    if days_ahead < 0 or days_ahead > 15:
        bot_logger.warning(f"forecast: {city} date {target_date} is {days_ahead}d away (supported: 0–15)")
        return None

    params = {
        "latitude": city_data["lat"],
        "longitude": city_data["lon"],
        "models": "gfs_seamless",
        "daily": "temperature_2m_max",
        "temperature_unit": "fahrenheit",
        "timezone": city_data["timezone"],
        "forecast_days": min(days_ahead + 1, 16),
    }

    try:
        resp = requests.get(config.OPEN_METEO_ENSEMBLE_URL, params=params, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        bot_logger.error(f"Open-Meteo request failed for {city}: {e}")
        return None

    daily = data.get("daily", {})
    dates = daily.get("time", [])
    target_str = target_date.isoformat()

    if target_str not in dates:
        bot_logger.warning(f"forecast: {target_str} not in Open-Meteo response for {city}")
        return None

    idx = dates.index(target_str)

    # Ensemble members are returned as "temperature_2m_max_member01", etc.
    # The base "temperature_2m_max" is the ensemble mean — skip it.
    highs = []
    member = 1
    while True:
        key_name = f"temperature_2m_max_member{member:02d}"
        if key_name not in daily:
            break
        vals = daily[key_name]
        if idx < len(vals) and vals[idx] is not None:
            highs.append(float(vals[idx]))
        member += 1

    # Fallback: if member keys absent, use ensemble mean as single value
    if not highs:
        mean_vals = daily.get("temperature_2m_max", [])
        if idx < len(mean_vals) and mean_vals[idx] is not None:
            highs = [float(mean_vals[idx])]
            bot_logger.warning(f"forecast: no ensemble members found for {city}, using mean only")

    if not highs:
        bot_logger.warning(f"forecast: no temperature data for {city} on {target_date}")
        return None

    import time
    cache_key = _cache_key(city, target_date)
    _forecast_cache[cache_key] = highs
    _cache_timestamps[cache_key] = time.time()

    bot_logger.info(
        f"Forecast {city} {target_date}: {len(highs)} members, "
        f"range {min(highs):.1f}–{max(highs):.1f}°F, mean {sum(highs)/len(highs):.1f}°F"
    )
    return highs


def calc_probability(highs: list[float], threshold_f: float, yes_if: str,
                     threshold_f_upper: float = None) -> float:
    """
    yes_if: 'above'  → P(high > threshold_f)
            'below'  → P(high < threshold_f)
            'exact'  → P(threshold_f < high <= threshold_f_upper)
    Returns probability in [0, 1].
    """
    if not highs:
        return 0.5

    if yes_if == "above":
        count = sum(1 for h in highs if h > threshold_f)
    elif yes_if == "exact" and threshold_f_upper is not None:
        count = sum(1 for h in highs if threshold_f < h <= threshold_f_upper)
    else:
        count = sum(1 for h in highs if h < threshold_f)

    return count / len(highs)


def get_forecast_probability(city: str, target_date: date, threshold_f: float,
                             yes_if: str, threshold_f_upper: float = None) -> Optional[float]:
    """
    Full pipeline: fetch ensemble → calculate probability.
    For yes_if='exact', pass threshold_f as lower bound and threshold_f_upper as upper bound.
    Returns None if data unavailable.
    """
    highs = fetch_ensemble_highs(city, target_date)
    if highs is None:
        return None
    prob = calc_probability(highs, threshold_f, yes_if, threshold_f_upper)
    return prob
