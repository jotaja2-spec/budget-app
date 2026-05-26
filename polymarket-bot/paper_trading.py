"""
Paper trading engine: simulates order fills and tracks theoretical P&L
without touching real money.

State is persisted in paper_state.json so it survives restarts.
"""

import json
import os
from datetime import datetime

from logger import log_trade, bot_logger

STATE_FILE = os.path.join(os.path.dirname(__file__), "paper_state.json")


def _load_state(starting_bankroll: float) -> dict:
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "bankroll": starting_bankroll,
        "starting_bankroll": starting_bankroll,
        "open_positions": [],
        "closed_positions": [],
        "total_trades": 0,
        "realized_pnl": 0.0,
    }


def _save_state(state: dict):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        bot_logger.error(f"paper_trading: failed to save state: {e}")


class PaperTrader:
    def __init__(self, starting_bankroll: float):
        self._state = _load_state(starting_bankroll)

    @property
    def bankroll(self) -> float:
        return self._state["bankroll"]

    @property
    def open_positions(self) -> list:
        return self._state["open_positions"]

    @property
    def open_position_count(self) -> int:
        return len(self._state["open_positions"])

    @property
    def total_trades(self) -> int:
        return self._state["total_trades"]

    @property
    def realized_pnl(self) -> float:
        return self._state["realized_pnl"]

    def place_order(self, signal: dict, size_usd: float) -> dict:
        """Simulate placing an order. Returns a position record."""
        market = signal["market"]
        pos = {
            "id": f"paper_{self._state['total_trades'] + 1:04d}",
            "market_id": market["id"],
            "question": market["question"],
            "city": market["city"],
            "direction": signal["direction"],
            "price": signal["trade_price"],
            "size_usd": size_usd,
            "shares": round(size_usd / signal["trade_price"], 4),
            "edge_at_entry": signal["edge"],
            "forecast_prob": signal["forecast_prob"],
            "opened_at": datetime.utcnow().isoformat() + "Z",
            "end_date": market.get("end_date", ""),
            "status": "open",
        }

        self._state["open_positions"].append(pos)
        self._state["bankroll"] -= size_usd
        self._state["total_trades"] += 1
        _save_state(self._state)

        log_trade(
            mode="PAPER",
            city=market["city"],
            market_id=market["id"],
            direction=signal["direction"],
            price=signal["trade_price"],
            size_usd=size_usd,
            edge=signal["edge"],
            reason=f"forecast={signal['forecast_prob']:.3f} vs market={signal['market_price']:.3f}",
        )

        return pos

    def settle_position(self, position_id: str, outcome: str):
        """
        Call when a market resolves. outcome: 'YES' or 'NO'.
        Calculates P&L and moves position to closed.
        """
        pos = next((p for p in self._state["open_positions"] if p["id"] == position_id), None)
        if not pos:
            bot_logger.warning(f"paper_trading: position {position_id} not found")
            return

        won = pos["direction"] == outcome
        if won:
            # Each share pays $1 on resolution; profit = shares - cost
            pnl = pos["shares"] - pos["size_usd"]
        else:
            pnl = -pos["size_usd"]

        pos["pnl"] = round(pnl, 4)
        pos["settled_at"] = datetime.utcnow().isoformat() + "Z"
        pos["outcome"] = outcome
        pos["status"] = "closed"

        self._state["realized_pnl"] += pnl
        self._state["bankroll"] += pos["size_usd"] + pnl  # return cost + profit/loss
        self._state["open_positions"] = [p for p in self._state["open_positions"] if p["id"] != position_id]
        self._state["closed_positions"].append(pos)

        _save_state(self._state)
        bot_logger.info(
            f"Paper position {position_id} settled: outcome={outcome} pnl=${pnl:+.2f}"
        )

    def already_in_market(self, market_id: str) -> bool:
        return any(p["market_id"] == market_id for p in self._state["open_positions"])

    def status_summary(self) -> dict:
        return {
            "bankroll": round(self.bankroll, 2),
            "starting_bankroll": self._state["starting_bankroll"],
            "net_pnl": round(self.bankroll - self._state["starting_bankroll"], 2),
            "realized_pnl": round(self.realized_pnl, 2),
            "open_positions": self.open_position_count,
            "total_trades": self.total_trades,
        }
