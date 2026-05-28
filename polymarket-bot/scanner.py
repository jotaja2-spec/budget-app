"""
Fetches weather markets from Polymarket via the Events API.

Polymarket organises temperature markets as events titled:
  "Highest temperature in [City] on [Date]?"
Each event contains nested markets like:
  "Will the highest temperature in NYC be 22°C on May 28?"
  "Will the highest temperature in NYC be 24°C or above on May 28?"

This scanner fetches those events, extracts the nested markets,
and returns parsed dicts ready for signal evaluation.
"""

import json
import re
import requests
from datetime import date, datetime
from typing import Optional

import config
from logger import bot_logger

EVENTS_URL = "https://gamma-api.polymarket.com/events"

# Matches event titles: "Highest temperature in NYC on May 28?"
_EVENT_TITLE_RE = re.compile(r"highest temperature in (.+?) on", re.IGNORECASE)

# Matches market questions — three formats:
#   "...be 22°C on..."           → exact bucket
#   "...be 22°C or below on..."  → lower bracket
#   "...be 22°C or above on..."  → upper bracket
_MARKET_Q_RE = re.compile(
    r"be\s+(\d+(?:\.\d+)?)\s*°?C\s*(or below|or above)?",
    re.IGNORECASE,
)

_DATE_RE = re.compile(
    r"on\s+((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,?\s*\d{4})?)",
    re.IGNORECASE,
)


def _celsius_to_f(c: float) -> float:
    return c * 9.0 / 5.0 + 32.0


def _match_city(text: str) -> Optional[str]:
    """
    Match city name from event title to a known city.
    Checks config.CITIES aliases first, then falls back to dynamic lookup.
    Returns the canonical city name to use as the lookup key.
    """
    from city_lookup import get_city_data

    t = text.lower().strip()

    # Check config aliases with word-boundary matching
    for city_name, city_data in config.CITIES.items():
        for alias in city_data["aliases"]:
            if alias == t or re.search(r"\b" + re.escape(alias) + r"\b", t):
                return city_name

    # Fall back to dynamic geocoding for unknown cities
    # Use the raw text as the city name (it comes from Polymarket's event title)
    city_data = get_city_data(text.strip())
    if city_data:
        return text.strip()  # use the Polymarket name as the key

    return None


def _parse_end_date(question: str) -> str:
    m = _DATE_RE.search(question)
    if not m:
        return ""
    raw = m.group(1).strip()
    for fmt in ("%B %d, %Y", "%B %d %Y", "%b %d, %Y", "%b %d %Y", "%B %d", "%b %d"):
        try:
            d = datetime.strptime(raw, fmt)
            year = d.year if d.year > 2000 else date.today().year
            return date(year, d.month, d.day).isoformat() + "T00:00:00Z"
        except ValueError:
            continue
    return ""


def _parse_prices(market: dict) -> tuple[Optional[float], Optional[float]]:
    outcomes = market.get("outcomes", "[]")
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except Exception:
            outcomes = []
    prices = market.get("outcomePrices", "[]")
    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except Exception:
            prices = []

    yes_price = no_price = None
    if isinstance(outcomes, list) and isinstance(prices, list):
        for i, o in enumerate(outcomes):
            s = str(o).upper()
            if s == "YES" and i < len(prices):
                try:
                    yes_price = float(prices[i])
                except Exception:
                    pass
            elif s == "NO" and i < len(prices):
                try:
                    no_price = float(prices[i])
                except Exception:
                    pass
    return yes_price, no_price


def _parse_token_ids(market: dict) -> tuple:
    clob = market.get("clobTokenIds", [])
    if isinstance(clob, str):
        try:
            clob = json.loads(clob)
        except Exception:
            clob = []
    return (clob[0] if len(clob) > 0 else None,
            clob[1] if len(clob) > 1 else None)


def _fetch_events(offset: int = 0) -> list:
    try:
        r = requests.get(EVENTS_URL, params={
            "active": "true", "closed": "false",
            "limit": 100, "offset": offset,
            "order": "startDate", "ascending": "false",
        }, timeout=20)
        r.raise_for_status()
        data = r.json()
        return data if isinstance(data, list) else data.get("data", [])
    except Exception as e:
        bot_logger.error(f"Events API fetch failed (offset={offset}): {e}")
        return []


def get_weather_markets() -> list[dict]:
    """Fetch and parse all active temperature markets from Polymarket events."""
    results = []
    offset = 0

    while offset < 3000:
        batch = _fetch_events(offset=offset)
        if not batch:
            break

        for event in batch:
            title = event.get("title", "") or ""
            m = _EVENT_TITLE_RE.search(title)
            if not m:
                continue

            city_raw = m.group(1).strip()
            city = _match_city(city_raw)
            if city is None:
                bot_logger.debug(f"scanner: no config match for city '{city_raw}'")
                continue

            nested_markets = event.get("markets", [])
            if not nested_markets:
                continue

            for mkt in nested_markets:
                question = mkt.get("question", "")
                qm = _MARKET_Q_RE.search(question)
                if not qm:
                    continue

                threshold_c = float(qm.group(1))
                bracket     = (qm.group(2) or "").lower().strip()
                threshold_f = _celsius_to_f(threshold_c)

                if bracket == "or above":
                    yes_if = "above"
                elif bracket == "or below":
                    yes_if = "below"
                else:
                    # Exact bucket: P(X-0.5°C < temp ≤ X+0.5°C)
                    yes_price_raw, _ = _parse_prices(mkt)
                    if yes_price_raw is None or yes_price_raw < 0.02 or yes_price_raw > 0.98:
                        continue
                    yes_if = "exact"
                    threshold_f = _celsius_to_f(threshold_c - 0.5)   # lower bound

                yes_price, no_price = _parse_prices(mkt)
                if yes_price is None:
                    continue

                liquidity = float(mkt.get("liquidity", 0) or 0)
                if liquidity < config.MIN_MARKET_LIQUIDITY:
                    continue

                end_date = mkt.get("endDate", "") or _parse_end_date(question)
                token_yes, token_no = _parse_token_ids(mkt)

                # Upper bound for exact bucket markets
                threshold_f_upper = _celsius_to_f(threshold_c + 0.5) if yes_if == "exact" else None

                results.append({
                    "id":              mkt.get("id", ""),
                    "condition_id":    mkt.get("conditionId", ""),
                    "question":        question,
                    "city":            city,
                    "threshold_f":     round(threshold_f, 2),
                    "threshold_f_upper": threshold_f_upper,
                    "threshold_c":     threshold_c,
                    "yes_if":          yes_if,
                    "yes_price":    yes_price,
                    "no_price":     no_price if no_price is not None else round(1 - yes_price, 4),
                    "liquidity":    liquidity,
                    "volume_24h":   float(mkt.get("volume24hr", 0) or 0),
                    "end_date":     end_date,
                    "token_id_yes": token_yes,
                    "token_id_no":  token_no,
                })

        if len(batch) < 100:
            break
        offset += 100

    city_counts = {}
    for r in results:
        city_counts[r["city"]] = city_counts.get(r["city"], 0) + 1

    bot_logger.info(
        f"Scanner found {len(results)} weather markets across "
        f"{len(city_counts)} cities: "
        + ", ".join(f"{c}({n})" for c, n in sorted(city_counts.items()))
    )
    return results
