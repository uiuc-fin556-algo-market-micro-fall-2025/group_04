# VWAP Mean Reversion Strategy - Documentation

**Strategy Name:** VWAPStrategy  
**Version:** 1.0  
**Date:** December 10, 2025  
**Framework:** RCM StrategyStudio  
**Order Type:** Market Orders (Aggressive Taker)

---

## Table of Contents
1. [Strategy Overview](#strategy-overview)
2. [Trading Logic](#trading-logic)
3. [VWAP Calculation](#vwap-calculation)
4. [Entry & Exit Rules](#entry--exit-rules)
5. [Parameters](#parameters)
6. [Implementation Details](#implementation-details)
7. [Key Differences from TakerStrategy](#key-differences-from-takerstrategy)
8. [Usage Guide](#usage-guide)
9. [Troubleshooting](#troubleshooting)

---

## Strategy Overview

### Concept
The VWAP Mean Reversion strategy exploits temporary price deviations from the Volume-Weighted Average Price (VWAP). The strategy assumes that when prices deviate significantly from VWAP, they will revert back to the mean.

### Key Features
- **Signal Generator:** Rolling 5-minute VWAP calculated from trade ticks
- **Deviation Measurement:** Basis points (bps) difference between mid-price and VWAP
- **Order Type:** Market orders for immediate execution (aggressive taker)
- **Position Management:** Incremental position building up to max inventory
- **Exit Strategy:** Full mean reversion (price crosses back to VWAP)

### Strategy Type
- **Frequency:** High-frequency (reacts to every trade event)
- **Style:** Market Taker (liquidity consumer)
- **Direction:** Directional (long or short based on deviation)

---

## Trading Logic

### Signal Flow

```
Trade Event → Update VWAP Window → Calculate Deviation → Check Conditions → Send Market Order
```

### Decision Tree

```
1. Is VWAP ready? (≥3 trades)
   └─ NO → Skip, wait for more data
   └─ YES → Continue

2. Calculate deviation = (mid_price - VWAP) / VWAP × 10,000 bps

3. Do we have a position?
   └─ YES → Check exit signal
      ├─ Long & dev ≥ 0 → EXIT (price reverted to VWAP)
      └─ Short & dev ≤ 0 → EXIT (price reverted to VWAP)
   └─ NO → Check entry signal

4. Are we below max inventory?
   └─ YES → Check entry thresholds
      ├─ dev < -threshold → BUY (price below VWAP)
      └─ dev > +threshold → SELL (price above VWAP)
   └─ NO → Skip (max inventory reached)
```

---

## VWAP Calculation

### Formula

\[
VWAP = \frac{\sum (Price_i \times Volume_i)}{\sum Volume_i}
\]

### Implementation

```cpp
// On every trade:
1. AddTradeToWindow(price, volume, timestamp)
   - cumulative_pv += price × volume
   - cumulative_volume += volume
   - vwap_window.push_back(trade_record)

2. PruneOldTrades(cutoff_time)
   - Remove trades older than 5 minutes
   - Update cumulative_pv and cumulative_volume

3. GetVWAP()
   - return cumulative_pv / cumulative_volume
```

### Rolling Window
- **Window Size:** 300 seconds (5 minutes)
- **Data Structure:** `std::deque<VWAPTradeRecord>`
- **Pruning:** Automatic removal of trades older than window
- **Ready Check:** Requires ≥3 trades OR ≥60 seconds of history

---

## Entry & Exit Rules

### Entry Signals

#### BUY Signal (Go Long)
- **Condition:** `deviation < -entry_threshold_bps`
- **Interpretation:** Price is significantly BELOW VWAP
- **Expectation:** Price will rise back to VWAP
- **Order:** Market BUY at current ask
- **Position:** Increase long position by `position_size`

**Example:**
```
VWAP = $100.00
Mid-price = $99.95
Deviation = -5.0 bps
Threshold = 2.0 bps
Action: BUY (deviation -5 < -2)
```

#### SELL Signal (Go Short)
- **Condition:** `deviation > +entry_threshold_bps`
- **Interpretation:** Price is significantly ABOVE VWAP
- **Expectation:** Price will fall back to VWAP
- **Order:** Market SELL at current bid
- **Position:** Decrease position by `position_size` (go short)

**Example:**
```
VWAP = $100.00
Mid-price = $100.05
Deviation = +5.0 bps
Threshold = 2.0 bps
Action: SELL (deviation +5 > +2)
```

### Exit Signals

#### Exit Long Position
- **Condition:** `current_position > 0 AND deviation ≥ 0`
- **Interpretation:** Price has reverted to or above VWAP
- **Order:** Market SELL to flatten position
- **Target Position:** 0 (flat)

#### Exit Short Position
- **Condition:** `current_position < 0 AND deviation ≤ 0`
- **Interpretation:** Price has reverted to or below VWAP
- **Order:** Market BUY to flatten position
- **Target Position:** 0 (flat)

### Position Constraints
- **Max Inventory:** Configurable (default 5)
- **Position Size:** Configurable shares per trade (default 1)
- **No new entries** when `abs(current_position) ≥ max_inventory`
- **Always allow exits** regardless of inventory

---

## Parameters

### Configurable Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `vwap_window_seconds` | Startup | 300 | Rolling window size (5 minutes) |
| `entry_threshold_bps` | Runtime | 2.0 | Deviation threshold to trigger entry (bps) |
| `max_inventory` | Runtime | 5 | Maximum position size (absolute value) |
| `position_size` | Runtime | 1 | Number of shares per order |
| `debug` | Runtime | true | Enable detailed logging |

### Parameter Details

#### vwap_window_seconds
- **Range:** 60-600 seconds
- **Recommendation:** 300 (5 minutes) for HFT
- **Impact:** Larger window = smoother VWAP, less responsive

#### entry_threshold_bps
- **Range:** 0.5-10.0 bps
- **Recommendation:** 2.0-5.0 for liquid instruments
- **Impact:** Lower threshold = more trades, higher frequency

#### max_inventory
- **Range:** 1-100
- **Recommendation:** 5-10 for HFT
- **Impact:** Higher inventory = more risk, potential for larger profits

#### position_size
- **Range:** 1-10
- **Recommendation:** 1 for fine-grained control
- **Impact:** Larger size = faster position building

---

## Implementation Details

### File Structure

```
VWAP.h          - Strategy class definition
VWAP.cpp        - Strategy implementation
Makefile        - Build configuration
```

### Key Classes and Structures

#### VWAPTradeRecord
```cpp
struct VWAPTradeRecord {
    Utilities::TimeType timestamp;
    double price;
    int volume;
};
```

#### VWAPStrategy Class
**Inherits:** `Strategy` (StrategyStudio base class)

**Key Methods:**
- `OnTrade()` - Core trading logic, triggered on every trade event
- `AddTradeToWindow()` - Updates VWAP calculation
- `PruneOldTrades()` - Maintains rolling window
- `IsVWAPReady()` - Checks if enough data for trading
- `SendOrder()` - Executes market orders

### Event Handling

#### Registered Events
```cpp
RegisterForStrategyEvents() {
    - RegisterForTrades(*it)    // Get trade events
    - RegisterForQuotes(*it)    // Get quote data for mid-price
}
```

#### Event Priority
1. **OnTrade()** - Primary event, drives all trading logic
2. **OnOrderUpdate()** - Tracks order fills and position changes
3. **OnStrategyCommand()** - Manual intervention (cancel orders)

### Order Execution

#### Market Order Parameters
```cpp
OrderParams(
    instrument,              // Trading instrument
    abs(trade_size),        // Order quantity
    price,                  // Indicative price (ask for buy, bid for sell)
    MARKET_CENTER_ID,       // NASDAQ for equities, CME for futures
    ORDER_SIDE,             // BUY or SELL
    ORDER_TIF_DAY,         // Time in force: Day
    ORDER_TYPE_MARKET      // MARKET order (immediate execution)
);
```

#### Price Selection
- **BUY orders:** Use `ask` price (pay the spread)
- **SELL orders:** Use `bid` price (cross the spread)
- **Market orders execute at best available price** (price is indicative)

### Position Tracking

Uses StrategyStudio's built-in portfolio tracker:
```cpp
int current_position = portfolio().position(instrument);
```

No manual position tracking needed - StrategyStudio updates automatically on fills.

---

## Key Differences from TakerStrategy

| Feature | TakerStrategy | VWAPStrategy |
|---------|---------------|--------------|
| **Signal Source** | Order book imbalance | VWAP deviation |
| **Event Handler** | `OnTopQuote()` | `OnTrade()` |
| **Signal Frequency** | Every quote (microseconds) | Every trade (seconds) |
| **Calculation** | `(bidSize - askSize) / totalSize` | `(mid - VWAP) / VWAP × 10000` |
| **Data Window** | Last N quotes (5 default) | Last 5 minutes of trades |
| **Consecutive Signals** | Required (3 default) | Not required |
| **Bootstrap Time** | Immediate (quotes always available) | ~3 trades or 1 minute |
| **Order Type** | Market (same) | Market (same) |
| **Position Management** | `AdjustPortfolio()` (same) | `AdjustPortfolio()` (same) |

### Why OnTrade vs OnTopQuote?

**VWAP Strategy uses OnTrade:**
- ✅ VWAP requires trade data (price × volume)
- ✅ More efficient (fewer events than quotes)
- ✅ Trades contain actual transaction information
- ❌ Less frequent updates (could miss opportunities)

**TakerStrategy uses OnTopQuote:**
- ✅ Extremely high frequency (microsecond updates)
- ✅ Always has recent data
- ✅ Can react instantly to order book changes
- ❌ More computational overhead (many events)

---

## Usage Guide

### Building the Strategy

```bash
# Clean previous builds
wsl make clean

# Compile the strategy
wsl make

# Expected output: VWAP.so
```

### Deploying to StrategyStudio

```bash
# Copy to strategy directory
make copy_strategy

# Or manually:
cp VWAP.so /student_work/kyahata2/ss/bt/strategies_dlls/.
```

### Running a Backtest

```bash
cd ~/ss/bt/utilities
./StrategyCommandLine cmd start_backtest 2021-11-05 2021-11-05 VWAPStrategy 1
```

### Monitoring Strategy

#### Debug Logging
When `debug=true`, you'll see:

```
Added trade: price=100.05 vol=500 | window_size=23 | VWAP=100.02
SPY | Trade: 500@100.05 | Mid=100.04 | VWAP=100.02 | Dev=2.0bps | Pos=0
ENTRY BUY signal (dev=-2.5bps)
Sending MARKET BUY order for SPY for 1 units at ~100.04
Order Update - OrderID: 12345, UpdateType: FILL, Fill Quantity: 1, Fill Price: 100.04
EXIT LONG signal - price reverted to VWAP
Sending MARKET SELL order for SPY for 1 units at ~100.03
```

#### Key Metrics to Watch
- **VWAP window size** - Should grow to ~50-200 trades in 5 minutes
- **Deviation (bps)** - Should oscillate around 0
- **Position** - Should range from -max_inventory to +max_inventory
- **Fill rate** - Market orders should fill immediately

---

## Troubleshooting

### Problem: Strategy Not Generating Orders

#### Symptom
```
VWAP window not ready yet (size=0)
VWAP window not ready yet (size=1)
VWAP window not ready yet (size=2)
```

#### Causes & Solutions
1. **Not enough trades yet**
   - Solution: Wait for 3 trades (should happen within seconds)
   - Check: Is the instrument actively trading?

2. **Events not registered**
   - Solution: Verify `RegisterForStrategyEvents()` is not empty
   - Check: Should see `RegisterForTrades(*it)`

3. **Threshold too high**
   - Solution: Lower `entry_threshold_bps` from 2.0 to 0.5
   - Check: Monitor deviation values in logs

### Problem: Orders Not Filling

#### Symptom
```
Sending MARKET BUY order for SPY for 1 units at ~100.04
(No fill confirmation)
```

#### Causes & Solutions
1. **Invalid quotes**
   - Check: "Skipping trade due to lack of two sided quote"
   - Solution: Ensure market is open and quotes are valid

2. **Insufficient liquidity**
   - Rare for market orders, but possible in illiquid instruments
   - Solution: Reduce position_size

3. **Backtest data quality**
   - Solution: Verify historical data includes trade and quote data

### Problem: Excessive Trading

#### Symptom
```
ENTRY BUY signal (dev=-2.1bps)
ENTRY BUY signal (dev=-2.0bps)
ENTRY BUY signal (dev=-2.05bps)
... (hundreds of trades)
```

#### Causes & Solutions
1. **Threshold too low**
   - Solution: Increase `entry_threshold_bps` from 2.0 to 5.0
   - Effect: Fewer, higher-quality signals

2. **No max inventory check**
   - Check: Should see "Position: X" approaching max_inventory
   - Solution: Verify max_inventory is properly configured

3. **Exit logic not working**
   - Check: Should see "EXIT LONG/SHORT signal"
   - Solution: Verify deviation crossing logic

### Problem: Position Gets Stuck

#### Symptom
```
SPY | Dev=5.0bps | Pos=5
SPY | Dev=6.0bps | Pos=5
SPY | Dev=7.0bps | Pos=5
(Never exits)
```

#### Causes & Solutions
1. **Exit condition never met**
   - Position is long but deviation never crosses 0
   - Solution: Add stop-loss or timeout logic

2. **Trend continuation**
   - Price keeps moving away from VWAP
   - Solution: Add maximum holding period

3. **VWAP drift**
   - VWAP itself is trending
   - Solution: Use shorter VWAP window (e.g., 60 seconds)

---

## Performance Considerations

### Computational Complexity
- **OnTrade frequency:** ~100-1000 events/second (depends on instrument)
- **VWAP calculation:** O(1) per trade (incremental update)
- **Window pruning:** O(k) where k = trades removed (usually 1-2)
- **Overall:** Very efficient, suitable for HFT

### Memory Usage
- **VWAP window:** ~50-200 records × 24 bytes = ~1-5 KB
- **Total strategy:** < 10 KB per instrument
- **Scalable** to hundreds of instruments

### Latency
- **Event to decision:** < 1 microsecond
- **Decision to order:** < 10 microseconds
- **Order to fill:** Depends on exchange (typically 100-1000 microseconds)
- **Total loop:** ~1-10 milliseconds

---

## Future Enhancements

### Potential Improvements
1. **Dynamic thresholds** - Adjust based on volatility
2. **Stop-loss logic** - Exit on adverse moves
3. **Time-based exits** - Close positions at end of day
4. **Multi-instrument** - Portfolio-level position management
5. **Adaptive window** - Vary VWAP window based on market conditions
6. **Smart execution** - Use TWAP for large orders

### Advanced Features
- **Correlation filters** - Only trade when instrument correlates with market VWAP
- **Volume profile** - Weight recent trades more heavily
- **Intraday patterns** - Adjust parameters by time of day
- **Machine learning** - Predict optimal entry thresholds

---

## References

### StrategyStudio Documentation
- Event Handlers: `RCM/StrategyStudio/docs/html`
- Order Management: `OrderParams`, `TradeActions`
- Position Tracking: `IPortfolio`, `IOrderTracker`

### Academic Background
- Berkowitz, S. A., Logue, D. E., & Noser, E. A. (1988). "The Total Cost of Transactions on the NYSE"
- Konishi, H. (2002). "Optimal Slice of a VWAP Trade"
- Kissell, R. (2013). "The Science of Algorithmic Trading and Portfolio Management"

---

## Appendix: Complete Code Reference

### Files Included
- `VWAP.h` (117 lines) - Strategy header
- `VWAP.cpp` (361 lines) - Strategy implementation
- `Makefile` - Build configuration

### Quick Reference Commands

```bash
# Build
wsl make clean && wsl make

# Deploy
make copy_strategy

# Run backtest
cd ~/ss/bt/utilities
./StrategyCommandLine cmd start_backtest 2021-11-05 2021-11-05 VWAPStrategy 1

# View results
cd ~/ss/bt/backtesting-results
ls -lt | head
```

---

**Version History:**
- v1.0 (2025-12-10) - Initial implementation with market orders, rolling VWAP, mean reversion logic

**Author:** dlariviere / UIUC  
**Framework:** RCM StrategyStudio  
**License:** Educational Use

