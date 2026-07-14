"""
Desktop app window for Polymarket Trading.
Wraps the dashboard in a native Windows window (no browser needed).
Run with: pythonw app.py
Requires: pywebview  (pip install pywebview)
"""

import os
import subprocess
import sys
import time

import requests
import webview

BASE = os.path.dirname(os.path.abspath(__file__))
DASH = "http://localhost:5000"


def _server_ready(timeout: int = 10) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            requests.get(DASH, timeout=1)
            return True
        except Exception:
            time.sleep(0.5)
    return False


def _ensure_server():
    try:
        requests.get(DASH, timeout=1)
        return  # already running
    except Exception:
        pass
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable
    subprocess.Popen(
        [pythonw, os.path.join(BASE, "server.py")],
        cwd=BASE,
        creationflags=subprocess.DETACHED_PROCESS,
    )
    _server_ready(timeout=10)


def main():
    _ensure_server()
    window = webview.create_window(
        title     = "Polymarket Trading",
        url       = DASH,
        width     = 1280,
        height    = 820,
        resizable = True,
        min_size  = (480, 600),
    )
    webview.start(gui="edgechromium")


if __name__ == "__main__":
    main()
