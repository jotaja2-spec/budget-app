"""
Checks Polymarket Gamma API to see if open paper positions have resolved.
When a market closes, reads the winning outcome and settles the position.
"""

import json
import requests
from typing import Optional

import config
from logger import bot_logger

GAMMA_MARKETS = f"{config.GAMMA_API_URL}/markets"


def _fetch_market(market_id: str) -> Optional[dict]:
    """Fetch a single market by ID from Gamma API."""
    try:
        r = requests.get(GAMMA_MARKETS, params={"id": market_id}, timeout=10)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, list):
            return data[0] if data else None
        if isinstance(data, dict):
            items = data.get("data", [])
            return items[0] if items else None
    except Exception as e:
        bot_logger.debug(f"settler: fetch failed for {market_id}: {e}")
    return None


def _parse_outcome(market: dict) -> Optional[str]:
    """
    Returns 'YES' or 'NO' if the market has resolved, else None.
    Determined by whichever outcome price is 1.0 (the winner).
    """
    # Market must be closed or archived to be resolved
    if not market.get("closed") and not market.get("archived"):
        return None

    outcomes = market.get("outcomes", "[]")
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except Exception:
            return None

    prices = market.get("outcomePrices", "[]")
    if isinstance(prices, str):
        try:
            prices = json.loads(prices)
        except Exception:
            return None

    if not isinstance(outcomes, list) or not isinstance(prices, list):
        return None

    for i, outcome in enumerate(outcomes):
        if i < len(prices):
            try:
                if float(prices[i]) >= 0.99:
                    return str(outcome).upper()
            except Exception:
                pass

    return None


def check_and_settle(paper_trader) -> int:
    """
    Check all open positions for resolution. Settle any that have closed.
    Returns the number of positions settled this call.
    """
    settled = 0
    for pos in list(paper_trader.open_positions):
        market_id = pos.get("market_id")
        if not market_id:
            continue

        market = _fetch_market(market_id)
        if not market:
            continue

        outcome = _parse_outcome(market)
        if not outcome:
            continue

        won = pos["direction"] == outcome
        pnl_est = pos["shares"] - pos["size_usd"] if won else -pos["size_usd"]

        bot_logger.info(
            f"Settlement: {pos['id']} | {pos['city']} | "
            f"Bet={pos['direction']} Outcome={outcome} | "
            f"{'WIN' if won else 'LOSS'} ${pnl_est:+.2f}"
        )

        paper_trader.settle_position(pos["id"], outcome)
        settled += 1

    if settled:
        bot_logger.info(f"Settled {settled} position(s) this cycle")

    return settled
