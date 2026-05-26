"""
Polls the Polymarket Gamma API for open temperature/weather markets
matching the configured target cities.

Each returned market dict contains:
  id, question, city, threshold_f, direction, yes_price, no_price,
  liquidity, end_date, condition_id, token_id_yes, token_id_no
"""

import re
import requests
from datetime import datetime, date
from typing import Optional

import config
from logger import bot_logger

# Keywords that flag a market as weather-related
WEATHER_KEYWORDS = re.compile(
    r"\b(temperature|temp|high|low|degrees|fahrenheit|celsius|°f|°c|weather)\b",
    re.IGNORECASE,
)

# Parses questions like:
#   "Will the high temperature in New York exceed 85°F on July 4?"
#   "Will Chicago temperature be above 90°F on 2025-07-04?"
#   "Will the low temperature in Miami be below 60°F?"
_QUESTION_RE = re.compile(
    r"(?P<direction>above|below|exceed|over|under|at least|at most)"
    r"\s+(?P<threshold>[\d.]+)\s*°?\s*(?P<unit>[FC])",
    re.IGNORECASE,
)

_DATE_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
    r"\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s*\d{4})?)\b",
    re.IGNORECASE,
)


def _celsius_to_f(c: float) -> float:
    return c * 9 / 5 + 32


def _parse_question(question: str) -> Optional[dict]:
    """Extract threshold_f, direction ('YES_above'/'YES_below') from question text."""
    m = _QUESTION_RE.search(question)
    if not m:
        return None

    threshold = float(m.group("threshold"))
    unit = m.group("unit").upper()
    direction_word = m.group("direction").lower()

    if unit == "C":
        threshold = _celsius_to_f(threshold)

    # Normalize direction: does "YES" resolve if temp is ABOVE or BELOW threshold?
    above_words = {"above", "exceed", "over", "at least"}
    direction = "above" if direction_word in above_words else "below"

    return {"threshold_f": threshold, "yes_if": direction}


def _match_city(question: str) -> Optional[str]:
    q = question.lower()
    for city_name, city_data in config.CITIES.items():
        for alias in city_data["aliases"]:
            if alias in q:
                return city_name
    return None


def _fetch_markets(offset: int = 0, limit: int = 500) -> list:
    url = f"{config.GAMMA_API_URL}/markets"
    params = {
        "active": "true",
        "closed": "false",
        "limit": limit,
        "offset": offset,
        "order": "volume24hr",
        "ascending": "false",
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # Gamma API returns list or {"data": [...], "count": N}
        if isinstance(data, list):
            return data
        return data.get("data", [])
    except Exception as e:
        bot_logger.error(f"Gamma API fetch failed (offset={offset}): {e}")
        return []


def get_weather_markets() -> list[dict]:
    """Return parsed weather markets for configured cities."""
    raw_markets = []
    offset = 0

    # Fetch up to 2000 markets to find weather ones (they're a small subset)
    while offset < 2000:
        batch = _fetch_markets(offset=offset)
        if not batch:
            break
        raw_markets.extend(batch)
        if len(batch) < 500:
            break
        offset += 500

    results = []
    for m in raw_markets:
        question = m.get("question", "")
        if not question:
            continue
        if not WEATHER_KEYWORDS.search(question):
            continue

        city = _match_city(question)
        if city is None:
            continue

        parsed = _parse_question(question)
        if parsed is None:
            continue

        # Price for YES outcome (Polymarket prices are 0–1 representing probability)
        outcomes = m.get("outcomes", "[]")
        if isinstance(outcomes, str):
            import json
            try:
                outcomes = json.loads(outcomes)
            except Exception:
                outcomes = []

        outcome_prices = m.get("outcomePrices", "[]")
        if isinstance(outcome_prices, str):
            import json
            try:
                outcome_prices = json.loads(outcome_prices)
            except Exception:
                outcome_prices = []

        yes_price = no_price = None
        if isinstance(outcomes, list) and isinstance(outcome_prices, list):
            for i, o in enumerate(outcomes):
                if str(o).upper() == "YES" and i < len(outcome_prices):
                    try:
                        yes_price = float(outcome_prices[i])
                    except (ValueError, TypeError):
                        pass
                elif str(o).upper() == "NO" and i < len(outcome_prices):
                    try:
                        no_price = float(outcome_prices[i])
                    except (ValueError, TypeError):
                        pass

        if yes_price is None:
            continue

        liquidity = float(m.get("liquidity", 0) or 0)

        # Token IDs for CLOB orders (clobTokenIds field)
        clob_token_ids = m.get("clobTokenIds", [])
        if isinstance(clob_token_ids, str):
            import json
            try:
                clob_token_ids = json.loads(clob_token_ids)
            except Exception:
                clob_token_ids = []

        token_id_yes = clob_token_ids[0] if len(clob_token_ids) > 0 else None
        token_id_no = clob_token_ids[1] if len(clob_token_ids) > 1 else None

        results.append(
            {
                "id": m.get("id", ""),
                "condition_id": m.get("conditionId", ""),
                "question": question,
                "city": city,
                "threshold_f": parsed["threshold_f"],
                "yes_if": parsed["yes_if"],  # "above" or "below"
                "yes_price": yes_price,
                "no_price": no_price if no_price is not None else round(1 - yes_price, 4),
                "liquidity": liquidity,
                "volume_24h": float(m.get("volume24hr", 0) or 0),
                "end_date": m.get("endDate", ""),
                "token_id_yes": token_id_yes,
                "token_id_no": token_id_no,
            }
        )

    bot_logger.info(f"Scanner found {len(results)} weather markets across target cities")
    return results
