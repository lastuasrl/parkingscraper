import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os

def plot_parking_data(csv_path='data/parking_data_dolomites.csv'):
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return

    print("Loading data...")
    try:
        df = pd.read_csv(csv_path, comment='#', encoding='utf-8')
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    if df.empty:
        print("CSV is empty.")
        return

    # Normalize names (handle encoding issues)
    def normalize_name(n):
        if not isinstance(n, str): return n
        replacements = [
            ('Ã¼', 'ü'), ('Ã«', 'ë'), ('Ã¤', 'ä'), ('Ã¶', 'ö'),
            ('ÃŸ', 'ß'), ('SÃ¼d', 'Süd'), ('SÃ«uc', 'Sëuc'),
            ('Dantercepies', 'Dantercëpies'), ('Mont Seuc', 'Mont Sëuc')
        ]
        for old, new in replacements:
            n = n.replace(old, new)
        return n.strip()

    df['name'] = df['name'].apply(normalize_name)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['available'] = pd.to_numeric(df['available'], errors='coerce').clip(lower=0)
    df = df.dropna(subset=['available'])

    # Extract time components
    df['time_of_day'] = df['timestamp'].dt.hour * 60 + df['timestamp'].dt.minute
    df['year'] = df['timestamp'].dt.isocalendar().year
    df['week'] = df['timestamp'].dt.isocalendar().week
    df['year_week'] = df['year'].astype(str) + '-W' + df['week'].astype(str).str.zfill(2)

    # Filter to 7am-6pm
    df = df[(df['time_of_day'] >= 420) & (df['time_of_day'] <= 1080)]
    df['time_bucket'] = (df['time_of_day'] // 5) * 5

    # Get date ranges per week (before aggregation)
    print("Computing weekly averages...")
    week_ranges = df.groupby('year_week')['timestamp'].agg(['min', 'max'])
    week_ranges['start'] = week_ranges['min'].dt.date
    week_ranges['end'] = week_ranges['max'].dt.date

    # PRE-COMPUTE all weekly averages in ONE operation
    weekly_avg = df.groupby(['year_week', 'name', 'time_bucket'])['available'].mean().reset_index()

    unique_weeks = sorted(weekly_avg['year_week'].unique())
    num_weeks = len(unique_weeks)

    if num_weeks == 0:
        print("No data available to plot.")
        return

    print(f"Generating plots for {num_weeks} weeks...")

    # Color map
    all_locations = sorted(weekly_avg['name'].unique())
    cmap = plt.get_cmap('turbo')
    color_map = {loc: cmap(i / max(1, len(all_locations) - 1)) for i, loc in enumerate(all_locations)}

    # Pre-compute time axis
    reference_date = pd.Timestamp('2000-01-01')
    start_time = reference_date + pd.Timedelta(hours=7)
    end_time = reference_date + pd.Timedelta(hours=18)
    all_buckets = sorted(weekly_avg['time_bucket'].unique())
    bucket_to_time = {b: reference_date + pd.Timedelta(minutes=int(b)) for b in all_buckets}

    # Create plots directory
    plots_dir = os.path.join(os.path.dirname(csv_path) or '.', 'plots')
    os.makedirs(plots_dir, exist_ok=True)

    # Generate plots
    for year_week in unique_weeks:
        week_avg = weekly_avg[weekly_avg['year_week'] == year_week]
        week_start = week_ranges.loc[year_week, 'start']
        week_end = week_ranges.loc[year_week, 'end']

        fig, ax = plt.subplots(figsize=(20, 8))

        for loc in sorted(week_avg['name'].unique()):
            loc_data = week_avg[week_avg['name'] == loc].sort_values('time_bucket')
            times = [bucket_to_time[b] for b in loc_data['time_bucket']]
            ax.plot(times, loc_data['available'], label=loc, marker='.', markersize=4, linewidth=1.5, color=color_map[loc])

        ax.set_xlim(start_time, end_time)
        ax.set_title(f'Weekly Average Parking Availability - {year_week} ({week_start} to {week_end})', fontweight='bold', fontsize=16)
        ax.set_xlabel('Time of Day', fontsize=12)
        ax.set_ylabel('Average Available Spaces', fontsize=12)
        ax.legend(bbox_to_anchor=(1.01, 1), loc='upper left', fontsize='small')
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax.tick_params(axis='x', rotation=45)

        plt.tight_layout()
        output_file = os.path.join(plots_dir, f'parking_{year_week}.png')
        plt.savefig(output_file, dpi=100)
        print(f"Plot saved to {output_file}")
        plt.close()

    # Generate markdown report
    md_file = os.path.join(plots_dir, 'parking_report.md')
    with open(md_file, 'w', encoding='utf-8') as f:
        f.write('# Weekly Parking Availability Report\n\n')
        for year_week in unique_weeks:
            f.write(f'## {year_week}\n\n')
            f.write(f'![Parking {year_week}](parking_{year_week}.png)\n\n')
    print(f"Markdown report saved to {md_file}")

if __name__ == "__main__":
    import sys
    csv_file = sys.argv[1] if len(sys.argv) > 1 else 'data/parking_data_dolomites.csv'
    plot_parking_data(csv_file)
