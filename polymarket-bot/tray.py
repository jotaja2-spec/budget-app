"""
System tray icon for Polymarket Trading.
Run with: pythonw tray.py
Right-click the tray icon for options.
"""

import math
import os
import subprocess
import sys
import threading
import time
import webbrowser

import pystray
import requests
from PIL import Image, ImageDraw, ImageFont

BASE        = os.path.dirname(os.path.abspath(__file__))
STATUS_URL  = "http://localhost:5000/api/status"
POLL_SECS   = 15

_state = {"status": None, "icon": None}


# ── Icon drawing ──────────────────────────────────────────────────────────────

def _hex_points(cx, cy, r):
    return [
        (cx + r * math.cos(math.radians(90 + i * 60)),
         cy + r * math.sin(math.radians(90 + i * 60)))
        for i in range(6)
    ]

def _make_icon(color: str, letter: str = "P") -> Image.Image:
    size = 64
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    pts  = _hex_points(size // 2, size // 2, size // 2 - 2)
    draw.polygon(pts, fill=color)
    # Simple centered dot as inner mark (avoids font sizing issues)
    inner = size // 2 - 10
    pts2  = _hex_points(size // 2, size // 2, inner)
    draw.polygon(pts2, fill=(0, 0, 0, 80))
    return img

ICONS = {
    "running": _make_icon("#22c55e"),
    "halted":  _make_icon("#f59e0b"),
    "stopped": _make_icon("#64748b"),
    "offline": _make_icon("#ef4444"),
}


# ── Status polling ────────────────────────────────────────────────────────────

def _fetch() -> dict | None:
    try:
        r = requests.get(STATUS_URL, timeout=3)
        return r.json()
    except Exception:
        return None


def _icon_state(s: dict | None) -> str:
    if s is None:
        return "offline"
    if s.get("halted"):
        return "halted"
    if s.get("bot_running"):
        return "running"
    return "stopped"


def _tooltip(s: dict | None) -> str:
    if s is None:
        return "Polymarket Trading — server offline"
    bankroll = s.get("bankroll", 0)
    pnl      = s.get("net_pnl", 0)
    mode     = s.get("mode", "PAPER")
    sign     = "+" if pnl >= 0 else ""
    status   = "Running" if s.get("bot_running") else "Stopped"
    return f"Polymarket Trading [{mode}]\n{status} | ${bankroll:.2f} | P&L: {sign}${pnl:.2f}"


# ── Menu actions ──────────────────────────────────────────────────────────────

def _open_dashboard(_=None):
    webbrowser.open("http://localhost:5000")


def _open_app(_=None):
    subprocess.Popen(
        [sys.executable, os.path.join(BASE, "app.py")],
        creationflags=subprocess.DETACHED_PROCESS if sys.platform == "win32" else 0,
    )


def _quit_tray(icon, _=None):
    icon.stop()


# ── Polling thread ────────────────────────────────────────────────────────────

def _poll(icon: pystray.Icon):
    while True:
        s = _fetch()
        _state["status"] = s
        state_key = _icon_state(s)
        icon.icon    = ICONS[state_key]
        icon.title   = _tooltip(s)
        time.sleep(POLL_SECS)


# ── Build menu ────────────────────────────────────────────────────────────────

def _build_menu() -> pystray.Menu:
    s     = _state["status"]
    label = _tooltip(s)
    return pystray.Menu(
        pystray.MenuItem(label, None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open Browser Dashboard", _open_dashboard),
        pystray.MenuItem("Open Desktop App",       _open_app),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit Tray",              _quit_tray),
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    icon = pystray.Icon(
        name   = "polymarket_trading",
        icon   = ICONS["offline"],
        title  = "Polymarket Trading — connecting…",
        menu   = pystray.Menu(
            pystray.MenuItem("Open Browser Dashboard", _open_dashboard),
            pystray.MenuItem("Open Desktop App",       _open_app),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit Tray",              _quit_tray),
        ),
    )
    _state["icon"] = icon
    threading.Thread(target=_poll, args=(icon,), daemon=True).start()
    icon.run()


if __name__ == "__main__":
    main()
