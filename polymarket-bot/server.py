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

# ── CPU temperature ───────────────────────────────────────────────────────────
CPU_TEMP_ALERT_C   = 95          # degrees Celsius
TEMP_CHECK_SECS    = 120         # check every 2 minutes
TEMP_ALERT_COOLDOWN = 900        # only re-alert every 15 minutes
_last_temp_alert   = 0.0
_cached_cpu_temp   = None        # updated by background thread


def _read_cpu_temp() -> float | None:
    """
    Read CPU temperature via HWiNFO64 shared memory.
    Requires HWiNFO64 running with Shared Memory Support enabled
    (Settings -> Sensors -> Shared Memory Support).
    """
    HWINFO_SM_NAME    = "Global\\HWiNFO_SENS_SM2"
    HWINFO_SM_SIZE    = 1 * 1024 * 1024   # 1 MB buffer
    HWINFO_SIGNATURE  = 0x53697748        # 'HWiS'
    READING_TYPE_TEMP = 1
    SENSOR_STR        = 128
    UNIT_STR          = 16

    try:
        import ctypes, struct

        # Open shared memory
        FILE_MAP_READ = 0x0004
        k32   = ctypes.windll.kernel32
        h     = k32.OpenFileMappingW(FILE_MAP_READ, False, HWINFO_SM_NAME)
        if not h:
            return None
        ptr   = k32.MapViewOfFile(h, FILE_MAP_READ, 0, 0, HWINFO_SM_SIZE)
        if not ptr:
            k32.CloseHandle(h)
            return None
        data  = ctypes.string_at(ptr, HWINFO_SM_SIZE)
        k32.UnmapViewOfFile(ptr)
        k32.CloseHandle(h)

        # Parse header: sig, ver, rev, poll_time(int64), off_sensor, sz_sensor,
        #               num_sensor, off_reading, sz_reading, num_reading
        hdr_fmt  = "<IIIqIIIIII"
        hdr_size = struct.calcsize(hdr_fmt)
        sig, _, _, _, _, _, _, off_reading, sz_reading, num_reading = \
            struct.unpack_from(hdr_fmt, data)

        if sig != HWINFO_SIGNATURE:
            return None

        # Reading element: tReading, sensorIdx, readingID,
        #   labelOrig[128], labelUser[128], unit[16],
        #   value, valueMin, valueMax, valueAvg  (all doubles)
        rd_fmt = f"<III{SENSOR_STR}s{SENSOR_STR}s{UNIT_STR}sdddd"
        rd_size = struct.calcsize(rd_fmt)

        cpu_temps = []
        for i in range(num_reading):
            off = off_reading + i * sz_reading
            chunk = data[off: off + rd_size]
            if len(chunk) < rd_size:
                break
            t_reading, _, _, label_orig, _, _, val, *_ = struct.unpack(rd_fmt, chunk)
            if t_reading == READING_TYPE_TEMP:
                label = label_orig.rstrip(b"\x00").decode("utf-8", errors="ignore").lower()
                if "cpu" in label and 0 < val < 150:
                    cpu_temps.append(val)

        if cpu_temps:
            return round(max(cpu_temps), 1)

    except Exception:
        pass

    return None


def _temp_monitor():
    """Background thread: checks CPU temp every 2 min, alerts if >90°C."""
    global _last_temp_alert, _cached_cpu_temp
    while True:
        time.sleep(TEMP_CHECK_SECS)
        temp = _read_cpu_temp()
        _cached_cpu_temp = temp
        if temp is not None and temp >= CPU_TEMP_ALERT_C:
            now = time.time()
            if now - _last_temp_alert > TEMP_ALERT_COOLDOWN:
                _last_temp_alert = now
                try:
                    from notifications import send_notification
                    send_notification(
                        "🔥 CPU Temperature Warning",
                        f"CPU is at {temp:.0f}°C — above {CPU_TEMP_ALERT_C}°C!\n"
                        f"Check your cooling immediately.",
                        priority=1,
                        force=True,   # bypass quiet hours for safety alerts
                    )
                except Exception:
                    pass
PAPER_STATE = os.path.join(BASE, "paper_state.json")
RISK_STATE  = os.path.join(BASE, "risk_state.json")
PID_FILE    = os.path.join(BASE, "bot.pid")
BOT_LOG     = os.path.join(BASE, "logs", "bot.log")
TRADE_LOG   = os.path.join(BASE, "logs", "trades.log")


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
    # Format: 2025-07-04 10:00:00 | INFO     | TRADE | mode=PAPER city=... market=... direction=... price=... size=$... edge=... | reason
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
        "cpu_pct":  round(cpu, 1),
        "mem_pct":  round(mem.percent, 1),
        "cpu_temp": _cached_cpu_temp,
    })


@app.route("/api/shutdown", methods=["POST"])
def api_shutdown():
    """Kill the bot process, then shut down the server."""
    bot_killed = False
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
            proc = psutil.Process(pid)
            proc.terminate()
            proc.wait(timeout=5)
            os.remove(PID_FILE)
            bot_killed = True
        except psutil.NoSuchProcess:
            bot_killed = True  # already gone
            try:
                os.remove(PID_FILE)
            except FileNotFoundError:
                pass
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    def _stop_server():
        import time as _time
        _time.sleep(0.4)
        os.kill(os.getpid(), signal.SIGTERM)

    threading.Thread(target=_stop_server, daemon=True).start()
    return jsonify({"status": "shutting_down", "bot_killed": bot_killed})


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
    # Start CPU temperature monitor in background
    threading.Thread(target=_temp_monitor, daemon=True).start()
    # Grab initial reading immediately
    _cached_cpu_temp = _read_cpu_temp()

    ip = _local_ip()
    print(f"Dashboard running at http://localhost:5000")
    print(f"Phone access (same WiFi): http://{ip}:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)
