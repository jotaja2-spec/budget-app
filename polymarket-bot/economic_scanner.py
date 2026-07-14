"""
Scans Polymarket Gamma API for economic markets:
CPI/inflation, Fed rate decisions, unemployment, GDP.

Returns parsed market dicts ready for signal evaluation.
"""

import json
import re
import requests
from datetime import date, datetime
from typing import Optional

import config
from logger import bot_logger

# Markets containing these keywords are candidates
ECON_KEYWORDS = re.compile(
    r"\b(cpi|consumer price index|inflation|federal reserve|fed rate|fomc|"
    r"interest rate|rate cut|rate hike|rate hold|basis point|"
    r"unemployment|jobless|jobs report|nonfarm payroll|nfp|"
    r"gdp|gross domestic product)\b",
    re.IGNORECASE,
)

# Market type classifiers
_FED_RE    = re.compile(r"\b(fed|fomc|federal reserve|interest rate|rate cut|rate hike|rate hold|basis point)\b", re.IGNORECASE)
_CPI_RE    = re.compile(r"\b(cpi|consumer price|inflation)\b", re.IGNORECASE)
_UNEMPLOY_RE = re.compile(r"\b(unemployment|jobless|nonfarm|payroll|nfp)\b", re.IGNORECASE)
_GDP_RE    = re.compile(r"\b(gdp|gross domestic)\b", re.IGNORECASE)

# Threshold extraction: "above 3%", "exceed 4.5%", "below 25 basis points"
_THRESHOLD_RE = re.compile(
    r"(?P<direction>above|below|exceed|over|under|at least|at most|more than|less than)"
    r"\s+(?P<threshold>[\d.]+)\s*(?P<unit>%|basis points?|bps?)?",
    re.IGNORECASE,
)

# Date extraction for resolution proximity
_DATE_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|"
    r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4})\b",
    re.IGNORECASE,
)

_ABOVE_WORDS = {"above", "exceed", "over", "at least", "more than"}


def _classify(question: str) -> Optional[str]:
    if _FED_RE.search(question):    return "fed"
    if _CPI_RE.search(question):    return "cpi"
    if _UNEMPLOY_RE.search(question): return "unemployment"
    if _GDP_RE.search(question):    return "gdp"
    return None


def _parse_threshold(question: str) -> Optional[dict]:
    """Extract numeric threshold and direction from question text."""
    m = _THRESHOLD_RE.search(question)
    if not m:
        return None
    direction_word = m.group("direction").lower()
    threshold = float(m.group("threshold"))
    unit = (m.group("unit") or "").lower()

    # Convert basis points to percent
    if "basis" in unit or "bp" in unit:
        threshold = threshold / 100.0

    direction = "above" if direction_word in _ABOVE_WORDS else "below"
    return {"threshold": threshold, "direction": direction}


def _parse_end_date(end_date_str: str) -> Optional[date]:
    if not end_date_str:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d"):
        try:
            return datetime.strptime(end_date_str[:19], fmt[:len(end_date_str[:19])]).date()
        except Exception:
            continue
    try:
        return date.fromisoformat(end_date_str[:10])
    except Exception:
        return None


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
            if str(o).upper() == "YES" and i < len(prices):
                try:
                    yes_price = float(prices[i])
                except Exception:
                    pass
            elif str(o).upper() == "NO" and i < len(prices):
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


def _fetch_markets(offset: int = 0, limit: int = 500) -> list:
    try:
        resp = requests.get(
            f"{config.GAMMA_API_URL}/markets",
            params={
                "active": "true",
                "closed": "false",
                "limit": limit,
                "offset": offset,
                "order": "volume24hr",
                "ascending": "false",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, list) else data.get("data", [])
    except Exception as e:
        bot_logger.error(f"Economic scanner Gamma fetch failed (offset={offset}): {e}")
        return []


def get_economic_markets() -> list[dict]:
    """Return parsed economic markets ready for signal evaluation."""
    raw = []
    offset = 0
    while offset < 2000:
        batch = _fetch_markets(offset=offset)
        if not batch:
            break
        raw.extend(batch)
        if len(batch) < 500:
            break
        offset += 500

    results = []
    today = date.today()

    for m in raw:
        question = m.get("question", "")
        if not ECON_KEYWORDS.search(question):
            continue

        market_type = _classify(question)
        if not market_type:
            continue

        yes_price, no_price = _parse_prices(m)
        if yes_price is None:
            continue

        liquidity = float(m.get("liquidity", 0) or 0)
        if liquidity < config.MIN_MARKET_LIQUIDITY:
            continue

        end_date = _parse_end_date(m.get("endDate", ""))
        days_until = (end_date - today).days if end_date else 30
        if end_date and days_until < 0:
            continue  # already resolved

        threshold_data = _parse_threshold(question)

        token_yes, token_no = _parse_token_ids(m)

        results.append({
            "id":            m.get("id", ""),
            "condition_id":  m.get("conditionId", ""),
            "question":      question,
            "market_type":   market_type,
            "threshold":     threshold_data["threshold"] if threshold_data else None,
            "direction":     threshold_data["direction"] if threshold_data else None,
            "yes_price":     yes_price,
            "no_price":      no_price if no_price is not None else round(1 - yes_price, 4),
            "liquidity":     liquidity,
            "volume_24h":    float(m.get("volume24hr", 0) or 0),
            "end_date":      m.get("endDate", ""),
            "days_until":    days_until,
            "token_id_yes":  token_yes,
            "token_id_no":   token_no,
        })

    bot_logger.info(f"Economic scanner found {len(results)} markets "
                    f"(Fed: {sum(1 for r in results if r['market_type']=='fed')}, "
                    f"CPI: {sum(1 for r in results if r['market_type']=='cpi')}, "
                    f"Jobs: {sum(1 for r in results if r['market_type']=='unemployment')}, "
                    f"GDP: {sum(1 for r in results if r['market_type']=='gdp')})")
    return results
