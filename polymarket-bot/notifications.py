from datetime import datetime
import requests
import config
from logger import bot_logger

QUIET_START = 20  # 8pm
QUIET_END   = 7   # 7am


def _pushover_enabled() -> bool:
    return bool(config.PUSHOVER_API_TOKEN and config.PUSHOVER_USER_KEY)


def _in_quiet_hours() -> bool:
    hour = datetime.now().hour
    return hour >= QUIET_START or hour < QUIET_END


def send_notification(title: str, message: str, priority: int = 0) -> bool:
    """
    priority: -1=low, 0=normal, 1=high, 2=emergency (emergency requires retry/expire params)
    Returns True on success.
    """
    if not _pushover_enabled():
        return False
    if _in_quiet_hours():
        bot_logger.debug(f"Notification suppressed (quiet hours 8pm–7am): {title}")
        return False

    payload = {
        "token": config.PUSHOVER_API_TOKEN,
        "user": config.PUSHOVER_USER_KEY,
        "title": title,
        "message": message,
        "priority": priority,
    }
    if priority == 2:
        payload["retry"] = 60
        payload["expire"] = 3600

    try:
        resp = requests.post(config.PUSHOVER_API_URL, data=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        bot_logger.warning(f"Pushover notification failed: {e}")
        return False


def notify_trade(city: str, direction: str, price: float, size_usd: float, edge: float, paper: bool):
    mode = "PAPER" if paper else "LIVE"
    title = f"[{mode}] Trade: {city}"
    msg = (
        f"Direction: {direction}\n"
        f"Price: {price:.3f}\n"
        f"Size: ${size_usd:.2f}\n"
        f"Edge: {edge*100:+.1f}%"
    )
    send_notification(title, msg)


def notify_daily_loss_limit(bankroll: float, loss: float, limit: float):
    title = "Bot Halted — Daily Loss Limit Hit"
    msg = (
        f"Loss today: ${loss:.2f}\n"
        f"Limit: ${limit:.2f}\n"
        f"Current bankroll: ${bankroll:.2f}\n"
        f"No more trades until tomorrow."
    )
    send_notification(title, msg, priority=1)


def notify_startup(paper: bool, bankroll: float):
    mode = "PAPER TRADING" if paper else "LIVE TRADING"
    title = f"Bot Started — {mode}"
    msg = f"Bankroll: ${bankroll:.2f}\nScanning every 5 minutes."
    send_notification(title, msg)
