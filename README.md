# Dolomites Parking Scraper

Collects real-time parking availability data from the Dolomites region via the [South Tyrol Open Data Hub](https://opendatahub.com/) API.

## Coverage

| Region | Stations | Description |
|--------|----------|-------------|
| **Val Gardena** | 12 | Ski area parking with real-time sensors |
| **Bressanone** | 3 | Train station / Isarco Valley gateway |
| **Brunico** | 1 | Train station / Puster Valley gateway |
| **Total** | **16** | Real-time availability data |

## Setup

```bash
pip install -r requirements.txt
```

## Usage

**Run continuously (every 5 minutes):**
```bash
python scraper_dolomites.py
```

**Run once:**
```bash
python scraper_dolomites.py --once
```

**Generate parking plot:**
```bash
python plot_parking_data.py parking_data_dolomites.csv
```

**Generate snow plot:**
```bash
python plot_snow_data.py snow_data.csv
```

**Download historical data (fills gaps):**
```bash
# Download specific date range
python download_historical.py 2024-12-01 2026-02-09

# Download from Dec 1, 2024 to today
python download_historical.py
```

**⚠️ Historical Download Behavior:**
- **Safely merges** with existing data (does not overwrite)
- Automatically **skips dates that already exist** in the CSV
- **Deduplicates** records based on timestamp + station name
- Useful for **filling gaps** when scraper was not running
- API retains data for months/years (exact retention period not documented)

## Output

- **Parking**: Saved to `parking_data_plot.png` (or custom name).
- **Snow**: Saved to `snow_data_plot.png`.
- `timestamp` - ISO format datetime
- `name` - Parking location name
- `available` - Number of free spots
- `capacity` - Total capacity
- `location` - Town/village name
- `region` - Val Gardena / Puster Valley Gateway / Isarco Valley Gateway
- `latitude`, `longitude` - GPS coordinates
- `data_timestamp` - When sensor recorded data

## Data Source

- **API**: South Tyrol Open Data Hub
- **Endpoint**: `https://mobility.api.opendatahub.com/v2/flat/ParkingStation/*/latest`
- **License**: Open Data (CC0)
- **Update frequency**: Real-time (sensors update every 1-2 minutes)

See [DATA_SOURCES.md](DATA_SOURCES.md) for detailed API documentation and information about data availability in other Dolomites regions.

## Archive

Old scrapers (HTML-based and Val Gardena-only API version) are preserved in the `archive/` folder.
