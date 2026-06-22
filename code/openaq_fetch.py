import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv
load_dotenv()

API_KEY = os.environ.get("OPENAQ_API_KEY")
HEADERS = {"X-API-Key": API_KEY}
BASE_URL = "https://api.openaq.org/v3"
SEARCH_RADIUS_M = 25000   
REQUEST_PAUSE_S = 1.1   
print("=" * 60)
print("RUNNING openaq_fetch.py")
print("Key loaded:", (API_KEY[:10] + "...") if API_KEY else "MISSING - check your .env file")
print("=" * 60)

if not API_KEY:
    raise SystemExit(
        "No API key found. Make sure a .env file exists in this folder "
        "with a line like: OPENAQ_API_KEY=your_key_here"
    )

def _request_with_backoff(url, params, max_retries=5):
    """GET with handling for OpenAQ's rate-limit headers and 429 responses."""
    for attempt in range(max_retries):
        r = requests.get(url, headers=HEADERS, params=params, timeout=20)

        if r.status_code == 401:
            raise RuntimeError(
                "401 Invalid credentials -- your API key is wrong, expired, "
                "or revoked. Double check the .env file."
            )

        if r.status_code == 429:
            wait = int(r.headers.get("x-ratelimit-reset", 30))
            print(f"  Rate limited, waiting {wait}s...")
            time.sleep(wait + 1)
            continue

        r.raise_for_status()

        remaining = r.headers.get("x-ratelimit-remaining")
        if remaining is not None and int(remaining) < 3:
            reset = int(r.headers.get("x-ratelimit-reset", 5))
            time.sleep(reset + 1)

        return r.json()

    raise RuntimeError(f"Gave up after {max_retries} retries on {url}")


def get_locations_near(lat, lon, radius_m=SEARCH_RADIUS_M, limit=50):
    """Step 1: find OpenAQ stations near a coordinate. Metadata only."""
    params = {"coordinates": f"{lat},{lon}", "radius": radius_m, "limit": limit}
    return _request_with_backoff(f"{BASE_URL}/locations", params).get("results", [])


def get_latest_for_location(location_id, limit=100):
    """Step 2: actual current pollutant readings for one station."""
    return _request_with_backoff(
        f"{BASE_URL}/locations/{location_id}/latest", {"limit": limit}
    ).get("results", [])

def fetch_all(matched_csv="matched_areas.csv", out_csv="openaq_realtime.csv", append=True):
    
    fetched_at = pd.Timestamp.utcnow().isoformat()
    matched = pd.read_csv(matched_csv)
    rows = []

    for i, row in matched.iterrows():
        area, state, lat, lon = row["area"], row["state"], row["lat"], row["lon"]
        print(f"[{i + 1}/{len(matched)}] {area}, {state}...")

        try:
            locations = get_locations_near(lat, lon)
        except requests.HTTPError as e:
            print(f"  Skipped (locations lookup failed: {e})")
            continue

        if not locations:
            print("  No OpenAQ station within 25km")
            continue

        for loc in locations:
            loc_id = loc["id"]
            try:
                latest = get_latest_for_location(loc_id)
            except requests.HTTPError as e:
                print(f"  Skipped station {loc_id} ({e})")
                continue

            for entry in latest:
                param = entry.get("parameter") or {}
                rows.append({
                    "fetched_at": fetched_at,
                    "area": area,
                    "state": state,
                    "station_id": loc_id,
                    "station_name": loc.get("name"),
                    "sensor_id": entry.get("sensorsId"),
                    "parameter": param.get("name"),
                    "value": entry.get("value"),
                    "unit": param.get("units"),
                    "datetime_utc": (entry.get("datetime") or {}).get("utc"),
                    "station_lat": (entry.get("coordinates") or {}).get("latitude"),
                    "station_lon": (entry.get("coordinates") or {}).get("longitude"),
                })

        time.sleep(REQUEST_PAUSE_S)

    df = pd.DataFrame(rows)

    if append and os.path.exists(out_csv):
        df.to_csv(out_csv, mode="a", header=False, index=False)
        print(f"\nAppended {len(df)} readings (timestamp: {fetched_at}) -> {out_csv}")
    else:
        df.to_csv(out_csv, index=False)
        print(f"\nSaved {len(df)} readings across {df['area'].nunique() if len(df) else 0} areas -> {out_csv}")

    return df


if __name__ == "__main__":
    fetch_all()