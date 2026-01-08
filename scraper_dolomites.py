#!/usr/bin/env python3
"""
Dolomites Region Parking Scraper (API Version)
Collects parking availability data from South Tyrol Open Data Hub API.
Covers: Val Gardena, Brunico (Puster Valley gateway), Bressanone (Isarco Valley gateway)
https://opendatahub.com/
"""

import requests
import csv
import io
from datetime import datetime
from pathlib import Path
import time
import sys

API_URL = "https://mobility.api.opendatahub.com/v2/flat/ParkingStation/*/latest"
API_PARAMS = {
    "limit": 200,
    "offset": 0,
    "where": "sorigin.in.(GARDENA,skidata)",
    "shownull": "false",
    "distinct": "true"
}

# Exclude Bolzano stations (latitude < 46.55)
MIN_LATITUDE = 46.55

DATA_FILE = Path(__file__).parent / "data" / "parking_data_dolomites.csv"
INTERVAL_MINUTES = 5

CSV_HEADER_COMMENT = """# Dolomites Region Parking Data (API Version)
# Source: South Tyrol Open Data Hub
# API: https://mobility.api.opendatahub.com/v2/
# Coverage: Val Gardena, Brunico, Bressanone
# Update frequency: Real-time (sensor-based)
# Scrape interval: Every 5 minutes
#
"""

# Location mapping based on station names
LOCATION_MAP = {
    # Val Gardena
    "danterc": "Wolkenstein",
    "sciuz": "Wolkenstein",
    "vallunga": "Wolkenstein",
    "langental": "Wolkenstein",
    "seceda": "St. Ulrich",
    "setil": "St. Ulrich",
    "mont s": "St. Ulrich",
    "central": "St. Ulrich",
    "posta": "St. Ulrich",
    "pana": "St. Christina",
    "monte pana": "St. Christina",
    "cristauta": "St. Christina",
    "iman": "St. Christina",
    # Gateway stations
    "brunico": "Brunico",
    "bruneck": "Brunico",
    "bressanone": "Bressanone",
    "brixen": "Bressanone",
}

# Region mapping for categorization
REGION_MAP = {
    "Wolkenstein": "Val Gardena",
    "St. Ulrich": "Val Gardena",
    "St. Christina": "Val Gardena",
    "Brunico": "Puster Valley Gateway",
    "Bressanone": "Isarco Valley Gateway",
}


def extract_location(station_name):
    """Extract village/town location from station name."""
    name_lower = station_name.lower()
    for keyword, location in LOCATION_MAP.items():
        if keyword in name_lower:
            return location
    return "Dolomites"


def extract_region(location):
    """Extract region from location."""
    return REGION_MAP.get(location, "Other")


def fetch_parking_data():
    """Fetch parking data from Open Data Hub API."""
    headers = {
        "Accept": "application/json",
        "User-Agent": "DolomitesParkingScraper/1.0"
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

    # SKIDATA returns historical data - deduplicate by station name, keep latest
    stations_by_name = {}
    for station in data["data"]:
        name = station.get("sname", "Unknown")
        mtime = station.get("mvalidtime", "")

        # Keep only the most recent entry per station
        if name not in stations_by_name or mtime > stations_by_name[name].get("mvalidtime", ""):
            stations_by_name[name] = station

    parking_data = []

    for station in stations_by_name.values():
        # Get coordinates
        coords = station.get("scoordinate", {})
        lat = coords.get("y")
        lon = coords.get("x")

        # Filter out Bolzano stations (latitude < 46.55)
        if lat and lat < MIN_LATITUDE:
            continue

        # Extract station info
        name = station.get("sname", "Unknown")
        source = station.get("sorigin", "Unknown")

        # Get availability from mvalue (measurement value)
        available = station.get("mvalue")
        if available is not None:
            available = int(available)

        # Get capacity from metadata
        metadata = station.get("smetadata", {})
        capacity = metadata.get("capacity", 0)

        # Get measurement timestamp
        mtime = station.get("mvalidtime")

        # Extract location and region
        location = extract_location(name)
        region = extract_region(location)

        entry = {
            "timestamp": timestamp,
            "name": name,
            "available": available if available is not None else "N/A",
            "capacity": capacity if capacity else "N/A",
            "location": location,
            "region": region,
            "source": source,
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

    fieldnames = ["timestamp", "name", "available", "capacity", "location", "region",
                  "source", "latitude", "longitude", "data_timestamp", "status"]
    existing_data = []

    # Read existing data if file exists (skip comment lines)
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", newline="", encoding="utf-8") as f:
            lines = f.readlines()
            data_lines = [line for line in lines if not line.startswith('#')]
            if data_lines:
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
    print(f"[{datetime.now()}] Fetching Dolomites parking data from Open Data Hub API...")
    data = fetch_parking_data()

    if data:
        save_to_csv(data)

        # Group by region for display
        regions = {}
        for entry in data:
            region = entry.get('region', 'Other')
            if region not in regions:
                regions[region] = []
            regions[region].append(entry)

        for region in sorted(regions.keys()):
            print(f"\n=== {region} ===")
            print(f"{'Station Name':<50} {'Free':>6} {'Cap':>6} {'Location':<15}")
            print("-" * 85)
            for entry in sorted(regions[region], key=lambda x: x['name']):
                avail = entry.get('available', 'N/A')
                cap = entry.get('capacity', 'N/A')
                print(f"{entry['name']:<50} {str(avail):>6} {str(cap):>6} {entry['location']:<15}")
    else:
        print(f"[{datetime.now()}] No data retrieved or error occurred")

    return data


def run_continuous():
    """Run the scraper continuously."""
    print("=" * 85)
    print("Dolomites Region Parking Scraper (API Version)")
    print("Coverage: Val Gardena, Brunico, Bressanone")
    print(f"Source: South Tyrol Open Data Hub")
    print(f"Collecting data every {INTERVAL_MINUTES} minutes")
    print(f"Data saved to: {DATA_FILE}")
    print("Press Ctrl+C to stop")
    print("=" * 85 + "\n")

    try:
        while True:
            run_once()
            print(f"\nNext scrape in {INTERVAL_MINUTES} minutes...\n")
            time.sleep(INTERVAL_MINUTES * 60)
    except KeyboardInterrupt:
        print("\n\nScraper stopped by user.")
        print(f"Data saved in: {DATA_FILE}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--once":
        run_once()
    else:
        run_continuous()
