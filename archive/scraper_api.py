#!/usr/bin/env python3
"""
Val Gardena Parking Scraper (API Version)
Collects parking availability data from South Tyrol Open Data Hub API.
https://opendatahub.com/
"""

import requests
import csv
from datetime import datetime
from pathlib import Path
import time
import sys

API_URL = "https://mobility.api.opendatahub.com/v2/flat/ParkingStation/*/latest"
API_PARAMS = {
    "limit": 200,
    "offset": 0,
    "where": "sorigin.eq.GARDENA",
    "shownull": "false",
    "distinct": "true"
}

DATA_FILE = Path(__file__).parent / "parking_data_api.csv"
INTERVAL_MINUTES = 5  # API updates frequently (real-time sensors)

CSV_HEADER_COMMENT = """# Val Gardena Parking Data (API Version)
# Source: South Tyrol Open Data Hub
# API: https://mobility.api.opendatahub.com/v2/
# Update frequency: Real-time (sensor-based)
# Scrape interval: Every 5 minutes
#
"""

# Location mapping based on station codes/names
LOCATION_MAP = {
    "danterc": "Wolkenstein",  # Matches Dantercëpies with any umlaut variant
    "sciuz": "Wolkenstein",
    "vallunga": "Wolkenstein",
    "langental": "Wolkenstein",
    "seceda": "St. Ulrich",
    "setil": "St. Ulrich",
    "mont s": "St. Ulrich",  # Matches Mont Sëuc with any umlaut variant
    "central": "St. Ulrich",
    "posta": "St. Ulrich",
    "pana": "St. Christina",
    "monte pana": "St. Christina",
    "cristauta": "St. Christina",
    "iman": "St. Christina",
}


def extract_location(station_name):
    """Extract village location from station name."""
    name_lower = station_name.lower()
    for keyword, location in LOCATION_MAP.items():
        if keyword in name_lower:
            return location
    return "Val Gardena"


def fetch_parking_data():
    """Fetch parking data from Open Data Hub API."""
    headers = {
        "Accept": "application/json",
        "User-Agent": "ValGardenaParkingScraper/2.0"
    }

    try:
        response = requests.get(API_URL, params=API_PARAMS, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"[{datetime.now()}] Error fetching API data: {e}")
        return None
    except ValueError as e:
        print(f"[{datetime.now()}] Error parsing JSON: {e}")
        return None

    if "data" not in data:
        print(f"[{datetime.now()}] Unexpected API response format")
        return None

    timestamp = datetime.now().isoformat()
    parking_data = []

    for station in data["data"]:
        # Extract station info
        name = station.get("sname", "Unknown")

        # Get availability from mvalue (measurement value)
        available = station.get("mvalue")
        if available is not None:
            available = int(available)

        # Get capacity from metadata
        metadata = station.get("smetadata", {})
        capacity = metadata.get("capacity", 0)

        # Get coordinates
        coords = station.get("scoordinate", {})
        lat = coords.get("y")
        lon = coords.get("x")

        # Get measurement timestamp
        mtime = station.get("mvalidtime")

        entry = {
            "timestamp": timestamp,
            "name": name,
            "available": available if available is not None else "N/A",
            "capacity": capacity if capacity else "N/A",
            "location": extract_location(name),
            "latitude": lat,
            "longitude": lon,
            "data_timestamp": mtime,
            "status": "OK" if available is not None else "No data"
        }

        parking_data.append(entry)

    print(f"[{datetime.now()}] Retrieved {len(parking_data)} parking stations from API")
    return parking_data


def save_to_csv(data):
    """Append parking data to CSV file."""
    if not data:
        return

    fieldnames = ["timestamp", "name", "available", "capacity", "location",
                  "latitude", "longitude", "data_timestamp", "status"]
    existing_data = []

    # Read existing data if file exists (skip comment lines)
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", newline="", encoding="utf-8") as f:
            lines = f.readlines()
            data_lines = [line for line in lines if not line.startswith('#')]
            if data_lines:
                import io
                reader = csv.DictReader(io.StringIO(''.join(data_lines)))
                existing_data = list(reader)

    # Append new data
    existing_data.extend(data)

    # Sort by timestamp, then by name
    existing_data.sort(key=lambda x: (x["timestamp"], x["name"]))

    # Write all data back with header comment
    with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
        f.write(CSV_HEADER_COMMENT)
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(existing_data)

    print(f"[{datetime.now()}] Saved {len(data)} entries ({len(existing_data)} total) to {DATA_FILE}")


def run_once():
    """Run the scraper once and save data."""
    print(f"[{datetime.now()}] Fetching parking data from Open Data Hub API...")
    data = fetch_parking_data()

    if data:
        save_to_csv(data)
        print(f"\n{'Station Name':<45} {'Free':>6} {'Cap':>6} {'Location':<15}")
        print("-" * 80)
        for entry in sorted(data, key=lambda x: x['name']):
            avail = entry.get('available', 'N/A')
            cap = entry.get('capacity', 'N/A')
            print(f"{entry['name']:<45} {str(avail):>6} {str(cap):>6} {entry['location']:<15}")
    else:
        print(f"[{datetime.now()}] No data retrieved or error occurred")

    return data


def run_continuous():
    """Run the scraper continuously."""
    print("=" * 80)
    print("Val Gardena Parking Scraper (API Version)")
    print(f"Source: South Tyrol Open Data Hub")
    print(f"Collecting data every {INTERVAL_MINUTES} minutes")
    print(f"Data saved to: {DATA_FILE}")
    print("Press Ctrl+C to stop")
    print("=" * 80 + "\n")

    try:
        while True:
            run_once()
            next_run = datetime.now().replace(microsecond=0)
            next_run = next_run.replace(
                minute=(next_run.minute // INTERVAL_MINUTES + 1) * INTERVAL_MINUTES % 60
            )
            print(f"\nNext scrape at {next_run.strftime('%H:%M:%S')}...\n")
            time.sleep(INTERVAL_MINUTES * 60)
    except KeyboardInterrupt:
        print("\n\nScraper stopped by user.")
        print(f"Data saved in: {DATA_FILE}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        run_once()
    else:
        run_continuous()
