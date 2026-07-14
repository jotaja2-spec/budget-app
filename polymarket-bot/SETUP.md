# Polymarket Trading — Setup Guide

## What you need before starting

### 1. Your Polymarket private key
This is the private key for the crypto wallet linked to your Polymarket account.

To find it:
1. Go to polymarket.com and log in
2. Click your profile → **Settings** → **Export Private Key** (or check your wallet app)
3. It looks like: `0x4f3e...` (66 characters starting with 0x)

> **Keep this safe — it controls your wallet.**

### 2. (Optional) Pushover for phone notifications
If you want push alerts when the bot trades:
1. Install the Pushover app on your phone (iOS/Android)
2. Sign up at pushover.net
3. Get your **User Key** from the dashboard
4. Create an **API Token** (free for 30 days, then $5 one-time)

---

## First-time setup

Open a Command Prompt in the `polymarket-bot` folder and run:

```
pip install -r requirements.txt
```

Then copy the config template:
```
copy .env.template .env
```

Open `.env` in Notepad and fill in:

```
POLY_PRIVATE_KEY=0x_your_key_here

# Optional — leave blank to skip notifications
PUSHOVER_API_TOKEN=
PUSHOVER_USER_KEY=

# Leave these as-is to start in safe paper trading mode
PAPER_TRADING=true
STARTING_BANKROLL=100
```

---

## Install desktop shortcuts (one time)

Right-click `install_shortcuts.ps1` → **Run with PowerShell**

This creates three shortcuts on your desktop:
- **Start Polymarket Trading** — launches everything (bot + tray icon + browser)
- **Polymarket Trading App** — opens the desktop app window
- **Polymarket Dashboard** — opens the browser dashboard

---

## Daily use

1. Double-click **Start Polymarket Trading** on your desktop
2. A browser window opens automatically showing the dashboard
3. A hexagon icon appears in your taskbar tray (bottom-right)
4. **Phone:** open your browser and go to the URL shown at the top of the dashboard

---

## What the bot does (paper trading mode)

- Scans Polymarket every 5 minutes for weather prediction markets
- Compares market prices against real weather forecast data
- Places simulated trades when it finds a 12%+ edge
- Tracks paper P&L — no real money moves until you set `PAPER_TRADING=false`

---

## Switching to live trading

Only do this after running paper mode for a few days and you're comfortable.

In `.env`, change:
```
PAPER_TRADING=false
```

Make sure your Polymarket wallet has USDC on Polygon network funded.
