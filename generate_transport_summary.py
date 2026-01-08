#!/usr/bin/env python3
"""
Generate summary statistics report for public transport data.
Creates plots and a markdown report for bus/train stops and routes.
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
STOPS_FILE = DATA_DIR / "transport_stops.csv"
ROUTES_FILE = DATA_DIR / "transport_routes.csv"
PLOTS_DIR = DATA_DIR / "plots"
REPORT_FILE = PLOTS_DIR / "monthly_summary.md"


def load_data():
    """Load transport data."""
    print("Loading transport data...")

    stops_df = pd.read_csv(STOPS_FILE, comment='#', encoding='utf-8')
    routes_df = pd.read_csv(ROUTES_FILE, comment='#', encoding='utf-8')

    print(f"Loaded {len(stops_df):,} stops")
    print(f"Loaded {len(routes_df):,} routes")

    return stops_df, routes_df


def plot_stops_by_region(stops_df):
    """Plot number of stops by region."""
    region_counts = stops_df['region'].value_counts()

    fig, ax = plt.subplots(figsize=(12, 6))

    colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(region_counts)))
    bars = ax.barh(range(len(region_counts)), region_counts.values, color=colors)

    ax.set_yticks(range(len(region_counts)))
    ax.set_yticklabels(region_counts.index)
    ax.set_xlabel('Number of Stops')
    ax.set_title('Public Transport Stops by Region', fontweight='bold', fontsize=14)
    ax.grid(axis='x', linestyle='--', alpha=0.7)

    # Add value labels
    for bar, val in zip(bars, region_counts.values):
        ax.text(bar.get_width() + 20, bar.get_y() + bar.get_height()/2,
                f'{val:,}', ha='left', va='center', fontsize=10)

    plt.tight_layout()
    output_file = PLOTS_DIR / 'transport_stops_by_region.png'
    plt.savefig(output_file, dpi=120)
    plt.close()
    print(f"Saved: {output_file}")
    return region_counts


def plot_stops_by_location(stops_df):
    """Plot number of stops by specific location."""
    # Get top 15 locations
    location_counts = stops_df['location'].value_counts().head(15)

    fig, ax = plt.subplots(figsize=(12, 7))

    colors = plt.cm.plasma(np.linspace(0.2, 0.8, len(location_counts)))
    bars = ax.barh(range(len(location_counts)), location_counts.values, color=colors)

    ax.set_yticks(range(len(location_counts)))
    ax.set_yticklabels(location_counts.index)
    ax.set_xlabel('Number of Stops')
    ax.set_title('Top 15 Locations by Number of Stops', fontweight='bold', fontsize=14)
    ax.grid(axis='x', linestyle='--', alpha=0.7)

    for bar, val in zip(bars, location_counts.values):
        ax.text(bar.get_width() + 10, bar.get_y() + bar.get_height()/2,
                f'{val:,}', ha='left', va='center', fontsize=10)

    plt.tight_layout()
    output_file = PLOTS_DIR / 'transport_stops_by_location.png'
    plt.savefig(output_file, dpi=120)
    plt.close()
    print(f"Saved: {output_file}")
    return location_counts


def plot_routes_by_type(routes_df):
    """Plot routes by transport type."""
    type_counts = routes_df['route_type'].value_counts()

    fig, ax = plt.subplots(figsize=(10, 6))

    colors = ['#2ecc71', '#3498db', '#9b59b6', '#e74c3c', '#f39c12']
    wedges, texts, autotexts = ax.pie(type_counts.values, labels=type_counts.index,
                                       autopct='%1.1f%%', colors=colors[:len(type_counts)],
                                       explode=[0.02] * len(type_counts))

    ax.set_title('Routes by Transport Type', fontweight='bold', fontsize=14)

    # Add legend with counts
    legend_labels = [f'{t}: {c:,}' for t, c in zip(type_counts.index, type_counts.values)]
    ax.legend(wedges, legend_labels, loc='lower right')

    plt.tight_layout()
    output_file = PLOTS_DIR / 'transport_routes_by_type.png'
    plt.savefig(output_file, dpi=120)
    plt.close()
    print(f"Saved: {output_file}")
    return type_counts


def plot_geographic_distribution(stops_df):
    """Plot geographic distribution of stops."""
    fig, ax = plt.subplots(figsize=(12, 10))

    # Color by region
    regions = stops_df['region'].unique()
    colors = plt.cm.tab10(np.linspace(0, 1, len(regions)))
    color_map = dict(zip(regions, colors))

    for region in regions:
        region_stops = stops_df[stops_df['region'] == region]
        ax.scatter(region_stops['stop_lon'], region_stops['stop_lat'],
                  c=[color_map[region]], label=region, alpha=0.6, s=20)

    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.set_title('Geographic Distribution of Transport Stops', fontweight='bold', fontsize=14)
    ax.legend(loc='upper left', fontsize='small')
    ax.grid(True, linestyle='--', alpha=0.5)

    plt.tight_layout()
    output_file = PLOTS_DIR / 'transport_geographic_distribution.png'
    plt.savefig(output_file, dpi=120)
    plt.close()
    print(f"Saved: {output_file}")


def plot_route_numbers(routes_df):
    """Plot distribution of route numbers."""
    # Extract numeric route numbers where possible
    routes_df = routes_df.copy()
    routes_df['route_num'] = pd.to_numeric(routes_df['route_short_name'], errors='coerce')
    numeric_routes = routes_df.dropna(subset=['route_num'])

    if len(numeric_routes) > 0:
        fig, ax = plt.subplots(figsize=(14, 5))

        # Group into bins
        bins = [0, 50, 100, 200, 300, 400, 500, 1000]
        labels = ['1-50', '51-100', '101-200', '201-300', '301-400', '401-500', '500+']
        numeric_routes['route_bin'] = pd.cut(numeric_routes['route_num'], bins=bins, labels=labels)
        bin_counts = numeric_routes['route_bin'].value_counts().sort_index()

        bars = ax.bar(range(len(bin_counts)), bin_counts.values, color='steelblue', edgecolor='navy')

        ax.set_xticks(range(len(bin_counts)))
        ax.set_xticklabels(bin_counts.index)
        ax.set_xlabel('Route Number Range')
        ax.set_ylabel('Number of Routes')
        ax.set_title('Distribution of Route Numbers', fontweight='bold', fontsize=14)
        ax.grid(axis='y', linestyle='--', alpha=0.7)

        for bar, val in zip(bars, bin_counts.values):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                    f'{val}', ha='center', va='bottom', fontsize=10)

        plt.tight_layout()
        output_file = PLOTS_DIR / 'transport_route_distribution.png'
        plt.savefig(output_file, dpi=120)
        plt.close()
        print(f"Saved: {output_file}")


def generate_statistics(stops_df, routes_df):
    """Generate summary statistics."""
    stats = {
        'total_stops': len(stops_df),
        'total_routes': len(routes_df),
        'num_regions': stops_df['region'].nunique(),
        'num_locations': stops_df['location'].nunique(),
        'lat_range': f"{stops_df['stop_lat'].min():.4f} - {stops_df['stop_lat'].max():.4f}",
        'lon_range': f"{stops_df['stop_lon'].min():.4f} - {stops_df['stop_lon'].max():.4f}",
    }

    return stats


def write_markdown_report(stats, stops_df, routes_df, region_counts, type_counts):
    """Generate markdown report."""
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    # Get top locations
    location_counts = stops_df['location'].value_counts()

    report = f"""# Dolomites Public Transport - Summary Report

*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*
*Data Source: Open Data Hub GTFS - STA (Südtirol Transportstrukturen AG)*

## Overview

| Metric | Value |
|--------|-------|
| Total Stops | {stats['total_stops']:,} |
| Total Routes | {stats['total_routes']:,} |
| Regions Covered | {stats['num_regions']} |
| Distinct Locations | {stats['num_locations']} |
| Latitude Range | {stats['lat_range']} |
| Longitude Range | {stats['lon_range']} |

---

## Stops by Region

Distribution of public transport stops across different regions of the Dolomites.

![Stops by Region](transport_stops_by_region.png)

| Region | Stops |
|--------|-------|
"""

    for region, count in region_counts.items():
        report += f"| {region} | {count:,} |\n"

    report += """
---

## Top Locations

The locations with the most public transport stops.

![Stops by Location](transport_stops_by_location.png)

---

## Routes by Transport Type

Breakdown of routes by type of transport (bus, train, cable car, etc.).

![Routes by Type](transport_routes_by_type.png)

| Transport Type | Routes |
|----------------|--------|
"""

    for route_type, count in type_counts.items():
        report += f"| {route_type} | {count:,} |\n"

    report += """
---

## Geographic Distribution

Map showing the geographic spread of all transport stops in the Dolomites region.

![Geographic Distribution](transport_geographic_distribution.png)

---

## Route Number Distribution

Distribution of bus/train route numbers.

![Route Distribution](transport_route_distribution.png)

---

## Sample Stops by Region

"""

    for region in ['Val Gardena', 'Alta Badia', 'Puster Valley', 'Isarco Valley']:
        region_stops = stops_df[stops_df['region'] == region]['stop_name'].head(10).tolist()
        if region_stops:
            report += f"### {region}\n\n"
            for stop in region_stops:
                report += f"- {stop}\n"
            report += "\n"

    report += """---

## Sample Routes

| Route | Name | Type |
|-------|------|------|
"""

    for _, row in routes_df.head(20).iterrows():
        name = row['route_long_name'] if row['route_long_name'] else row['route_short_name']
        report += f"| {row['route_short_name']} | {name} | {row['route_type']} |\n"

    report += """
---

*Schedule data from STA - Südtirol Transportstrukturen AG*
*License: CC0*
"""

    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\nMarkdown report saved to: {REPORT_FILE}")


def main():
    print("=" * 60)
    print("Generating Transport Summary Report")
    print("=" * 60)

    # Load data
    stops_df, routes_df = load_data()

    # Generate plots
    print("\nGenerating plots...")
    region_counts = plot_stops_by_region(stops_df)
    plot_stops_by_location(stops_df)
    type_counts = plot_routes_by_type(routes_df)
    plot_geographic_distribution(stops_df)
    plot_route_numbers(routes_df)

    # Generate statistics
    print("\nCalculating statistics...")
    stats = generate_statistics(stops_df, routes_df)

    # Write report
    write_markdown_report(stats, stops_df, routes_df, region_counts, type_counts)

    print("\n" + "=" * 60)
    print("Done!")


if __name__ == "__main__":
    main()
