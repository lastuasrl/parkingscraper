#!/usr/bin/env python3
"""
Download historical parking data from Open Data Hub API.
Fetches all available historical data (approximately 1 month retention).

IMPORTANT: This script now MERGES with existing data instead of overwriting.
- Checks for existing CSV file
- Only downloads dates that are missing
- Safely merges new data with existing data
- Deduplicates based on timestamp + name
"""

import requests
import csv
from datetime import datetime, timedelta
from pathlib import Path
import time
import sys
import pandas as pd

API_BASE = "https://mobility.api.opendatahub.com/v2/flat/ParkingStation/free"
MIN_LATITUDE = 46.55  # Exclude Bolzano stations

DATA_FILE = Path(__file__).parent / "data" / "parking_data_dolomites.csv"

CSV_HEADER_COMMENT = """# Dolomites Region Parking Data (Historical + Live)
# Source: South Tyrol Open Data Hub
# API: https://mobility.api.opendatahub.com/v2/
# Coverage: Val Gardena, Brunico, Bressanone
# Includes historical data from API
#
"""

# Location mapping based on station names
LOCATION_MAP = {
    "danterc": "Wolkenstein", "sciuz": "Wolkenstein", "vallunga": "Wolkenstein",
    "langental": "Wolkenstein", "seceda": "St. Ulrich", "setil": "St. Ulrich",
    "mont s": "St. Ulrich", "central": "St. Ulrich", "posta": "St. Ulrich",
    "pana": "St. Christina", "monte pana": "St. Christina", "cristauta": "St. Christina",
    "iman": "St. Christina", "brunico": "Brunico", "bruneck": "Brunico",
    "bressanone": "Bressanone", "brixen": "Bressanone",
}

REGION_MAP = {
    "Wolkenstein": "Val Gardena", "St. Ulrich": "Val Gardena", "St. Christina": "Val Gardena",
    "Brunico": "Puster Valley Gateway", "Bressanone": "Isarco Valley Gateway",
}


def extract_location(station_name):
    name_lower = station_name.lower()
    for keyword, location in LOCATION_MAP.items():
        if keyword in name_lower:
            return location
    return "Dolomites"


def extract_region(location):
    return REGION_MAP.get(location, "Other")


def fetch_day(date_from, date_to):
    """Fetch all data for a single day with pagination."""
    all_records = []
    offset = 0
    limit = 200

    while True:
        url = f"{API_BASE}/{date_from}/{date_to}"
        params = {
            "limit": limit,
            "offset": offset,
            "where": "sorigin.in.(GARDENA,skidata)",
            "shownull": "false",
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
        except Exception as e:
            print(f"  Error fetching {date_from}: {e}")
            break

        records = data.get("data", [])
        if not records:
            break

        all_records.extend(records)

        if len(records) < limit:
            break

        offset += limit
        time.sleep(0.1)  # Rate limiting

    return all_records


def process_records(records):
    """Convert API records to CSV format."""
    processed = []

    for record in records:
        coords = record.get("scoordinate", {})
        lat = coords.get("y")
        lon = coords.get("x")

        # Filter out Bolzano stations
        if lat and lat < MIN_LATITUDE:
            continue

        name = record.get("sname", "Unknown")
        source = record.get("sorigin", "Unknown")
        available = record.get("mvalue")
        if available is not None:
            available = int(available)

        metadata = record.get("smetadata", {})
        capacity = metadata.get("capacity", 0)
        mtime = record.get("mvalidtime")

        # Use measurement time as timestamp (historical data)
        if mtime:
            # Convert API timestamp format to ISO
            timestamp = mtime.replace(" ", "T").split("+")[0]
        else:
            timestamp = datetime.now().isoformat()

        location = extract_location(name)
        region = extract_region(location)

        processed.append({
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
        })

    return processed


def get_existing_dates(csv_file):
    """Read existing CSV and return set of dates that already have data."""
    if not csv_file.exists():
        return set()

    try:
        # Read CSV, skip comment lines
        df = pd.read_csv(csv_file, comment='#')
        if df.empty:
            return set()

        # Parse timestamps and extract dates
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
        dates = df['timestamp'].dt.date.dropna().unique()
        print(f"Found existing data for {len(dates)} dates ({dates.min()} to {dates.max()})")
        return set(dates)
    except Exception as e:
        print(f"Warning: Could not read existing CSV: {e}")
        return set()


def load_existing_data(csv_file):
    """Load all existing records from CSV."""
    if not csv_file.exists():
        return []

    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            # Skip comment lines
            lines = [line for line in f if not line.startswith('#')]

        reader = csv.DictReader(lines)
        existing = list(reader)
        print(f"Loaded {len(existing)} existing records")
        return existing
    except Exception as e:
        print(f"Warning: Could not load existing data: {e}")
        return []


def download_historical(start_date=None, end_date=None, skip_existing=True):
    """Download all historical data from API."""
    if end_date is None:
        end_date = datetime.now().date()
    if start_date is None:
        # Start from Dec 1, 2024 (known data availability)
        start_date = datetime(2024, 12, 1).date()

    # Check for existing data
    existing_dates = get_existing_dates(DATA_FILE) if skip_existing else set()

    print(f"Downloading historical data from {start_date} to {end_date}")
    if existing_dates:
        print(f"Skipping {len(existing_dates)} dates that already exist")
    print("=" * 60)

    all_data = []
    current = start_date
    skipped_count = 0

    while current <= end_date:
        # Skip dates that already exist
        if current in existing_dates:
            skipped_count += 1
            current += timedelta(days=1)
            continue
        next_day = current + timedelta(days=1)
        date_from = current.strftime("%Y-%m-%d")
        date_to = next_day.strftime("%Y-%m-%d")

        print(f"Fetching {date_from}...", end=" ", flush=True)
        records = fetch_day(date_from, date_to)

        if records:
            processed = process_records(records)
            all_data.extend(processed)
            print(f"{len(processed)} records")
        else:
            print("no data")

        current = next_day
        time.sleep(0.2)  # Rate limiting between days

    print("=" * 60)
    print(f"Total records downloaded: {len(all_data)}")
    if skipped_count > 0:
        print(f"Skipped {skipped_count} dates that already exist")

    return all_data


def save_to_csv(data, output_file=None, merge_with_existing=True):
    """Save data to CSV file, merging with existing data if present."""
    if output_file is None:
        output_file = DATA_FILE

    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Load existing data if merging
    all_data = data.copy()
    if merge_with_existing and output_file.exists():
        existing = load_existing_data(output_file)
        print(f"Merging {len(data)} new records with {len(existing)} existing records...")
        all_data.extend(existing)

    # Sort by timestamp, then by name
    all_data.sort(key=lambda x: (x["timestamp"], x["name"]))

    # Remove duplicates (same timestamp + name)
    seen = set()
    unique_data = []
    for record in all_data:
        key = (record["timestamp"], record["name"])
        if key not in seen:
            seen.add(key)
            unique_data.append(record)

    fieldnames = ["timestamp", "name", "available", "capacity", "location", "region",
                  "source", "latitude", "longitude", "data_timestamp", "status"]

    # Write combined data
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        f.write(CSV_HEADER_COMMENT)
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(unique_data)

    print(f"Saved {len(unique_data)} unique records to {output_file}")
    if merge_with_existing:
        print(f"  ({len(data)} new + {len(unique_data) - len(data)} existing after deduplication)")
    return unique_data


if __name__ == "__main__":
    # Parse optional date arguments
    start = None
    end = None

    if len(sys.argv) > 1:
        start = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
    if len(sys.argv) > 2:
        end = datetime.strptime(sys.argv[2], "%Y-%m-%d").date()

    data = download_historical(start, end)

    if data:
        save_to_csv(data)
        print("\nDone! Run 'python plot_parking_data.py' to generate plots.")
    else:
        print("\nNo data downloaded.")
