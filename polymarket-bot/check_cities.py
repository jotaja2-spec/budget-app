"""Check which cities Polymarket has weather markets for vs what we support."""
import re
import requests
import config

EVENTS_URL = "https://gamma-api.polymarket.com/events"
TITLE_RE   = re.compile(r"highest temperature in (.+?) on", re.IGNORECASE)

print("Fetching active weather events from Polymarket...\n")

polymarket_cities = set()
offset = 0
while offset < 3000:
    r = requests.get(EVENTS_URL, params={
        "active": "true", "closed": "false",
        "limit": 100, "offset": offset,
        "order": "startDate", "ascending": "false",
    }, timeout=20)
    batch = r.json()
    if isinstance(batch, dict):
        batch = batch.get("data", [])
    if not batch:
        break
    for e in batch:
        m = TITLE_RE.search(e.get("title", ""))
        if m:
            polymarket_cities.add(m.group(1).strip())
    if len(batch) < 100:
        break
    offset += 100

# Our configured aliases (flattened)
our_aliases = set()
for city_name, data in config.CITIES.items():
    our_aliases.add(city_name.lower())
    for alias in data["aliases"]:
        our_aliases.add(alias.lower())

print(f"{'CITY ON POLYMARKET':<30} {'STATUS'}")
print("-" * 50)
missing = []
for city in sorted(polymarket_cities):
    matched = any(city.lower() == a or a in city.lower() or city.lower() in a
                  for a in our_aliases)
    status = "✓ covered" if matched else "✗ MISSING"
    print(f"  {city:<28} {status}")
    if not matched:
        missing.append(city)

print(f"\nTotal on Polymarket: {len(polymarket_cities)}")
print(f"Missing from our config: {len(missing)}")
if missing:
    print("\nNeed to add:")
    for c in missing:
        print(f"  - {c}")

input("\nDone. Press Enter to close...")
