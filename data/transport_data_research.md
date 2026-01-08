# Public Transport Ridership Data Research - South Tyrol

*Research Date: January 2026*

## Objective

Find actual bus/train ridership data (passenger counts, trips over time) for South Tyrol / Dolomites region - not just static stop locations.

## Research Findings

### What's NOT Publicly Available via API

| Data Type | Status |
|-----------|--------|
| Passenger counts per trip/stop | Not exposed |
| Ridership time-series data | Not in Open Data Hub |
| Real-time vehicle occupancy | Not available |
| SIRI real-time feeds | Internal use only (no public endpoint) |

### What IS Available (Public APIs)

| Data Type | Source | Format | Time-Series? |
|-----------|--------|--------|--------------|
| ParkingStation | Open Data Hub API | Real-time availability | Yes |
| GTFS Schedules | GTFS API | Static timetables | No |
| ON_DEMAND vehicles | Open Data Hub API | Real-time positions | Limited |

## Where Ridership Data Exists

### 1. STA - Südtiroler Transportstrukturen AG

- **Website**: https://www.sta.bz.it
- **Email**: info@sta.bz.it
- **What they have**:
  - SIRI real-time data infrastructure
  - NeTEx/ITxPT standardized data
  - Historical ridership data
- **Access**: Requires data partnership agreement

### 2. ASTAT - Provincial Statistics Institute

- **Website**: https://astat.provinz.bz.it
- **What they publish**:
  - Annual mobility reports
  - Total validations (52.7M passengers in 2015)
  - Modal split: 79% bus, 19% train, 2% cable car
  - Daily counts by station (e.g., Bolzano: 5,367 validations/day)
- **Format**: PDF reports (not machine-readable)
- **Access**: Contact for raw data availability

### 3. Open Data Hub

- **Website**: https://opendatahub.com
- **Role**: Coordinates data sharing for South Tyrol region
- **Access**: Contact for data partnership

## Recommended Next Steps

1. **Contact STA** to request API access to SIRI real-time data or historical ridership statistics

2. **Contact ASTAT** to ask if raw data behind their mobility reports is available in downloadable format (CSV/Excel)

3. **Contact Open Data Hub** to establish a data partnership for mobility data access

## Technical Notes

- STA uses European standards: NeTEx, SIRI, ITxPT, OJP
- The "Bingo Project" is STA's multi-year digitalization initiative for public mobility
- Real-time data exists but is used internally for the südtirolmobil app

## Conclusion

Bus/train ridership data exists but is **not exposed via public API**. A data sharing agreement with STA or ASTAT would be required to access passenger count statistics for trend analysis.

---

*This research was conducted using the Open Data Hub API and web searches for available South Tyrol transport data sources.*
