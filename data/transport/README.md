# Dolomites Public Transport Data

Complete bus and train schedule data for the Dolomites region of South Tyrol, Italy.

## Data Source

**Open Data Hub GTFS API - STA (Südtirol Transportstrukturen AG)**
- API: https://gtfs.api.opendatahub.com/v1
- Dataset: `sta-time-tables`
- Format: GTFS (General Transit Feed Specification)
- Updates: Daily

## Data Files

### Core Data

| File | Records | Size | Description |
|------|---------|------|-------------|
| `transport_stops.csv` | 4,258 | 338 KB | All bus/train stops in Dolomites region |
| `transport_routes.csv` | 490 | 16 KB | Bus/train routes serving the region |
| `transport_trips.csv` | 20,580 | 1.6 MB | Individual trips (specific route instances) |

### Schedule Data

| File | Records | Size | Description |
|------|---------|------|-------------|
| `transport_stop_times.csv` | 305,781 | 21 MB | **Arrival/departure times** for each stop on each trip |
| `transport_calendar.csv` | 1,133 | 47 KB | Service calendar (which days routes run) |
| `transport_calendar_dates.csv` | 63,390 | 1.3 MB | Service exceptions (holidays, special dates) |

### Visualizations

| File | Type | Description |
|------|------|-------------|
| `plots/transport_map.html` | Interactive Map | Zoomable map with all 4,258 stops plotted |
| `plots/transport_*.png` | Static Charts | Region distribution, route types, etc. |
| `plots/monthly_summary.md` | Report | Statistics and analysis |

## Coverage

### Geographic Regions

- **South Tyrol**: 3,887 stops (91.3%)
- **Isarco Valley**: 112 stops (2.6%)
- **Val Gardena**: 110 stops (2.6%)
- **Puster Valley**: 99 stops (2.3%)
- **Alta Badia**: 49 stops (1.2%)
- **Val di Fassa**: 1 stop (0.0%)

### Transport Types

- **Bus**: Primary mode (majority of routes)
- **Rail**: Regional trains
- **Cable Car**: Mountain access
- **Aerial Lift**: Ski lifts and gondolas
- **Funicular**: Incline railways

## Using the Data

### Download Latest Data

```bash
python download_transport.py
```

This will:
1. Download latest GTFS data from Open Data Hub
2. Parse all schedule information
3. Filter to Dolomites region (latitude > 46.55°)
4. Save to CSV files

### Query Schedules

```bash
python query_transport_schedules.py
```

Example queries:
- Find stops by name
- Get schedule for a specific stop
- Find all routes serving a location
- Find connections between two locations
- Show all stops for a route

### Visualize Stops

```bash
python generate_transport_map.py
```

Creates an interactive HTML map showing all transport stops.

### Generate Statistics

```bash
python generate_transport_summary.py
```

Creates charts and reports about the transport network.

## Data Structure

### Stops (transport_stops.csv)

```csv
stop_id,stop_name,stop_lat,stop_lon,location,region
it:22021:266:0:1320,"Bivio Corvara",46.85581814,11.16097075,Corvara,Alta Badia
```

### Routes (transport_routes.csv)

```csv
route_id,route_short_name,route_long_name,route_type,agency_name
1-350-26a-1,350,CHIUSA/KLAUSEN - ORTISEI/ST.ULRICH,Bus,STA
```

### Trips (transport_trips.csv)

```csv
trip_id,route_id,service_id,trip_headsign,direction_id,shape_id
1.T0.1-350-26a-1.1.H,1-350-26a-1,1:350:26a:1,Ortisei,1,shp_1_241
```

### Stop Times (transport_stop_times.csv)

```csv
trip_id,arrival_time,departure_time,stop_id,stop_sequence,pickup_type,drop_off_type
1.T0.1-350-26a-1.1.H,08:30:00,08:30:00,it:22021:266:0:1320,5,0,0
```

**Key Fields:**
- `arrival_time`: When bus arrives (HH:MM:SS)
- `departure_time`: When bus departs (HH:MM:SS)
- `stop_sequence`: Order of stops on trip (1, 2, 3...)
- `pickup_type`: 0=regular pickup, 1=no pickup
- `drop_off_type`: 0=regular drop-off, 1=no drop-off

### Calendar (transport_calendar.csv)

```csv
service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date
1:350:26a:1,1,1,1,1,1,0,0,20240101,20241231
```

**Days of Week:** 1=service runs, 0=no service

### Calendar Dates (transport_calendar_dates.csv)

```csv
service_id,date,exception_type
1:350:26a:1,20241225,2
```

**Exception Types:**
- 1 = Service added on this date
- 2 = Service removed on this date

## Example Use Cases

### 1. Find Next Bus from Corvara

```python
import pandas as pd
from datetime import datetime

stops = pd.read_csv('transport_stops.csv', comment='#')
stop_times = pd.read_csv('transport_stop_times.csv', comment='#')

# Find Corvara stops
corvara_stops = stops[stops['location'] == 'Corvara']

# Get departures after 08:00
departures = stop_times[
    (stop_times['stop_id'].isin(corvara_stops['stop_id'])) &
    (stop_times['departure_time'] >= '08:00:00')
].sort_values('departure_time')

print(departures.head(10))
```

### 2. Find All Routes to Alta Badia

```python
# Find Alta Badia stops
alta_badia_stops = stops[stops['region'] == 'Alta Badia']

# Find trips serving these stops
trips_serving = stop_times[
    stop_times['stop_id'].isin(alta_badia_stops['stop_id'])
]['trip_id'].unique()

# Get routes
trips = pd.read_csv('transport_trips.csv', comment='#')
routes = pd.read_csv('transport_routes.csv', comment='#')

route_ids = trips[trips['trip_id'].isin(trips_serving)]['route_id'].unique()
alta_badia_routes = routes[routes['route_id'].isin(route_ids)]

print(alta_badia_routes)
```

### 3. Check if Service Runs on Christmas

```python
calendar_dates = pd.read_csv('transport_calendar_dates.csv', comment='#')

christmas = calendar_dates[calendar_dates['date'] == '20241225']
print(f"Services affected on Christmas: {len(christmas)}")
```

## Building Your Superapplication

The data is structured to support:

✅ **Journey Planning**: Find connections between locations
✅ **Real-time Lookups**: Show next departures from any stop
✅ **Route Exploration**: View all stops for a route
✅ **Schedule Validation**: Check if service runs on specific dates
✅ **Geographic Visualization**: Plot routes and stops on maps
✅ **Analytics**: Analyze coverage, frequency, connections

### Integration Points

1. **Web Application**: Load CSVs into database (SQLite, PostgreSQL)
2. **Mobile App**: Sync data locally for offline access
3. **API Service**: Build REST API on top of the data
4. **Chatbot**: Natural language queries ("Next bus to Corvara?")
5. **Trip Planner**: Multi-modal journey planning

## Data Quality Notes

- **Coverage**: Filtered to Dolomites region (latitude > 46.55°)
- **Completeness**: All GTFS schedule data included
- **Accuracy**: Data from official STA source
- **Freshness**: Run `download_transport.py` to update
- **Limitations**:
  - No real-time position data
  - No passenger count data
  - No fare information
  - Some route names may be abbreviated

## API Documentation

See `transport_data_research.md` for details about:
- Open Data Hub API endpoints
- GTFS format specification
- Data partnership options
- Real-time data availability

## Scripts

- **`download_transport.py`** - Download and parse GTFS data
- **`query_transport_schedules.py`** - Example schedule queries
- **`generate_transport_map.py`** - Create interactive map
- **`generate_transport_summary.py`** - Generate statistics

## Support

- **Open Data Hub**: https://opendatahub.com
- **STA Website**: https://www.sta.bz.it
- **GTFS Specification**: https://gtfs.org

---

*Last updated: 2026-02-09*
*Data source: Open Data Hub GTFS API - STA*
