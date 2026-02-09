#!/usr/bin/env python3
"""
Query public transport schedules for the Dolomites region.
Provides examples of how to work with the schedule data.
"""

import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data" / "transport"

# Load data files
print("Loading transport data...")
stops_df = pd.read_csv(DATA_DIR / "transport_stops.csv", encoding='utf-8')
routes_df = pd.read_csv(DATA_DIR / "transport_routes.csv", encoding='utf-8')
trips_df = pd.read_csv(DATA_DIR / "transport_trips.csv", encoding='utf-8')
stop_times_df = pd.read_csv(DATA_DIR / "transport_stop_times.csv", encoding='utf-8')
calendar_df = pd.read_csv(DATA_DIR / "transport_calendar.csv", encoding='utf-8')

print(f"Loaded {len(stops_df):,} stops, {len(routes_df):,} routes, {len(trips_df):,} trips, {len(stop_times_df):,} stop times")
print()


def find_stops_by_name(stop_name_query):
    """Find stops matching a name query."""
    matches = stops_df[stops_df['stop_name'].str.contains(stop_name_query, case=False, na=False)]
    return matches


def get_stop_schedule(stop_id, limit=20):
    """Get upcoming departures from a specific stop."""
    # Get stop times for this stop
    stop_schedule = stop_times_df[stop_times_df['stop_id'] == stop_id].copy()

    # Join with trips to get route info
    stop_schedule = stop_schedule.merge(trips_df[['trip_id', 'route_id', 'trip_headsign']], on='trip_id')

    # Join with routes to get route names
    stop_schedule = stop_schedule.merge(routes_df[['route_id', 'route_short_name', 'route_long_name', 'route_type']], on='route_id')

    # Sort by departure time
    stop_schedule = stop_schedule.sort_values('departure_time')

    return stop_schedule.head(limit)


def get_route_stops(route_short_name):
    """Get all stops served by a route."""
    # Find the route
    route = routes_df[routes_df['route_short_name'] == route_short_name]

    if route.empty:
        return None, None

    route_id = route.iloc[0]['route_id']

    # Find trips for this route
    route_trips = trips_df[trips_df['route_id'] == route_id]['trip_id'].unique()

    # Get stop times for these trips
    route_stop_times = stop_times_df[stop_times_df['trip_id'].isin(route_trips)]

    # Get unique stops
    unique_stop_ids = route_stop_times['stop_id'].unique()
    route_stops = stops_df[stops_df['stop_id'].isin(unique_stop_ids)]

    return route, route_stops


def get_location_routes(location_name):
    """Get all routes serving a specific location."""
    # Find stops in this location
    location_stops = stops_df[stops_df['location'].str.contains(location_name, case=False, na=False)]

    if location_stops.empty:
        return None

    # Get stop times for these stops
    location_stop_times = stop_times_df[stop_times_df['stop_id'].isin(location_stops['stop_id'])]

    # Get trips
    trip_ids = location_stop_times['trip_id'].unique()
    location_trips = trips_df[trips_df['trip_id'].isin(trip_ids)]

    # Get routes
    route_ids = location_trips['route_id'].unique()
    location_routes = routes_df[routes_df['route_id'].isin(route_ids)]

    return location_routes


def find_connections(from_location, to_location, after_time="06:00:00"):
    """Find connections between two locations."""
    # Find stops in origin location
    from_stops = stops_df[stops_df['location'].str.contains(from_location, case=False, na=False)]

    # Find stops in destination location
    to_stops = stops_df[stops_df['location'].str.contains(to_location, case=False, na=False)]

    if from_stops.empty or to_stops.empty:
        return None

    # Get departures from origin
    from_stop_times = stop_times_df[
        (stop_times_df['stop_id'].isin(from_stops['stop_id'])) &
        (stop_times_df['departure_time'] >= after_time)
    ].copy()

    # Get arrivals to destination
    to_stop_times = stop_times_df[
        stop_times_df['stop_id'].isin(to_stops['stop_id'])
    ].copy()

    # Find common trips (direct connections)
    common_trips = set(from_stop_times['trip_id']) & set(to_stop_times['trip_id'])

    connections = []
    for trip_id in common_trips:
        departure = from_stop_times[from_stop_times['trip_id'] == trip_id].iloc[0]
        arrival = to_stop_times[to_stop_times['trip_id'] == trip_id].iloc[0]

        # Get trip info
        trip_info = trips_df[trips_df['trip_id'] == trip_id].iloc[0]
        route_info = routes_df[routes_df['route_id'] == trip_info['route_id']].iloc[0]

        connections.append({
            'route': route_info['route_short_name'],
            'route_name': route_info['route_long_name'],
            'departure': departure['departure_time'],
            'arrival': arrival['arrival_time'],
            'trip_id': trip_id,
        })

    return pd.DataFrame(connections).sort_values('departure')


# ============================================
# Example Queries
# ============================================

if __name__ == "__main__":
    print("=" * 70)
    print("TRANSPORT SCHEDULE QUERY EXAMPLES")
    print("=" * 70)
    print()

    # Example 1: Find stops in Corvara
    print("1. FIND STOPS IN CORVARA")
    print("-" * 70)
    corvara_stops = find_stops_by_name("Corvara")
    print(f"Found {len(corvara_stops)} stops in Corvara:")
    print(corvara_stops[['stop_name', 'location', 'region']].head(10))
    print()

    # Example 2: Get schedule for first Corvara stop
    if not corvara_stops.empty:
        print("2. SCHEDULE FOR FIRST CORVARA STOP")
        print("-" * 70)
        first_stop = corvara_stops.iloc[0]
        print(f"Stop: {first_stop['stop_name']} (ID: {first_stop['stop_id']})")
        print()

        schedule = get_stop_schedule(first_stop['stop_id'], limit=10)
        if not schedule.empty:
            print("Next 10 departures:")
            for idx, row in schedule.iterrows():
                print(f"  {row['departure_time']:8s} - Route {row['route_short_name']:6s} to {row['trip_headsign']}")
        print()

    # Example 3: Find all routes serving Val Gardena
    print("3. ROUTES SERVING VAL GARDENA")
    print("-" * 70)
    val_gardena_routes = get_location_routes("St. Ulrich")
    if val_gardena_routes is not None:
        print(f"Found {len(val_gardena_routes)} routes serving Val Gardena:")
        for idx, route in val_gardena_routes.head(10).iterrows():
            route_name = str(route['route_long_name']) if pd.notna(route['route_long_name']) else route['route_short_name']
            print(f"  Route {route['route_short_name']:6s} - {route_name:40s} ({route['route_type']})")
    print()

    # Example 4: Find connections
    print("4. CONNECTIONS FROM CORVARA TO BADIA")
    print("-" * 70)
    connections = find_connections("Corvara", "Badia", after_time="08:00:00")
    if connections is not None and not connections.empty:
        print(f"Found {len(connections)} direct connections after 08:00:")
        for idx, conn in connections.head(5).iterrows():
            print(f"  {conn['departure']:8s} to {conn['arrival']:8s} - Route {conn['route']:6s} ({conn['route_name']})")
    else:
        print("No direct connections found")
    print()

    # Example 5: Route details
    print("5. STOPS SERVED BY ROUTE 350")
    print("-" * 70)
    route_info, route_stops = get_route_stops("350")
    if route_info is not None:
        print(f"Route: {route_info.iloc[0]['route_short_name']} - {route_info.iloc[0]['route_long_name']}")
        print(f"Type: {route_info.iloc[0]['route_type']}")
        print(f"Stops: {len(route_stops)} stops")
        print()
        print("Sample stops:")
        for idx, stop in route_stops.head(10).iterrows():
            print(f"  • {stop['stop_name']:40s} ({stop['location']})")
    print()

    print("=" * 70)
    print("Query examples completed!")
    print()
    print("Use these functions to build your superapplication:")
    print("  - find_stops_by_name(query)")
    print("  - get_stop_schedule(stop_id)")
    print("  - get_route_stops(route_short_name)")
    print("  - get_location_routes(location_name)")
    print("  - find_connections(from_location, to_location, after_time)")
    print("=" * 70)
