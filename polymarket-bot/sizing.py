"""
Half-Kelly position sizing with hard caps.

Kelly formula: f* = (b*p - q) / b
  b = (1/price) - 1   (decimal odds)
  p = forecast probability of winning
  q = 1 - p

We use half-Kelly (f = 0.5 * f*) and cap at:
  - MAX_SINGLE_TRADE_PCT * bankroll
  - MAX_POSITION_SIZE_USD absolute cap
"""

import config


def kelly_size(forecast_prob: float, trade_price: float, bankroll: float) -> float:
    """
    Returns position size in USD. Returns 0 if Kelly is negative (no edge).
    trade_price: the price paid per share (0–1), e.g. 0.45 for a YES at 45¢
    """
    if trade_price <= 0 or trade_price >= 1:
        return 0.0

    b = (1.0 / trade_price) - 1.0  # decimal odds
    p = forecast_prob
    q = 1.0 - p

    kelly_fraction = (b * p - q) / b
    if kelly_fraction <= 0:
        return 0.0

    half_kelly = kelly_fraction * config.KELLY_FRACTION  # 0.5x Kelly

    # Cap 1: percentage of bankroll
    pct_cap = bankroll * config.MAX_SINGLE_TRADE_PCT

    # Cap 2: absolute dollar max
    abs_cap = config.MAX_POSITION_SIZE_USD

    raw_size = half_kelly * bankroll
    size = min(raw_size, pct_cap, abs_cap)

    # Floor at $1 to avoid dust orders
    return max(round(size, 2), 1.0) if size >= 1.0 else 0.0


def shares_from_size(size_usd: float, price: float) -> float:
    """Convert dollar size to number of shares at given price."""
    if price <= 0:
        return 0.0
    return round(size_usd / price, 4)
