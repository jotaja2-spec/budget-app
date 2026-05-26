"""
Compares forecast probability to market price and outputs trading signals.

Signal:
  direction: "YES" or "NO"
  edge: forecast_prob - market_price  (positive = forecast says YES is underpriced)
  forecast_prob: probability from ensemble
  market_price: current YES price on Polymarket
"""

from datetime import date
from typing import Optional

import config
from forecast import get_forecast_probability
from logger import log_scan, log_signal, bot_logger


def _parse_market_date(end_date_str: str) -> Optional[date]:
    """Try several date formats used by Polymarket."""
    if not end_date_str:
        return None
    formats = ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%d"]
    for fmt in formats:
        try:
            return date.fromisoformat(end_date_str[:10])
        except ValueError:
            continue
    return None


def evaluate_market(market: dict) -> Optional[dict]:
    """
    Returns a signal dict if the market has a tradeable edge, else None.

    Signal keys: market, direction, side_token_id, trade_price,
                 edge, forecast_prob, market_price, size_hint_usd
    """
    city = market["city"]
    threshold_f = market["threshold_f"]
    yes_if = market["yes_if"]
    yes_price = market["yes_price"]
    no_price = market["no_price"]
    liquidity = market["liquidity"]

    if liquidity < config.MIN_MARKET_LIQUIDITY:
        bot_logger.debug(
            f"SKIP {market['id']} — liquidity ${liquidity:.0f} < ${config.MIN_MARKET_LIQUIDITY:.0f}"
        )
        return None

    target_date = _parse_market_date(market.get("end_date", ""))
    if target_date is None:
        bot_logger.debug(f"SKIP {market['id']} — could not parse end_date '{market.get('end_date')}'")
        return None

    forecast_prob = get_forecast_probability(city, target_date, threshold_f, yes_if)
    if forecast_prob is None:
        return None

    # Edge is defined relative to YES:
    #   positive edge → YES is underpriced → buy YES
    #   negative edge → NO is underpriced (YES is overpriced) → buy NO
    edge = forecast_prob - yes_price

    log_scan(city, market["id"], yes_price, forecast_prob, edge)

    abs_edge = abs(edge)
    if abs_edge < config.EDGE_THRESHOLD:
        return None

    if edge > 0:
        # Buy YES
        direction = "YES"
        trade_price = yes_price
        side_token_id = market.get("token_id_yes")
    else:
        # Buy NO (equivalent to shorting YES)
        direction = "NO"
        trade_price = no_price
        side_token_id = market.get("token_id_no")
        edge = abs_edge  # normalize to positive for downstream sizing

    log_signal(city, market["id"], direction, edge, 0)  # size filled in by sizing.py

    return {
        "market": market,
        "direction": direction,
        "side_token_id": side_token_id,
        "trade_price": trade_price,
        "edge": edge,
        "forecast_prob": forecast_prob,
        "market_price": yes_price,
    }


def generate_signals(markets: list[dict]) -> list[dict]:
    """Evaluate all markets and return signals sorted by edge descending."""
    signals = []
    for m in markets:
        sig = evaluate_market(m)
        if sig:
            signals.append(sig)
    signals.sort(key=lambda s: s["edge"], reverse=True)
    return signals
