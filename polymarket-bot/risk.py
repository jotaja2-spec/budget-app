"""
Risk manager: tracks daily P&L, enforces loss limits, and counts open positions.

State is persisted in risk_state.json so it survives restarts within the same day.
"""

import json
import os
from datetime import date

import config
from logger import log_risk_halt, bot_logger

STATE_FILE = os.path.join(os.path.dirname(__file__), "risk_state.json")


def _load_state() -> dict:
    today = date.today().isoformat()
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
            if state.get("date") == today:
                return state
        except Exception:
            pass
    return {"date": today, "daily_pnl": 0.0, "halted": False}


def _save_state(state: dict):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        bot_logger.error(f"risk: failed to save state: {e}")


class RiskManager:
    def __init__(self, bankroll: float):
        self.bankroll = bankroll
        self._state = _load_state()

    @property
    def daily_loss_limit(self) -> float:
        return self.bankroll * config.DAILY_LOSS_LIMIT_PCT

    @property
    def daily_pnl(self) -> float:
        return self._state["daily_pnl"]

    @property
    def is_halted(self) -> bool:
        return self._state["halted"]

    def can_trade(self, open_positions: int) -> tuple[bool, str]:
        """Returns (allowed, reason_if_denied)."""
        if self.is_halted:
            return False, "daily loss limit already hit — halted for today"
        daily_loss = -min(self.daily_pnl, 0)
        if daily_loss >= self.daily_loss_limit:
            self._halt("daily loss limit reached")
            return False, f"daily loss ${daily_loss:.2f} >= limit ${self.daily_loss_limit:.2f}"
        if open_positions >= config.MAX_OPEN_POSITIONS:
            return False, f"max open positions ({config.MAX_OPEN_POSITIONS}) reached"
        return True, ""

    def record_trade(self, size_usd: float):
        """Call when a trade is placed (deduct from bankroll immediately)."""
        # We don't know P&L until settlement; track cost as unrealized loss.
        # Actual P&L is recorded via record_settlement().
        pass

    def record_settlement(self, pnl: float):
        """Call when a position settles with realized P&L."""
        self._state["daily_pnl"] += pnl
        if self._state["daily_pnl"] < -self.daily_loss_limit:
            self._halt(
                f"realized P&L ${self._state['daily_pnl']:.2f} "
                f"exceeded limit ${-self.daily_loss_limit:.2f}"
            )
        _save_state(self._state)

    def _halt(self, reason: str):
        self._state["halted"] = True
        _save_state(self._state)
        log_risk_halt(reason)

    def reset_for_new_day(self):
        today = date.today().isoformat()
        if self._state.get("date") != today:
            self._state = {"date": today, "daily_pnl": 0.0, "halted": False}
            _save_state(self._state)
            bot_logger.info("Risk manager: new trading day, state reset")
