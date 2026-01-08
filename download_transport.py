#!/usr/bin/env python3
"""
Download and parse South Tyrol public transport schedules from GTFS.
Source: Open Data Hub GTFS API - STA (Südtirol Transportstrukturen AG)
"""

import requests
import zipfile
import io
import csv
from pathlib import Path
from datetime import datetime

GTFS_API = "https://gtfs.api.opendatahub.com/v1"
DATASET_ID = "sta-time-tables"

DATA_DIR = Path(__file__).parent / "data"
MIN_LATITUDE = 46.55  # Filter to Dolomites region (exclude Bolzano)

# GTFS route types
ROUTE_TYPES = {
    0: "Tram",
    1: "Metro",
    2: "Rail",
    3: "Bus",
    4: "Ferry",
    5: "Cable Tram",
    6: "Aerial Lift",
    7: "Funicular",
    11: "Trolleybus",
    12: "Monorail",
}

# Location mapping based on stop names
LOCATION_MAP = {
    # Val Gardena
    "ortisei": "St. Ulrich", "urtijei": "St. Ulrich", "st. ulrich": "St. Ulrich",
    "s. cristina": "St. Christina", "st. christina": "St. Christina", "santa cristina": "St. Christina",
    "selva": "Wolkenstein", "wolkenstein": "Wolkenstein",
    "plan de gralba": "Wolkenstein", "dantercepies": "Wolkenstein",
    # Puster Valley
    "brunico": "Brunico", "bruneck": "Brunico",
    "dobbiaco": "Toblach", "toblach": "Toblach",
    "san candido": "Innichen", "innichen": "Innichen",
    # Isarco Valley
    "bressanone": "Bressanone", "brixen": "Bressanone",
    "chiusa": "Klausen", "klausen": "Klausen",
    # Alta Badia
    "corvara": "Corvara", "la villa": "La Villa", "badia": "Badia",
    "san cassiano": "San Cassiano",
    # Fassa Valley
    "canazei": "Canazei", "campitello": "Campitello",
    "pozza di fassa": "Pozza di Fassa", "moena": "Moena",
}

REGION_MAP = {
    "St. Ulrich": "Val Gardena", "St. Christina": "Val Gardena", "Wolkenstein": "Val Gardena",
    "Brunico": "Puster Valley", "Toblach": "Puster Valley", "Innichen": "Puster Valley",
    "Bressanone": "Isarco Valley", "Klausen": "Isarco Valley",
    "Corvara": "Alta Badia", "La Villa": "Alta Badia", "Badia": "Alta Badia", "San Cassiano": "Alta Badia",
    "Canazei": "Val di Fassa", "Campitello": "Val di Fassa", "Pozza di Fassa": "Val di Fassa", "Moena": "Val di Fassa",
}


def download_gtfs():
    """Download GTFS zip file from Open Data Hub."""
    print(f"Downloading GTFS data from {DATASET_ID}...")

    url = f"{GTFS_API}/dataset/{DATASET_ID}/raw"
    response = requests.get(url, timeout=60)
    response.raise_for_status()

    print(f"Downloaded {len(response.content) / 1024 / 1024:.1f} MB")
    return zipfile.ZipFile(io.BytesIO(response.content))


def extract_location(stop_name):
    """Extract location from stop name."""
    name_lower = stop_name.lower()
    for keyword, location in LOCATION_MAP.items():
        if keyword in name_lower:
            return location
    return "Other"


def extract_region(location):
    """Get region from location."""
    return REGION_MAP.get(location, "South Tyrol")


def parse_stops(gtfs_zip):
    """Parse stops.txt and filter to Dolomites region."""
    print("Parsing stops...")

    with gtfs_zip.open("stops.txt") as f:
        # Use utf-8-sig to handle BOM
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
        stops = {}

        for row in reader:
            try:
                lat = float(row.get("stop_lat", 0))
                lon = float(row.get("stop_lon", 0))
            except (ValueError, TypeError):
                continue

            # Filter by latitude
            if lat < MIN_LATITUDE:
                continue

            stop_id = row.get("stop_id", "")
            stop_name = row.get("stop_name", "Unknown")
            location = extract_location(stop_name)
            region = extract_region(location)

            stops[stop_id] = {
                "stop_id": stop_id,
                "stop_name": stop_name,
                "stop_lat": lat,
                "stop_lon": lon,
                "location": location,
                "region": region,
            }

    print(f"Found {len(stops)} stops in Dolomites region")
    return stops


def parse_routes(gtfs_zip):
    """Parse routes.txt."""
    print("Parsing routes...")

    with gtfs_zip.open("routes.txt") as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
        routes = {}

        for row in reader:
            route_id = row.get("route_id", "")
            route_type = int(row.get("route_type", 3))

            routes[route_id] = {
                "route_id": route_id,
                "route_short_name": row.get("route_short_name", ""),
                "route_long_name": row.get("route_long_name", ""),
                "route_type": ROUTE_TYPES.get(route_type, "Unknown"),
                "agency_id": row.get("agency_id", ""),
            }

    print(f"Found {len(routes)} routes")
    return routes


def parse_agencies(gtfs_zip):
    """Parse agency.txt."""
    print("Parsing agencies...")

    with gtfs_zip.open("agency.txt") as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
        agencies = {}

        for row in reader:
            agency_id = row.get("agency_id", "")
            agencies[agency_id] = row.get("agency_name", "Unknown")

    print(f"Found {len(agencies)} agencies")
    return agencies


def parse_trips(gtfs_zip):
    """Parse trips.txt to link routes to stops."""
    print("Parsing trips...")

    with gtfs_zip.open("trips.txt") as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
        trips = {}

        for row in reader:
            trip_id = row.get("trip_id", "")
            trips[trip_id] = row.get("route_id", "")

    print(f"Found {len(trips)} trips")
    return trips


def find_routes_serving_stops(gtfs_zip, dolomites_stops, trips, routes):
    """Find which routes serve Dolomites stops via stop_times.txt."""
    print("Finding routes serving Dolomites region...")

    dolomites_stop_ids = set(dolomites_stops.keys())
    route_ids_serving_dolomites = set()

    with gtfs_zip.open("stop_times.txt") as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))

        for row in reader:
            stop_id = row.get("stop_id", "")
            if stop_id in dolomites_stop_ids:
                trip_id = row.get("trip_id", "")
                if trip_id in trips:
                    route_ids_serving_dolomites.add(trips[trip_id])

    # Filter routes
    dolomites_routes = {
        rid: routes[rid] for rid in route_ids_serving_dolomites if rid in routes
    }

    print(f"Found {len(dolomites_routes)} routes serving Dolomites")
    return dolomites_routes


def save_stops_csv(stops, output_file):
    """Save stops to CSV."""
    output_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["stop_id", "stop_name", "stop_lat", "stop_lon", "location", "region"]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        f.write(f"# Dolomites Region Public Transport Stops\n")
        f.write(f"# Source: Open Data Hub GTFS - STA\n")
        f.write(f"# Generated: {datetime.now().isoformat()}\n")
        f.write("#\n")

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        # Sort by region, then location, then name
        sorted_stops = sorted(stops.values(), key=lambda x: (x["region"], x["location"], x["stop_name"]))
        writer.writerows(sorted_stops)

    print(f"Saved {len(stops)} stops to {output_file}")


def save_routes_csv(routes, agencies, output_file):
    """Save routes to CSV."""
    output_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["route_id", "route_short_name", "route_long_name", "route_type", "agency_name"]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        f.write(f"# Dolomites Region Public Transport Routes\n")
        f.write(f"# Source: Open Data Hub GTFS - STA\n")
        f.write(f"# Generated: {datetime.now().isoformat()}\n")
        f.write("#\n")

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for route in sorted(routes.values(), key=lambda x: (x["route_type"], x["route_short_name"])):
            row = {
                "route_id": route["route_id"],
                "route_short_name": route["route_short_name"],
                "route_long_name": route["route_long_name"],
                "route_type": route["route_type"],
                "agency_name": agencies.get(route["agency_id"], "Unknown"),
            }
            writer.writerow(row)

    print(f"Saved {len(routes)} routes to {output_file}")


def main():
    """Download and parse GTFS data."""
    print("=" * 60)
    print("South Tyrol Public Transport Data Downloader")
    print("=" * 60)

    # Download GTFS
    gtfs_zip = download_gtfs()

    # Parse data
    stops = parse_stops(gtfs_zip)
    routes = parse_routes(gtfs_zip)
    agencies = parse_agencies(gtfs_zip)
    trips = parse_trips(gtfs_zip)

    # Find routes serving Dolomites
    dolomites_routes = find_routes_serving_stops(gtfs_zip, stops, trips, routes)

    # Save to CSV
    save_stops_csv(stops, DATA_DIR / "transport_stops.csv")
    save_routes_csv(dolomites_routes, agencies, DATA_DIR / "transport_routes.csv")

    print("=" * 60)
    print("Done!")

    # Print summary
    print(f"\nSummary:")
    print(f"  Stops: {len(stops)}")
    print(f"  Routes: {len(dolomites_routes)}")

    # Count by region
    region_counts = {}
    for stop in stops.values():
        region = stop["region"]
        region_counts[region] = region_counts.get(region, 0) + 1

    print(f"\nStops by region:")
    for region, count in sorted(region_counts.items(), key=lambda x: -x[1]):
        print(f"  {region}: {count}")


if __name__ == "__main__":
    main()
