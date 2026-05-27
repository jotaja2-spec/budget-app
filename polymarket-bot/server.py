"""
Dashboard server — serves the web UI and a JSON API backed by the bot's state files.
Run with: python server.py
Then open: http://localhost:5000
"""

import json
import os
import re
import signal
import socket
import threading
import time
import psutil
from flask import Flask, jsonify, send_from_directory, request

app = Flask(__name__, static_folder=".")

BASE = os.path.dirname(__file__)
PAPER_STATE = os.path.join(BASE, "paper_state.json")
RISK_STATE  = os.path.join(BASE, "risk_state.json")
PID_FILE    = os.path.join(BASE, "bot.pid")
TRAY_PID    = os.path.join(BASE, "tray.pid")
BOT_LOG     = os.path.join(BASE, "logs", "bot.log")
TRADE_LOG   = os.path.join(BASE, "logs", "trades.log")

# ── Health monitor settings ───────────────────────────────────────────────────
MONITOR_INTERVAL_SECS = 120   # check every 2 minutes
RAM_WARN_SYSTEM_PCT   = 90    # alert if system RAM exceeds this %
RAM_WARN_BOT_MB       = 400   # alert if bot process exceeds this MB
ALERT_COOLDOWN_SECS   = 1800  # max one alert per type per 30 minutes

_monitor = {
    "bot_was_running":    False,
    "shutdown_requested": False,
    "last_ram_alert":     0.0,
    "last_crash_alert":   0.0,
}


def _send_alert(title: str, message: str):
    """Send a push notification that bypasses quiet hours."""
    try:
        from notifications import send_notification
        send_notification(title, message, priority=1, force=True)
    except Exception:
        pass


def _health_monitor():
    """Background thread: watches for bot crashes and high RAM usage."""
    # Give the bot a moment to start before we begin watching
    time.sleep(30)
    while True:
        now = time.time()

        # ── Crash detection ──────────────────────────────────────────────────
        currently_running = _bot_running()
        if (
            _monitor["bot_was_running"]
            and not currently_running
            and not _monitor["shutdown_requested"]
            and now - _monitor["last_crash_alert"] > ALERT_COOLDOWN_SECS
        ):
            _monitor["last_crash_alert"] = now
            _send_alert(
                "⚠️ Polymarket Bot Stopped",
                "The trading bot stopped unexpectedly.\n"
                "Check the dashboard logs to see what happened.\n"
                "Restart with 'Start Polymarket Trading' on your desktop.",
            )
        _monitor["bot_was_running"] = currently_running

        # ── RAM warning ─────────────────────────────────────────────────────
        if now - _monitor["last_ram_alert"] > ALERT_COOLDOWN_SECS:
            # System RAM
            mem = psutil.virtual_memory()
            if mem.percent >= RAM_WARN_SYSTEM_PCT:
                _monitor["last_ram_alert"] = now
                _send_alert(
                    "⚠️ High RAM Usage",
                    f"System RAM is at {mem.percent:.0f}%.\n"
                    "Consider closing other applications or restarting the bot.",
                )

            # Bot process RAM
            elif os.path.exists(PID_FILE):
                try:
                    with open(PID_FILE) as f:
                        pid = int(f.read().strip())
                    bot_mb = psutil.Process(pid).memory_info().rss / (1024 * 1024)
                    if bot_mb >= RAM_WARN_BOT_MB:
                        _monitor["last_ram_alert"] = now
                        _send_alert(
                            "⚠️ Bot Using Too Much RAM",
                            f"The bot is using {bot_mb:.0f}MB of RAM.\n"
                            "Restart it with 'Stop' then 'Start Polymarket Trading'.",
                        )
                except Exception:
                    pass

        time.sleep(MONITOR_INTERVAL_SECS)


def _read_json(path: str) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def _tail(path: str, n: int = 100) -> list[str]:
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            buf = b""
            pos = size
            lines_found = 0
            chunk = 4096
            while pos > 0 and lines_found < n + 1:
                read_size = min(chunk, pos)
                pos -= read_size
                f.seek(pos)
                buf = f.read(read_size) + buf
                lines_found = buf.count(b"\n")
            lines = buf.decode("utf-8", errors="replace").splitlines()
            return lines[-n:] if len(lines) >= n else lines
    except FileNotFoundError:
        return []
    except Exception:
        return []


def _parse_trade_lines(lines: list[str]) -> list[dict]:
    trades = []
    pattern = re.compile(
        r"(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"
        r".*?TRADE \| mode=(?P<mode>\S+) city=(?P<city>[^m]+?) market=(?P<market>\S+)"
        r" direction=(?P<direction>\S+) price=(?P<price>[\d.]+) size=\$(?P<size>[\d.]+)"
        r" edge=(?P<edge>[+-][\d.]+)"
        r".*?\| (?P<reason>.+)$"
    )
    for line in reversed(lines):
        m = pattern.search(line)
        if m:
            trades.append({
                "ts": m.group("ts"),
                "mode": m.group("mode"),
                "city": m.group("city").strip(),
                "market": m.group("market"),
                "direction": m.group("direction"),
                "price": float(m.group("price")),
                "size": float(m.group("size")),
                "edge": float(m.group("edge")),
                "reason": m.group("reason"),
            })
        if len(trades) >= 50:
            break
    return trades


@app.route("/")
def index():
    return send_from_directory(".", "dashboard.html")


def _bot_running() -> bool:
    if not os.path.exists(PID_FILE):
        return False
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        return psutil.pid_exists(pid)
    except Exception:
        return False


@app.route("/api/status")
def api_status():
    paper = _read_json(PAPER_STATE)
    risk  = _read_json(RISK_STATE)

    starting = paper.get("starting_bankroll", 100.0)
    bankroll = paper.get("bankroll", starting)

    cpu = psutil.cpu_percent(interval=None)
    mem = psutil.virtual_memory()

    return jsonify({
        "mode": "PAPER" if not paper else ("LIVE" if paper.get("live") else "PAPER"),
        "bankroll": round(bankroll, 2),
        "starting_bankroll": round(starting, 2),
        "net_pnl": round(bankroll - starting, 2),
        "realized_pnl": round(paper.get("realized_pnl", 0), 2),
        "total_trades": paper.get("total_trades", 0),
        "open_positions": len(paper.get("open_positions", [])),
        "daily_pnl": round(risk.get("daily_pnl", 0), 2),
        "halted": risk.get("halted", False),
        "date": risk.get("date", "—"),
        "has_data": bool(paper),
        "bot_running": _bot_running(),
        "cpu_pct": round(cpu, 1),
        "mem_pct": round(mem.percent, 1),
    })


def _kill_pid_file(path: str) -> bool:
    """Kill the process whose PID is stored in path. Returns True if killed."""
    if not os.path.exists(path):
        return False
    try:
        with open(path) as f:
            pid = int(f.read().strip())
        proc = psutil.Process(pid)
        proc.terminate()
        proc.wait(timeout=5)
        os.remove(path)
        return True
    except psutil.NoSuchProcess:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        return True
    except Exception:
        return False


@app.route("/api/shutdown", methods=["POST"])
def api_shutdown():
    """Kill bot, tray, and any app window, then shut down the server."""
    _monitor["shutdown_requested"] = True  # prevents crash alert firing
    _kill_pid_file(PID_FILE)   # trading bot
    _kill_pid_file(TRAY_PID)   # system tray

    # Also kill any app.py (pywebview) process by name
    try:
        for proc in psutil.process_iter(["pid", "cmdline"]):
            cmdline = " ".join(proc.info.get("cmdline") or [])
            if "app.py" in cmdline and proc.pid != os.getpid():
                proc.terminate()
    except Exception:
        pass

    def _stop_server():
        import time as _time
        _time.sleep(0.4)
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=_stop_server, daemon=True).start()
    return jsonify({"status": "shutting_down"})


@app.route("/api/positions")
def api_positions():
    paper = _read_json(PAPER_STATE)
    return jsonify(paper.get("open_positions", []))


@app.route("/api/trades")
def api_trades():
    lines = _tail(TRADE_LOG, 200)
    return jsonify(_parse_trade_lines(lines))


@app.route("/api/logs")
def api_logs():
    lines = _tail(BOT_LOG, 60)
    return jsonify(lines)


def _local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


@app.route("/api/info")
def api_info():
    return jsonify({"local_ip": _local_ip(), "port": 5000})


if __name__ == "__main__":
    threading.Thread(target=_health_monitor, daemon=True).start()
    ip = _local_ip()
    print(f"Dashboard running at http://localhost:5000")
    print(f"Phone access (same WiFi): http://{ip}:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
