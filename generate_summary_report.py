#!/usr/bin/env python3
"""
Generate monthly summary statistics report for parking data.
Creates plots and a markdown report.
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
from pathlib import Path
import os

DATA_FILE = Path(__file__).parent / "data" / "parking_data_dolomites.csv"
PLOTS_DIR = Path(__file__).parent / "data" / "plots"
REPORT_FILE = Path(__file__).parent / "data" / "plots" / "monthly_summary.md"


def load_data():
    """Load and prepare parking data."""
    print("Loading data...")
    df = pd.read_csv(DATA_FILE, comment='#', encoding='utf-8')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['available'] = pd.to_numeric(df['available'], errors='coerce')
    df = df.dropna(subset=['available'])
    df['available'] = df['available'].clip(lower=0)

    # Extract time components
    df['date'] = df['timestamp'].dt.date
    df['month'] = df['timestamp'].dt.to_period('M')
    df['year_month'] = df['timestamp'].dt.strftime('%Y-%m')
    df['hour'] = df['timestamp'].dt.hour

    print(f"Loaded {len(df):,} observations")
    print(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"Parking stations: {df['name'].nunique()}")

    return df


def plot_observations_per_month(df):
    """Plot number of observations per month."""
    monthly_counts = df.groupby('year_month').size()

    fig, ax = plt.subplots(figsize=(14, 5))
    bars = ax.bar(range(len(monthly_counts)), monthly_counts.values, color='steelblue', edgecolor='navy')

    ax.set_xticks(range(len(monthly_counts)))
    ax.set_xticklabels(monthly_counts.index, rotation=45, ha='right')
    ax.set_xlabel('Month')
    ax.set_ylabel('Number of Observations')
    ax.set_title('Data Collection Volume Over Time', fontweight='bold', fontsize=14)
    ax.grid(axis='y', linestyle='--', alpha=0.7)

    # Add value labels on bars
    for bar, val in zip(bars, monthly_counts.values):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1000,
                f'{val:,}', ha='center', va='bottom', fontsize=8)

    plt.tight_layout()
    output_file = PLOTS_DIR / 'summary_observations_per_month.png'
    plt.savefig(output_file, dpi=120)
    plt.close()
    print(f"Saved: {output_file}")
    return monthly_counts


def plot_avg_availability_per_month(df):
    """Plot average availability per month for each parking station."""
    # Calculate monthly averages per station
    monthly_avg = df.groupby(['year_month', 'name'])['available'].mean().unstack()

    fig, ax = plt.subplots(figsize=(16, 8))

    cmap = plt.get_cmap('turbo')
    stations = sorted(monthly_avg.columns)
    colors = {s: cmap(i / max(1, len(stations)-1)) for i, s in enumerate(stations)}

    for station in stations:
        if station in monthly_avg.columns:
            data = monthly_avg[station].dropna()
            ax.plot(range(len(data)), data.values, marker='o', markersize=4,
                   label=station, color=colors[station], linewidth=1.5)

    ax.set_xticks(range(len(monthly_avg.index)))
    ax.set_xticklabels(monthly_avg.index, rotation=45, ha='right')
    ax.set_xlabel('Month')
    ax.set_ylabel('Average Available Spaces')
    ax.set_title('Monthly Average Availability by Parking Station', fontweight='bold', fontsize=14)
    ax.legend(bbox_to_anchor=(1.01, 1), loc='upper left', fontsize='small')
    ax.grid(True, linestyle='--', alpha=0.7)

    plt.tight_layout()
    output_file = PLOTS_DIR / 'summary_avg_availability_by_station.png'
    plt.savefig(output_file, dpi=120)
    plt.close()
    print(f"Saved: {output_file}")
    return monthly_avg


def plot_overall_availability_trend(df):
    """Plot overall average availability trend."""
    # Daily average across all stations
    daily_avg = df.groupby('date')['available'].mean()

    # Convert to DataFrame for rolling average
    daily_df = pd.DataFrame({'date': daily_avg.index, 'available': daily_avg.values})
    daily_df['date'] = pd.to_datetime(daily_df['date'])
    daily_df = daily_df.sort_values('date')
    daily_df['rolling_7d'] = daily_df['available'].rolling(7, min_periods=1).mean()

    fig, ax = plt.subplots(figsize=(14, 5))

    ax.plot(daily_df['date'], daily_df['available'], alpha=0.3, color='steelblue', label='Daily Average')
    ax.plot(daily_df['date'], daily_df['rolling_7d'], color='navy', linewidth=2, label='7-Day Rolling Average')

    ax.set_xlabel('Date')
    ax.set_ylabel('Average Available Spaces')
    ax.set_title('Overall Parking Availability Trend', fontweight='bold', fontsize=14)
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    plt.xticks(rotation=45, ha='right')

    plt.tight_layout()
    output_file = PLOTS_DIR / 'summary_overall_trend.png'
    plt.savefig(output_file, dpi=120)
    plt.close()
    print(f"Saved: {output_file}")
    return daily_df


def plot_hourly_pattern(df):
    """Plot average availability by hour of day."""
    hourly_avg = df.groupby('hour')['available'].mean()

    fig, ax = plt.subplots(figsize=(12, 5))

    bars = ax.bar(hourly_avg.index, hourly_avg.values, color='steelblue', edgecolor='navy')

    ax.set_xlabel('Hour of Day')
    ax.set_ylabel('Average Available Spaces')
    ax.set_title('Average Parking Availability by Hour of Day', fontweight='bold', fontsize=14)
    ax.set_xticks(range(24))
    ax.set_xticklabels([f'{h:02d}:00' for h in range(24)], rotation=45, ha='right')
    ax.grid(axis='y', linestyle='--', alpha=0.7)

    plt.tight_layout()
    output_file = PLOTS_DIR / 'summary_hourly_pattern.png'
    plt.savefig(output_file, dpi=120)
    plt.close()
    print(f"Saved: {output_file}")
    return hourly_avg


def plot_by_region(df):
    """Plot average availability by region over time."""
    if 'region' not in df.columns:
        print("No region column found, skipping region plot")
        return None

    monthly_region = df.groupby(['year_month', 'region'])['available'].mean().unstack()

    fig, ax = plt.subplots(figsize=(14, 6))

    colors = ['#e41a1c', '#377eb8', '#4daf4a', '#984ea3', '#ff7f00']
    for i, region in enumerate(monthly_region.columns):
        data = monthly_region[region].dropna()
        ax.plot(range(len(data)), data.values, marker='o', markersize=6,
               label=region, color=colors[i % len(colors)], linewidth=2)

    ax.set_xticks(range(len(monthly_region.index)))
    ax.set_xticklabels(monthly_region.index, rotation=45, ha='right')
    ax.set_xlabel('Month')
    ax.set_ylabel('Average Available Spaces')
    ax.set_title('Monthly Average Availability by Region', fontweight='bold', fontsize=14)
    ax.legend()
    ax.grid(True, linestyle='--', alpha=0.7)

    plt.tight_layout()
    output_file = PLOTS_DIR / 'summary_by_region.png'
    plt.savefig(output_file, dpi=120)
    plt.close()
    print(f"Saved: {output_file}")
    return monthly_region


def generate_statistics(df, monthly_counts):
    """Generate summary statistics."""
    stats = {
        'total_observations': len(df),
        'date_range_start': df['timestamp'].min().strftime('%Y-%m-%d'),
        'date_range_end': df['timestamp'].max().strftime('%Y-%m-%d'),
        'num_stations': df['name'].nunique(),
        'num_months': len(monthly_counts),
        'avg_observations_per_month': int(monthly_counts.mean()),
        'total_days': (df['timestamp'].max() - df['timestamp'].min()).days,
    }

    # Per-station stats
    station_stats = df.groupby('name').agg({
        'available': ['mean', 'min', 'max', 'std'],
        'timestamp': 'count'
    }).round(1)
    station_stats.columns = ['avg_available', 'min_available', 'max_available', 'std_available', 'observations']
    station_stats = station_stats.sort_values('observations', ascending=False)

    return stats, station_stats


def write_markdown_report(stats, station_stats, monthly_counts):
    """Generate markdown report."""
    PLOTS_DIR.mkdir(parents=True, exist_ok=True)

    report = f"""# Dolomites Parking Data - Monthly Summary Report

*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*

## Overview

| Metric | Value |
|--------|-------|
| Total Observations | {stats['total_observations']:,} |
| Data Collection Period | {stats['date_range_start']} to {stats['date_range_end']} |
| Total Days Covered | {stats['total_days']} |
| Number of Months | {stats['num_months']} |
| Parking Stations | {stats['num_stations']} |
| Avg. Observations/Month | {stats['avg_observations_per_month']:,} |

---

## Data Collection Volume

Number of parking availability observations recorded per month.

![Observations Per Month](summary_observations_per_month.png)

---

## Overall Availability Trend

Daily average parking availability across all stations, with 7-day rolling average.

![Overall Trend](summary_overall_trend.png)

---

## Monthly Average by Station

Average available spaces per month for each parking station.

![Average Availability by Station](summary_avg_availability_by_station.png)

---

## Availability by Region

Monthly average availability grouped by geographic region.

![Availability by Region](summary_by_region.png)

---

## Daily Patterns

Average parking availability by hour of day (across all data).

![Hourly Pattern](summary_hourly_pattern.png)

---

## Per-Station Statistics

| Station | Avg Available | Min | Max | Std Dev | Observations |
|---------|--------------|-----|-----|---------|--------------|
"""

    for station, row in station_stats.head(20).iterrows():
        report += f"| {station} | {row['avg_available']:.1f} | {int(row['min_available'])} | {int(row['max_available'])} | {row['std_available']:.1f} | {int(row['observations']):,} |\n"

    if len(station_stats) > 20:
        report += f"\n*Showing top 20 of {len(station_stats)} stations*\n"

    report += f"""
---

## Monthly Observation Counts

| Month | Observations |
|-------|--------------|
"""

    for month, count in monthly_counts.items():
        report += f"| {month} | {count:,} |\n"

    report += """
---

*Data source: South Tyrol Open Data Hub - Parking API*
"""

    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\nMarkdown report saved to: {REPORT_FILE}")


def main():
    print("=" * 60)
    print("Generating Monthly Summary Report")
    print("=" * 60)

    # Load data
    df = load_data()

    # Generate plots
    print("\nGenerating plots...")
    monthly_counts = plot_observations_per_month(df)
    plot_avg_availability_per_month(df)
    plot_overall_availability_trend(df)
    plot_hourly_pattern(df)
    plot_by_region(df)

    # Generate statistics
    print("\nCalculating statistics...")
    stats, station_stats = generate_statistics(df, monthly_counts)

    # Write report
    write_markdown_report(stats, station_stats, monthly_counts)

    print("\n" + "=" * 60)
    print("Done!")


if __name__ == "__main__":
    main()
