import logging
import os
from logging.handlers import RotatingFileHandler
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "bot.log")
TRADE_LOG_FILE = os.path.join(LOG_DIR, "trades.log")


def _make_logger(name: str, log_file: str, level=logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        return logger

    fmt = logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Rotating file: 5 MB max, keep 5 backups
    fh = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=5)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    return logger


bot_logger = _make_logger("bot", LOG_FILE)
trade_logger = _make_logger("trades", TRADE_LOG_FILE)


def log_scan(city: str, market_id: str, market_price: float, forecast_prob: float, edge: float):
    bot_logger.info(
        f"SCAN | city={city} market={market_id} "
        f"market_price={market_price:.3f} forecast={forecast_prob:.3f} edge={edge:+.3f}"
    )


def log_signal(city: str, market_id: str, direction: str, edge: float, size_usd: float):
    bot_logger.info(
        f"SIGNAL | city={city} market={market_id} "
        f"direction={direction} edge={edge:+.3f} size=${size_usd:.2f}"
    )


def log_trade(
    mode: str,
    city: str,
    market_id: str,
    direction: str,
    price: float,
    size_usd: float,
    edge: float,
    reason: str,
):
    trade_logger.info(
        f"TRADE | mode={mode} city={city} market={market_id} "
        f"direction={direction} price={price:.3f} size=${size_usd:.2f} "
        f"edge={edge:+.3f} | {reason}"
    )


def log_risk_halt(reason: str):
    bot_logger.warning(f"RISK HALT | {reason}")


def log_error(msg: str, exc: Exception = None):
    if exc:
        bot_logger.error(f"{msg} | {type(exc).__name__}: {exc}")
    else:
        bot_logger.error(msg)
