# Dolomites Parking Data Sources

## Summary

Real-time parking APIs are only available for regions that have:
1. Invested in parking sensor infrastructure (AESYS or similar)
2. Partnered with Open Data Hub to share data publicly

## Available Data Sources

### South Tyrol Open Data Hub
- **API**: `https://mobility.api.opendatahub.com/v2/`
- **Documentation**: https://opendatahub.com/
- **License**: Open Data

| Region | Source Code | Stations | Description |
|--------|-------------|----------|-------------|
| Val Gardena | `GARDENA` | 12 | Ski area parking with real-time sensors |
| Bressanone | `skidata` | 3 | Train station mobility center (480 spaces) |
| Brunico | `skidata` | 1 | Train station mobility center (240 spaces) |

### Not Available (No Public API)

| Region | Province | Reason |
|--------|----------|--------|
| Val di Fassa | Trentino | Different province. dati.trentino.it has only static location data |
| Val Badia / Alta Badia | South Tyrol | No sensor infrastructure integrated with Open Data Hub |
| San Candido / Sesto | South Tyrol | No smart parking investment |
| Chiusa | South Tyrol | No data available |
| Cortina d'Ampezzo | Veneto | Different region, no data integration |
| Livinallongo / Arabba | Veneto | Different region, no data integration |
| Pragser Wildsee | South Tyrol | Proprietary booking system (pragsparking.com), closed API |

## Data Update Frequency

- **Source database**: Updates every 1-2 minutes (real-time AESYS sensors)
- **Recommended scrape interval**: 5 minutes

## API Endpoints Used

### Val Gardena Only
```
GET https://mobility.api.opendatahub.com/v2/flat/ParkingStation/*/latest
?where=sorigin.eq.GARDENA
```

### Dolomites Region (Val Gardena + Gateways)
```
GET https://mobility.api.opendatahub.com/v2/flat/ParkingStation/*/latest
?where=sorigin.in.(GARDENA,skidata)
```
Note: Filter out Bolzano stations by latitude < 46.55

## Other Potential Data Sources

### Trentino Open Data (dati.trentino.it)
- Has parking location data but NO real-time availability
- Covers Trento city only, not Val di Fassa

### Trentino Trasporti API
- Reverse-engineered: https://github.com/matteocontrini/trentino-trasporti-api
- Public transport only, no parking data

### Pragser Wildsee Booking
- Website: https://pragsparking.com
- Requires online reservation (seasonal)
- No public API available

## Contact for Data Integration

To request parking data integration for missing regions:
- **Open Data Hub**: https://opendatahub.com/
- **NOI Techpark**: https://noi.bz.it/

---

# Dolomiti Superski Data Sources

## Available via Open Data Hub Tourism API

**Base URL**: `https://tourism.api.opendatahub.com/v1/`

### Ski Regions
```
GET /SkiRegion?pagesize=50
```
Returns 4 ski regions:
- **Dolomiti Superski** (DSS) - 1,200 km of runs, 12 ski regions, 450 lifts
- Ortler Skiarena
- Skiworld Ahrntal
- Ski Centre Eisacktal/Wipptal

### Snow Reports (Real-time)
```
GET /Weather/SnowReport?language=en
```
**31 ski areas covered**, including:
- Val Gardena - Alpe di Siusi
- Alta Badia
- Kronplatz
- 3 Zinnen Dolomiten
- Carezza Dolomites
- Obereggen
- Gitschberg - Jochtal
- Plose

**Data fields available:**
- Snow depth (valley & mountain stations)
- New snow accumulation
- Temperature
- Last snowfall date
- **Operational lift count** (open/total)
- **Open slopes count**
- Cross-country tracks status
- Toboggan runs status
- Webcam URLs
- GPS coordinates

### Ski Areas
```
GET /SkiArea?pagesize=100
```

### Other Winter Data
- `/ODHActivityPoi?type=winter` - Winter activities
- Lifts, Slopes, Ski tracks via LTS data

## NOT Available (No Public API)

| Data Type | Status |
|-----------|--------|
| **Skipass sales statistics** | Not public - contact Dolomiti Superski |
| **Real-time lift queue times** | Not available |
| **Individual lift status** | Partial via Snow Report |
| **Revenue/financial data** | Annual reports only |

## Dolomiti Superski Statistics (from press releases)

- **Size**: 1,246 km of slopes, 450 lifts
- **Annual investment**: ~100-120 million EUR/season
- **Online sales**: 30% of total skipass sales
- **Member companies**: 130 cableway operators

## API Examples

### Get all snow reports
```bash
curl "https://tourism.api.opendatahub.com/v1/Weather/SnowReport?language=en"
```

### Get ski regions
```bash
curl "https://tourism.api.opendatahub.com/v1/SkiRegion"
```

### Export as CSV
Append `&format=csv` to any query
