# Trading Data Analysis Tool

Comprehensive analysis tool for trading backtesting data (fill, order, and PnL CSV files).

## Features

- **Automatic file detection**: Automatically finds and analyzes all file sets in the directory
- **Comprehensive visualizations**: Generates 4 detailed visualization files per file set
- **Performance metrics**: Calculates key trading performance indicators
- **Risk analysis**: Includes drawdown, volatility, and statistical analysis

## File Structure

The script expects CSV files with the following naming pattern:
- `*_pnl.csv` - Profit & Loss data
- `*_fill.csv` - Fill/execution data  
- `*_order.csv` - Order data

All three files with the same prefix will be analyzed together as a file set.

## Usage

```bash
python3 analyze_trading_data.py
```

The script will automatically:
1. Find all file sets (matching `*_pnl.csv`, `*_fill.csv`, `*_order.csv`)
2. Analyze each file set independently
3. Generate outputs with unique names for each set

## Output Files

For each file set, the script generates:

1. **`{prefix}_dashboard.png`** - Main performance dashboard (8 charts)
2. **`{prefix}_detailed.png`** - Detailed analysis charts (8 charts)
3. **`{prefix}_timeseries.png`** - Time series analysis & heatmaps (5 charts)
4. **`{prefix}_risk.png`** - Risk & statistical analysis (6 charts)
5. **`{prefix}_report.txt`** - Comprehensive text report

## Requirements

```bash
pip install pandas numpy matplotlib seaborn
```

## GitLab Repository Setup

### Files to Push:

✅ **Push these files:**
- `analyze_trading_data.py` - Main analysis script
- `*.csv` - Your data files (if you want to version control them)
- `README.md` - This file
- `.gitignore` - Git ignore rules

❌ **Don't push these (auto-generated):**
- `*.png` - Visualization files (can be regenerated)
- `*_report.txt` - Report files (can be regenerated)
- `analysis_output.log` - Log files

The `.gitignore` file is already configured to exclude generated outputs.

## Example

If you have files:
- `BACK_Strategy1_2025-01-01_pnl.csv`
- `BACK_Strategy1_2025-01-01_fill.csv`
- `BACK_Strategy1_2025-01-01_order.csv`

The script will generate:
- `Strategy1_2025-01-01_dashboard.png`
- `Strategy1_2025-01-01_detailed.png`
- `Strategy1_2025-01-01_timeseries.png`
- `Strategy1_2025-01-01_risk.png`
- `Strategy1_2025-01-01_report.txt`

## Analysis Metrics

The tool calculates:
- Total Return & Final PnL
- Maximum Drawdown
- Volatility (Standard Deviation)
- Sharpe-like Ratio
- Win Rate
- Execution Costs
- Slippage Analysis
- Trade Statistics

## License

Free to use and modify as needed.

