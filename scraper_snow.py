#!/usr/bin/env python3
"""
South Tyrol Snow Report Scraper
Collects snow and lift status data from South Tyrol Open Data Hub API.
Covers 31 ski areas including Dolomiti Superski, Ortler Skiarena, and more.
https://opendatahub.com/
"""

import requests
import csv
import io
from datetime import datetime
from pathlib import Path
import time
import sys

API_URL = "https://tourism.api.opendatahub.com/v1/Weather/SnowReport"
API_PARAMS = {
    "language": "en"
}

DATA_FILE = Path(__file__).parent / "data" / "snow_data.csv"
INTERVAL_MINUTES = 30  # Snow data changes less frequently than parking

CSV_HEADER_COMMENT = """# South Tyrol Snow Report Data
# Source: South Tyrol Open Data Hub (Tourism API)
# API: https://tourism.api.opendatahub.com/v1/Weather/SnowReport
# Coverage: 31 ski areas (Dolomiti Superski, Ortler Skiarena, etc.)
# Update frequency: Data updated by ski areas, typically daily
# Scrape interval: Every 30 minutes
#
"""

# Ski region classification
REGION_MAP = {
    "Val Gardena - Alpe di Siusi": "Dolomiti Superski",
    "Alta Badia": "Dolomiti Superski",
    "Kronplatz": "Dolomiti Superski",
    "3 Zinnen Dolomiten": "Dolomiti Superski",
    "Carezza Dolomites": "Dolomiti Superski",
    "Obereggen": "Dolomiti Superski",
    "Gitschberg - Jochtal": "Dolomiti Superski",
    "Plose": "Dolomiti Superski",
    "Jochgrimm": "Dolomiti Superski",
    "Schöneben": "Ortler Skiarena",
    "Watles": "Ortler Skiarena",
    "Trafoi": "Ortler Skiarena",
    "Schwemmalm": "Ortler Skiarena",
    "Reinswald": "Ortler Skiarena",
    "Rittner Horn": "Ortler Skiarena",
    "Pfelders": "Ortler Skiarena",
    "Sulden": "Ortler Skiarena",
    "Vigiljoch": "Ortler Skiarena",
    "Rosskopf": "Ortler Skiarena",
    "Ladurns": "Ortler Skiarena",
    "Meran 2000": "Ortler Skiarena",
    "Alpin Arena Schnals": "Ortler Skiarena",
    "Speikboden": "Skiworld Ahrntal",
    "Klausberg": "Skiworld Ahrntal",
    "Ratschings": "Other",
}


def get_region(ski_area_name):
    """Get ski region for a ski area."""
    for key, region in REGION_MAP.items():
        if key.lower() in ski_area_name.lower():
            return region
    return "Other"


def fetch_snow_data():
    """Fetch snow report data from Open Data Hub API."""
    headers = {
        "Accept": "application/json",
        "User-Agent": "SouthTyrolSnowScraper/1.0"
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

    if not isinstance(data, list):
        print(f"[{datetime.now()}] Unexpected API response format")
        return None

    timestamp = datetime.now().isoformat()
    snow_data = []

    for area in data:
        # Get ski area info
        name = area.get("Areaname", "Unknown")
        ski_region = area.get("Skiregion", "")

        # Get snow measurements from measuring points
        measuring_points = area.get("Measuringpoints", [])
        snow_valley = None
        snow_mountain = None
        new_snow = None
        temperature = None
        last_update = None

        for mp in measuring_points:
            # Get snow heights (convert to int, handling strings)
            mp_snow_raw = mp.get("SnowHeight")
            mp_snow = None
            if mp_snow_raw:
                try:
                    mp_snow = int(float(str(mp_snow_raw)))
                except (ValueError, TypeError):
                    pass

            if mp_snow:
                # Assume first is valley, max is mountain
                if snow_valley is None:
                    snow_valley = mp_snow
                if mp_snow > (snow_mountain or 0):
                    snow_mountain = mp_snow

            # Get new snow
            mp_new_raw = mp.get("newSnowHeight")
            if mp_new_raw:
                try:
                    mp_new = int(float(str(mp_new_raw)))
                    if new_snow is None or mp_new > new_snow:
                        new_snow = mp_new
                except (ValueError, TypeError):
                    pass

            # Get temperature
            mp_temp = mp.get("Temperature")
            if mp_temp is not None and temperature is None:
                try:
                    temperature = float(str(mp_temp))
                except (ValueError, TypeError):
                    pass

            # Get last update
            mp_date = mp.get("LastUpdate")
            if mp_date and mp_date != "0001-01-01T00:00:00":
                if last_update is None or mp_date > last_update:
                    last_update = mp_date

        # Get lift and slope status (lowercase field names, convert to int)
        def safe_int(val):
            if val is None:
                return 0
            try:
                return int(float(str(val)))
            except (ValueError, TypeError):
                return 0

        lifts_open = safe_int(area.get("openskilift"))
        lifts_total = safe_int(area.get("totalskilift"))
        slopes_open = safe_int(area.get("openskislopes"))
        slopes_total = safe_int(area.get("totalskislopes"))
        slopes_km_open = area.get("openskislopeskm") or "N/A"
        slopes_km_total = area.get("SkiAreaSlopeKm") or "N/A"

        # Cross-country and toboggan
        xc_open = safe_int(area.get("opentracks"))
        xc_total = safe_int(area.get("totaltracks"))
        sledge_open = safe_int(area.get("openslides"))
        sledge_total = safe_int(area.get("totalslides"))

        # Skating - not in this API format
        skating_open = 0
        skating_total = 0

        # Get webcam URL if available
        webcam_url = None
        webcams = area.get("WebcamUrl", [])
        if webcams and len(webcams) > 0:
            webcam_url = webcams[0]

        # Use API-provided region, fallback to our mapping
        region = ski_region if ski_region else get_region(name)

        entry = {
            "timestamp": timestamp,
            "ski_area": name,
            "region": region,
            "snow_valley_cm": snow_valley if snow_valley else "N/A",
            "snow_mountain_cm": snow_mountain if snow_mountain else "N/A",
            "new_snow_cm": new_snow if new_snow else "N/A",
            "temperature_c": temperature if temperature else "N/A",
            "lifts_open": lifts_open,
            "lifts_total": lifts_total,
            "slopes_open": slopes_open,
            "slopes_total": slopes_total,
            "slopes_km_open": slopes_km_open if slopes_km_open else "N/A",
            "slopes_km_total": slopes_km_total if slopes_km_total else "N/A",
            "xc_tracks_open": xc_open,
            "xc_tracks_total": xc_total,
            "sledge_runs_open": sledge_open,
            "sledge_runs_total": sledge_total,
            "skating_open": skating_open,
            "skating_total": skating_total,
            "last_update": last_update if last_update else "N/A",
            "webcam_url": webcam_url if webcam_url else "N/A",
            "status": "OK"
        }

        snow_data.append(entry)

    print(f"[{datetime.now()}] Retrieved {len(snow_data)} ski areas from API")
    return snow_data


def save_to_csv(data):
    """Append snow data to CSV file."""
    if not data:
        return

    fieldnames = ["timestamp", "ski_area", "region", "snow_valley_cm", "snow_mountain_cm",
                  "new_snow_cm", "temperature_c", "lifts_open", "lifts_total",
                  "slopes_open", "slopes_total", "slopes_km_open", "slopes_km_total",
                  "xc_tracks_open", "xc_tracks_total", "sledge_runs_open", "sledge_runs_total",
                  "skating_open", "skating_total", "last_update", "webcam_url", "status"]
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

    # Sort by timestamp, then by ski area
    existing_data.sort(key=lambda x: (x["timestamp"], x["ski_area"]))

    # Write all data back with header comment
    with open(DATA_FILE, "w", newline="", encoding="utf-8") as f:
        f.write(CSV_HEADER_COMMENT)
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(existing_data)

    print(f"[{datetime.now()}] Saved {len(data)} entries ({len(existing_data)} total) to {DATA_FILE}")


def run_once():
    """Run the scraper once and save data."""
    print(f"[{datetime.now()}] Fetching snow report data from Open Data Hub API...")
    data = fetch_snow_data()

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
            print(f"{'Ski Area':<35} {'Snow(V)':<8} {'Snow(M)':<8} {'Lifts':<10} {'Slopes':<10}")
            print("-" * 80)
            for entry in sorted(regions[region], key=lambda x: x['ski_area']):
                snow_v = entry.get('snow_valley_cm', 'N/A')
                snow_m = entry.get('snow_mountain_cm', 'N/A')
                lifts = f"{entry.get('lifts_open', 0)}/{entry.get('lifts_total', 0)}"
                slopes = f"{entry.get('slopes_open', 0)}/{entry.get('slopes_total', 0)}"
                print(f"{entry['ski_area']:<35} {str(snow_v):<8} {str(snow_m):<8} {lifts:<10} {slopes:<10}")
    else:
        print(f"[{datetime.now()}] No data retrieved or error occurred")

    return data


def run_continuous():
    """Run the scraper continuously."""
    print("=" * 80)
    print("South Tyrol Snow Report Scraper")
    print("Coverage: 31 ski areas (Dolomiti Superski, Ortler Skiarena, etc.)")
    print(f"Source: South Tyrol Open Data Hub")
    print(f"Collecting data every {INTERVAL_MINUTES} minutes")
    print(f"Data saved to: {DATA_FILE}")
    print("Press Ctrl+C to stop")
    print("=" * 80 + "\n")

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
