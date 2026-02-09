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
    "St. Ulrich": "#2196F3",    # blue
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


# -- Main --------------------------------------------------------------------
def main():
    # Load data first (cached after first run)
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

        show_all_map = st.checkbox("Show all stops", value=False, key="map_all")
        if show_all_map:
            st.markdown(f"**All {len(stations)} stations in Val Gardena:**")
            all_display = stations[['stop_name', 'location', 'departures']].copy()
            all_display.columns = ['Stop Name', 'Village', 'Departures']
            all_display = all_display.sort_values(['Village', 'Departures'], ascending=[True, False])
            all_display.index = range(1, len(all_display) + 1)
            st.table(all_display)

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

            village_stations = village_stations.sort_values('departures', ascending=False)

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

    stops_file = DATA_DIR / "transport_stops.csv"
    if stops_file.exists():
        import os
        file_time = datetime.fromtimestamp(os.path.getmtime(stops_file))
        st.sidebar.caption(f"Data updated: {file_time.strftime('%Y-%m-%d %H:%M')}")


if __name__ == "__main__":
    main()
