#!/usr/bin/env python3
"""
Val Gardena Parking Scraper
Collects parking availability data every 5 minutes from public parking places.
"""

import requests
from bs4 import BeautifulSoup
import csv
import io
import re
from datetime import datetime
from pathlib import Path
import time
import sys

BASE_URL = "https://www.valgardena.it/de/oeffentliche-parkplaetze/"
DATA_FILE = Path(__file__).parent / "data" / "parking_data.csv"
INTERVAL_MINUTES = 5  # Source database updates every 1-2 minutes (real-time AESYS sensors)
MAX_PAGES = 10  # Safety limit for pagination


def fetch_page(url, headers):
    """Fetch a single page and return soup object."""
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        response.encoding = 'utf-8'
        return BeautifulSoup(response.text, "html.parser")
    except requests.RequestException as e:
        print(f"[{datetime.now()}] Error fetching {url}: {e}")
        return None


def get_total_pages(soup):
    """Extract total number of pages from pagination info (e.g., 'Seite 1 von 6')."""
    page_text = soup.get_text()
    match = re.search(r'Seite\s+\d+\s+von\s+(\d+)', page_text)
    if match:
        return int(match.group(1))
    return 1


def extract_parking_from_page(soup, timestamp):
    """Extract all parking entries from a single page."""
    parking_data = []
    page_text = soup.get_text(separator=' ', strip=True)

    # Pattern for availability
    availability_pattern = re.compile(r'Verfügbare Parkplätze:\s*(-?\d+)', re.IGNORECASE)

    # Find parking cards - they typically have titles like "Parkplatz X" or "Parkgarage X"
    # Look for heading elements that contain parking names
    parking_headings = soup.find_all(lambda tag:
        tag.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'a'] and
        tag.get_text() and
        re.search(r'(Parkplatz|Parkgarage|Parkhaus|Centrum Parkgarage)', tag.get_text(), re.IGNORECASE)
    )

    seen_names = set()

    for heading in parking_headings:
        name = heading.get_text(strip=True)

        # Clean up the name - remove navigation artifacts
        name = re.sub(r'\s+', ' ', name).strip()

        # Skip if we've already seen this parking lot (duplicates across pages)
        if name in seen_names or not name:
            continue
        seen_names.add(name)

        entry = {
            "timestamp": timestamp,
            "name": name,
            "available": "N/A",
            "location": extract_location(name),
            "status": "No availability data"
        }

        # Strategy 1: Search in parent container
        found = False
        curr = heading
        for _ in range(8):  # Walk up the DOM tree
            if not curr:
                break
            container_text = curr.get_text(" ", strip=True)

            # Only use this container if it has exactly one availability number
            # to avoid mixing data from adjacent parking lots
            matches = list(availability_pattern.finditer(container_text))
            if len(matches) == 1:
                entry["available"] = int(matches[0].group(1))
                entry["status"] = "OK"
                found = True
                break
            elif len(matches) > 1:
                # Multiple matches - container too large, try to find the closest one
                name_pos = container_text.find(name)
                if name_pos >= 0:
                    closest = min(matches, key=lambda m: abs(m.start() - name_pos))
                    # Only use if reasonably close (within 500 chars)
                    if abs(closest.start() - name_pos) < 500:
                        entry["available"] = int(closest.group(1))
                        entry["status"] = "OK"
                        found = True
                        break
            curr = curr.parent

        # Strategy 2: Context search in full page text
        if not found:
            # Escape special regex chars in name for searching
            safe_name = re.escape(name)
            name_match = re.search(safe_name, page_text)
            if name_match:
                idx = name_match.start()
                # Search in a window around the name
                context = page_text[max(0, idx-100):idx+400]
                avail_match = availability_pattern.search(context)
                if avail_match:
                    entry["available"] = int(avail_match.group(1))
                    entry["status"] = "OK (context)"

        parking_data.append(entry)

    return parking_data


def fetch_parking_data():
    """Fetch and parse parking data from all pages of the website."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8"
    }

    timestamp = datetime.now().isoformat()
    all_parking_data = []
    seen_names = set()

    # Fetch first page to get total page count
    print(f"[{datetime.now()}] Fetching page 1...")
    soup = fetch_page(BASE_URL, headers)
    if not soup:
        return None

    total_pages = get_total_pages(soup)
    print(f"[{datetime.now()}] Found {total_pages} pages of parking data")

    # Extract from first page
    page_data = extract_parking_from_page(soup, timestamp)
    for entry in page_data:
        if entry["name"] not in seen_names:
            seen_names.add(entry["name"])
            all_parking_data.append(entry)

    # Fetch remaining pages
    for page_num in range(2, min(total_pages + 1, MAX_PAGES + 1)):
        print(f"[{datetime.now()}] Fetching page {page_num}...")
        url = f"{BASE_URL}?page={page_num}"
        soup = fetch_page(url, headers)
        if soup:
            page_data = extract_parking_from_page(soup, timestamp)
            for entry in page_data:
                if entry["name"] not in seen_names:
                    seen_names.add(entry["name"])
                    all_parking_data.append(entry)
        time.sleep(0.5)  # Be polite to the server

    print(f"[{datetime.now()}] Found {len(all_parking_data)} unique parking locations")
    return all_parking_data


def extract_location(parking_name):
    """Extract location (village) from parking name."""
    name_lower = parking_name.lower()

    # St. Christina locations
    st_christina = ["iman", "monte pana", "calonia", "turnhalle", "cristauta", "cendevaves", "dosses"]
    for loc in st_christina:
        if loc in name_lower:
            return "St. Christina"

    # Wolkenstein locations
    wolkenstein = ["sciuz", "langental", "col raiser", "dantercëpies", "dantercepies",
                   "plan de gralba", "grödnerjoch", "grodner", "sellajoch", "maciaconi",
                   "continental", "eisstadion", "saslong", "bacher", "kulturhaus", "wolkenstein"]
    for loc in wolkenstein:
        if loc in name_lower:
            return "Wolkenstein"

    # St. Ulrich locations
    st_ulrich = ["central", "seceda", "sëuc", "seuc", "mont sëuc", "setil", "fever",
                 "tresval", "cavallino", "mar dolomit", "speckkeller", "gemeinde",
                 "bibliothek", "tennis", "mulin", "ingram", "edda", "plaza",
                 "nives", "ciampinoi", "ciampinëi", "ruacia", "fraz", "taiadices",
                 "chemun", "isgla", "la tambra"]
    for loc in st_ulrich:
        if loc in name_lower:
            return "St. Ulrich"

    return "Unknown"


CSV_HEADER_COMMENT = """# Val Gardena Parking Data
# Source: https://www.valgardena.it/de/oeffentliche-parkplaetze/
# Database: AESYS real-time parking sensors
# Update frequency: Source updates every 1-2 minutes (real-time)
# Scrape interval: Every 5 minutes
#
"""


def save_to_csv(data):
    """Append parking data to CSV file, sorted by timestamp then name."""
    if not data:
        return

    fieldnames = ["timestamp", "name", "available", "location", "status"]
    existing_data = []

    # Read existing data if file exists (skip comment lines)
    if DATA_FILE.exists():
        with open(DATA_FILE, "r", newline="", encoding="utf-8") as f:
            # Skip comment lines at the beginning
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

    print(f"[{datetime.now()}] Saved {len(data)} new entries ({len(existing_data)} total) to {DATA_FILE}")


def run_once():
    """Run the scraper once and save data."""
    print(f"[{datetime.now()}] Fetching parking data...")
    data = fetch_parking_data()

    if data:
        save_to_csv(data)
        print(f"\n{'Parking Location':<35} {'Available':>10} {'Location':<15}")
        print("-" * 65)
        for entry in data:
            avail = entry.get('available')
            avail_str = str(avail) if avail is not None else "N/A"
            print(f"{entry['name']:<35} {avail_str:>10} {entry['location']:<15}")
    else:
        print(f"[{datetime.now()}] No data found or error occurred")

    return data


def run_continuous():
    """Run the scraper continuously every 5 minutes."""
    print("=" * 65)
    print("Val Gardena Parking Scraper")
    print(f"Collecting data every {INTERVAL_MINUTES} minutes")
    print(f"Data saved to: {DATA_FILE}")
    print("Press Ctrl+C to stop")
    print("=" * 65 + "\n")

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
