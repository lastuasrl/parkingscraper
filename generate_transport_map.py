#!/usr/bin/env python3
"""
Generate interactive map of public transport stops.
Creates an HTML map with clustered markers for all transport stops in the Dolomites region.
"""

import sys
import pandas as pd
import folium
from folium.plugins import MarkerCluster
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
from pathlib import Path

# Constants (matching existing scripts)
DATA_DIR = Path(__file__).parent / "data" / "transport"
STOPS_FILE = DATA_DIR / "transport_stops.csv"
PLOTS_DIR = DATA_DIR / "plots"
MAP_FILE = PLOTS_DIR / "transport_map.html"


def load_stops():
    """Load and validate transport stops from CSV."""
    print("Loading transport data...")

    try:
        stops_df = pd.read_csv(STOPS_FILE, encoding='utf-8')
    except FileNotFoundError:
        print(f"Error: {STOPS_FILE} not found.")
        print("Run: python download_transport.py")
        sys.exit(1)

    # Validate coordinates
    initial_count = len(stops_df)
    stops_df = stops_df.dropna(subset=['stop_lat', 'stop_lon'])

    if len(stops_df) < initial_count:
        print(f"Warning: Removed {initial_count - len(stops_df)} stops with missing coordinates")

    # Fill empty regions with "Unknown"
    stops_df['region'] = stops_df['region'].fillna('Unknown')

    print(f"[OK] Loaded {len(stops_df):,} transport stops")

    return stops_df


def create_region_colors(stops_df):
    """Generate color mapping for regions using matplotlib colormap."""
    regions = sorted(stops_df['region'].unique())

    # Use tab10 colormap for consistency with existing visualizations
    colors = plt.cm.tab10(np.linspace(0, 1, len(regions)))

    # Convert RGBA to hex color codes
    region_colors = {}
    for region, color in zip(regions, colors):
        hex_color = mcolors.rgb2hex(color[:3])
        region_colors[region] = hex_color

    print(f"[OK] Found {len(regions)} regions")

    return region_colors


def build_map(stops_df, region_colors):
    """Create Folium map with clustered markers."""
    # Calculate geographic center from data bounds
    center_lat = (stops_df['stop_lat'].min() + stops_df['stop_lat'].max()) / 2
    center_lon = (stops_df['stop_lon'].min() + stops_df['stop_lon'].max()) / 2

    print(f"Creating map centered at {center_lat:.2f}°N, {center_lon:.2f}°E")

    # Initialize map
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=10,
        tiles='OpenStreetMap',
        control_scale=True
    )

    # Create marker cluster for performance
    marker_cluster = MarkerCluster(
        max_cluster_radius=50,
        spiderfyOnMaxZoom=True,
        showCoverageOnHover=False,
        zoomToBoundsOnClick=True
    )

    print(f"Adding {len(stops_df):,} markers with clustering...")

    # Add markers
    for idx, row in stops_df.iterrows():
        # Create popup content
        popup_html = f"""
        <div style="font-family: Arial, sans-serif; min-width: 200px;">
            <b>Stop Name:</b> {row['stop_name']}<br>
            <b>Location:</b> {row['location']}<br>
            <b>Region:</b> {row['region']}<br>
            <b>Coordinates:</b> {row['stop_lat']:.4f}, {row['stop_lon']:.4f}
        </div>
        """

        popup = folium.Popup(popup_html, max_width=300)

        # Get region color
        color = region_colors.get(row['region'], '#808080')

        # Create marker
        folium.CircleMarker(
            location=[row['stop_lat'], row['stop_lon']],
            radius=6,
            popup=popup,
            color=color,
            fillColor=color,
            fillOpacity=0.7,
            weight=2
        ).add_to(marker_cluster)

    # Add marker cluster to map
    marker_cluster.add_to(m)

    # Fit bounds to show all markers
    m.fit_bounds([
        [stops_df['stop_lat'].min(), stops_df['stop_lon'].min()],
        [stops_df['stop_lat'].max(), stops_df['stop_lon'].max()]
    ])

    return m


def add_legend(m, stops_df, region_colors):
    """Add HTML legend to map showing regions and counts."""
    # Count stops per region
    region_counts = stops_df['region'].value_counts().to_dict()

    # Build legend HTML
    legend_html = """
    <div style="
        position: fixed;
        top: 10px;
        right: 10px;
        width: 250px;
        background-color: white;
        border: 2px solid grey;
        border-radius: 5px;
        padding: 10px;
        font-size: 12px;
        font-family: Arial, sans-serif;
        z-index: 9999;
        box-shadow: 2px 2px 6px rgba(0,0,0,0.3);
        max-height: 80vh;
        overflow-y: auto;
    ">
        <h4 style="margin: 0 0 10px 0; font-size: 14px;">Transport Stops by Region</h4>
    """

    # Add each region with its color and count
    for region in sorted(region_colors.keys()):
        color = region_colors[region]
        count = region_counts.get(region, 0)
        legend_html += f"""
        <div style="margin: 5px 0; display: flex; align-items: center;">
            <div style="
                width: 20px;
                height: 20px;
                background-color: {color};
                border: 1px solid black;
                border-radius: 50%;
                margin-right: 8px;
                flex-shrink: 0;
            "></div>
            <span style="flex-grow: 1;">{region}</span>
            <span style="font-weight: bold; margin-left: 5px;">{count:,}</span>
        </div>
        """

    # Add total
    total = len(stops_df)
    legend_html += f"""
        <hr style="margin: 10px 0;">
        <div style="font-weight: bold; text-align: center;">
            Total Stops: {total:,}
        </div>
    </div>
    """

    # Add legend to map
    m.get_root().html.add_child(folium.Element(legend_html))

    return m


def main():
    """Generate interactive transport stops map."""
    print("=" * 60)
    print("Transport Stops Interactive Map Generator")
    print("=" * 60)
    print()

    # Ensure output directory exists
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load data
    stops_df = load_stops()

    # Create color mapping
    region_colors = create_region_colors(stops_df)

    # Build map
    m = build_map(stops_df, region_colors)

    # Add legend
    m = add_legend(m, stops_df, region_colors)

    # Save map
    print()
    print(f"Saving map to: {MAP_FILE}")
    m.save(str(MAP_FILE))

    # Get file size
    file_size = MAP_FILE.stat().st_size / (1024 * 1024)  # MB

    # Print summary
    print()
    print("=" * 60)
    print("[SUCCESS] Map generated successfully!")
    print("=" * 60)
    print(f"File: {MAP_FILE}")
    print(f"Size: {file_size:.2f} MB")
    print(f"Stops: {len(stops_df):,}")
    print(f"Regions: {len(region_colors)}")
    print()
    print("To view the map, run:")
    print(f"  start {MAP_FILE}")
    print()


if __name__ == "__main__":
    main()
