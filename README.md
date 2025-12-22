<h1 style="font-size: 3em; text-align: center;">FIN556 Report Group 4 – High-Frequency VWAP Strategy</h1>

- [1. Executive Summary](#1-executive-summary)
- [2. Meet the Team](#2-meet-the-team)
  - [Koki Yahata](#koki-yahata)
  - [Chia-Ning Chang](#chia-ning-chang)
  - [Ansh Bardoliwala](#ansh-bardoliwala)
- [3. Introduction to VWAP-Based Strategies](#3-introduction-to-vwap-based-strategies)
  - [3.1 VWAP Mean-Reversion Signal](#31-vwap-mean-reversion-signal)
  - [3.2 Maker vs. Taker Implementations](#32-maker-vs-taker-implementations)
- [4. Financial Instrument](#4-financial-instrument)
- [5. Market Data Analysis](#5-market-data-analysis)
- [6. Data Retrieval and Preprocessing](#6-data-retrieval-and-preprocessing)
  - [6.1 Order Book Updates (Quotes)](#61-order-book-updates-quotes)
  - [6.2 Trades and VWAP Construction](#62-trades-and-vwap-construction)
- [7. Strategy Design and Results](#7-strategy-design-and-results)
  - [7.1 Python Notebook Backtest (`vwap_based_strategy.ipynb`)](#71-python-notebook-backtest-vwap_based_strategyipynb)
  - [7.2 StrategyStudio Backtest + VWAP8 Output Diagnosis](#72-strategystudio-backtest--vwap8-output-diagnosis)
- [8. Future Implications and Improvements](#8-future-implications-and-improvements)

---

## 1. Executive Summary
This project chronicles the evolution of a high-frequency trading (HFT) strategy from theoretical research to an event-driven production environment. Our strategy exploits short-lived price dislocations from the **Volume-Weighted Average Price (VWAP)**.

Through rigorous backtesting, we discovered that while the VWAP signal is statistically sound, the execution model is the primary driver of profitability. Our initial C++ implementation—a **"Taker" model** using pure VWAP—resulted in massive losses due to spread-crossing costs. By incorporating the **Order Book Imbalance (OBI)** filter identified in our Python research and pivoting to a **"Maker" execution style**, we successfully neutralized these costs. This report highlights the transition from a research prototype on SPY to a multi-asset C++ system (StrategyStudio) running on MSFT and AAPL.

---

# 2. Meet the Team

We are Group 4 in FIN556, combining experience in **algorithmic trading**, **high-performance systems**, and **machine learning**.

## Koki Yahata

I am a senior majoring in Computer Science. My focus is in algorithmic trading and web3 development. I develop market making strategies and on-chain arbitrage strategies. I am familiar with Python, Rust, C++, TypeScript, and Solidity.

Email: kyahata2@illinois.edu<br> 
LinkedIn: [Koki Yahata](https://www.linkedin.com/in/koki-yahata)

## Chia-Ning Chang

I am a master student in Finance. My focus is in algorithmic trading strategy design and Portfolio Management. I develop all weather macro strategies on equities and double carry strategies on futures. I am familiar with Python.

Email: cc173@illinois.edu<br>
LinkedIn: [Charlie Chang](https://www.linkedin.com/in/charlie-chianing-chang)

## Ansh Bardoliwala

I am a master’s student in Finance at the University of Illinois Urbana-Champaign. My focus is on algorithmic trading, market microstructure, and quantitative research. 
I work on data-driven trading strategies, order-book analysis, and transaction-cost modeling, with experience in Python-based backtesting and financial data analysis.

Email: apb8@illinois.edu<br>
LinkedIn: [Ansh Bardoliwala](https://www.linkedin.com/in/ansh-bardoliwala-ms-finance/) 

## Howard Ding

I am a senior majoring in Finance, Mathematics, and Statistics. My focus is on algorithmic trading, data science, and portfolio management. I am familiar with C++, Python, R, and SQL. 

Email: howardd2@illinois.edu<br>
LinkedIn: [Howard Ding](https://www.linkedin.com/in/hzding/) 

---

## 3. Strategy Methodology

### 3.1 VWAP Mean-Reversion Signal
The VWAP serves as the intraday benchmark for "fair value." Our strategy assumes that when the mid-price drifts significantly from the rolling 5-minute VWAP, it is likely to mean-revert. We calculate VWAP Deviation in basis points (bps):

$$\text{Deviation (bps)} = \left( \frac{\text{Mid-Price}}{\text{VWAP}_{5\text{min}}} - 1 \right) \times 10,000$$

### 3.2 Order Book Imbalance (OBI) Filter
To prevent trading into a trending market (the "falling knife" scenario), we use OBI as a confirmation signal. OBI measures the relative buy/sell pressure at the best bid and ask:

$$\text{OBI} = \frac{\text{Bid Size}_1 - \text{Ask Size}_1}{\text{Bid Size}_1 + \text{Ask Size}_1}$$

### 3.3 Signal Matrix
The `generate_signals` function classifies market states into five categories based on a **2 bps threshold** and a **±0.5 OBI filter**:

| Signal | Deviation | OBI Filter | Interpretation |
| :--- | :--- | :--- | :--- |
| **STRONG BUY** | $< -2$ bps | $> 0.5$ | Undervalued with strong bid pressure |
| **BUY** | $< -2$ bps | $\leq 0.5$ | Undervalued |
| **NEUTRAL** | $[-2, 2]$ bps | Any | Equilibrium price |
| **SELL** | $> 2$ bps | $\geq -0.5$ | Overvalued |
| **STRONG SELL** | $> 2$ bps | $< -0.5$ | Overvalued with strong ask pressure |

---

## 4. Phase I: Python Research & Proof of Concept
The `vwap_based_strategy.ipynb` notebook validated the strategy using SPY intraday data.

* **Statistical Coherence:** The 5-minute deviation showed a centered distribution ($\sigma \approx 2.38$ bps). The ±2 bps threshold successfully captured the "outer tails" where mean reversion is most likely.
* **Visual Validation:** Signal scatter plots confirmed that **STRONG** signals (0.1% of observations) aligned with large negative deviations and high bid-side pressure.
* **Backtest Result:** Using a conservative maker-style simulation, the prototype produced 6 fills and a positive PnL of **$0.04**, proving that the combination of VWAP and OBI could be profitable if execution costs were minimized.

![Python backtest PnL](assets/vwap_based_backest_python.png)

![Python backtest inventory](assets/vwap_based_inventory.png)

---

## 5. Phase II: C++ Implementation & Strategy Evolution

### 5.1 Initial Trial: The Pure VWAP Taker (Structural Failure)
In our first C++ iteration in StrategyStudio, we implemented a pure VWAP signal using Market Orders (Taker style).

* **The Result:** The strategy suffered a catastrophic negative drift of approximately **–$86,000**.
* **The Lesson:** At the HFT scale, crossing the bid-ask spread to "take" liquidity is prohibitively expensive. The alpha signal was completely overwhelmed by transaction costs.

### 5.2 The Pivot: VWAP + OFI Maker Strategy
Applying the insights from our Python research, we refined the C++ strategy (`src/VWAP.cpp`) with two major changes:
1.  **Added OBI Filter:** We restricted entries to points where order book imbalance confirmed the mean-reversion signal.
2.  **Pivoted to Maker Style:** The strategy was rewritten to use Limit Orders. Instead of paying the spread, the strategy now "rests" orders at the best bid/ask to capture the spread (`LiquidityAction: ADDED`).

---

## 6. Comparative Analysis: Research vs. Production
The final backtest on MSFT and AAPL (2019-09-13) demonstrated the success of the execution pivot.

| Metric | Python (Research - SPY) | StrategyStudio (Production - MSFT/AAPL) |
| :--- | :--- | :--- |
| **Execution Style** | Simulated Maker | Active Event-Driven Maker |
| **Total Fills** | 6 | 65 |
| **Execution Cost** | Negligible | **$0.19** (Successfully neutralized) |
| **Net PnL** | +$0.04 | **–$2.85** |
| **Fill Rate** | N/A | ~89% |

**Analysis:**
The C++ implementation successfully "plugged the cost leak." Total execution costs dropped from thousands in the Taker model to just **$0.19**. While the PnL remained slightly negative (–$2.85), the strategy stayed effectively flat across 65 trades, representing a massive improvement over the initial Taker version. 

The remaining loss is attributed to **Adverse Selection (Toxic Fills)**—a common HFT challenge where limit orders are filled precisely when the price is about to crash through the quote level.

---

## 7. Future Implications and Improvements
* **Solve Adverse Selection:** Incorporate Micro-Price or high-frequency momentum indicators to cancel resting orders before "toxic" fills occur.
* **Dynamic Thresholds:** Replace the static ±2 bps threshold with an adaptive threshold that scales with rolling market volatility.
* **Inventory Management:** The observed ~$56 drawdown suggests the need for tighter stop-losses or time-based inventory dumps to prevent holding positions during adverse trends.
* **Signal Expansion:** Use deeper order book levels (L2/L3) to calculate a more robust "weighted" imbalance signal.