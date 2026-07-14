"""
Economic data fetchers for trading signals.

Sources:
  - CME FedWatch: Fed rate change probabilities (no API key needed)
  - FRED API: CPI, unemployment, GDP actual data (free API key required)

All public-facing functions return a probability (0.0-1.0) of the YES
outcome, or None if data is unavailable.
"""

import math
import re
import time
import requests
from datetime import date, datetime
from typing import Optional

from logger import bot_logger

_cache: dict = {}
_CACHE_TTL = 3600  # economic data changes slowly — cache 1 hour

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
}


# ── Cache helpers ─────────────────────────────────────────────────────────────

def _get_cached(key: str):
    entry = _cache.get(key)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
        return entry["val"]
    return None


def _set_cached(key: str, val):
    _cache[key] = {"val": val, "ts": time.time()}
    return val


# ── Normal distribution ───────────────────────────────────────────────────────

def _prob_above(mean: float, std: float, threshold: float) -> float:
    """P(X > threshold) where X ~ N(mean, std). Uses math.erf — no scipy needed."""
    if std <= 0:
        return 1.0 if mean > threshold else 0.0
    z = (threshold - mean) / (std * math.sqrt(2))
    return 0.5 * (1.0 - math.erf(z))


def _prob_below(mean: float, std: float, threshold: float) -> float:
    return 1.0 - _prob_above(mean, std, threshold)


def _forecast_std(base_std: float, days_until_release: int) -> float:
    """Uncertainty grows with time: std scales with sqrt(months ahead)."""
    months = max(days_until_release / 30, 0.25)
    return base_std * math.sqrt(months)


# ── CME FedWatch ──────────────────────────────────────────────────────────────

_CME_URL = "https://www.cmegroup.com/CmeWS/mvc/MeetTheFed/V1/getFedWatch"


def _fetch_fedwatch() -> Optional[list]:
    cached = _get_cached("fedwatch")
    if cached is not None:
        return cached

    try:
        r = requests.get(_CME_URL, headers=_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        # Response may be a list or {"meetings": [...]}
        meetings = data if isinstance(data, list) else data.get("meetings", [])
        return _set_cached("fedwatch", meetings)
    except Exception as e:
        bot_logger.warning(f"CME FedWatch fetch failed: {e}")
        return None


def get_fed_probability(question: str, target_date: Optional[date] = None) -> Optional[float]:
    """
    Returns P(YES) for a Fed rate market question.
    Detects cut / hike / hold intent from question text.
    """
    q = question.lower()
    is_cut  = bool(re.search(r"\b(cut|lower|reduc|decreas)\b", q))
    is_hike = bool(re.search(r"\b(hike|rais|increas)\b", q))
    is_hold = bool(re.search(r"\b(hold|pause|unchang|no change|steady)\b", q))

    if not any([is_cut, is_hike, is_hold]):
        return None

    meetings = _fetch_fedwatch()
    if not meetings:
        return None

    # Find the meeting closest to target_date (or next upcoming)
    today = date.today()
    chosen = None
    for m in meetings:
        raw = m.get("date") or m.get("meetingDate") or m.get("month", "")
        try:
            mdate = datetime.strptime(raw[:10], "%Y-%m-%d").date()
        except Exception:
            continue
        if mdate >= today:
            if target_date is None or abs((mdate - target_date).days) <= 45:
                chosen = m
                break

    if chosen is None and meetings:
        chosen = meetings[0]
    if chosen is None:
        return None

    # Probabilities keyed like {"525-550": 5.2, "500-525": 72.1, ...}
    # or {"cut_25": 0.70, "hold": 0.25, "hike_25": 0.05}
    probs = chosen.get("prob", chosen.get("probabilities", {}))
    if not probs:
        return None

    total_cut = total_hike = total_hold = 0.0
    current_rate = None

    # Try to infer current rate from keys to detect cuts vs hikes
    rate_keys = []
    for k in probs:
        parts = re.findall(r"\d+", str(k))
        if len(parts) == 2:
            rate_keys.append((int(parts[0]), int(parts[1])))

    if rate_keys:
        rate_keys.sort()
        # The "current" rate is probably the bucket with highest probability
        max_prob_key = max(probs, key=lambda k: float(probs[k]))
        parts = re.findall(r"\d+", str(max_prob_key))
        if len(parts) == 2:
            current_rate = (int(parts[0]) + int(parts[1])) / 2

    for k, v in probs.items():
        try:
            pct = float(v) / 100.0 if float(v) > 1.0 else float(v)
        except Exception:
            continue
        k_str = str(k).lower()
        nums = re.findall(r"\d+", k_str)

        if any(w in k_str for w in ["cut", "lower", "decreas"]):
            total_cut += pct
        elif any(w in k_str for w in ["hike", "rais", "increas"]):
            total_hike += pct
        elif any(w in k_str for w in ["hold", "unch", "pause", "no change"]):
            total_hold += pct
        elif current_rate is not None and len(nums) == 2:
            mid = (int(nums[0]) + int(nums[1])) / 2
            if mid < current_rate:
                total_cut += pct
            elif mid > current_rate:
                total_hike += pct
            else:
                total_hold += pct

    # Normalize
    total = total_cut + total_hike + total_hold
    if total < 0.01:
        return None
    total_cut  /= total
    total_hike /= total
    total_hold /= total

    if is_cut:   return round(total_cut, 4)
    if is_hike:  return round(total_hike, 4)
    if is_hold:  return round(total_hold, 4)
    return None


# ── FRED API ──────────────────────────────────────────────────────────────────

_FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


def _fetch_fred(series_id: str, api_key: str, limit: int = 13) -> Optional[list]:
    cache_key = f"fred_{series_id}"
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    try:
        r = requests.get(
            _FRED_BASE,
            params={
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "sort_order": "desc",
                "limit": limit,
            },
            timeout=15,
        )
        r.raise_for_status()
        obs = [o for o in r.json().get("observations", []) if o.get("value", ".") != "."]
        return _set_cached(cache_key, obs)
    except Exception as e:
        bot_logger.warning(f"FRED {series_id} fetch failed: {e}")
        return None


def _get_fred_api_key() -> str:
    import config
    return getattr(config, "FRED_API_KEY", "")


def get_cpi_probability(threshold_pct: float, direction: str,
                        days_until_release: int = 30) -> Optional[float]:
    """
    P(CPI YoY will be above/below threshold_pct%) using FRED data + normal model.
    direction: "above" or "below"
    """
    api_key = _get_fred_api_key()
    if not api_key:
        bot_logger.debug("economic_data: FRED_API_KEY not set — skipping CPI probability")
        return None

    obs = _fetch_fred("CPIAUCSL", api_key, limit=14)
    if not obs or len(obs) < 13:
        return None

    try:
        curr     = float(obs[0]["value"])
        year_ago = float(obs[12]["value"])
        cpi_yoy  = (curr - year_ago) / year_ago * 100.0
    except Exception as e:
        bot_logger.warning(f"CPI YoY calc failed: {e}")
        return None

    # Historical 1-month CPI forecast error ~0.15%, grows with time horizon
    std = _forecast_std(base_std=0.15, days_until_release=days_until_release)

    if direction == "above":
        return round(_prob_above(cpi_yoy, std, threshold_pct), 4)
    return round(_prob_below(cpi_yoy, std, threshold_pct), 4)


def get_unemployment_probability(threshold_pct: float, direction: str,
                                 days_until_release: int = 30) -> Optional[float]:
    """
    P(unemployment will be above/below threshold_pct%) using FRED data.
    direction: "above" or "below"
    """
    api_key = _get_fred_api_key()
    if not api_key:
        bot_logger.debug("economic_data: FRED_API_KEY not set — skipping unemployment probability")
        return None

    obs = _fetch_fred("UNRATE", api_key, limit=3)
    if not obs:
        return None

    try:
        current_rate = float(obs[0]["value"])
    except Exception:
        return None

    # Unemployment moves slowly; 1-month std ~0.12%
    std = _forecast_std(base_std=0.12, days_until_release=days_until_release)

    if direction == "above":
        return round(_prob_above(current_rate, std, threshold_pct), 4)
    return round(_prob_below(current_rate, std, threshold_pct), 4)


def get_gdp_probability(threshold_pct: float, direction: str,
                        days_until_release: int = 60) -> Optional[float]:
    """
    P(GDP growth will be above/below threshold_pct%) using FRED data.
    direction: "above" or "below"
    """
    api_key = _get_fred_api_key()
    if not api_key:
        return None

    # A191RL1Q225SBEA = real GDP growth rate, quarterly, annualized
    obs = _fetch_fred("A191RL1Q225SBEA", api_key, limit=4)
    if not obs:
        return None

    try:
        current_gdp = float(obs[0]["value"])
    except Exception:
        return None

    # GDP forecast error ~0.5% for 1-quarter ahead
    std = _forecast_std(base_std=0.5, days_until_release=days_until_release)

    if direction == "above":
        return round(_prob_above(current_gdp, std, threshold_pct), 4)
    return round(_prob_below(current_gdp, std, threshold_pct), 4)
