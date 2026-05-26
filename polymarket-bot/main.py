"""
Polymarket Weather Bot — main entry point.

Run with:   python main.py
Background: pythonw main.py   (Windows, no terminal window)
"""

import time
import sys
from datetime import datetime

import config
from logger import bot_logger, log_error
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


def main():
    mode = "PAPER TRADING" if config.PAPER_TRADING else "LIVE TRADING"
    bot_logger.info(f"Bot starting — {mode} | bankroll=${config.STARTING_BANKROLL:.2f}")

    paper_trader = PaperTrader(config.STARTING_BANKROLL)
    risk = RiskManager(
        bankroll=paper_trader.bankroll if config.PAPER_TRADING else config.STARTING_BANKROLL
    )

    notify_startup(config.PAPER_TRADING, config.STARTING_BANKROLL)
    print_status(paper_trader, risk)

    scan_num = 0
    while True:
        scan_num += 1
        bot_logger.info(f"--- Scan #{scan_num} ---")

        try:
            run_scan_cycle(paper_trader, risk)
        except KeyboardInterrupt:
            bot_logger.info("Bot stopped by user")
            print("\nBot stopped.")
            sys.exit(0)
        except Exception as e:
            log_error("Unhandled error in scan cycle", e)

        print_status(paper_trader, risk)

        bot_logger.info(f"Sleeping {config.SCAN_INTERVAL_SECONDS}s until next scan...")
        try:
            time.sleep(config.SCAN_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            bot_logger.info("Bot stopped by user")
            print("\nBot stopped.")
            sys.exit(0)


if __name__ == "__main__":
    main()
