# Polymarket Weather Bot

Scans Polymarket temperature markets every 5 minutes, compares market-implied probabilities
against GFS ensemble weather forecasts from Open-Meteo, and places trades when the forecast
disagrees with market price by 12%+.

---

## Quick Start (Windows)

### 1. Install Python

Download Python 3.11+ from **python.org**.
During install, check **"Add Python to PATH"**.

Verify in PowerShell:
```powershell
python --version
```

### 2. Clone or copy this folder

```powershell
cd C:\Users\YourName\
# If you have git:
git clone https://github.com/your-repo/polymarket-bot
cd polymarket-bot
# Otherwise just navigate to the folder you downloaded
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Create your .env file

```powershell
copy .env.template .env
```

Open `.env` in Notepad or VS Code and fill in your values (see sections below).

### 5. Run the bot

```powershell
python main.py
```

The bot prints a status block every 5 minutes. Press **Ctrl+C** to stop.

**Silent background mode (no terminal window):**
```powershell
pythonw main.py
```
Check Task Manager → Details to see it running. Logs are in the `logs/` folder.

---

## How to Get Your Polymarket Private Key

Your private key lets the bot place orders on your behalf.
**Never share this key with anyone. Never commit it to git.**

### If you use MetaMask (most common)

1. Open MetaMask in your browser
2. Click the round account icon (top right)
3. Click **Account Details**
4. Click **Show private key**
5. Enter your MetaMask password
6. Copy the key (starts with `0x...`, 66 characters total)
7. Paste it as `POLY_PRIVATE_KEY=0x...` in your `.env` file

### If you signed up with Email or Google (Polymarket embedded wallet)

1. Go to **polymarket.com** and log in
2. Click your profile icon (top right) → **Settings**
3. Scroll to **Wallet** or **Export Wallet**
4. Click **Export Private Key**
5. Complete any verification step they require
6. Copy the `0x...` key and paste it into `.env`

### Getting your L2 API credentials (POLY_API_KEY, etc.)

The bot can derive these automatically from your private key on first run.
You can leave `POLY_API_KEY`, `POLY_API_SECRET`, and `POLY_API_PASSPHRASE`
blank — the bot will generate and log them for you. Once generated, copy
them from the log output into `.env` to skip the derivation step next time.

---

## Pushover Notifications

1. Install **Pushover** on your phone (iOS or Android) — $5 one-time
2. Log in at **pushover.net** in a browser
3. Your **User Key** is shown on the main dashboard
4. Create an app token: click **Create an Application** → name it "PolyBot" → submit
5. Copy the **API Token** shown after creation
6. In `.env`:
   ```
   PUSHOVER_USER_KEY=your_user_key_here
   PUSHOVER_API_TOKEN=your_app_token_here
   ```

---

## Configuration Reference (.env)

| Variable | Default | Description |
|---|---|---|
| `PAPER_TRADING` | `true` | `true` = simulate only, `false` = real orders |
| `STARTING_BANKROLL` | `100.0` | Your USDC balance |
| `EDGE_THRESHOLD` | `0.12` | Min forecast vs market gap to trade (12%) |
| `DAILY_LOSS_LIMIT_PCT` | `0.20` | Bot halts if daily loss exceeds 20% of bankroll |
| `MAX_POSITION_SIZE_USD` | `15.0` | Hard cap per trade in USD |
| `MAX_OPEN_POSITIONS` | `5` | Max simultaneous open positions |
| `MAX_SINGLE_TRADE_PCT` | `0.03` | Kelly cap: max 3% of bankroll per trade |
| `MIN_MARKET_LIQUIDITY` | `5000.0` | Skip markets with less than $5,000 liquidity |
| `KELLY_FRACTION` | `0.5` | Half-Kelly sizing (0.5 = conservative) |
| `SCAN_INTERVAL_SECONDS` | `300` | Scan every 5 minutes |

---

## Reading the Logs

Logs are written to the `logs/` folder:

- `logs/bot.log` — every scan, signal, skip decision, and error
- `logs/trades.log` — every trade placed (paper or live)

**What a healthy first run looks like:**
```
2025-07-04 10:00:00 | INFO     | Bot starting — PAPER TRADING | bankroll=$100.00
2025-07-04 10:00:01 | INFO     | Scanner found 3 weather markets across target cities
2025-07-04 10:00:02 | INFO     | Forecast New York 2025-07-05: 31 members, range 78.2–91.4°F, mean 84.1°F
2025-07-04 10:00:02 | INFO     | SCAN | city=New York market=abc123 market_price=0.420 forecast=0.581 edge=+0.161
2025-07-04 10:00:02 | INFO     | SIGNAL | city=New York market=abc123 direction=YES edge=+0.161 size=$0.00
```

**Signs something is wrong:**
- `Scanner found 0 weather markets` every scan — Gamma API may have changed; check their docs
- `Open-Meteo request failed` — check your internet connection
- `RISK HALT` in logs — daily loss limit was hit; check `risk_state.json`
- `py-clob-client` import errors — run `pip install py-clob-client` again

---

## Going Live (When You're Ready)

1. Watch paper trading for at least 48 hours
2. Verify signals make sense: forecast probabilities should differ from market prices on the markets it trades
3. Confirm your wallet has USDC on Polygon network
4. In `.env`, change: `PAPER_TRADING=false`
5. Run `python main.py` — first real trade will fire on the next scan with a signal

---

## Migrating to Raspberry Pi

The code runs identically on Linux — no Windows-specific dependencies.

```bash
# On the Pi (Ubuntu/Raspberry Pi OS):
sudo apt update && sudo apt install python3 python3-pip git -y
git clone https://github.com/your-repo/polymarket-bot
cd polymarket-bot
pip3 install -r requirements.txt
cp .env.template .env
nano .env  # fill in your values
python3 main.py  # test it runs
```

**To run as a systemd service (runs 24/7, restarts on crash):**

Create `/etc/systemd/system/polybot.service`:
```ini
[Unit]
Description=Polymarket Weather Bot
After=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/polymarket-bot
ExecStart=/usr/bin/python3 /home/pi/polymarket-bot/main.py
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable polybot
sudo systemctl start polybot
sudo journalctl -u polybot -f  # watch live logs
```

---

## Project Structure

```
polymarket-bot/
├── .env                  # Your secrets — never share or commit
├── .env.template         # Safe template with placeholder values
├── main.py               # Entry point — main scan loop
├── config.py             # Loads .env, all settings in one place
├── scanner.py            # Polymarket Gamma API — finds markets
├── forecast.py           # Open-Meteo GFS ensemble weather data
├── signals.py            # Edge calculation logic
├── sizing.py             # Kelly Criterion position sizing
├── executor.py           # Polymarket CLOB API — places orders
├── risk.py               # Daily loss limit, position limits
├── logger.py             # Trade and scan logging
├── paper_trading.py      # Simulated trading mode
├── requirements.txt      # Python dependencies
├── README.md             # This file
├── logs/                 # Created automatically on first run
│   ├── bot.log
│   └── trades.log
├── paper_state.json      # Paper trading P&L (auto-created)
└── risk_state.json       # Daily risk state (auto-created)
```
