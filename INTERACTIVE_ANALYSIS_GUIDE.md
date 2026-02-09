# Interactive Parking Analysis - Quick Start Guide

## Overview

The new **`parking_report_interactive.ipynb`** notebook provides interactive analysis of parking availability across the Dolomites region with:
- **Real-time filtering** by region, month, and location
- **Interactive visualizations** using Plotly (hover, zoom, pan)
- **Heatmaps** showing hourly and daily occupancy patterns
- **Peak analysis** comparing multiple time periods
- **Month comparison** to track trends across months

## Installation

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

Or manually install core packages:
```bash
pip install pandas>=2.0.0 numpy>=1.24.0 plotly>=5.18.0 ipywidgets>=8.1.0 jupyterlab>=4.0.0
```

### 2. Enable JupyterLab Widgets (if using JupyterLab)
```bash
jupyter labextension install @jupyter-widgets/jupyterlab-manager
```

## Running the Notebook

### Option A: JupyterLab (Recommended)
```bash
jupyter lab
```
Then open `parking_report_interactive.ipynb`

### Option B: Classic Jupyter Notebook
```bash
jupyter notebook
```
Then navigate to `parking_report_interactive.ipynb`

### Option C: VS Code with Jupyter Extension
1. Install the Jupyter extension in VS Code
2. Open `parking_report_interactive.ipynb`
3. Select "Run All" or run cells individually

## Features

### 1. Summary Statistics
Displays overall metrics:
- Total data points and locations
- Date range covered
- Average availability by region

### 2. Interactive Line Plot
**Compare parking availability across time with multiple filters:**
- **Region Filter**: Val Gardena, Brunico, Bressanone, or All
- **Month Selection**: Compare 1 or multiple months
- **Location Filter**: Select specific parking lots
- **Granularity**: 15-minute, hourly, or daily averages
- **Metric**: Available spaces or occupancy percentage

**Tips:**
- Select multiple months to see seasonal trends
- Hover over lines to see exact values
- Click legend items to toggle visibility
- Use the rangeslider at bottom to zoom in/out

### 3. Interactive Heatmap
**Analyze occupancy patterns by time and day:**
- **Hour × Day of Week**: See weekly patterns (when are peak times?)
- **Date × Hour**: See how occupancy evolves over the month

**Color Scale:**
- 🟢 Green = Many available spaces
- 🟡 Yellow = Medium occupancy
- 🔴 Red = Full/Limited spaces

### 4. Peak Analysis
**Detailed statistics on busiest/quietest times:**
- Peak hour distribution
- Daily occupancy trends
- Min/max availability ranges
- Summary statistics with dates

**Outputs:**
- Chart showing peak times and occupancy
- Text summary with key insights
  - Peak hour and available spaces
  - Quietest hour
  - Highest/lowest occupancy days

### 5. Month Comparison Grid
**Compare 2-4 months side-by-side:**
- Select month range (start to end)
- Choose multiple locations for each region
- View overlaid trends for easy comparison

**Use Cases:**
- Compare winter vs. spring demand
- See effects of holidays
- Track seasonal patterns
- Analyze specific months in detail

## Performance Notes

**Load Time:**
- Initial data load: ~15-30 seconds
- Pre-aggregation (first run): ~10-20 seconds
- Subsequent widget interactions: < 500ms

**Memory Usage:**
- Full dataset with aggregations: ~150-200 MB
- Optimized data types reduce overhead

**Tips for Better Performance:**
- Use "All" region and filter by location instead of pre-filtering region
- Select specific months rather than loading entire dataset
- Close unnecessary browser tabs if memory is constrained

## Data Updates

To refresh the notebook with latest parking data:

1. **Collect new data** (runs scraper once):
   ```bash
   python scraper_dolomites.py --once
   ```

2. **Re-run the notebook** to load fresh data:
   - In JupyterLab: Click "Restart kernel and run all cells"
   - Or run cells manually to preserve outputs

## Exporting Visualizations

### Save Individual Plots
1. Hover over any Plotly chart
2. Click the **camera icon** (📷) in top-right
3. Choose "Download plot as png"

### Save Entire Notebook as HTML
- **JupyterLab**: File → Export As → HTML
- **Classic Notebook**: File → Download as → HTML
- Opens in any web browser (no Jupyter required)

### Save as PDF
- Export as HTML first
- Open HTML in browser and print to PDF

## Troubleshooting

### Widgets Not Showing
- **JupyterLab**: Install widgets extension: `jupyter labextension install @jupyter-widgets/jupyterlab-manager`
- **Classic Notebook**: Run `jupyter nbextension enable --py widgetsnbextension`
- Restart Jupyter after installation

### Data Not Loading
- Verify `data/parking_data_dolomites.csv` exists
- Check file is not corrupted: `head -5 data/parking_data_dolomites.csv`
- File should be 250MB+ with 2M+ records

### Slow Performance
- Your machine may need more RAM for full dataset
- Try filtering by single region/month first
- Close other applications to free memory

### No Data for Selected Filters
- Check that location exists in the selected region
- Verify month range has data (see Summary Statistics)
- Some locations may not have data in all months

## Comparison: Old vs. New

| Feature | Old (PNG plots) | New (Interactive Notebook) |
|---------|---|---|
| **Chart Type** | Static matplotlib | Interactive Plotly |
| **Generation** | 5-10 min (59 PNGs) | 20-30 sec (once) |
| **Storage** | 30MB disk | 0MB (in-memory) |
| **Interactivity** | None | Full (zoom, hover, filter) |
| **Region Filtering** | ❌ Manual | ✅ Dropdown |
| **Month Comparison** | ❌ Manual scrolling | ✅ Side-by-side grid |
| **Heatmaps** | ❌ Not available | ✅ 2 types |
| **Peak Analysis** | ❌ Manual inspection | ✅ Automated |
| **Export** | PNG download | HTML, PNG, PDF |

## Advanced Usage

### Customizing the Notebook

**Change default month:**
In Cell 7 (Line Plot), edit:
```python
value=[available_months[-1]]  # Change to [available_months[0]] for first month
```

**Change color scheme:**
In Cell 5, modify:
```python
cmap = px.colors.sequential.Turbo  # Change to Viridis, Plasma, etc.
```

**Add more aggregation views:**
In Cell 4, add new pre-computed dataframes for additional analysis

### Creating Custom Analyses

You can add more cells below the export notes for custom analysis:
```python
# Example: Find busiest day overall
busiest_day = df_filtered.groupby('date')['occupancy_pct'].mean().idxmax()
print(f"Busiest day: {busiest_day}")
```

## Support

For issues or feature requests:
1. Check if dependencies are installed: `pip list | grep plotly`
2. Verify data file exists and is readable
3. Test with a single month/region first
4. Check browser console (F12) for JavaScript errors

## Files in This Project

- **`parking_report_interactive.ipynb`** - Main interactive analysis notebook
- **`parking_report.ipynb`** - Original static matplotlib notebook
- **`parking_report.md`** - Markdown report with charts
- **`parking_report.Rmd`** - R markdown version
- **`data/parking_data_dolomites.csv`** - Raw parking data (297MB)
- **`data/plots/`** - Legacy PNG plots (backup)
- **`scraper_dolomites.py`** - API scraper that collects the data
- **`requirements.txt`** - Python dependencies
