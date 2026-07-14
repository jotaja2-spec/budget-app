"""
Generates trading signals for economic markets by comparing
external probability estimates against Polymarket prices.

Mirrors the pattern of signals.py for weather markets.
"""

from typing import Optional

import config
from economic_data import (
    get_fed_probability,
    get_cpi_probability,
    get_unemployment_probability,
    get_gdp_probability,
)
from logger import bot_logger


def _get_probability(market: dict) -> Optional[float]:
    """Route to the correct data source based on market type."""
    mtype     = market["market_type"]
    question  = market["question"]
    threshold = market.get("threshold")
    direction = market.get("direction")
    days      = market.get("days_until", 30)

    if mtype == "fed":
        return get_fed_probability(question)

    if threshold is None or direction is None:
        bot_logger.debug(f"SKIP econ {market['id']} — no threshold parsed from question")
        return None

    if mtype == "cpi":
        return get_cpi_probability(threshold, direction, days_until_release=days)

    if mtype == "unemployment":
        return get_unemployment_probability(threshold, direction, days_until_release=days)

    if mtype == "gdp":
        return get_gdp_probability(threshold, direction, days_until_release=days)

    return None


def evaluate_economic_market(market: dict) -> Optional[dict]:
    """
    Returns a signal dict if the market has a tradeable edge, else None.
    Signal format is identical to weather signals for compatibility with
    the existing executor, sizing, and paper_trading modules.
    """
    yes_price = market["yes_price"]
    no_price  = market["no_price"]

    forecast_prob = _get_probability(market)
    if forecast_prob is None:
        return None

    edge = forecast_prob - yes_price

    abs_edge = abs(edge)
    if abs_edge < config.EDGE_THRESHOLD:
        bot_logger.debug(
            f"SKIP econ {market['id']} — edge {abs_edge:.3f} < threshold {config.EDGE_THRESHOLD}"
        )
        return None

    if edge > 0:
        direction     = "YES"
        trade_price   = yes_price
        side_token_id = market.get("token_id_yes")
    else:
        direction     = "NO"
        trade_price   = no_price
        side_token_id = market.get("token_id_no")
        edge = abs_edge

    bot_logger.info(
        f"ECON SIGNAL {market['market_type'].upper()} | {direction} | "
        f"edge={edge:.3f} | forecast={forecast_prob:.3f} | market={yes_price:.3f} | "
        f"q={market['question'][:80]}"
    )

    return {
        "market":       market,
        "direction":    direction,
        "side_token_id": side_token_id,
        "trade_price":  trade_price,
        "edge":         edge,
        "forecast_prob": forecast_prob,
        "market_price": yes_price,
        "signal_type":  "economic",
    }


def generate_economic_signals(markets: list[dict]) -> list[dict]:
    """Evaluate all economic markets and return signals sorted by edge."""
    signals = []
    for m in markets:
        sig = evaluate_economic_market(m)
        if sig:
            signals.append(sig)
    signals.sort(key=lambda s: s["edge"], reverse=True)
    return signals
