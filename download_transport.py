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

DATA_DIR = Path(__file__).parent / "data" / "transport"
MIN_LATITUDE = 46.49  # Filter to Dolomites region (include Bolzano)

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
# NOTE: Order matters! More specific matches must come before general ones
LOCATION_MAP = {
    # Val Gardena
    "ortisei": "St. Ulrich", "urtijei": "St. Ulrich", "st. ulrich": "St. Ulrich",
    "s. cristina": "St. Christina", "st. christina": "St. Christina", "santa cristina": "St. Christina",
    "siusi": "Siusi",  # Must come before "wolkenstein" to avoid misclassifying "Siusi, Piazza Oswald von Wolkenstein"
    "selva val gardena": "Wolkenstein", "selva gardena": "Wolkenstein",  # More specific match first
    "selva,": "Wolkenstein",  # Match "Selva, " (with comma) for actual Selva stops
    "wolkenstein": "Wolkenstein",
    "plan de gralba": "Wolkenstein", "dantercepies": "Wolkenstein",
    # Puster Valley
    "anterselva": "Rasen-Antholz", "antholz": "Rasen-Antholz",  # FIX: Add before generic "selva"
    "rasun": "Rasen-Antholz", "rasen": "Rasen-Antholz",
    "valdaora": "Valdaora", "olang": "Valdaora",
    "brunico": "Brunico", "bruneck": "Brunico",
    "dobbiaco": "Toblach", "toblach": "Toblach",
    "san candido": "Innichen", "innichen": "Innichen",
    # Isarco Valley
    "bressanone": "Bressanone", "brixen": "Bressanone",
    "chiusa": "Klausen", "klausen": "Klausen",
    "ponte gardena": "Ponte Gardena", "waidbruck": "Ponte Gardena",
    # Bolzano
    "bolzano": "Bolzano", "bozen": "Bolzano",
    # Alta Badia
    "corvara": "Corvara", "la villa": "La Villa", "badia": "Badia",
    "san cassiano": "San Cassiano",
    # Fassa Valley
    "canazei": "Canazei", "campitello": "Campitello",
    "pozza di fassa": "Pozza di Fassa", "moena": "Moena",
}

REGION_MAP = {
    "St. Ulrich": "Val Gardena", "St. Christina": "Val Gardena", "Wolkenstein": "Val Gardena",
    "Rasen-Antholz": "Puster Valley", "Valdaora": "Puster Valley",
    "Brunico": "Puster Valley", "Toblach": "Puster Valley", "Innichen": "Puster Valley",
    "Bressanone": "Isarco Valley", "Klausen": "Isarco Valley", "Ponte Gardena": "Isarco Valley",
    "Bolzano": "Bolzano",
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
        trip_route_map = {}

        for row in reader:
            trip_id = row.get("trip_id", "")
            trip_route_map[trip_id] = row.get("route_id", "")

            trips[trip_id] = {
                "trip_id": trip_id,
                "route_id": row.get("route_id", ""),
                "service_id": row.get("service_id", ""),
                "trip_headsign": row.get("trip_headsign", ""),
                "direction_id": row.get("direction_id", ""),
                "shape_id": row.get("shape_id", ""),
            }

    print(f"Found {len(trips)} trips")
    return trips, trip_route_map


def parse_stop_times(gtfs_zip, dolomites_stops, dolomites_trips):
    """Parse stop_times.txt and filter to Dolomites stops only."""
    print("Parsing stop times (schedules)...")

    dolomites_stop_ids = set(dolomites_stops.keys())
    dolomites_trip_ids = set(dolomites_trips.keys())
    stop_times = []

    with gtfs_zip.open("stop_times.txt") as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))

        for row in reader:
            trip_id = row.get("trip_id", "")
            stop_id = row.get("stop_id", "")

            # Only include stop times for Dolomites trips and stops
            if trip_id in dolomites_trip_ids and stop_id in dolomites_stop_ids:
                stop_times.append({
                    "trip_id": trip_id,
                    "arrival_time": row.get("arrival_time", ""),
                    "departure_time": row.get("departure_time", ""),
                    "stop_id": stop_id,
                    "stop_sequence": row.get("stop_sequence", ""),
                    "pickup_type": row.get("pickup_type", "0"),
                    "drop_off_type": row.get("drop_off_type", "0"),
                })

    print(f"Found {len(stop_times):,} stop times for Dolomites region")
    return stop_times


def parse_calendar(gtfs_zip):
    """Parse calendar.txt for service schedules."""
    print("Parsing service calendar...")

    calendar_entries = []

    with gtfs_zip.open("calendar.txt") as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))

        skipped = 0
        for row in reader:
            if not row.get("start_date", "").strip() or not row.get("end_date", "").strip():
                skipped += 1
                continue  # skip corrupt entries with missing dates
            calendar_entries.append({
                "service_id": row.get("service_id", ""),
                "monday": row.get("monday", "0"),
                "tuesday": row.get("tuesday", "0"),
                "wednesday": row.get("wednesday", "0"),
                "thursday": row.get("thursday", "0"),
                "friday": row.get("friday", "0"),
                "saturday": row.get("saturday", "0"),
                "sunday": row.get("sunday", "0"),
                "start_date": row.get("start_date", ""),
                "end_date": row.get("end_date", ""),
            })
        if skipped:
            print(f"  Skipped {skipped:,} corrupt calendar rows (missing dates)")

    print(f"Found {len(calendar_entries):,} service calendars")
    return calendar_entries


def parse_calendar_dates(gtfs_zip):
    """Parse calendar_dates.txt for service exceptions."""
    print("Parsing service calendar exceptions...")

    calendar_dates = []

    with gtfs_zip.open("calendar_dates.txt") as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))

        skipped = 0
        for row in reader:
            if not row.get("date", "").strip() or not row.get("exception_type", "").strip():
                skipped += 1
                continue  # skip corrupt entries with missing date/exception_type
            calendar_dates.append({
                "service_id": row.get("service_id", ""),
                "date": row.get("date", ""),
                "exception_type": row.get("exception_type", ""),
            })
        if skipped:
            print(f"  Skipped {skipped:,} corrupt calendar exception rows")

    print(f"Found {len(calendar_dates):,} calendar exceptions")
    return calendar_dates


def find_routes_serving_stops(gtfs_zip, dolomites_stops, trip_route_map, routes):
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
                if trip_id in trip_route_map:
                    route_ids_serving_dolomites.add(trip_route_map[trip_id])

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


def save_trips_csv(trips, output_file):
    """Save trips to CSV."""
    output_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["trip_id", "route_id", "service_id", "trip_headsign", "direction_id", "shape_id"]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        sorted_trips = sorted(trips.values(), key=lambda x: (x["route_id"], x["trip_id"]))
        writer.writerows(sorted_trips)

    print(f"Saved {len(trips):,} trips to {output_file}")


def save_stop_times_csv(stop_times, output_file):
    """Save stop times to CSV."""
    output_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence", "pickup_type", "drop_off_type"]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        sorted_times = sorted(stop_times, key=lambda x: (x["trip_id"], int(x.get("stop_sequence", "0") or "0")))
        writer.writerows(sorted_times)

    print(f"Saved {len(stop_times):,} stop times to {output_file}")


def save_calendar_csv(calendar_entries, output_file):
    """Save service calendar to CSV."""
    output_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["service_id", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "start_date", "end_date"]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(calendar_entries)

    print(f"Saved {len(calendar_entries):,} calendar entries to {output_file}")


def save_calendar_dates_csv(calendar_dates, output_file):
    """Save calendar exceptions to CSV."""
    output_file.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["service_id", "date", "exception_type"]

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        sorted_dates = sorted(calendar_dates, key=lambda x: (x["date"], x["service_id"]))
        writer.writerows(sorted_dates)

    print(f"Saved {len(calendar_dates):,} calendar exceptions to {output_file}")


def refresh_gtfs_data():
    """Download and parse GTFS data, saving to CSV files. Returns True on success."""
    # Download GTFS
    gtfs_zip = download_gtfs()
    print()

    # Parse basic data
    stops = parse_stops(gtfs_zip)
    routes = parse_routes(gtfs_zip)
    agencies = parse_agencies(gtfs_zip)
    trips, trip_route_map = parse_trips(gtfs_zip)
    print()

    # Find routes and trips serving Dolomites
    dolomites_routes = find_routes_serving_stops(gtfs_zip, stops, trip_route_map, routes)

    # Filter trips to only those serving Dolomites
    dolomites_trip_ids = {trip_id for trip_id, route_id in trip_route_map.items()
                          if route_id in dolomites_routes}
    dolomites_trips = {tid: trips[tid] for tid in dolomites_trip_ids if tid in trips}
    print(f"Found {len(dolomites_trips):,} trips serving Dolomites")
    print()

    # Parse schedule data
    stop_times = parse_stop_times(gtfs_zip, stops, dolomites_trips)
    calendar = parse_calendar(gtfs_zip)
    calendar_dates = parse_calendar_dates(gtfs_zip)
    print()

    # Save to CSV
    print("Saving data files...")
    save_stops_csv(stops, DATA_DIR / "transport_stops.csv")
    save_routes_csv(dolomites_routes, agencies, DATA_DIR / "transport_routes.csv")
    save_trips_csv(dolomites_trips, DATA_DIR / "transport_trips.csv")
    save_stop_times_csv(stop_times, DATA_DIR / "transport_stop_times.csv")
    save_calendar_csv(calendar, DATA_DIR / "transport_calendar.csv")
    save_calendar_dates_csv(calendar_dates, DATA_DIR / "transport_calendar_dates.csv")

    print(f"\nRefresh complete: {len(stops)} stops, {len(dolomites_routes)} routes, "
          f"{len(stop_times):,} stop times")
    return True


def main():
    """Download and parse GTFS data."""
    print("=" * 60)
    print("South Tyrol Public Transport Data Downloader")
    print("=" * 60)
    print()

    refresh_gtfs_data()

    print()
    print("=" * 60)
    print("Download Complete!")
    print("=" * 60)
    print(f"\nFiles saved to: {DATA_DIR}")
    print()


if __name__ == "__main__":
    main()
