"""
Polymarket Weather Bot — main entry point.

Run with:   python main.py
Background: pythonw main.py   (Windows, no terminal window)
"""

import os
import time
import sys
import signal
from datetime import datetime

import psutil

import config
from logger import bot_logger, log_error

BASE = os.path.dirname(__file__)
PID_FILE = os.path.join(BASE, "bot.pid")

# CPU thresholds
CPU_WARN_PCT = 60
CPU_THROTTLE_PCT = 80


def _write_pid():
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def _remove_pid():
    try:
        os.remove(PID_FILE)
    except FileNotFoundError:
        pass


def _cpu_check() -> bool:
    """
    Returns True if safe to scan.
    At 60–80% CPU logs a warning but proceeds.
    Above 80% skips the scan entirely for one cycle.
    """
    usage = psutil.cpu_percent(interval=1)
    if usage >= CPU_THROTTLE_PCT:
        bot_logger.warning(
            f"CPU at {usage:.0f}% — skipping scan to avoid overloading system "
            f"(threshold: {CPU_THROTTLE_PCT}%)"
        )
        return False
    if usage >= CPU_WARN_PCT:
        bot_logger.warning(f"CPU at {usage:.0f}% — proceeding but load is elevated")
    return True
from scanner import get_weather_markets
from signals import generate_signals
from sizing import kelly_size
from risk import RiskManager
from paper_trading import PaperTrader
from notifications import notify_startup, notify_trade, notify_daily_loss_limit

if not config.PAPER_TRADING:
    from executor import place_live_order, get_live_positions


def print_status(paper_trader: PaperTrader, risk: RiskManager):
    summary = paper_trader.status_summary() if config.PAPER_TRADING else {}
    mode = "PAPER" if config.PAPER_TRADING else "LIVE"
    line = (
        f"\n{'='*60}\n"
        f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Mode: {mode}\n"
    )
    if config.PAPER_TRADING:
        line += (
            f"  Bankroll:      ${summary['bankroll']:.2f}  "
            f"(started ${summary['starting_bankroll']:.2f})\n"
            f"  Net P&L:       ${summary['net_pnl']:+.2f}\n"
            f"  Open positions:{summary['open_positions']}\n"
            f"  Trades today:  {summary['total_trades']}\n"
        )
    line += (
        f"  Daily P&L:     ${risk.daily_pnl:+.2f}  "
        f"(limit: -${risk.daily_loss_limit:.2f})\n"
        f"  Halted:        {'YES ⚠' if risk.is_halted else 'No'}\n"
        f"{'='*60}\n"
    )
    print(line, flush=True)


def run_scan_cycle(paper_trader: PaperTrader, risk: RiskManager):
    if not _cpu_check():
        return

    risk.reset_for_new_day()

    if risk.is_halted:
        bot_logger.info("Daily loss limit hit — skipping scan cycle")
        return

    # Determine open position count
    open_count = paper_trader.open_position_count if config.PAPER_TRADING else len(get_live_positions())

    allowed, reason = risk.can_trade(open_count)
    if not allowed:
        bot_logger.info(f"No trading: {reason}")
        return

    markets = get_weather_markets()
    if not markets:
        bot_logger.info("No weather markets found this scan")
        return

    signals = generate_signals(markets)
    if not signals:
        bot_logger.info("No signals above edge threshold this scan")
        return

    bot_logger.info(f"{len(signals)} signal(s) found — evaluating top opportunities")

    for sig in signals:
        # Re-check capacity before each trade
        open_count = paper_trader.open_position_count if config.PAPER_TRADING else len(get_live_positions())
        allowed, reason = risk.can_trade(open_count)
        if not allowed:
            bot_logger.info(f"Stopping signal processing: {reason}")
            break

        market = sig["market"]

        # Don't double-enter the same market
        if config.PAPER_TRADING and paper_trader.already_in_market(market["id"]):
            bot_logger.debug(f"Already in market {market['id']}, skipping")
            continue

        bankroll = paper_trader.bankroll if config.PAPER_TRADING else config.STARTING_BANKROLL
        size_usd = kelly_size(sig["forecast_prob"], sig["trade_price"], bankroll)

        if size_usd <= 0:
            bot_logger.debug(f"Kelly size=0 for {market['id']}, skipping")
            continue

        if config.PAPER_TRADING:
            paper_trader.place_order(sig, size_usd)
            notify_trade(
                city=market["city"],
                direction=sig["direction"],
                price=sig["trade_price"],
                size_usd=size_usd,
                edge=sig["edge"],
                paper=True,
            )
        else:
            result = place_live_order(sig, size_usd)
            if result:
                notify_trade(
                    city=market["city"],
                    direction=sig["direction"],
                    price=sig["trade_price"],
                    size_usd=size_usd,
                    edge=sig["edge"],
                    paper=False,
                )
            else:
                bot_logger.warning(f"Live order failed for {market['id']}")


def _shutdown(signum=None, frame=None):
    bot_logger.info("Bot shutting down")
    _remove_pid()
    sys.exit(0)


def main():
    _write_pid()
    signal.signal(signal.SIGTERM, _shutdown)

    mode = "PAPER TRADING" if config.PAPER_TRADING else "LIVE TRADING"
    cpu_now = psutil.cpu_percent(interval=1)
    bot_logger.info(
        f"Bot starting — {mode} | bankroll=${config.STARTING_BANKROLL:.2f} | "
        f"CPU at start: {cpu_now:.0f}%"
    )

    paper_trader = PaperTrader(config.STARTING_BANKROLL)
    risk = RiskManager(
        bankroll=paper_trader.bankroll if config.PAPER_TRADING else config.STARTING_BANKROLL
    )

    notify_startup(config.PAPER_TRADING, config.STARTING_BANKROLL)
    print_status(paper_trader, risk)

    scan_num = 0
    try:
        while True:
            scan_num += 1
            bot_logger.info(f"--- Scan #{scan_num} | CPU {psutil.cpu_percent():.0f}% ---")

            try:
                run_scan_cycle(paper_trader, risk)
            except Exception as e:
                log_error("Unhandled error in scan cycle", e)

            print_status(paper_trader, risk)

            bot_logger.info(f"Sleeping {config.SCAN_INTERVAL_SECONDS}s until next scan...")
            time.sleep(config.SCAN_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        bot_logger.info("Bot stopped")
        _remove_pid()
        print("\nBot stopped.")


if __name__ == "__main__":
    main()
