#!/usr/bin/env python3
"""
Val Gardena Bus Schedule & Map Application
A simple, tourist-friendly web app to explore bus schedules and stops in Val Gardena.
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from pathlib import Path
from datetime import datetime, date, time
import time as _time
import os
import math
import folium
from streamlit_folium import st_folium

# Page config
st.set_page_config(
    page_title="Val Gardena Bus Schedules",
    page_icon="\U0001f68d",
    layout="wide"
)

# Compact table styling with stable column widths
st.markdown("""<style>
    .stTable table { table-layout: fixed; width: auto !important; }
    .stTable td, .stTable th {
        padding: 4px 10px !important;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .stTable th:nth-child(1), .stTable td:nth-child(1) { width: 40px; }
    .stTable th:nth-child(2), .stTable td:nth-child(2) { width: 180px; }
    .stTable th:nth-child(3), .stTable td:nth-child(3) { width: 60px; }
    .stTable th:nth-child(4), .stTable td:nth-child(4) { width: 60px; }
    .stTable th:nth-child(5), .stTable td:nth-child(5) { width: 180px; }
    .stTable th:nth-child(6), .stTable td:nth-child(6) { width: 60px; }
</style>""", unsafe_allow_html=True)

# Paths
DATA_DIR = Path(__file__).parent / "data" / "transport"

# Village color mapping
VILLAGE_COLORS = {
    "St. Ulrich": "#7B1FA2",    # violet
    "St. Christina": "#4CAF50",  # green
    "Wolkenstein": "#F44336",    # red
    "Bolzano": "#757575",        # gray
    "Ponte Gardena": "#757575",  # gray
    "Bressanone": "#757575",     # gray
}

# Hardcoded Val Gardena center
VG_CENTER = [46.5650, 11.7100]

# Tourist-friendly main stops (2 per VG village + external hubs)
MAIN_STOP_NAMES = [
    "Ortisei, Sarteur",
    "Ortisei, Piazza S. Antonio",
    "S. Cristina, Municipio",
    "S. Cristina, Dosses",
    "Selva, Piazza Nives",
    "Selva, Ciampinoi",
    "Bolzano, Autostazione A",
    "Ponte Gardena, Paese",
    "Bressanone, Autostazione",
]

# Short display names for the schematic
SHORT_NAMES = {
    "Ortisei, Sarteur": "Sarteur",
    "Ortisei, Piazza S. Antonio": "Piazza S. Antonio",
    "S. Cristina, Municipio": "Municipio",
    "S. Cristina, Dosses": "Dosses",
    "Selva, Piazza Nives": "Piazza Nives",
    "Selva, Ciampinoi": "Ciampinoi",
    "Bolzano, Autostazione A": "Bolzano",
    "Ponte Gardena, Paese": "Ponte Gardena",
    "Bressanone, Autostazione": "Bressanone",
}

# Village assignment for main stops
STOP_VILLAGE = {
    "Ortisei, Sarteur": "St. Ulrich",
    "Ortisei, Piazza S. Antonio": "St. Ulrich",
    "S. Cristina, Municipio": "St. Christina",
    "S. Cristina, Dosses": "St. Christina",
    "Selva, Piazza Nives": "Wolkenstein",
    "Selva, Ciampinoi": "Wolkenstein",
    "Bolzano, Autostazione A": "Bolzano",
    "Ponte Gardena, Paese": "Ponte Gardena",
    "Bressanone, Autostazione": "Bressanone",
}

# External locations (outside Val Gardena) — always show main stop only
EXTERNAL_LOCATIONS = {"Bolzano", "Ponte Gardena", "Bressanone"}


def compute_trip_destinations(stop_times_df, stops_df, trips_df):
    """Compute destinations for each trip with 3-level fallback:

    1. trip_headsign (if non-empty)
    2. Sibling headsign: another trip on the same route that has a headsign
    3. Geo fallback: for circular routes, the geographically furthest stop from
       the origin; for linear routes, the last stop.
    """
    st_with_names = stop_times_df.merge(
        stops_df[['stop_id', 'stop_name', 'stop_lat', 'stop_lon']],
        on='stop_id', how='left'
    )

    # Geo fallback: furthest stop for circular, last stop for linear
    def _geo_fallback(group):
        ordered = group.sort_values('stop_sequence')
        first = ordered.iloc[0]
        last = ordered.iloc[-1]
        if first['stop_name'] == last['stop_name'] and len(ordered) > 2:
            # Circular: find the stop geographically furthest from origin
            dlat = ordered['stop_lat'] - first['stop_lat']
            dlon = ordered['stop_lon'] - first['stop_lon']
            dist_sq = dlat ** 2 + dlon ** 2
            return ordered.loc[dist_sq.idxmax(), 'stop_name']
        return last['stop_name']

    geo = st_with_names.groupby('trip_id').apply(
        _geo_fallback, include_groups=False
    ).reset_index(name='geo_dest')

    # Build trip-level table with route_id and headsign
    trip_dest = trips_df[['trip_id', 'route_id', 'trip_headsign']].merge(
        geo, on='trip_id', how='left'
    )

    # Sibling headsign: for each route, find the most common non-empty headsign
    has_hs = trip_dest[
        trip_dest['trip_headsign'].notna() & (trip_dest['trip_headsign'].str.strip() != '')
    ]
    route_headsign = has_hs.groupby('route_id')['trip_headsign'].agg(
        lambda x: x.value_counts().index[0]
    ).reset_index(name='sibling_dest')

    trip_dest = trip_dest.merge(route_headsign, on='route_id', how='left')

    # Apply 3-level fallback
    blank = trip_dest['trip_headsign'].isna() | (trip_dest['trip_headsign'].str.strip() == '')
    trip_dest['destination'] = trip_dest['trip_headsign']
    # Level 2: sibling headsign
    use_sibling = blank & trip_dest['sibling_dest'].notna()
    trip_dest.loc[use_sibling, 'destination'] = trip_dest.loc[use_sibling, 'sibling_dest']
    # Level 3: geo fallback
    still_blank = blank & ~use_sibling
    trip_dest.loc[still_blank, 'destination'] = trip_dest.loc[still_blank, 'geo_dest']

    return trip_dest[['trip_id', 'destination']]


def get_active_service_ids(calendar_df, calendar_dates_df, target_date):
    """Return set of service_ids active on target_date using GTFS calendar rules."""
    day_name = target_date.strftime('%A').lower()  # 'monday', 'tuesday', etc.
    date_int = int(target_date.strftime('%Y%m%d'))  # e.g. 20260209

    # Base: services running on this day of week within the valid date range
    active = set(calendar_df[
        (calendar_df[day_name] == 1) &
        (calendar_df['start_date'] <= date_int) &
        (calendar_df['end_date'] >= date_int)
    ]['service_id'])

    # Exceptions from calendar_dates
    exceptions = calendar_dates_df[calendar_dates_df['date'] == date_int]
    added = set(exceptions[exceptions['exception_type'] == 1]['service_id'])
    removed = set(exceptions[exceptions['exception_type'] == 2]['service_id'])

    return (active | added) - removed


def _ensure_fresh_gtfs(max_age_hours=24):
    """Re-download GTFS data if CSVs are stale or missing."""
    sentinel = DATA_DIR / "transport_stop_times.csv"
    if sentinel.exists():
        age_hours = (_time.time() - sentinel.stat().st_mtime) / 3600
        if age_hours < max_age_hours:
            return  # data is fresh
    # Import and call the download pipeline
    from download_transport import refresh_gtfs_data
    with st.spinner("Downloading fresh bus schedule data..."):
        refresh_gtfs_data()
    # Invalidate cached data so new CSVs are loaded
    load_data.clear()


@st.cache_data
def load_data():
    """Load all transport data, filter to Val Gardena, consolidate stops."""
    stops_df = pd.read_csv(DATA_DIR / "transport_stops.csv", encoding='utf-8')
    routes_df = pd.read_csv(DATA_DIR / "transport_routes.csv", encoding='utf-8')
    trips_df = pd.read_csv(DATA_DIR / "transport_trips.csv", encoding='utf-8')
    stop_times_df = pd.read_csv(DATA_DIR / "transport_stop_times.csv", encoding='utf-8')
    calendar_df = pd.read_csv(DATA_DIR / "transport_calendar.csv", encoding='utf-8')
    calendar_dates_df = pd.read_csv(DATA_DIR / "transport_calendar_dates.csv", encoding='utf-8')

    # Compute trip destinations on full data (before VG filtering)
    trip_destinations = compute_trip_destinations(stop_times_df, stops_df, trips_df)

    # Step 1: Find VG core stops and the trips that serve them
    vg_locations = ['St. Ulrich', 'St. Christina', 'Wolkenstein']
    vg_core_stops = stops_df[
        (stops_df['region'] == 'Val Gardena') |
        (stops_df['location'].isin(vg_locations))
    ].copy()
    vg_core_stops = vg_core_stops.drop_duplicates(subset=['stop_id'])

    vg_core_stop_ids = set(vg_core_stops['stop_id'])
    vg_core_st = stop_times_df[stop_times_df['stop_id'].isin(vg_core_stop_ids)]
    vg_trip_ids = set(vg_core_st['trip_id'].unique())

    # Step 2: Include external hub stops, but only for trips already serving VG
    ext_locations = list(EXTERNAL_LOCATIONS)
    ext_stops = stops_df[stops_df['location'].isin(ext_locations)].copy()

    all_stops = pd.concat([vg_core_stops, ext_stops]).drop_duplicates(subset=['stop_id'])
    all_stops = all_stops[
        (all_stops['stop_lat'] >= 46.4) & (all_stops['stop_lat'] <= 46.8) &
        (all_stops['stop_lon'] >= 11.0) & (all_stops['stop_lon'] <= 12.0)
    ].copy()

    # Get stop times: all stops, but only VG trips
    vg_stop_times = stop_times_df[
        (stop_times_df['stop_id'].isin(all_stops['stop_id'])) &
        (stop_times_df['trip_id'].isin(vg_trip_ids))
    ].copy()

    vg_trips = trips_df[trips_df['trip_id'].isin(vg_trip_ids)].copy()
    vg_route_ids = vg_trips['route_id'].unique()
    vg_routes = routes_df[routes_df['route_id'].isin(vg_route_ids)].copy()

    # Filter trip destinations
    vg_trip_destinations = trip_destinations[trip_destinations['trip_id'].isin(vg_trip_ids)].copy()

    # Consolidate stops into stations
    stations = consolidate_stops(all_stops, vg_stop_times)

    return stations, vg_routes, vg_trips, vg_stop_times, vg_trip_destinations, calendar_df, calendar_dates_df


def consolidate_stops(stops_df, stop_times_df):
    """Group raw stops by name into consolidated stations."""
    # Count departures per stop
    dep_counts = stop_times_df.groupby('stop_id').size().reset_index(name='dep_count')

    stops_with_deps = stops_df.merge(dep_counts, on='stop_id', how='left')
    stops_with_deps['dep_count'] = stops_with_deps['dep_count'].fillna(0).astype(int)

    # Group by stop_name
    stations = stops_with_deps.groupby('stop_name').agg(
        stop_lat=('stop_lat', 'mean'),
        stop_lon=('stop_lon', 'mean'),
        location=('location', 'first'),
        region=('region', 'first'),
        departures=('dep_count', 'sum'),
        stop_ids=('stop_id', list),
    ).reset_index()

    # Mark main stations using hardcoded list
    stations['is_main'] = stations['stop_name'].isin(MAIN_STOP_NAMES)

    return stations


def create_schematic_svg(stations, selected_stop=None):
    """Create an inline SVG schematic transit diagram with external connections."""
    # Only use VG main stops for the schematic line
    vg_main_names = [n for n in MAIN_STOP_NAMES if STOP_VILLAGE.get(n) not in EXTERNAL_LOCATIONS]
    main = stations[stations['stop_name'].isin(vg_main_names)].copy()
    if main.empty:
        return "<p>No main stations found</p>"

    # Sort by longitude (west to east)
    main = main.sort_values('stop_lon')

    # SVG dimensions
    svg_w, svg_h = 900, 170
    vg_left = 280
    vg_right = 860
    vg_w = vg_right - vg_left
    line_y = 65

    # External stop positions
    ponte_x = 140
    bolzano_x = ponte_x       # directly below Ponte Gardena
    bolzano_y = line_y + 60
    bressanone_x = ponte_x
    bressanone_y = line_y - 50

    # Compute x positions for VG stops
    lon_min = main['stop_lon'].min()
    lon_max = main['stop_lon'].max()
    lon_range = lon_max - lon_min if lon_max > lon_min else 1

    positions = []
    for _, row in main.iterrows():
        x = vg_left + ((row['stop_lon'] - lon_min) / lon_range) * vg_w
        name = row['stop_name']
        village = STOP_VILLAGE.get(name, row['location'])
        color = VILLAGE_COLORS.get(village, '#9E9E9E')
        short = SHORT_NAMES.get(name, name)
        positions.append({
            'x': x, 'name': name, 'short': short,
            'village': village, 'color': color,
        })

    # Build SVG
    svg_parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" '
        f'style="width:100%;max-width:{svg_w}px;height:auto;font-family:sans-serif;">',
        f'<rect width="{svg_w}" height="{svg_h}" rx="8" fill="white"/>',
    ]

    # --- External connections ---
    # Bolzano — Ponte Gardena (vertical, dashed)
    svg_parts.append(
        f'<line x1="{bolzano_x}" y1="{bolzano_y}" x2="{ponte_x}" y2="{line_y}" '
        f'stroke="#BDBDBD" stroke-width="2" stroke-dasharray="6,4"/>'
    )
    # Ponte Gardena — first VG stop (horizontal, dashed)
    svg_parts.append(
        f'<line x1="{ponte_x}" y1="{line_y}" x2="{positions[0]["x"]}" y2="{line_y}" '
        f'stroke="#BDBDBD" stroke-width="2" stroke-dasharray="6,4"/>'
    )
    # Ponte Gardena — Bressanone (vertical up, dashed)
    svg_parts.append(
        f'<line x1="{ponte_x}" y1="{line_y}" x2="{bressanone_x}" y2="{bressanone_y}" '
        f'stroke="#BDBDBD" stroke-width="2" stroke-dasharray="6,4"/>'
    )

    # Map selected stop to its external village for highlighting
    selected_village = STOP_VILLAGE.get(selected_stop) if selected_stop else None
    ext_color = "#757575"

    # External stop circles and labels
    for ex_x, ex_y, ex_label, ex_village in [
        (bolzano_x, bolzano_y, "Bolzano", "Bolzano"),
        (ponte_x, line_y, "Ponte Gardena", "Ponte Gardena"),
        (bressanone_x, bressanone_y, "Bressanone", "Bressanone"),
    ]:
        is_selected = (selected_village == ex_village)
        r = 9 if is_selected else 5

        if is_selected:
            svg_parts.append(
                f'<circle cx="{ex_x}" cy="{ex_y}" r="14" '
                f'fill="none" stroke="{ext_color}" stroke-width="3" opacity="0.4"/>'
            )

        svg_parts.append(
            f'<circle cx="{ex_x}" cy="{ex_y}" r="{r}" '
            f'fill="{ext_color}" stroke="white" stroke-width="1.5"/>'
        )

        font_weight = "bold"
        font_size = "12" if is_selected else "11"
        if ex_label == "Ponte Gardena":
            svg_parts.append(
                f'<text x="{ex_x}" y="{ex_y + 20}" text-anchor="middle" '
                f'fill="{ext_color}" font-size="10" font-weight="{font_weight}">{ex_label}</text>'
            )
        else:
            svg_parts.append(
                f'<text x="{ex_x + 14}" y="{ex_y + 4}" text-anchor="start" '
                f'fill="{ext_color}" font-size="{font_size}" font-weight="{font_weight}">{ex_label}</text>'
            )

    # --- Val Gardena stops ---
    village_groups = {}
    for p in positions:
        v = p['village']
        if v not in village_groups:
            village_groups[v] = []
        village_groups[v].append(p['x'])

    for village, xs in village_groups.items():
        x_min, x_max = min(xs) - 30, max(xs) + 30
        color = VILLAGE_COLORS.get(village, '#9E9E9E')
        svg_parts.append(
            f'<rect x="{x_min}" y="{line_y - 18}" width="{x_max - x_min}" height="36" '
            f'rx="18" fill="{color}" opacity="0.10"/>'
        )

    # Draw line segments between VG stops
    for i in range(len(positions) - 1):
        p1, p2 = positions[i], positions[i + 1]
        if p1['village'] == p2['village']:
            svg_parts.append(
                f'<line x1="{p1["x"]}" y1="{line_y}" x2="{p2["x"]}" y2="{line_y}" '
                f'stroke="{p1["color"]}" stroke-width="4" stroke-linecap="round"/>'
            )
        else:
            svg_parts.append(
                f'<line x1="{p1["x"]}" y1="{line_y}" x2="{p2["x"]}" y2="{line_y}" '
                f'stroke="#BDBDBD" stroke-width="2" stroke-dasharray="8,4"/>'
            )

    # Draw stop circles and labels
    for idx, p in enumerate(positions):
        is_selected = (selected_stop and p['name'] == selected_stop)
        r = 10 if is_selected else 7

        if is_selected:
            svg_parts.append(
                f'<circle cx="{p["x"]}" cy="{line_y}" r="16" '
                f'fill="none" stroke="{p["color"]}" stroke-width="3" opacity="0.4"/>'
            )

        svg_parts.append(
            f'<circle cx="{p["x"]}" cy="{line_y}" r="{r}" '
            f'fill="{p["color"]}" stroke="white" stroke-width="2"/>'
        )

        label_y = line_y + 35 if idx % 2 == 0 else line_y + 50
        font_weight = "bold" if is_selected else "normal"
        font_size = "12" if is_selected else "11"
        svg_parts.append(
            f'<line x1="{p["x"]}" y1="{line_y + r + 2}" x2="{p["x"]}" y2="{label_y - 10}" '
            f'stroke="#CCC" stroke-width="1"/>'
        )
        svg_parts.append(
            f'<text x="{p["x"]}" y="{label_y}" text-anchor="middle" '
            f'fill="#333" font-size="{font_size}" font-weight="{font_weight}">{p["short"]}</text>'
        )

    # Draw village names above the line
    for village, xs in village_groups.items():
        cx = sum(xs) / len(xs)
        color = VILLAGE_COLORS.get(village, '#9E9E9E')
        svg_parts.append(
            f'<text x="{cx}" y="{line_y - 25}" text-anchor="middle" '
            f'fill="{color}" font-size="13" font-weight="bold">{village}</text>'
        )

    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


def get_station_schedule(station_row, stop_times_df, trips_df, routes_df, trip_destinations, after_time=None):
    """Get deduplicated schedule for a station (all its stop_ids)."""
    stop_ids = station_row['stop_ids']

    schedule = stop_times_df[stop_times_df['stop_id'].isin(stop_ids)].copy()

    if after_time:
        schedule = schedule[schedule['departure_time'] >= after_time]

    # Join trips and routes
    schedule = schedule.merge(
        trips_df[['trip_id', 'route_id']],
        on='trip_id'
    )
    schedule = schedule.merge(
        routes_df[['route_id', 'route_short_name']],
        on='route_id'
    )

    # Join pre-computed destinations
    schedule = schedule.merge(
        trip_destinations[['trip_id', 'destination']],
        on='trip_id',
        how='left'
    )

    # Fallback if destination is still blank
    schedule['destination'] = schedule['destination'].fillna(
        'Route ' + schedule['route_short_name']
    )

    # Deduplicate: same route within ~2 min at the same station = same bus
    # (a station can have multiple stop_ids, so the same bus shows up with
    #  slightly different times, e.g. 16:09 arriving and 16:10 departing)

    # For each route, find its most common destination (the "main" one)
    route_main_dest = schedule.groupby('route_short_name')['destination'].agg(
        lambda x: x.value_counts().index[0]
    )
    schedule['_is_main'] = schedule.apply(
        lambda r: r['destination'] == route_main_dest.get(r['route_short_name'], ''), axis=1
    )

    # Convert to minutes for proximity comparison
    def _time_to_minutes(t):
        parts = t.split(':')
        return int(parts[0]) * 60 + int(parts[1])

    schedule['_minutes'] = schedule['departure_time'].apply(_time_to_minutes)

    # Sort by route, then time, then prefer main destination first
    schedule = schedule.sort_values(
        ['route_short_name', '_minutes', '_is_main'],
        ascending=[True, True, False]
    )

    # Proximity dedup: same route within 2 min = same bus, keep first (main dest preferred)
    keep = []
    prev_route = None
    prev_min = -999
    for idx in schedule.index:
        route = schedule.loc[idx, 'route_short_name']
        mins = schedule.loc[idx, '_minutes']
        if route != prev_route or (mins - prev_min) >= 2:
            keep.append(idx)
            prev_route = route
            prev_min = mins
    schedule = schedule.loc[keep]

    schedule = schedule.drop(columns=['_is_main', '_minutes'])
    schedule = schedule.sort_values('departure_time')

    return schedule[['departure_time', 'route_short_name', 'destination', 'trip_id']]


def format_time(time_str):
    """Format HH:MM:SS to HH:MM."""
    try:
        h, m, _s = time_str.split(':')
        return f"{h}:{m}"
    except Exception:
        return time_str


# Route colors for the network map
ROUTE_COLORS = {
    '1': '#1976D2', '2': '#0288D1', '3': '#0097A7', '4': '#00796B', '5': '#388E3C',
    '172': '#7B1FA2',
    '333': '#C2185B',
    '350': '#E64A19', '351': '#F57C00', '352': '#FFA000', '353': '#FBC02D',
    '355.1': '#8BC34A', '355.2': '#CDDC39', '355.3': '#AFB42B', '355.4': '#689F38',
    '360': '#5C6BC0',
    '471': '#D32F2F', '473': '#E91E63',
    'N170': '#455A64', 'N352': '#607D8B',
}


@st.cache_data
def load_route_network():
    """Load full route network for buses serving Ortisei."""
    stops_df = pd.read_csv(DATA_DIR / "transport_stops.csv", encoding='utf-8')
    stop_times_df = pd.read_csv(DATA_DIR / "transport_stop_times.csv", encoding='utf-8')
    trips_df = pd.read_csv(DATA_DIR / "transport_trips.csv", encoding='utf-8')
    routes_df = pd.read_csv(DATA_DIR / "transport_routes.csv", encoding='utf-8')

    # Find Ortisei stop_ids and trips
    ortisei_ids = set(stops_df[stops_df['location'] == 'St. Ulrich']['stop_id'])
    ortisei_trip_ids = set(
        stop_times_df[stop_times_df['stop_id'].isin(ortisei_ids)]['trip_id']
    )

    # Get routes for these trips
    trip_route = trips_df[trips_df['trip_id'].isin(ortisei_trip_ids)][['trip_id', 'route_id']]
    trip_route = trip_route.merge(routes_df[['route_id', 'route_short_name']], on='route_id')

    # For each route, pick one representative trip (the one with most stops)
    trip_stop_counts = stop_times_df[
        stop_times_df['trip_id'].isin(ortisei_trip_ids)
    ].groupby('trip_id').size().reset_index(name='n_stops')

    trip_route = trip_route.merge(trip_stop_counts, on='trip_id')
    best_trips = trip_route.sort_values('n_stops', ascending=False).drop_duplicates('route_short_name')

    # Build route paths: list of (lat, lon) for each route
    route_paths = {}
    for _, row in best_trips.iterrows():
        rname = row['route_short_name']
        tid = row['trip_id']
        trip_st = stop_times_df[stop_times_df['trip_id'] == tid].sort_values('stop_sequence')
        trip_st = trip_st.merge(
            stops_df[['stop_id', 'stop_name', 'stop_lat', 'stop_lon', 'location']],
            on='stop_id', how='left'
        )
        coords = []
        for _, s in trip_st.iterrows():
            coords.append({
                'name': s['stop_name'],
                'lat': s['stop_lat'],
                'lon': s['stop_lon'],
                'location': s.get('location', ''),
            })
        route_paths[rname] = coords

    return route_paths


def _classify_stop(name, location):
    """Classify a stop into a named place using stop_name patterns."""
    if location and location not in ('Other', ''):
        return location
    nl = name.lower()
    if 'funes' in nl or 'villnoss' in nl or 'villnoess' in nl:
        return 'Funes'
    if 'colfosco' in nl:
        return 'Colfosco'
    if 'passo gardena' in nl or 'grodner joch' in nl:
        return 'Passo Gardena'
    if 'passo sella' in nl or 'sella joch' in nl or 'rifugio passo sella' in nl:
        return 'Passo Sella'
    if 'passo pordoi' in nl or 'pordoi joch' in nl:
        return 'Passo Pordoi'
    if 'plan de gralba' in nl:
        return 'Plan de Gralba'
    if 'castelrotto' in nl or 'kastelruth' in nl:
        return 'Castelrotto'
    if 'laion' in nl or 'lajen' in nl:
        return 'Laion'
    if 'pontives' in nl:
        return 'Pontives'
    return 'Other'


def create_route_network_svg(route_paths):
    """Create a subway-style transit map with parallel colored route lines."""
    if not route_paths:
        return "<p>No route data</p>"

    svg_w, svg_h = 960, 520
    line_y = 185

    # Node positions (hand-crafted schematic layout)
    nodes = {
        # Main valley (horizontal)
        'Ortisei':        (400, line_y),
        'S. Cristina':    (530, line_y),
        'Selva':          (640, line_y),
        # North of Ortisei (local routes — real geographic direction)
        'Seceda':         (420, line_y - 65),
        'Resciesa':       (370, line_y - 65),
        'Miraortisei':    (345, line_y - 45),
        'Costamula':      (455, line_y - 95),
        # South from Ortisei: Bulla spur, then 172 line
        'Bulla':          (355, line_y + 50),
        'Castelrotto':    (310, line_y + 90),
        'Siusi':          (265, line_y + 125),
        # West from Ortisei
        'Pontives':       (290, line_y),
        # Route 360/351 goes via Laion (above main line)
        'Laion':          (200, line_y - 35),
        # Ponte Gardena (junction)
        'Ponte Gardena':  (120, line_y),
        # Northwest from P. Gardena: Chiusa → Funes → Bressanone
        'Chiusa':         (75, line_y - 35),
        'Funes':          (55, line_y - 60),
        'Bressanone':     (35, line_y - 85),
        # South from P. Gardena
        'Bolzano':        (60, line_y + 55),
        # East from Selva
        'Plan de Gralba': (720, line_y - 20),
        # Northeast: Passo Gardena → Colfosco → Corvara (summer)
        'Passo Gardena':  (780, line_y - 50),
        'Colfosco':       (835, line_y - 75),
        'Corvara':        (885, line_y - 95),
        # Southeast: Passo Sella → Passo Pordoi (summer)
        'Passo Sella':    (780, line_y + 15),
        'Passo Pordoi':   (850, line_y + 40),
        # Local destinations from Ortisei, S. Cristina and Selva
        'S. Giacomo':     (470, line_y - 75),
        'Col Raiser':     (555, line_y - 45),
        'Monte Pana':     (505, line_y + 45),
        'Dantercepies':   (715, line_y - 40),
        'Vallunga':       (665, line_y - 70),
        'Daunëi':         (660, line_y + 80),
    }

    # Subway lines: each line has a color and a path of segments
    route_lines = [
        {
            'id': '360', 'label': 'Bressanone',
            'color': '#6A1B9A',
            'segments': [
                ('Selva', 'S. Cristina'), ('S. Cristina', 'Ortisei'),
                ('Ortisei', 'Pontives'),
                ('Pontives', 'Laion'), ('Laion', 'Ponte Gardena'),
                ('Ponte Gardena', 'Chiusa'), ('Chiusa', 'Funes'),
                ('Funes', 'Bressanone'),
            ],
            'dashed': False,
        },
        {
            'id': '350', 'label': 'Bolzano',
            'color': '#E65100',
            'segments': [
                ('Selva', 'S. Cristina'), ('S. Cristina', 'Ortisei'),
                ('Ortisei', 'Pontives'), ('Pontives', 'Ponte Gardena'),
                ('Ponte Gardena', 'Bolzano'),
            ],
            'dashed': False,
        },
        {
            'id': '172', 'label': 'Siusi',
            'color': '#2E7D32',
            'segments': [
                ('Selva', 'S. Cristina'), ('S. Cristina', 'Ortisei'),
                ('Ortisei', 'Castelrotto'), ('Castelrotto', 'Siusi'),
            ],
            'dashed': False,
        },
        {
            'id': '473', 'label': 'Corvara',
            'color': '#00695C',
            'segments': [
                ('Selva', 'Plan de Gralba'),
                ('Plan de Gralba', 'Passo Gardena'), ('Passo Gardena', 'Colfosco'),
                ('Colfosco', 'Corvara'),
            ],
            'dashed': True,
        },
        {
            'id': '471', 'label': 'Passo Sella',
            'color': '#1565C0',
            'segments': [
                ('Selva', 'Plan de Gralba'),
                ('Plan de Gralba', 'Passo Sella'), ('Passo Sella', 'Passo Pordoi'),
            ],
            'dashed': True,
        },
    ]

    # Build segment → list of (line_index, color, dashed)
    seg_lines = {}
    for li, line in enumerate(route_lines):
        for a, b in line['segments']:
            key = frozenset((a, b))
            if key not in seg_lines:
                seg_lines[key] = []
            seg_lines[key].append((li, line['color'], line['dashed']))

    # Perpendicular offset for parallel lines
    def _offset(x1, y1, x2, y2, off):
        dx, dy = x2 - x1, y2 - y1
        length = (dx**2 + dy**2) ** 0.5
        if length == 0:
            return x1, y1, x2, y2
        px, py = -dy / length, dx / length
        return (x1 + px*off, y1 + py*off, x2 + px*off, y2 + py*off)

    spacing = 5
    line_w = 3.5

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" '
        f'style="width:100%;max-width:{svg_w}px;height:auto;font-family:sans-serif;">',
        f'<rect width="{svg_w}" height="{svg_h}" rx="10" fill="white"/>',
    ]

    # Draw all route segments as parallel colored lines
    drawn = set()
    for line in route_lines:
        for a, b in line['segments']:
            key = frozenset((a, b))
            if key in drawn:
                continue
            drawn.add(key)
            # Normalize direction: left-to-right, then top-to-bottom
            ax, ay = nodes[a]
            bx, by = nodes[b]
            if ax > bx or (ax == bx and ay > by):
                a, b = b, a
                ax, ay, bx, by = bx, by, ax, ay
            lines_here = seg_lines[key]
            n = len(lines_here)
            for i, (li, color, dashed) in enumerate(lines_here):
                off = (i - (n - 1) / 2) * spacing
                ox1, oy1, ox2, oy2 = _offset(ax, ay, bx, by, off)
                dash = ' stroke-dasharray="8,4"' if dashed else ''
                svg.append(
                    f'<line x1="{ox1:.1f}" y1="{oy1:.1f}" '
                    f'x2="{ox2:.1f}" y2="{oy2:.1f}" '
                    f'stroke="{color}" stroke-width="{line_w}" '
                    f'stroke-linecap="round"{dash}/>'
                )

    # Local connections (thin lines to local destinations)
    # Tuple: (from, to, dashed) — dashed=True for seasonal routes
    local_conns = [
        ('Ortisei', 'Seceda', False), ('Ortisei', 'Miraortisei', False),
        ('Miraortisei', 'Resciesa', False), ('Resciesa', 'Seceda', False),
        ('Ortisei', 'Bulla', False),
        ('Ortisei', 'S. Giacomo', False), ('Ortisei', 'Costamula', False),
        ('S. Cristina', 'Col Raiser', True), ('S. Cristina', 'Monte Pana', True),
        ('Selva', 'Dantercepies', False), ('Selva', 'Vallunga', False),
        ('Selva', 'Daunëi', False), ('Vallunga', 'Dantercepies', False),
    ]
    for a, b, dashed in local_conns:
        ax, ay = nodes[a]
        bx, by = nodes[b]
        dash = ' stroke-dasharray="6,4"' if dashed else ''
        svg.append(
            f'<line x1="{ax}" y1="{ay}" x2="{bx}" y2="{by}" '
            f'stroke="#CE93D8" stroke-width="2" stroke-linecap="round" opacity="0.5"{dash}/>'
        )

    # Route number labels on local connections
    # (label, x-offset from midpoint, y-offset from midpoint)
    local_route_labels = [
        ('Ortisei', 'S. Giacomo', '1', 0, -5),
        ('Ortisei', 'Bulla', '2', -12, 0),
        ('Ortisei', 'Costamula', '3', 5, -5),
        ('Ortisei', 'Seceda', '4', -15, -5),
        ('S. Cristina', 'Col Raiser', '21', 5, -5),
        ('S. Cristina', 'Monte Pana', '355', 5, -5),
        ('Selva', 'Dantercepies', '21', 5, -8),
        ('Selva', 'Vallunga', '355', 5, -5),
        ('Selva', 'Daunëi', '22', -14, 5),
        ('Vallunga', 'Dantercepies', '23', -18, -14),
    ]
    for a, b, label, dx, dy in local_route_labels:
        ax, ay = nodes[a]
        bx, by = nodes[b]
        mx, my = (ax + bx) / 2 + dx, (ay + by) / 2 + dy
        svg.append(
            f'<text x="{mx:.0f}" y="{my:.0f}" fill="#CE93D8" '
            f'font-size="8" font-weight="bold">{label}</text>'
        )

    # Siusi → Bolzano continuation arrow
    sx, sy = nodes['Siusi']
    bx, by = nodes['Bolzano']
    # Arrow pointing from Siusi towards Bolzano direction (southwest)
    angle = math.atan2(by - sy, bx - sx)
    arr_len = 60
    ax2 = sx + arr_len * math.cos(angle)
    ay2 = sy + arr_len * math.sin(angle)
    svg.append(
        f'<line x1="{sx}" y1="{sy}" x2="{ax2:.0f}" y2="{ay2:.0f}" '
        f'stroke="#999" stroke-width="{line_w}" stroke-linecap="round" '
        f'stroke-dasharray="8,4"/>'
    )
    # Arrow tip
    tip_dx = 10 * math.cos(angle)
    tip_dy = 10 * math.sin(angle)
    perp_x = 5 * math.cos(angle + math.pi/2)
    perp_y = 5 * math.sin(angle + math.pi/2)
    p1 = f'{ax2 + tip_dx:.0f},{ay2 + tip_dy:.0f}'
    p2 = f'{ax2 + perp_x:.0f},{ay2 + perp_y:.0f}'
    p3 = f'{ax2 - perp_x:.0f},{ay2 - perp_y:.0f}'
    svg.append(f'<polygon points="{p1} {p2} {p3}" fill="#999"/>')
    svg.append(
        f'<text x="{ax2 + 8:.0f}" y="{ay2 + 4:.0f}" fill="#999" '
        f'font-size="9" font-style="italic">Bolzano</text>'
    )

    # Funes Valley stub (route 333, summer — extends east from Funes stop)
    fx, fy = nodes['Funes']
    fv_color = '#999'
    svg.append(
        f'<line x1="{fx}" y1="{fy}" x2="{fx + 70}" y2="{fy}" '
        f'stroke="{fv_color}" stroke-width="{line_w}" stroke-linecap="round" '
        f'stroke-dasharray="8,4"/>'
    )
    # Arrow tip
    svg.append(
        f'<polygon points="{fx + 70},{fy - 5} {fx + 80},{fy} {fx + 70},{fy + 5}" '
        f'fill="{fv_color}"/>'
    )
    svg.append(
        f'<text x="{fx + 85}" y="{fy - 2}" fill="{fv_color}" '
        f'font-size="10" font-weight="bold">Funes Valley</text>'
    )
    svg.append(
        f'<text x="{fx + 85}" y="{fy + 10}" fill="#AAA" '
        f'font-size="8">333 (summer)</text>'
    )

    # Alpe di Siusi stub (routes 11/12 — extends south from Monte Pana)
    mpx, mpy = nodes['Monte Pana']
    as_color = '#999'
    # Arrow pointing southwest from Monte Pana towards Alpe di Siusi
    as_angle = math.atan2(1, -0.5)  # down and slightly left
    as_len = 55
    as_x2 = mpx + as_len * math.cos(as_angle)
    as_y2 = mpy + as_len * math.sin(as_angle)
    svg.append(
        f'<line x1="{mpx}" y1="{mpy}" x2="{as_x2:.0f}" y2="{as_y2:.0f}" '
        f'stroke="{as_color}" stroke-width="{line_w}" stroke-linecap="round" '
        f'stroke-dasharray="8,4"/>'
    )
    # Arrow tip
    as_tip_dx = 10 * math.cos(as_angle)
    as_tip_dy = 10 * math.sin(as_angle)
    as_perp_x = 5 * math.cos(as_angle + math.pi/2)
    as_perp_y = 5 * math.sin(as_angle + math.pi/2)
    asp1 = f'{as_x2 + as_tip_dx:.0f},{as_y2 + as_tip_dy:.0f}'
    asp2 = f'{as_x2 + as_perp_x:.0f},{as_y2 + as_perp_y:.0f}'
    asp3 = f'{as_x2 - as_perp_x:.0f},{as_y2 - as_perp_y:.0f}'
    svg.append(f'<polygon points="{asp1} {asp2} {asp3}" fill="{as_color}"/>')
    svg.append(
        f'<text x="{as_x2 + 8:.0f}" y="{as_y2 - 2:.0f}" fill="{as_color}" '
        f'font-size="10" font-weight="bold">Alpe di Siusi</text>'
    )
    svg.append(
        f'<text x="{as_x2 + 8:.0f}" y="{as_y2 + 10:.0f}" fill="#AAA" '
        f'font-size="8">11, 12 (winter)</text>'
    )

    # Draw stop nodes
    local_stops = {'Seceda', 'Resciesa', 'Miraortisei', 'Costamula', 'Bulla', 'S. Giacomo', 'Col Raiser', 'Monte Pana', 'Dantercepies', 'Vallunga', 'Daunëi'}
    valley_nodes = {'Ortisei', 'S. Cristina', 'Selva'}

    for place in set(nodes.keys()) - valley_nodes:
        x, y = nodes[place]
        # Color based on serving route lines
        serving = []
        for line in route_lines:
            for a, b in line['segments']:
                if place in (a, b):
                    serving.append(line['color'])
                    break
        if place in local_stops:
            fill, r = '#CE93D8', 4
        elif len(serving) == 1:
            fill, r = serving[0], 5
        elif len(serving) > 1:
            fill, r = '#555', 6
        else:
            fill, r = '#999', 4
        svg.append(
            f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="white" stroke-width="1.5"/>'
        )

        # Label positioning — explicit overrides for nodes near lines
        label_pos = {
            'Seceda':        (x - 5, y - 6, 'end'),
            'Resciesa':      (x - 10, y - 8, 'end'),
            'Miraortisei':   (x - 10, y + 4, 'end'),
            'Costamula':     (x + 10, y - 8, 'start'),
            'Bulla':         (x + 12, y + 5, 'start'),
            'Pontives':      (x, y - 20, 'middle'),
            'Ponte Gardena': (x + 12, y + 16, 'start'),
            'Laion':         (x + 12, y - 8, 'start'),
            'Bolzano':       (x + 12, y + 5, 'start'),
            'Chiusa':        (x - 12, y + 14, 'end'),
            'Funes':         (x - 12, y + 14, 'end'),
            'Bressanone':    (x, y - 14, 'middle'),
            'Plan de Gralba': (x - 10, y + 24, 'end'),
            'Passo Gardena':  (x + 10, y + 16, 'start'),
            'Colfosco':      (x + 10, y + 14, 'start'),
            'Passo Sella':   (x - 10, y + 14, 'end'),
            'S. Giacomo':    (x + 10, y + 4, 'start'),
            'Col Raiser':    (x + 10, y - 8, 'start'),
            'Monte Pana':    (x + 10, y + 14, 'start'),
            'Dantercepies':  (x, y - 10, 'middle'),
            'Vallunga':      (x, y - 12, 'middle'),
            'Daunëi':        (x + 10, y + 14, 'start'),
        }
        if place in label_pos:
            lx, ly, anchor = label_pos[place]
        elif y > line_y:
            lx, ly, anchor = x + 10, y + 16, 'start'
        else:
            lx, ly, anchor = x + 10, y - 10, 'start'

        display_name = {'Plan de Gralba': 'Plan'}.get(place, place)
        svg.append(
            f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" '
            f'fill="#555" font-size="10" font-weight="bold">{display_name}</text>'
        )

    # Season annotations for seasonal local stops
    season_annotations = [
        ('Col Raiser', '(winter/summer)', 'start', 10, -8),
        ('Monte Pana', '(winter)', 'start', 10, 14),
    ]
    for place, season, anchor, dx, dy in season_annotations:
        x, y = nodes[place]
        lx, ly = x + dx, y + dy + 10
        svg.append(
            f'<text x="{lx}" y="{ly}" text-anchor="{anchor}" '
            f'fill="#AAA" font-size="8" font-style="italic">{season}</text>'
        )

    # Valley nodes (large interchange circles, drawn on top)
    valley_style = {
        'Ortisei':     {'color': '#7B1FA2', 'r': 12, 'fs': 14, 'dy': -22},
        'S. Cristina': {'color': '#555',    'r': 9,  'fs': 12, 'dy': 28},
        'Selva':       {'color': '#555',    'r': 9,  'fs': 12, 'dy': 28},
    }
    for place in ('Ortisei', 'S. Cristina', 'Selva'):
        x, y = nodes[place]
        s = valley_style[place]
        if place == 'Ortisei':
            svg.append(
                f'<circle cx="{x}" cy="{y}" r="{s["r"] + 5}" '
                f'fill="none" stroke="{s["color"]}" stroke-width="2" opacity="0.2"/>'
            )
        svg.append(
            f'<circle cx="{x}" cy="{y}" r="{s["r"]}" '
            f'fill="white" stroke="{s["color"]}" stroke-width="3"/>'
        )
        svg.append(
            f'<text x="{x}" y="{y + s["dy"]}" text-anchor="middle" '
            f'fill="{s["color"]}" font-size="{s["fs"]}" font-weight="bold">{place}</text>'
        )

    # Legend (bottom-left)
    lg_x, lg_y = 20, svg_h - 135
    for i, line in enumerate(route_lines):
        y = lg_y + i * 14
        dash = ' stroke-dasharray="6,3"' if line['dashed'] else ''
        summer = ' (summer)' if line['dashed'] else ''
        svg.append(
            f'<line x1="{lg_x}" y1="{y}" x2="{lg_x + 22}" y2="{y}" '
            f'stroke="{line["color"]}" stroke-width="{line_w}" '
            f'stroke-linecap="round"{dash}/>'
        )
        svg.append(
            f'<text x="{lg_x + 28}" y="{y + 4}" fill="#555" font-size="9">'
            f'{line["id"]} {line["label"]}{summer}</text>'
        )
    # Local line legend entries — Ortisei locals
    ly_local = lg_y + len(route_lines) * 14
    svg.append(
        f'<line x1="{lg_x}" y1="{ly_local}" x2="{lg_x + 22}" y2="{ly_local}" '
        f'stroke="#CE93D8" stroke-width="2" stroke-linecap="round"/>'
    )
    svg.append(
        f'<text x="{lg_x + 28}" y="{ly_local + 4}" fill="#CE93D8" font-size="9">'
        f'Ortisei: 1 S. Giacomo · 2 Bulla · 3 Costamula · 4 Seceda/Resciesa · 5 village loop</text>'
    )
    # Selva locals legend entry
    ly_local_s = ly_local + 14
    svg.append(
        f'<line x1="{lg_x}" y1="{ly_local_s}" x2="{lg_x + 22}" y2="{ly_local_s}" '
        f'stroke="#CE93D8" stroke-width="2" stroke-linecap="round"/>'
    )
    svg.append(
        f'<text x="{lg_x + 28}" y="{ly_local_s + 4}" fill="#CE93D8" font-size="9">'
        f'Selva: 21 Col Raiser↔Dantercepies · 22 Daunëi · 23 Daunëi–Vallunga–Dantercepies</text>'
    )
    # S. Cristina / seasonal legend entry
    ly_local_ss = ly_local_s + 14
    svg.append(
        f'<line x1="{lg_x}" y1="{ly_local_ss}" x2="{lg_x + 22}" y2="{ly_local_ss}" '
        f'stroke="#CE93D8" stroke-width="2" stroke-linecap="round" '
        f'stroke-dasharray="6,4"/>'
    )
    svg.append(
        f'<text x="{lg_x + 28}" y="{ly_local_ss + 4}" fill="#CE93D8" font-size="9">'
        f'355 Monte Pana/Vallunga (seasonal)</text>'
    )
    # Funes Valley legend
    ly_fv = ly_local_ss + 14
    svg.append(
        f'<line x1="{lg_x}" y1="{ly_fv}" x2="{lg_x + 22}" y2="{ly_fv}" '
        f'stroke="#999" stroke-width="{line_w}" stroke-linecap="round" '
        f'stroke-dasharray="6,3"/>'
    )
    svg.append(
        f'<text x="{lg_x + 28}" y="{ly_fv + 4}" fill="#999" font-size="9">'
        f'333 Funes Valley (summer)</text>'
    )

    svg.append('</svg>')
    return '\n'.join(svg)


def create_geographic_network_svg():
    """Create a geographic map showing actual bus stop locations."""
    # Real coordinates (lat, lon) for all destination stops
    geo = {
        # Main villages
        'Ortisei':        (46.5734, 11.6741),
        'S. Cristina':    (46.5581, 11.7209),
        'Selva':          (46.5558, 11.7562),
        # Ortisei local destinations
        'Seceda':         (46.5770, 11.6740),
        'Resciesa':       (46.5777, 11.6724),
        'Miraortisei':    (46.5779, 11.6581),
        # 'Grien' omitted — minor intermediate stop on route 4
        'Costamula':      (46.5843, 11.6941),
        'S. Giacomo':     (46.5709, 11.6905),
        'Bulla':          (46.5650, 11.6353),
        # S. Cristina local destinations
        'Col Raiser':     (46.5648, 11.7365),
        'Monte Pana':     (46.5509, 11.7156),
        # Selva local destinations
        'Dantercepies':   (46.5563, 11.7674),
        'Vallunga':       (46.5588, 11.7671),
        'Daunëi':         (46.5625, 11.7540),
        'Plan de Gralba': (46.5339, 11.7720),
        # Valley route stops
        'Pontives':       (46.5846, 11.6347),
        'Castelrotto':    (46.5678, 11.5609),
        'Siusi':          (46.5451, 11.5625),
        'Laion':          (46.6009, 11.5329),
        'Ponte Gardena':  (46.5978, 11.5314),
        # Summer pass routes
        'Passo Gardena':  (46.5497, 11.8063),
        'Colfosco':       (46.5543, 11.8558),
        'Corvara':        (46.5473, 11.8755),
        'Passo Sella':    (46.5080, 11.7685),
        'Passo Pordoi':   (46.4960, 11.7880),
    }
    skip_nodes = {'Seceda', 'Resciesa'}

    # SVG dimensions and projection
    svg_w, svg_h = 960, 620
    pad = 55

    lats = [c[0] for c in geo.values()]
    lons = [c[1] for c in geo.values()]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    # Add padding to bounds
    lat_range = max_lat - min_lat or 0.01
    lon_range = max_lon - min_lon or 0.01
    min_lat -= lat_range * 0.05
    max_lat += lat_range * 0.05
    min_lon -= lon_range * 0.05
    max_lon += lon_range * 0.05
    lat_range = max_lat - min_lat
    lon_range = max_lon - min_lon

    def proj(lat, lon):
        x = pad + (lon - min_lon) / lon_range * (svg_w - 2 * pad)
        y = pad + (max_lat - lat) / lat_range * (svg_h - 2 * pad)  # invert y
        return x, y

    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" '
        f'style="width:100%;max-width:{svg_w}px;height:auto;font-family:sans-serif;">',
        f'<rect width="{svg_w}" height="{svg_h}" rx="10" fill="#f8f9fa"/>',
        '<text x="480" y="22" text-anchor="middle" fill="#555" font-size="13" '
        'font-weight="bold">Geographic Stop Locations</text>',
    ]

    # Connections — same as schematic but with real coords
    main_route = [
        ('Ponte Gardena', 'Laion'), ('Laion', 'Pontives'),
        ('Pontives', 'Ortisei'), ('Ortisei', 'S. Cristina'),
        ('S. Cristina', 'Selva'),
    ]
    branch_172 = [('Ortisei', 'Castelrotto'), ('Castelrotto', 'Siusi')]
    branch_gardena = [
        ('Selva', 'Plan de Gralba'), ('Plan de Gralba', 'Passo Gardena'),
        ('Passo Gardena', 'Colfosco'), ('Colfosco', 'Corvara'),
    ]
    branch_sella = [
        ('Plan de Gralba', 'Passo Sella'), ('Passo Sella', 'Passo Pordoi'),
    ]
    local_ortisei = [
        ('Ortisei', 'Seceda'), ('Ortisei', 'Miraortisei'),
        ('Miraortisei', 'Resciesa'), ('Resciesa', 'Seceda'),
        ('Ortisei', 'S. Giacomo'), ('Ortisei', 'Costamula'),
        ('Ortisei', 'Bulla'),
    ]
    local_scristina = [
        ('S. Cristina', 'Col Raiser'), ('S. Cristina', 'Monte Pana'),
    ]
    local_selva = [
        ('Selva', 'Dantercepies'), ('Selva', 'Vallunga'),
        ('Selva', 'Daunëi'), ('Vallunga', 'Dantercepies'),
    ]

    # Draw connections
    def draw_lines(segs, color, width, dash=''):
        for a, b in segs:
            ax, ay = proj(*geo[a])
            bx, by = proj(*geo[b])
            svg.append(
                f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" '
                f'stroke="{color}" stroke-width="{width}" stroke-linecap="round"'
                f'{dash}/>'
            )

    draw_lines(main_route, '#6A1B9A', 2.5)
    draw_lines(branch_172, '#2E7D32', 2.5)
    draw_lines(branch_gardena, '#00695C', 2, ' stroke-dasharray="6,3"')
    draw_lines(branch_sella, '#1565C0', 2, ' stroke-dasharray="6,3"')
    draw_lines(local_ortisei, '#CE93D8', 1.5, ' opacity="0.6"')
    draw_lines(local_scristina, '#CE93D8', 1.5, ' opacity="0.6" stroke-dasharray="5,3"')
    draw_lines(local_selva, '#CE93D8', 1.5, ' opacity="0.6"')

    # Draw stop dots and labels
    valley = {'Ortisei', 'S. Cristina', 'Selva'}
    local = {
        'Seceda', 'Resciesa', 'Miraortisei', 'Costamula',
        'S. Giacomo', 'Bulla', 'Col Raiser', 'Monte Pana',
        'Dantercepies', 'Vallunga', 'Daunëi',
    }

    for name, (lat, lon) in geo.items():
        x, y = proj(lat, lon)
        if name in valley:
            r, fill, stroke, sw = 6, 'white', '#7B1FA2' if name == 'Ortisei' else '#555', 2.5
        elif name in local:
            r, fill, stroke, sw = 3, '#CE93D8', 'white', 1
        else:
            r, fill, stroke, sw = 4, '#555', 'white', 1.5
        svg.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
        )

        # Label placement — default to right of dot
        # Use smaller font for tightly-clustered local stops near Ortisei
        ortisei_cluster = {'Seceda', 'Resciesa', 'Miraortisei'}
        if name in valley:
            fs, fw = 11, 'bold'
        elif name in ortisei_cluster:
            fs, fw = 6, 'bold'
        elif name in local:
            fs, fw = 7, 'normal'
        else:
            fs, fw = 8, 'normal'
        color = '#7B1FA2' if name == 'Ortisei' else '#555' if name in valley else '#444'
        # Manual label offsets (dx, dy, anchor)
        label_adj = {
            'Ortisei':        (10, 5, 'start'),
            'S. Cristina':    (0, 16, 'middle'),
            'Selva':          (0, 16, 'middle'),
            'Seceda':         (5, -4, 'start'),
            'Resciesa':       (-5, -4, 'end'),
            'Miraortisei':    (-5, 10, 'end'),
            'Costamula':      (5, -4, 'start'),
            'S. Giacomo':     (5, 10, 'start'),
            'Bulla':          (-5, -5, 'end'),
            'Col Raiser':     (5, -4, 'start'),
            'Monte Pana':     (5, 10, 'start'),
            'Dantercepies':   (5, 10, 'start'),
            'Vallunga':       (5, -4, 'start'),
            'Daunëi':         (-5, 4, 'end'),
            'Pontives':       (0, -10, 'middle'),
            'Castelrotto':    (0, -10, 'middle'),
            'Siusi':          (0, 12, 'middle'),
            'Plan de Gralba': (-5, 12, 'end'),
            'Passo Gardena':  (5, 4, 'start'),
            'Colfosco':       (5, -6, 'start'),
            'Corvara':        (5, 10, 'start'),
            'Passo Sella':    (-5, 4, 'end'),
            'Passo Pordoi':   (5, 4, 'start'),
            'Laion':          (0, -10, 'middle'),
            'Ponte Gardena':  (0, 12, 'middle'),
        }
        dx, dy, anchor = label_adj.get(name, (8, 4, 'start'))
        svg.append(
            f'<text x="{x + dx:.1f}" y="{y + dy:.1f}" text-anchor="{anchor}" '
            f'fill="{color}" font-size="{fs}" font-weight="{fw}">{name}</text>'
        )

    svg.append('</svg>')
    return '\n'.join(svg)


def create_interactive_map():
    """Create a Folium map with markers for all subway-map locations."""
    VG_CENTER = [46.5650, 11.7100]

    # Geographic coordinates for all stops on the subway map (verified)
    # Valley villages
    valley_stops = {
        'Ortisei':      {'coords': [46.5750, 11.6676], 'color': '#7B1FA2', 'radius': 10},
        'S. Cristina':  {'coords': [46.5581, 11.7209], 'color': '#4CAF50', 'radius': 8},
        'Selva':        {'coords': [46.5558, 11.7562], 'color': '#F44336', 'radius': 8},
    }

    # All non-valley stops (grey)
    other_stops = {
        'Pontives':       {'coords': [46.5846, 11.6347]},
        'Laion':          {'coords': [46.6085, 11.5691]},
        'Ponte Gardena':  {'coords': [46.6014, 11.5327]},
        'Chiusa':         {'coords': [46.6429, 11.5733]},
        'Funes':          {'coords': [46.6566, 11.5968]},
        'Bressanone':     {'coords': [46.7151, 11.6526]},
        'Bolzano':        {'coords': [46.4981, 11.3585]},
        'Bulla':          {'coords': [46.5650, 11.6353]},
        'Castelrotto':    {'coords': [46.5678, 11.5609]},
        'Siusi':          {'coords': [46.5451, 11.5625]},
        'Plan de Gralba': {'coords': [46.5345, 11.7727]},
        'Passo Gardena':  {'coords': [46.5497, 11.8063]},
        'Colfosco':       {'coords': [46.5543, 11.8558]},
        'Corvara':        {'coords': [46.5473, 11.8755]},
        'Passo Sella':    {'coords': [46.5080, 11.7685]},
        'Passo Pordoi':   {'coords': [46.4960, 11.7880]},
        'S. Giacomo':     {'coords': [46.5709, 11.6905]},
        'Seceda':         {'coords': [46.5770, 11.6740]},
        'Resciesa':       {'coords': [46.5777, 11.6724]},
        'Miraortisei':    {'coords': [46.5779, 11.6581]},
        'Costamula':      {'coords': [46.5843, 11.6941]},
        'Col Raiser':     {'coords': [46.5648, 11.7365]},
        'Monte Pana':     {'coords': [46.5509, 11.7156]},
        'Dantercepies':   {'coords': [46.5563, 11.7674]},
        'Vallunga':       {'coords': [46.5588, 11.7671]},
        'Daunëi':         {'coords': [46.5625, 11.7540]},
        'Ranui':          {'coords': [46.6369, 11.7207]},
        'Alpe di Siusi':  {'coords': [46.5400, 11.5633]},
    }

    m = folium.Map(location=VG_CENTER, zoom_start=12, tiles='OpenStreetMap')

    # Valley stops — large markers
    for name, info in valley_stops.items():
        folium.CircleMarker(
            location=info['coords'],
            radius=info['radius'],
            color=info['color'],
            fill=True,
            fill_color=info['color'],
            fill_opacity=0.8,
            popup=folium.Popup(f"<b>{name}</b>", max_width=150),
            tooltip=name,
        ).add_to(m)

    # Other stops — grey markers
    for name, info in other_stops.items():
        folium.CircleMarker(
            location=info['coords'],
            radius=5,
            color='#999',
            fill=True,
            fill_color='#999',
            fill_opacity=0.7,
            popup=folium.Popup(f"<b>{name}</b>", max_width=150),
            tooltip=name,
        ).add_to(m)

    return m


# -- Main --------------------------------------------------------------------
def main():
    # Auto-refresh GTFS data if stale (>24h) or missing; then load (cached)
    _ensure_fresh_gtfs()
    stations, vg_routes, vg_trips, vg_stop_times, vg_trip_destinations, calendar_df, calendar_dates_df = load_data()

    st.title("\U0001f68d Val Gardena Bus Schedules")
    st.markdown("*Bus stops and schedules for Val Gardena, Bolzano, Ponte Gardena & Bressanone*")

    main_stations = stations[stations['is_main']]

    # Sidebar stats
    st.sidebar.header("Val Gardena Network")
    st.sidebar.metric("Main Stations", len(main_stations))
    st.sidebar.metric("All Stations", len(stations))
    st.sidebar.metric("Routes", vg_routes['route_short_name'].nunique())

    # Legend in sidebar
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Village Colors**")
    for village, color in VILLAGE_COLORS.items():
        st.sidebar.markdown(
            f'<span style="color:{color}; font-size:18px;">&#9679;</span> {village}',
            unsafe_allow_html=True,
        )

    # Tabs
    tab1, tab2, tab3 = st.tabs(["\U0001f5fa\ufe0f Valley Map", "\U0001f4c5 Schedules", "\U0001f68c Routes"])

    # -- TAB 1: Schematic Map ------------------------------------------------
    with tab1:
        svg = create_schematic_svg(stations)
        components.html(svg, height=220)

        # 2D geographic route network map
        st.markdown("### Bus Route Network from Ortisei")
        route_paths = load_route_network()
        network_svg = create_route_network_svg(route_paths)
        components.html(network_svg, height=530)

        # Geographic stop locations map
        st.markdown("### Geographic Stop Locations")
        geo_svg = create_geographic_network_svg()
        components.html(geo_svg, height=630)

        # Interactive geographic map
        st.markdown("### Interactive Map")
        geo_map = create_interactive_map()
        st_folium(geo_map, width=960, height=400, returned_objects=[])

        # Village bus network PDF maps
        st.markdown("### Village Bus Network Maps")
        col_o, col_sc, col_se = st.columns(3)
        with col_o:
            st.link_button("Ortisei", "https://www.valgardena.it/dl/stchristina/pdf/Network_bus_ortisei.pdf")
        with col_sc:
            st.link_button("S. Cristina", "https://www.valgardena.it/dl/stchristina/pdf/Network_bus_scristina.pdf")
        with col_se:
            st.link_button("Selva", "https://www.valgardena.it/dl/stchristina/pdf/Network_bus_selva.pdf")
        st.link_button("Full Val Gardena Network (all buses + lifts)", "https://www.valgardena.it/dl/stchristina/pdf/Network_bus_lifts_Val_Gardena.pdf")

    # -- TAB 2: Schedules ----------------------------------------------------
    with tab2:
        st.header("Departure Board")

        # Row 1: Village selector + Station picker
        col1, col2 = st.columns([1, 3])

        with col1:
            VILLAGE_LABELS = {
                "St. Ulrich / Ortisei": "St. Ulrich",
                "St. Christina / S. Cristina": "St. Christina",
                "Wolkenstein / Selva": "Wolkenstein",
                "Bolzano / Bozen": "Bolzano",
                "Ponte Gardena": "Ponte Gardena",
                "Bressanone / Brixen": "Bressanone",
            }
            village_label = st.radio(
                "From",
                options=list(VILLAGE_LABELS.keys()),
            )
            village = VILLAGE_LABELS[village_label]

        with col2:
            show_all_sched = st.checkbox(
                "Show all stops", value=False, key="sched_all",
            )

            is_external = village in EXTERNAL_LOCATIONS
            if show_all_sched and not is_external:
                village_stations = stations[stations['location'] == village]
            else:
                village_stations = main_stations[main_stations['location'] == village]

            main_order = {name: i for i, name in enumerate(MAIN_STOP_NAMES)}
            village_stations = village_stations.copy()
            village_stations['_priority'] = village_stations['stop_name'].map(main_order).fillna(999)
            village_stations = village_stations.sort_values(['_priority', 'departures'], ascending=[True, False])
            village_stations = village_stations.drop(columns=['_priority'])

            if village_stations.empty:
                st.warning(f"No stations found in {village}")
                station_name = None
            else:
                station_name = st.selectbox(
                    "Station",
                    options=village_stations['stop_name'].tolist(),
                )

            # Destination filter (by stop)
            origin_village = stations[stations['stop_name'] == station_name].iloc[0]['location'] if station_name else None
            dest_stop_options = ["All destinations"]
            dest_stop_ids_map = {}  # stop_name -> list of stop_ids
            for loc in ["St. Ulrich", "St. Christina", "Wolkenstein", "Bolzano", "Ponte Gardena", "Bressanone"]:
                if loc == origin_village:
                    continue
                loc_is_ext = loc in EXTERNAL_LOCATIONS
                if show_all_sched and not loc_is_ext:
                    loc_stations = stations[stations['location'] == loc]
                else:
                    loc_stations = main_stations[main_stations['location'] == loc]
                for _, row in loc_stations.sort_values('departures', ascending=False).iterrows():
                    dest_stop_options.append(row['stop_name'])
                    dest_stop_ids_map[row['stop_name']] = row['stop_ids']
            dest_stop_name = st.selectbox("To", options=dest_stop_options)
            dest_selected = dest_stop_name != "All destinations"

        # Row 2: Date and time pickers
        col3, col4 = st.columns(2)

        with col3:
            target_date = st.date_input("Date", value=date.today())

        with col4:
            time_filter = st.time_input("Departures after", value=time(8, 0))

        time_str = time_filter.strftime("%H:%M:00")

        # Filter to services active on the selected date
        active_services = get_active_service_ids(calendar_df, calendar_dates_df, target_date)
        active_trip_ids = set(vg_trips[vg_trips['service_id'].isin(active_services)]['trip_id'])
        active_stop_times = vg_stop_times[vg_stop_times['trip_id'].isin(active_trip_ids)]

        # Show schematic with selected stop highlighted
        if station_name:
            sched_svg = create_schematic_svg(stations, selected_stop=station_name)
            components.html(sched_svg, height=220)

        # Build schedule
        if station_name is not None and dest_selected:
            # --- Destination-filtered schedule (origin stop -> destination stop) ---
            # Origin: use selected station's stop_ids (expanded for external)
            origin_stop_ids = stations[stations['stop_name'] == station_name].iloc[0]['stop_ids']
            if origin_village in EXTERNAL_LOCATIONS:
                origin_stop_ids = sum(
                    stations[stations['location'] == origin_village]['stop_ids'].tolist(), []
                )

            # Destination: use selected destination stop's stop_ids
            dest_stop_ids = dest_stop_ids_map.get(dest_stop_name, [])

            # Get origin and dest stop_times
            origin_st = active_stop_times[active_stop_times['stop_id'].isin(origin_stop_ids)][
                ['trip_id', 'stop_id', 'stop_sequence', 'departure_time']
            ]
            dest_st = active_stop_times[active_stop_times['stop_id'].isin(dest_stop_ids)][
                ['trip_id', 'stop_sequence', 'arrival_time']
            ]

            # Find valid trips: origin before destination
            merged = origin_st.merge(dest_st, on='trip_id', suffixes=('_orig', '_dest'))
            valid = merged[merged['stop_sequence_dest'] > merged['stop_sequence_orig']]

            if not valid.empty:
                # For each trip: take the first origin stop and first dest stop in sequence
                valid = valid.sort_values(['trip_id', 'stop_sequence_orig', 'stop_sequence_dest'])
                per_trip = valid.drop_duplicates('trip_id', keep='first')

                # Apply time filter
                if time_str:
                    per_trip = per_trip[per_trip['departure_time'] >= time_str]

                # Add route info
                per_trip = per_trip.merge(
                    vg_trips[['trip_id', 'route_id']], on='trip_id'
                ).merge(
                    vg_routes[['route_id', 'route_short_name']], on='route_id'
                ).merge(
                    vg_trip_destinations[['trip_id', 'destination']], on='trip_id', how='left'
                )

                per_trip = per_trip.sort_values('departure_time')

                # Deduplicate: same route within 2 min = same bus
                keep = []
                prev_route, prev_min = None, -999
                for idx in per_trip.index:
                    route = per_trip.loc[idx, 'route_short_name']
                    parts = per_trip.loc[idx, 'departure_time'].split(':')
                    mins = int(parts[0]) * 60 + int(parts[1])
                    if route != prev_route or (mins - prev_min) >= 2:
                        keep.append(idx)
                        prev_route, prev_min = route, mins
                per_trip = per_trip.loc[keep]

                schedule = per_trip

                if not schedule.empty:
                    st.success(f"**{len(schedule)}** departures from **{station_name}** to **{dest_stop_name}**")

                    display = schedule[['departure_time', 'route_short_name', 'destination', 'arrival_time']].copy()
                    display.columns = ['Time', 'Route', 'Destination', 'Arrival']
                    display.insert(0, 'Station', station_name)
                    display['Time'] = display['Time'].apply(format_time)
                    display['Arrival'] = display['Arrival'].apply(format_time)

                    tbl = display.head(50)
                    tbl.index = range(1, len(tbl) + 1)
                    st.table(tbl)

                    if len(schedule) > 50:
                        st.info(f"Showing first 50 of {len(schedule)} departures")
                else:
                    st.warning("No departures found after the selected time")
            else:
                st.warning(f"No buses found from {station_name} to {dest_stop_name}")

        elif station_name is not None:
            # --- No destination filter: show all departures from selected stop ---
            station_row = stations[stations['stop_name'] == station_name].iloc[0]
            # For external locations, expand to all stops in that village
            origin_loc = station_row['location']
            if origin_loc in EXTERNAL_LOCATIONS:
                all_village_ids = sum(
                    stations[stations['location'] == origin_loc]['stop_ids'].tolist(), []
                )
                station_row = station_row.copy()
                station_row['stop_ids'] = all_village_ids
            schedule = get_station_schedule(
                station_row, active_stop_times, vg_trips, vg_routes,
                vg_trip_destinations, after_time=time_str
            )

            # Filter out buses whose destination is in the same village as origin
            if not schedule.empty:
                origin_stop_names = set(
                    stations[stations['location'] == origin_loc]['stop_name']
                )
                schedule = schedule[~schedule['destination'].isin(origin_stop_names)]
                # Also catch headsign variants (e.g. "Bolzano Autostazione")
                schedule = schedule[
                    ~schedule['destination'].str.startswith(origin_loc + ' ', na=False)
                    | (origin_loc == '')
                ]

            if not schedule.empty:
                st.success(f"**{len(schedule)}** departures from **{station_name}**")

                display = schedule[['departure_time', 'route_short_name', 'destination']].copy()
                display.columns = ['Time', 'Route', 'Destination']
                display.insert(0, 'Station', station_name)
                display['Time'] = display['Time'].apply(format_time)

                tbl = display.head(50)
                tbl.index = range(1, len(tbl) + 1)
                st.table(tbl)

                if len(schedule) > 50:
                    st.info(f"Showing first 50 of {len(schedule)} departures")
            else:
                st.warning("No departures found after the selected time")

    # -- TAB 3: Routes -------------------------------------------------------
    with tab3:
        st.header("Bus Routes")

        # Build route summary grouped by route_short_name
        route_trips = vg_trips.merge(
            vg_routes[['route_id', 'route_short_name']],
            on='route_id'
        )

        # Join pre-computed destinations
        route_trips = route_trips.merge(
            vg_trip_destinations[['trip_id', 'destination']],
            on='trip_id',
            how='left'
        )

        # Collect unique destinations per route
        route_summary = route_trips.groupby('route_short_name').agg(
            destinations=('destination', lambda x: ', '.join(
                sorted(set(v for v in x.dropna().unique() if v))
            )),
            daily_trips=('trip_id', 'nunique'),
        ).reset_index()

        route_summary.columns = ['Route', 'Destinations', 'Daily Trips']
        route_summary = route_summary.sort_values('Route')
        route_summary.index = range(1, len(route_summary) + 1)

        st.markdown(f"**{len(route_summary)}** unique routes serve the Val Gardena area")
        st.table(route_summary)

    # Footer
    st.sidebar.markdown("---")
    st.sidebar.info(
        "Bus schedules for Val Gardena.\n\n"
        "Data: Open Data Hub GTFS - STA"
    )

    stops_file = DATA_DIR / "transport_stop_times.csv"
    if stops_file.exists():
        age_hours = (_time.time() - stops_file.stat().st_mtime) / 3600
        if age_hours < 1:
            age_text = "just refreshed"
        elif age_hours < 24:
            age_text = f"updated {int(age_hours)}h ago"
        else:
            age_text = f"updated {int(age_hours / 24)}d ago"
        file_time = datetime.fromtimestamp(os.path.getmtime(stops_file))
        st.sidebar.caption(
            f"Schedule data: {age_text}\n\n"
            f"({file_time.strftime('%Y-%m-%d %H:%M')})"
        )


if __name__ == "__main__":
    main()
