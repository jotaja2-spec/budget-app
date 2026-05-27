import os
from dotenv import load_dotenv

load_dotenv()

# Cities to monitor with coordinates (lat/lon) and timezone for Open-Meteo
CITIES = {
    "New York": {
        "lat": 40.7128,
        "lon": -74.0060,
        "timezone": "America/New_York",
        "aliases": ["new york", "nyc", "new york city"],
    },
    "Los Angeles": {
        "lat": 34.0522,
        "lon": -118.2437,
        "timezone": "America/Los_Angeles",
        "aliases": ["los angeles", "la", "l.a."],
    },
    "Chicago": {
        "lat": 41.8781,
        "lon": -87.6298,
        "timezone": "America/Chicago",
        "aliases": ["chicago"],
    },
    "Miami": {
        "lat": 25.7617,
        "lon": -80.1918,
        "timezone": "America/New_York",
        "aliases": ["miami"],
    },
    "London": {
        "lat": 51.5074,
        "lon": -0.1278,
        "timezone": "Europe/London",
        "aliases": ["london"],
    },
    "San Francisco": {
        "lat": 37.7749,
        "lon": -122.4194,
        "timezone": "America/Los_Angeles",
        "aliases": ["san francisco", "sf", "s.f.", "san francisco, ca"],
    },
    "Phoenix": {
        "lat": 33.4484,
        "lon": -112.0740,
        "timezone": "America/Phoenix",
        "aliases": ["phoenix"],
    },
    "Houston": {
        "lat": 29.7604,
        "lon": -95.3698,
        "timezone": "America/Chicago",
        "aliases": ["houston"],
    },
    "Dallas": {
        "lat": 32.7767,
        "lon": -96.7970,
        "timezone": "America/Chicago",
        "aliases": ["dallas"],
    },
    "Seattle": {
        "lat": 47.6062,
        "lon": -122.3321,
        "timezone": "America/Los_Angeles",
        "aliases": ["seattle"],
    },
    "Denver": {
        "lat": 39.7392,
        "lon": -104.9903,
        "timezone": "America/Denver",
        "aliases": ["denver"],
    },
    "Atlanta": {
        "lat": 33.7490,
        "lon": -84.3880,
        "timezone": "America/New_York",
        "aliases": ["atlanta"],
    },
}

# Trading
PAPER_TRADING = os.getenv("PAPER_TRADING", "true").lower() == "true"
STARTING_BANKROLL = float(os.getenv("STARTING_BANKROLL", "100.0"))
EDGE_THRESHOLD = float(os.getenv("EDGE_THRESHOLD", "0.12"))
DAILY_LOSS_LIMIT_PCT = float(os.getenv("DAILY_LOSS_LIMIT_PCT", "0.20"))
MAX_POSITION_SIZE_USD = float(os.getenv("MAX_POSITION_SIZE_USD", "15.0"))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "5"))
MAX_SINGLE_TRADE_PCT = float(os.getenv("MAX_SINGLE_TRADE_PCT", "0.03"))
MIN_MARKET_LIQUIDITY = float(os.getenv("MIN_MARKET_LIQUIDITY", "5000.0"))
KELLY_FRACTION = float(os.getenv("KELLY_FRACTION", "0.5"))
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "300"))

# Polymarket credentials
POLY_PRIVATE_KEY = os.getenv("POLY_PRIVATE_KEY", "")
POLY_API_KEY = os.getenv("POLY_API_KEY", "")
POLY_API_SECRET = os.getenv("POLY_API_SECRET", "")
POLY_API_PASSPHRASE = os.getenv("POLY_API_PASSPHRASE", "")
POLY_CHAIN_ID = int(os.getenv("POLY_CHAIN_ID", "137"))

# Pushover
PUSHOVER_API_TOKEN = os.getenv("PUSHOVER_API_TOKEN", "")
PUSHOVER_USER_KEY = os.getenv("PUSHOVER_USER_KEY", "")

# FRED API key (free — https://fred.stlouisfed.org/docs/api/api_key.html)
# Enables CPI, unemployment, and GDP market trading.
# Fed rate markets work without this (uses CME FedWatch).
FRED_API_KEY = os.getenv("FRED_API_KEY", "")

# API endpoints
GAMMA_API_URL = "https://gamma-api.polymarket.com"
CLOB_API_URL = "https://clob.polymarket.com"
OPEN_METEO_ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
PUSHOVER_API_URL = "https://api.pushover.net/1/messages.json"
