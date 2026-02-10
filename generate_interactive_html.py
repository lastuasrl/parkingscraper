#!/usr/bin/env python3
"""
Generate standalone interactive HTML parking report using Plotly.
Reads from parking_data_dolomites.csv and produces parking_interactive.html.
"""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import sys
from pathlib import Path

CSV_PATH = Path(__file__).parent / "data" / "parking_data_dolomites.csv"
OUTPUT_PATH = Path(__file__).parent / "parking_interactive.html"


def load_data(csv_path):
    print(f"Loading {csv_path}...")
    df = pd.read_csv(csv_path, comment='#', encoding='utf-8')
    print(f"  {len(df):,} raw records")

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['available'] = pd.to_numeric(df['available'], errors='coerce')
    df['capacity'] = pd.to_numeric(df['capacity'], errors='coerce').fillna(0)
    df = df.dropna(subset=['available'])

    # Time components
    df['hour'] = df['timestamp'].dt.hour
    df['minute'] = df['timestamp'].dt.minute
    df['time_of_day'] = df['hour'] * 60 + df['minute']
    df['time_bucket'] = (df['time_of_day'] // 10) * 10  # 10-min buckets for HTML size
    df['month'] = df['timestamp'].dt.strftime('%Y-%m')
    df['day_of_week'] = df['timestamp'].dt.day_name()

    # ISO week
    iso = df['timestamp'].dt.isocalendar()
    df['year_week'] = iso.year.astype(str) + '-W' + iso.week.astype(str).str.zfill(2)

    # Filter 7am-6pm
    df = df[(df['time_of_day'] >= 420) & (df['time_of_day'] <= 1080)]
    print(f"  {len(df):,} records after filtering (7am-6pm)")
    print(f"  {df['name'].nunique()} stations, {df['month'].nunique()} months")
    print(f"  Range: {df['timestamp'].dt.date.min()} to {df['timestamp'].dt.date.max()}")
    return df


def make_color_map(names):
    cmap = px.colors.qualitative.Dark24 + px.colors.qualitative.Light24
    return {name: cmap[i % len(cmap)] for i, name in enumerate(sorted(names))}


def build_weekly_chart(df):
    """Weekly average line chart with dropdown to select week."""
    print("Building weekly chart...")

    weekly = df.groupby(['year_week', 'name', 'time_bucket']).agg(
        available=('available', 'mean')
    ).reset_index()

    # Week date ranges for titles
    week_dates = df.groupby('year_week')['timestamp'].agg(['min', 'max'])
    week_dates['label'] = week_dates.apply(
        lambda r: f"{r['min'].strftime('%b %d')} – {r['max'].strftime('%b %d, %Y')}", axis=1
    )

    weeks = sorted(weekly['year_week'].unique())
    all_names = sorted(weekly['name'].unique())
    colors = make_color_map(all_names)

    fig = go.Figure()

    # Add one trace per station per week
    for wi, week in enumerate(weeks):
        wdata = weekly[weekly['year_week'] == week]
        visible = (wi == len(weeks) - 1)  # Show latest week by default

        for name in all_names:
            sdata = wdata[wdata['name'] == name].sort_values('time_bucket')
            if sdata.empty:
                fig.add_trace(go.Scatter(
                    x=[], y=[], name=name, visible=visible,
                    line=dict(color=colors[name], width=2),
                    showlegend=visible,
                ))
            else:
                times = [f"{int(b)//60:02d}:{int(b)%60:02d}" for b in sdata['time_bucket']]
                fig.add_trace(go.Scatter(
                    x=times, y=sdata['available'].round(1),
                    name=name, mode='lines+markers',
                    line=dict(color=colors[name], width=2),
                    marker=dict(size=4),
                    visible=visible,
                    showlegend=visible,
                ))

    n_stations = len(all_names)

    # Build dropdown buttons
    buttons = []
    for wi, week in enumerate(weeks):
        label = f"{week} ({week_dates.loc[week, 'label']})"
        vis = [False] * (len(weeks) * n_stations)
        for si in range(n_stations):
            vis[wi * n_stations + si] = True
        # showlegend: only for the visible week
        showlegends = [(i // n_stations == wi) for i in range(len(vis))]
        buttons.append(dict(
            label=label,
            method='update',
            args=[
                {'visible': vis, 'showlegend': showlegends},
                {'title': f'Weekly Average Parking Availability – {label}'}
            ]
        ))

    default_label = f"{weeks[-1]} ({week_dates.loc[weeks[-1], 'label']})"
    fig.update_layout(
        title=f'Weekly Average Parking Availability – {default_label}',
        xaxis_title='Time of Day',
        yaxis_title='Average Available Spaces',
        hovermode='x unified',
        height=700,
        width=1500,
        yaxis=dict(rangemode='normal', range=[-50, None]),
        legend=dict(font=dict(size=10)),
        updatemenus=[dict(
            type='dropdown',
            direction='down',
            x=0.0, xanchor='left',
            y=1.15, yanchor='top',
            buttons=list(buttons),
            active=len(weeks) - 1,
            showactive=True,
            bgcolor='white',
            font=dict(size=11),
        )],
    )

    return fig


def build_heatmap(df):
    """Heatmap of availability: hour vs day-of-week, with month + station dropdowns."""
    print("Building heatmap chart...")

    hm = df.groupby(['month', 'name', 'hour', 'day_of_week']).agg(
        available=('available', 'mean')
    ).reset_index()

    months = sorted(hm['month'].unique())
    all_names = sorted(hm['name'].unique())
    day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    fig = go.Figure()

    # One heatmap trace per (month, station) combination
    for mi, month in enumerate(months):
        for ni, name in enumerate(all_names):
            mdata = hm[(hm['month'] == month) & (hm['name'] == name)]
            pivot = mdata.pivot_table(index='hour', columns='day_of_week', values='available', aggfunc='mean')
            pivot = pivot.reindex(columns=[d for d in day_order if d in pivot.columns])
            pivot = pivot.reindex(range(7, 19))

            visible = (mi == len(months) - 1 and ni == 0)

            fig.add_trace(go.Heatmap(
                z=pivot.values if not pivot.empty else [[]],
                x=[d[:3] for d in pivot.columns] if not pivot.empty else [],
                y=[f'{h:02d}:00' for h in pivot.index] if not pivot.empty else [],
                colorscale='RdYlGn',
                colorbar=dict(title='Spaces'),
                visible=visible,
            ))

    n_names = len(all_names)
    n_traces = len(months) * n_names

    # Month buttons
    month_buttons = []
    for mi, month in enumerate(months):
        vis = [False] * n_traces
        vis[mi * n_names] = True  # Show first station of this month
        month_buttons.append(dict(
            label=month,
            method='update',
            args=[{'visible': vis}, {'title': f'Weekly Pattern – {all_names[0]} – {month}'}]
        ))

    # Station buttons
    station_buttons = []
    default_mi = len(months) - 1
    for ni, name in enumerate(all_names):
        vis = [False] * n_traces
        vis[default_mi * n_names + ni] = True
        station_buttons.append(dict(
            label=name[:25],
            method='update',
            args=[{'visible': vis}, {'title': f'Weekly Pattern – {name} – {months[-1]}'}]
        ))

    fig.update_layout(
        title=f'Weekly Pattern – {all_names[0]} – {months[-1]}',
        xaxis_title='Day of Week',
        yaxis_title='Hour',
        height=550,
        width=900,
        updatemenus=[
            dict(
                type='dropdown', direction='down',
                x=0.0, xanchor='left', y=1.18, yanchor='top',
                buttons=list(month_buttons),
                active=len(months) - 1,
                showactive=True, bgcolor='white',
                font=dict(size=11),
            ),
            dict(
                type='dropdown', direction='down',
                x=0.35, xanchor='left', y=1.18, yanchor='top',
                buttons=list(station_buttons),
                active=0,
                showactive=True, bgcolor='white',
                font=dict(size=11),
            ),
        ],
    )

    return fig


def build_monthly_trend(df):
    """Monthly trend: average availability per station across months."""
    print("Building monthly trend chart...")

    monthly = df.groupby(['month', 'name']).agg(
        available=('available', 'mean'),
    ).reset_index()

    all_names = sorted(monthly['name'].unique())
    colors = make_color_map(all_names)

    fig = go.Figure()
    for name in all_names:
        sdata = monthly[monthly['name'] == name].sort_values('month')
        fig.add_trace(go.Bar(
            x=sdata['month'], y=sdata['available'].round(1),
            name=name, marker_color=colors[name],
        ))

    fig.update_layout(
        title='Monthly Average Availability by Station',
        xaxis_title='Month',
        yaxis_title='Avg Available Spaces',
        barmode='group',
        height=600,
        width=1500,
        hovermode='x unified',
        yaxis=dict(rangemode='normal', range=[-50, None]),
        legend=dict(font=dict(size=10)),
    )

    return fig


def generate_html(csv_path=None, output_path=None):
    csv_path = Path(csv_path) if csv_path else CSV_PATH
    output_path = Path(output_path) if output_path else OUTPUT_PATH

    df = load_data(csv_path)

    fig_weekly = build_weekly_chart(df)
    fig_heatmap = build_heatmap(df)
    fig_monthly = build_monthly_trend(df)

    # Build combined HTML
    date_min = df['timestamp'].dt.date.min()
    date_max = df['timestamp'].dt.date.max()
    n_records = len(df)
    n_stations = df['name'].nunique()
    n_months = df['month'].nunique()

    weekly_html = fig_weekly.to_html(full_html=False, include_plotlyjs=False)
    heatmap_html = fig_heatmap.to_html(full_html=False, include_plotlyjs=False)
    monthly_html = fig_monthly.to_html(full_html=False, include_plotlyjs=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Dolomites Parking – Interactive Report</title>
    <script src="https://cdn.plot.ly/plotly-2.35.0.min.js"></script>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
               margin: 0; padding: 20px 40px; background: #f8f9fa; color: #333; }}
        h1 {{ border-bottom: 3px solid #2c7be5; padding-bottom: 10px; }}
        h2 {{ color: #2c7be5; margin-top: 40px; }}
        .stats {{ display: flex; gap: 20px; flex-wrap: wrap; margin: 20px 0; }}
        .stat {{ background: white; border-radius: 8px; padding: 15px 25px;
                 box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .stat .value {{ font-size: 1.8em; font-weight: bold; color: #2c7be5; }}
        .stat .label {{ font-size: 0.9em; color: #666; }}
        .chart {{ background: white; border-radius: 8px; padding: 15px;
                  box-shadow: 0 1px 3px rgba(0,0,0,0.1); margin: 20px 0; }}
        .note {{ background: #e8f4fd; border-left: 4px solid #2c7be5; padding: 12px 16px;
                 margin: 20px 0; border-radius: 0 8px 8px 0; }}
    </style>
</head>
<body>
    <h1>Dolomites Parking – Interactive Report</h1>
    <p>Source: South Tyrol Open Data Hub &middot; Coverage: Val Gardena, Brunico, Bressanone</p>

    <div class="stats">
        <div class="stat"><div class="value">{n_records:,}</div><div class="label">Records (7am–6pm)</div></div>
        <div class="stat"><div class="value">{n_stations}</div><div class="label">Stations</div></div>
        <div class="stat"><div class="value">{n_months}</div><div class="label">Months</div></div>
        <div class="stat"><div class="value">{date_min} – {date_max}</div><div class="label">Date Range</div></div>
    </div>

    <div class="note">Use the dropdowns above each chart to switch weeks, months, or stations. Hover for details. Click legend items to toggle stations.</div>

    <h2>Weekly Average Availability</h2>
    <div class="chart">{weekly_html}</div>

    <h2>Weekly Heatmap (Hour × Day)</h2>
    <p>Select month and station from the dropdowns.</p>
    <div class="chart">{heatmap_html}</div>

    <h2>Monthly Trend</h2>
    <div class="chart">{monthly_html}</div>

    <p style="color:#999; margin-top:40px; font-size:0.85em;">
        Generated from {csv_path.name} &middot; {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}
    </p>
</body>
</html>"""

    output_path.write_text(html, encoding='utf-8')
    size_mb = output_path.stat().st_size / 1024 / 1024
    print(f"\nSaved to {output_path} ({size_mb:.1f} MB)")


if __name__ == '__main__':
    csv = sys.argv[1] if len(sys.argv) > 1 else None
    out = sys.argv[2] if len(sys.argv) > 2 else None
    generate_html(csv, out)
