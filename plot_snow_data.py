import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import os
import sys

def plot_snow_data(csv_path='data/snow_data.csv'):
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return

    # Load data (skip comment lines starting with #)
    try:
        df = pd.read_csv(csv_path, comment='#', encoding='utf-8')
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return

    if df.empty:
        print("CSV is empty.")
        return

    # Normalize ski_area names
    def normalize_name(n):
        if not isinstance(n, str): return n
        return n.replace('Ã«', 'ë').replace('Ã¼', 'ü').strip()
    
    df['ski_area'] = df['ski_area'].apply(normalize_name)

    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Ensure snow depths are numeric
    for col in ['snow_valley_cm', 'snow_mountain_cm', 'new_snow_cm']:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # Extract date for grouping
    df['date'] = df['timestamp'].dt.date
    
    unique_days = sorted(df['date'].unique())
    num_days = len(unique_days)
    
    if num_days == 0:
        print("No data available to plot.")
        return

    # If we have multiple snapshots per day, we'll take the latest one per day for the bar chart
    # or we can plot trends if there are many. 
    # Let's assume the user wants to see the current state or daily comparison.
    
    # Create vertically stacked subplots for each day
    fig, axes = plt.subplots(num_days, 1, figsize=(16, 8 * num_days), squeeze=False)
    
    # High contrast colormap
    cmap = plt.get_cmap('ocean') # Snow/water themed

    for i, day in enumerate(unique_days):
        ax = axes[i, 0]
        day_df = df[df['date'] == day]
        
        # Take the most recent entry for each ski area on this day
        latest_data = day_df.sort_values('timestamp').groupby('ski_area').last().reset_index()
        latest_data = latest_data.sort_values('snow_mountain_cm', ascending=False)
        
        areas = latest_data['ski_area']
        mountain = latest_data['snow_mountain_cm']
        valley = latest_data['snow_valley_cm']
        new_snow = latest_data['new_snow_cm']
        
        x = range(len(areas))
        width = 0.35
        
        ax.bar([pos - width/2 for pos in x], mountain, width, label='Snow Mountain (cm)', color='#1f77b4', alpha=0.8)
        ax.bar([pos + width/2 for pos in x], valley, width, label='Snow Valley (cm)', color='#aec7e8', alpha=0.8)
        
        # Add new snow as a separate marker or text if it exists
        for idx, val in enumerate(new_snow):
            if val > 0:
                ax.text(idx, max(mountain[idx], valley[idx]) + 5, f"+{int(val)}cm new", 
                        ha='center', va='bottom', color='red', fontweight='bold', fontsize=9)

        ax.set_title(f'Dolomites Snow Report - {day}', fontweight='bold', fontsize=18)
        ax.set_ylabel('Snow Depth (cm)', fontsize=14)
        ax.set_xticks(x)
        ax.set_xticklabels(areas, rotation=45, ha='right', fontsize=10)
        ax.legend(fontsize=12)
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        
        # Set a reasonable y-limit
        if not latest_data.empty:
            max_snow = max(mountain.max(), valley.max())
            ax.set_ylim(0, max_snow * 1.2 + 10)

    plt.tight_layout()

    # Create plots/ directory relative to CSV location
    plots_dir = os.path.join(os.path.dirname(csv_path) or '.', 'plots')
    os.makedirs(plots_dir, exist_ok=True)

    output_file = os.path.join(plots_dir, 'snow_report.png')
    plt.savefig(output_file, dpi=120)
    print(f"Snow plot saved to {output_file}")
    plt.close()

if __name__ == "__main__":
    csv_file = sys.argv[1] if len(sys.argv) > 1 else 'data/snow_data.csv'
    plot_snow_data(csv_file)
