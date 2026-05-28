"""
Order executor: places limit orders on the Polymarket CLOB API.
In paper trading mode, delegates to paper_trading.py instead.
"""

from typing import Optional

import config
from logger import log_trade, log_error, bot_logger

# Lazy import so the bot still runs in paper mode without py-clob-client installed
_clob_client = None


def _get_clob_client():
    global _clob_client
    if _clob_client is not None:
        return _clob_client

    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import ApiCreds
    except ImportError:
        raise RuntimeError(
            "py-clob-client is not installed. Run: pip install py-clob-client\n"
            "Or stay in PAPER_TRADING=true mode."
        )

    if not config.POLY_PRIVATE_KEY or config.POLY_PRIVATE_KEY.startswith("0xyour"):
        raise RuntimeError("POLY_PRIVATE_KEY is not set in .env")

    creds = None
    if config.POLY_API_KEY and not config.POLY_API_KEY.startswith("your_"):
        try:
            from py_clob_client.clob_types import ApiCreds
            creds = ApiCreds(
                api_key=config.POLY_API_KEY,
                api_secret=config.POLY_API_SECRET,
                api_passphrase=config.POLY_API_PASSPHRASE,
            )
        except Exception:
            pass

    _clob_client = ClobClient(
        host=config.CLOB_API_URL,
        chain_id=config.POLY_CHAIN_ID,
        key=config.POLY_PRIVATE_KEY,
        creds=creds,
    )

    # Auto-derive L2 credentials if not provided
    if creds is None:
        try:
            derived = _clob_client.create_or_derive_api_creds()
            bot_logger.info("CLOB: derived L2 API credentials")
        except Exception as e:
            bot_logger.warning(f"CLOB: could not derive L2 creds: {e}")

    return _clob_client


def place_live_order(signal: dict, size_usd: float) -> Optional[dict]:
    """
    Places a limit buy order on the CLOB API.
    Returns order response dict on success, None on failure.
    """
    from sizing import shares_from_size

    market = signal["market"]
    token_id = signal["side_token_id"]
    price = signal["trade_price"]
    shares = shares_from_size(size_usd, price)

    if not token_id:
        log_error(f"executor: no token_id for {market['id']} direction={signal['direction']}")
        return None

    if shares < 1:
        bot_logger.warning(f"executor: shares={shares} too small for {market['id']}, skipping")
        return None

    try:
        client = _get_clob_client()
        from py_clob_client.clob_types import OrderArgs, BUY
        from py_clob_client.order_builder.constants import BUY

        order_args = OrderArgs(
            token_id=token_id,
            price=round(price, 4),
            size=round(shares, 2),
            side=BUY,
        )
        resp = client.create_and_post_order(order_args)

        log_trade(
            mode="LIVE",
            city=market["city"],
            market_id=market["id"],
            direction=signal["direction"],
            price=price,
            size_usd=size_usd,
            edge=signal["edge"],
            reason=f"forecast={signal['forecast_prob']:.3f} vs market={signal['market_price']:.3f}",
        )

        bot_logger.info(f"LIVE order placed: {resp}")
        return resp

    except Exception as e:
        log_error(f"executor: order failed for {market['id']}", e)
        return None


def get_live_positions() -> list:
    """Returns list of open orders/positions from CLOB API."""
    try:
        client = _get_clob_client()
        return client.get_orders() or []
    except Exception as e:
        log_error("executor: failed to fetch open positions", e)
        return []
