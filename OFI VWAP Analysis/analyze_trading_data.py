#!/usr/bin/env python3
"""
Comprehensive Trading Data Analysis Script
Analyzes fill, order, and PnL CSV files from backtesting results
Supports analyzing multiple file sets automatically
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import warnings
import glob
import os
import sys
import re
warnings.filterwarnings('ignore')

# Set style for better-looking plots
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 8)

def find_file_sets():
    """Automatically find all file sets in the current directory"""
    # Find all PnL files
    pnl_files = glob.glob('*_pnl.csv')
    
    file_sets = []
    for pnl_file in pnl_files:
        # Extract base name (everything before _pnl.csv)
        base_name = pnl_file.replace('_pnl.csv', '')
        fill_file = base_name + '_fill.csv'
        order_file = base_name + '_order.csv'
        
        if os.path.exists(fill_file) and os.path.exists(order_file):
            file_sets.append({
                'base_name': base_name,
                'pnl_file': pnl_file,
                'fill_file': fill_file,
                'order_file': order_file
            })
    
    return file_sets

def load_data(pnl_file, fill_file, order_file, file_set_name=""):
    """Load all CSV files for a given file set"""
    if file_set_name:
        print(f"\nLoading data files for: {file_set_name}")
    else:
        print("Loading data files...")
    
    # Load PnL data
    pnl_df = pd.read_csv(pnl_file)
    # Handle mixed datetime formats (with and without microseconds)
    pnl_df['Time'] = pd.to_datetime(pnl_df['Time'], errors='coerce')
    
    # Load fill data
    fill_df = pd.read_csv(fill_file)
    fill_df['TradeTime'] = pd.to_datetime(fill_df['TradeTime'], errors='coerce')
    
    # Load order data
    order_df = pd.read_csv(order_file)
    order_df['EntryTime'] = pd.to_datetime(order_df['EntryTime'], errors='coerce')
    order_df['LastModTime'] = pd.to_datetime(order_df['LastModTime'], errors='coerce')
    
    # Remove rows with invalid datetime values
    pnl_df = pnl_df.dropna(subset=['Time'])
    fill_df = fill_df.dropna(subset=['TradeTime'])
    order_df = order_df.dropna(subset=['EntryTime', 'LastModTime'])
    
    print(f"✓ Loaded {len(pnl_df)} PnL records")
    print(f"✓ Loaded {len(fill_df)} fill records")
    print(f"✓ Loaded {len(order_df)} order records")
    
    return pnl_df, fill_df, order_df

def analyze_pnl(pnl_df):
    """Analyze PnL data"""
    print("\n" + "="*80)
    print("PROFIT & LOSS ANALYSIS")
    print("="*80)
    
    # Basic statistics
    final_pnl = pnl_df['Cumulative PnL'].iloc[-1]
    max_pnl = pnl_df['Cumulative PnL'].max()
    min_pnl = pnl_df['Cumulative PnL'].min()
    max_drawdown = min_pnl - max_pnl
    
    print(f"\nFinal Cumulative PnL: ${final_pnl:,.2f}")
    print(f"Maximum PnL: ${max_pnl:,.2f}")
    print(f"Minimum PnL: ${min_pnl:,.2f}")
    print(f"Maximum Drawdown: ${abs(max_drawdown):,.2f}")
    
    # Calculate daily PnL changes
    pnl_df['PnL_Change'] = pnl_df['Cumulative PnL'].diff()
    pnl_df['PnL_Change'].fillna(0, inplace=True)
    
    # Time-based analysis
    pnl_df['Hour'] = pnl_df['Time'].dt.hour
    pnl_df['Minute'] = pnl_df['Time'].dt.minute
    
    # Hourly PnL performance
    hourly_pnl = pnl_df.groupby('Hour')['PnL_Change'].sum()
    
    print(f"\nHourly PnL Performance:")
    for hour, pnl in hourly_pnl.items():
        print(f"  Hour {int(hour):02d}:00 - ${pnl:,.2f}")
    
    return pnl_df

def analyze_fills(fill_df):
    """Analyze fill/execution data"""
    print("\n" + "="*80)
    print("FILL/EXECUTION ANALYSIS")
    print("="*80)
    
    # Basic statistics
    total_fills = len(fill_df)
    unique_symbols = fill_df['Symbol'].nunique()
    total_volume = fill_df['Quantity'].abs().sum()
    total_execution_cost = fill_df['ExecutionCost'].sum()
    
    print(f"\nTotal Fills: {total_fills:,}")
    print(f"Unique Symbols Traded: {unique_symbols}")
    print(f"Total Volume: {total_volume:,} shares")
    print(f"Total Execution Costs: ${total_execution_cost:,.2f}")
    
    # Symbol analysis
    symbol_stats = fill_df.groupby('Symbol').agg({
        'Quantity': ['count', 'sum', lambda x: x.abs().sum()],
        'Price': ['mean', 'min', 'max'],
        'ExecutionCost': 'sum'
    }).round(2)
    
    symbol_stats.columns = ['Fill_Count', 'Net_Quantity', 'Total_Volume', 
                            'Avg_Price', 'Min_Price', 'Max_Price', 'Total_Cost']
    
    print(f"\nSymbol Statistics:")
    print(symbol_stats.sort_values('Fill_Count', ascending=False).head(10))
    
    # Buy vs Sell analysis
    fill_df['TradeType'] = fill_df['Quantity'].apply(lambda x: 'BUY' if x > 0 else 'SELL')
    trade_type_stats = fill_df.groupby('TradeType').agg({
        'Quantity': ['count', lambda x: x.abs().sum()],
        'ExecutionCost': 'sum'
    })
    
    print(f"\nTrade Type Statistics:")
    print(trade_type_stats)
    
    # Price analysis
    print(f"\nPrice Statistics:")
    print(f"  Average Fill Price: ${fill_df['Price'].mean():.2f}")
    print(f"  Median Fill Price: ${fill_df['Price'].median():.2f}")
    print(f"  Min Fill Price: ${fill_df['Price'].min():.2f}")
    print(f"  Max Fill Price: ${fill_df['Price'].max():.2f}")
    
    return fill_df

def analyze_orders(order_df):
    """Analyze order data"""
    print("\n" + "="*80)
    print("ORDER ANALYSIS")
    print("="*80)
    
    # Basic statistics
    total_orders = len(order_df)
    filled_orders = len(order_df[order_df['State'] == 'FILLED'])
    order_fill_rate = (filled_orders / total_orders) * 100
    
    print(f"\nTotal Orders: {total_orders:,}")
    print(f"Filled Orders: {filled_orders:,}")
    print(f"Order Fill Rate: {order_fill_rate:.2f}%")
    
    # Order type analysis
    order_type_stats = order_df.groupby('Type').agg({
        'OrderId': 'count',
        'FilledQty': 'sum',
        'ExecutionCost': 'sum'
    })
    
    print(f"\nOrder Type Statistics:")
    print(order_type_stats)
    
    # Side analysis
    side_stats = order_df.groupby('Side').agg({
        'OrderId': 'count',
        'FilledQty': 'sum',
        'ExecutionCost': 'sum'
    })
    
    print(f"\nSide Statistics:")
    print(side_stats)
    
    # Slippage analysis (difference between order price and average fill price)
    order_df['Slippage'] = order_df['AvgFillPrice'] - order_df['Price']
    order_df['Slippage_Pct'] = (order_df['Slippage'] / order_df['Price']) * 100
    
    print(f"\nSlippage Analysis:")
    print(f"  Average Slippage: ${order_df['Slippage'].mean():.4f}")
    print(f"  Average Slippage %: {order_df['Slippage_Pct'].mean():.4f}%")
    print(f"  Median Slippage: ${order_df['Slippage'].median():.4f}")
    print(f"  Max Positive Slippage: ${order_df['Slippage'].max():.4f}")
    print(f"  Max Negative Slippage: ${order_df['Slippage'].min():.4f}")
    
    return order_df

def calculate_performance_metrics(pnl_df, fill_df, order_df):
    """Calculate comprehensive performance metrics"""
    print("\n" + "="*80)
    print("PERFORMANCE METRICS")
    print("="*80)
    
    # Calculate returns
    initial_pnl = pnl_df['Cumulative PnL'].iloc[0]
    final_pnl = pnl_df['Cumulative PnL'].iloc[-1]
    total_return = final_pnl - initial_pnl
    
    # Calculate time period
    start_time = pnl_df['Time'].min()
    end_time = pnl_df['Time'].max()
    duration = end_time - start_time
    
    # Calculate drawdown
    pnl_df['RunningMax'] = pnl_df['Cumulative PnL'].expanding().max()
    pnl_df['Drawdown'] = pnl_df['Cumulative PnL'] - pnl_df['RunningMax']
    max_drawdown = pnl_df['Drawdown'].min()
    
    # Calculate volatility (standard deviation of PnL changes)
    pnl_changes = pnl_df['Cumulative PnL'].diff().dropna()
    volatility = pnl_changes.std()
    
    # Calculate Sharpe-like ratio (if we had risk-free rate, would use that)
    if volatility > 0:
        sharpe_like = (total_return / len(pnl_changes)) / volatility
    else:
        sharpe_like = 0
    
    # Win rate (from fills - assuming positive PnL change means win)
    pnl_df['PnL_Change'] = pnl_df['Cumulative PnL'].diff()
    winning_periods = (pnl_df['PnL_Change'] > 0).sum()
    total_periods = (pnl_df['PnL_Change'] != 0).sum()
    win_rate = (winning_periods / total_periods * 100) if total_periods > 0 else 0
    
    print(f"\nTrading Period: {start_time} to {end_time}")
    print(f"Duration: {duration}")
    print(f"\nTotal Return: ${total_return:,.2f}")
    print(f"Maximum Drawdown: ${abs(max_drawdown):,.2f}")
    print(f"Volatility (Std Dev): ${volatility:,.2f}")
    print(f"Sharpe-like Ratio: {sharpe_like:.4f}")
    print(f"Win Rate: {win_rate:.2f}%")
    
    # Calculate average trade size
    avg_trade_size = fill_df['Quantity'].abs().mean()
    print(f"\nAverage Trade Size: {avg_trade_size:.2f} shares")
    
    # Calculate total costs
    total_costs = fill_df['ExecutionCost'].sum()
    print(f"Total Execution Costs: ${total_costs:,.2f}")
    print(f"Cost as % of PnL: {(total_costs/abs(total_return)*100) if total_return != 0 else 0:.2f}%")
    
    return {
        'total_return': total_return,
        'max_drawdown': max_drawdown,
        'volatility': volatility,
        'sharpe_like': sharpe_like,
        'win_rate': win_rate
    }

def create_visualizations(pnl_df, fill_df, order_df, output_prefix="trading_analysis"):
    """Create comprehensive visualizations with detailed plots and diagrams"""
    print("\n" + "="*80)
    print("GENERATING VISUALIZATIONS")
    print("="*80)
    
    # Prepare data - ensure no NaT values
    pnl_df = pnl_df.dropna(subset=['Time']).copy()
    fill_df = fill_df.dropna(subset=['TradeTime']).copy()
    
    pnl_df['PnL_Change'] = pnl_df['Cumulative PnL'].diff().fillna(0)
    pnl_df['RunningMax'] = pnl_df['Cumulative PnL'].expanding().max()
    pnl_df['Drawdown'] = pnl_df['Cumulative PnL'] - pnl_df['RunningMax']
    pnl_df['Hour'] = pnl_df['Time'].dt.hour
    pnl_df['Minute'] = pnl_df['Time'].dt.minute
    
    fill_df['TradeType'] = fill_df['Quantity'].apply(lambda x: 'BUY' if x > 0 else 'SELL')
    fill_df['AbsQuantity'] = fill_df['Quantity'].abs()
    fill_df['TradeValue'] = fill_df['Quantity'].abs() * fill_df['Price']
    
    order_df['Slippage'] = order_df['AvgFillPrice'] - order_df['Price']
    order_df['Slippage_Pct'] = (order_df['Slippage'] / order_df['Price']) * 100
    
    # ============================================================================
    # FIGURE 1: Main Performance Dashboard
    # ============================================================================
    fig1 = plt.figure(figsize=(20, 12))
    gs = fig1.add_gridspec(3, 3, hspace=0.3, wspace=0.3)
    
    # 1. Cumulative PnL with annotations
    ax1 = fig1.add_subplot(gs[0, :2])
    ax1.plot(pnl_df['Time'], pnl_df['Cumulative PnL'], linewidth=2.5, color='#2E86AB', label='Cumulative PnL')
    ax1.axhline(y=0, color='black', linestyle='--', linewidth=1, alpha=0.5)
    final_pnl = pnl_df['Cumulative PnL'].iloc[-1]
    max_pnl = pnl_df['Cumulative PnL'].max()
    min_pnl = pnl_df['Cumulative PnL'].min()
    final_time = pnl_df['Time'].iloc[-1]
    max_time = pnl_df.loc[pnl_df['Cumulative PnL'].idxmax(), 'Time']
    if pd.notna(final_time):
        ax1.scatter([final_time], [final_pnl], color='red', s=100, zorder=5, label=f'Final: ${final_pnl:.2f}')
    if pd.notna(max_time):
        ax1.scatter([max_time], [max_pnl], 
                    color='green', s=100, zorder=5, marker='^', label=f'Max: ${max_pnl:.2f}')
    ax1.set_title('Cumulative PnL Over Time', fontsize=16, fontweight='bold', pad=15)
    ax1.set_xlabel('Time', fontsize=12)
    ax1.set_ylabel('Cumulative PnL ($)', fontsize=12)
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.legend(loc='best', fontsize=10)
    ax1.tick_params(axis='x', rotation=45)
    
    # 2. Drawdown chart
    ax2 = fig1.add_subplot(gs[0, 2])
    ax2.fill_between(pnl_df['Time'], pnl_df['Drawdown'], 0, color='#A23B72', alpha=0.7)
    ax2.plot(pnl_df['Time'], pnl_df['Drawdown'], linewidth=1.5, color='#8B1A5A')
    max_dd = pnl_df['Drawdown'].min()
    ax2.axhline(y=max_dd, color='red', linestyle='--', linewidth=2, label=f'Max DD: ${max_dd:.2f}')
    ax2.set_title('Drawdown Analysis', fontsize=16, fontweight='bold', pad=15)
    ax2.set_xlabel('Time', fontsize=12)
    ax2.set_ylabel('Drawdown ($)', fontsize=12)
    ax2.grid(True, alpha=0.3, linestyle='--')
    ax2.legend(loc='best', fontsize=10)
    ax2.tick_params(axis='x', rotation=45)
    
    # 3. PnL Change Distribution
    ax3 = fig1.add_subplot(gs[1, 0])
    pnl_changes = pnl_df['PnL_Change'].dropna()
    pnl_changes = pnl_changes[pnl_changes != 0]
    ax3.hist(pnl_changes, bins=60, color='#F18F01', edgecolor='black', alpha=0.7)
    ax3.axvline(x=0, color='red', linestyle='--', linewidth=2)
    ax3.axvline(x=pnl_changes.mean(), color='blue', linestyle='--', linewidth=2, label=f'Mean: ${pnl_changes.mean():.2f}')
    ax3.set_title('PnL Change Distribution', fontsize=14, fontweight='bold', pad=10)
    ax3.set_xlabel('PnL Change ($)', fontsize=11)
    ax3.set_ylabel('Frequency', fontsize=11)
    ax3.grid(True, alpha=0.3, linestyle='--', axis='y')
    ax3.legend(loc='best', fontsize=9)
    
    # 4. Hourly PnL Performance Heatmap
    ax4 = fig1.add_subplot(gs[1, 1])
    hourly_pnl = pnl_df.groupby('Hour')['PnL_Change'].sum()
    colors = ['#D62828' if x < 0 else '#06A77D' for x in hourly_pnl.values]
    bars = ax4.bar(hourly_pnl.index, hourly_pnl.values, color=colors, alpha=0.7, edgecolor='black')
    ax4.axhline(y=0, color='black', linestyle='-', linewidth=1)
    ax4.set_title('Hourly PnL Performance', fontsize=14, fontweight='bold', pad=10)
    ax4.set_xlabel('Hour of Day', fontsize=11)
    ax4.set_ylabel('Total PnL ($)', fontsize=11)
    ax4.grid(True, alpha=0.3, linestyle='--', axis='y')
    # Add value labels on bars
    for bar in bars:
        height = bar.get_height()
        if abs(height) > 10:  # Only label significant values
            ax4.text(bar.get_x() + bar.get_width()/2., height,
                    f'${height:.0f}', ha='center', va='bottom' if height > 0 else 'top', fontsize=8)
    
    # 5. Buy vs Sell Analysis
    ax5 = fig1.add_subplot(gs[1, 2])
    trade_counts = fill_df['TradeType'].value_counts()
    trade_volumes = fill_df.groupby('TradeType')['AbsQuantity'].sum()
    colors_pie = ['#2E86AB', '#A23B72']
    wedges, texts, autotexts = ax5.pie(trade_counts.values, labels=trade_counts.index, 
                                       autopct='%1.1f%%', colors=colors_pie, startangle=90,
                                       textprops={'fontsize': 11, 'fontweight': 'bold'})
    ax5.set_title('Buy vs Sell Distribution\n(by Count)', fontsize=14, fontweight='bold', pad=10)
    # Add volume info
    volume_text = f"Buy Vol: {trade_volumes.get('BUY', 0):.0f}\nSell Vol: {trade_volumes.get('SELL', 0):.0f}"
    ax5.text(0, -1.3, volume_text, ha='center', fontsize=9, bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # 6. Top Symbols by Fill Count
    ax6 = fig1.add_subplot(gs[2, 0])
    symbol_counts = fill_df['Symbol'].value_counts().head(10)
    bars = ax6.barh(range(len(symbol_counts)), symbol_counts.values, color='#C73E1D', alpha=0.8, edgecolor='black')
    ax6.set_yticks(range(len(symbol_counts)))
    ax6.set_yticklabels(symbol_counts.index, fontsize=10)
    ax6.set_title('Top 10 Symbols by Fill Count', fontsize=14, fontweight='bold', pad=10)
    ax6.set_xlabel('Number of Fills', fontsize=11)
    ax6.grid(True, alpha=0.3, linestyle='--', axis='x')
    # Add value labels
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax6.text(width, bar.get_y() + bar.get_height()/2., f'{int(width)}',
                ha='left', va='center', fontsize=9, fontweight='bold')
    
    # 7. Volume Analysis by Symbol
    ax7 = fig1.add_subplot(gs[2, 1])
    symbol_volume = fill_df.groupby('Symbol')['AbsQuantity'].sum().sort_values(ascending=False).head(10)
    bars = ax7.barh(range(len(symbol_volume)), symbol_volume.values, color='#F77F00', alpha=0.8, edgecolor='black')
    ax7.set_yticks(range(len(symbol_volume)))
    ax7.set_yticklabels(symbol_volume.index, fontsize=10)
    ax7.set_title('Top 10 Symbols by Total Volume', fontsize=14, fontweight='bold', pad=10)
    ax7.set_xlabel('Total Volume (shares)', fontsize=11)
    ax7.grid(True, alpha=0.3, linestyle='--', axis='x')
    # Add value labels
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax7.text(width, bar.get_y() + bar.get_height()/2., f'{int(width):,}',
                ha='left', va='center', fontsize=9, fontweight='bold')
    
    # 8. Execution Cost Analysis
    ax8 = fig1.add_subplot(gs[2, 2])
    symbol_costs = fill_df.groupby('Symbol')['ExecutionCost'].sum().sort_values(ascending=False).head(10)
    bars = ax8.barh(range(len(symbol_costs)), symbol_costs.values, color='#FCBF49', alpha=0.8, edgecolor='black')
    ax8.set_yticks(range(len(symbol_costs)))
    ax8.set_yticklabels(symbol_costs.index, fontsize=10)
    ax8.set_title('Top 10 Symbols by Execution Cost', fontsize=14, fontweight='bold', pad=10)
    ax8.set_xlabel('Total Execution Cost ($)', fontsize=11)
    ax8.grid(True, alpha=0.3, linestyle='--', axis='x')
    # Add value labels
    for i, bar in enumerate(bars):
        width = bar.get_width()
        ax8.text(width, bar.get_y() + bar.get_height()/2., f'${width:.2f}',
                ha='left', va='center', fontsize=9, fontweight='bold')
    
    plt.suptitle('Trading Performance Dashboard - OfiIndex1 Strategy', 
                fontsize=18, fontweight='bold', y=0.995)
    plt.savefig(f'{output_prefix}_dashboard.png', dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Saved visualization: {output_prefix}_dashboard.png")
    plt.close()
    
    # ============================================================================
    # FIGURE 2: Detailed Analysis Charts
    # ============================================================================
    fig2 = plt.figure(figsize=(20, 14))
    gs2 = fig2.add_gridspec(3, 3, hspace=0.35, wspace=0.3)
    
    # 1. Volume Over Time
    ax1 = fig2.add_subplot(gs2[0, :2])
    fill_df['TimeBucket'] = pd.to_datetime(fill_df['TradeTime']).dt.floor('5min')
    volume_over_time = fill_df.groupby('TimeBucket')['AbsQuantity'].sum()
    ax1.bar(volume_over_time.index, volume_over_time.values, width=pd.Timedelta(minutes=4), 
            color='#06A77D', alpha=0.7, edgecolor='black', linewidth=0.5)
    ax1.set_title('Trading Volume Over Time (5-min buckets)', fontsize=16, fontweight='bold', pad=15)
    ax1.set_xlabel('Time', fontsize=12)
    ax1.set_ylabel('Volume (shares)', fontsize=12)
    ax1.grid(True, alpha=0.3, linestyle='--', axis='y')
    ax1.tick_params(axis='x', rotation=45)
    
    # 2. PnL vs Volume Scatter
    ax2 = fig2.add_subplot(gs2[0, 2])
    # Aggregate by time bucket
    pnl_df['TimeBucket'] = pd.to_datetime(pnl_df['Time']).dt.floor('5min')
    bucket_pnl = pnl_df.groupby('TimeBucket')['PnL_Change'].sum()
    bucket_volume = fill_df.groupby('TimeBucket')['AbsQuantity'].sum()
    combined = pd.DataFrame({'PnL': bucket_pnl, 'Volume': bucket_volume}).dropna()
    scatter = ax2.scatter(combined['Volume'], combined['PnL'], 
                         c=combined['PnL'], cmap='RdYlGn', alpha=0.6, s=50, edgecolors='black', linewidth=0.5)
    ax2.axhline(y=0, color='black', linestyle='--', linewidth=1)
    ax2.axvline(x=0, color='black', linestyle='--', linewidth=1)
    ax2.set_title('PnL vs Trading Volume', fontsize=14, fontweight='bold', pad=10)
    ax2.set_xlabel('Volume (shares)', fontsize=11)
    ax2.set_ylabel('PnL Change ($)', fontsize=11)
    ax2.grid(True, alpha=0.3, linestyle='--')
    plt.colorbar(scatter, ax=ax2, label='PnL ($)')
    
    # 3. Slippage Analysis - Box Plot
    ax3 = fig2.add_subplot(gs2[1, 0])
    slippage_data = order_df['Slippage'].dropna()
    bp = ax3.boxplot([slippage_data], vert=True, patch_artist=True, 
                     boxprops=dict(facecolor='#003049', alpha=0.7),
                     medianprops=dict(color='red', linewidth=2),
                     whiskerprops=dict(color='black', linewidth=1.5),
                     capprops=dict(color='black', linewidth=1.5))
    ax3.axhline(y=0, color='red', linestyle='--', linewidth=2)
    ax3.set_title('Slippage Distribution\n(Box Plot)', fontsize=14, fontweight='bold', pad=10)
    ax3.set_ylabel('Slippage ($)', fontsize=11)
    ax3.grid(True, alpha=0.3, linestyle='--', axis='y')
    ax3.set_xticklabels(['All Orders'])
    # Add statistics
    stats_text = f"Mean: ${slippage_data.mean():.4f}\nMedian: ${slippage_data.median():.4f}\nStd: ${slippage_data.std():.4f}"
    ax3.text(0.7, 0.95, stats_text, transform=ax3.transAxes, fontsize=9,
            verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # 4. Slippage by Order Side
    ax4 = fig2.add_subplot(gs2[1, 1])
    slippage_by_side = [order_df[order_df['Side'] == side]['Slippage'].dropna().values 
                        for side in ['BUY', 'SELL']]
    bp = ax4.boxplot(slippage_by_side, labels=['BUY', 'SELL'], patch_artist=True,
                     boxprops=dict(facecolor='#D62828', alpha=0.7),
                     medianprops=dict(color='yellow', linewidth=2),
                     whiskerprops=dict(color='black', linewidth=1.5))
    ax4.axhline(y=0, color='red', linestyle='--', linewidth=2)
    ax4.set_title('Slippage by Order Side', fontsize=14, fontweight='bold', pad=10)
    ax4.set_ylabel('Slippage ($)', fontsize=11)
    ax4.set_xlabel('Order Side', fontsize=11)
    ax4.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # 5. Order Fill Rate Analysis
    ax5 = fig2.add_subplot(gs2[1, 2])
    order_fill_rates = order_df.groupby('Type').apply(
        lambda x: (x['State'] == 'FILLED').sum() / len(x) * 100
    )
    colors_bar = ['#06A77D' if x > 80 else '#D62828' if x < 50 else '#F18F01' for x in order_fill_rates.values]
    bars = ax5.bar(order_fill_rates.index, order_fill_rates.values, color=colors_bar, alpha=0.8, edgecolor='black')
    ax5.set_title('Fill Rate by Order Type', fontsize=14, fontweight='bold', pad=10)
    ax5.set_xlabel('Order Type', fontsize=11)
    ax5.set_ylabel('Fill Rate (%)', fontsize=11)
    ax5.set_ylim([0, 105])
    ax5.grid(True, alpha=0.3, linestyle='--', axis='y')
    ax5.tick_params(axis='x', rotation=45)
    # Add value labels
    for bar in bars:
        height = bar.get_height()
        ax5.text(bar.get_x() + bar.get_width()/2., height,
                f'{height:.1f}%', ha='center', va='bottom', fontsize=10, fontweight='bold')
    
    # 6. Price Range by Symbol (Top 10)
    ax6 = fig2.add_subplot(gs2[2, 0])
    top_symbols = fill_df['Symbol'].value_counts().head(10).index
    price_ranges = []
    symbol_labels = []
    for symbol in top_symbols:
        symbol_data = fill_df[fill_df['Symbol'] == symbol]
        price_ranges.append([symbol_data['Price'].min(), symbol_data['Price'].max()])
        symbol_labels.append(symbol)
    
    y_pos = np.arange(len(symbol_labels))
    for i, (min_price, max_price) in enumerate(price_ranges):
        ax6.barh(i, max_price - min_price, left=min_price, height=0.6, 
                color='#2E86AB', alpha=0.7, edgecolor='black')
        ax6.text((min_price + max_price) / 2, i, f'${min_price:.2f}-${max_price:.2f}',
                ha='center', va='center', fontsize=8, fontweight='bold')
    
    ax6.set_yticks(y_pos)
    ax6.set_yticklabels(symbol_labels, fontsize=9)
    ax6.set_title('Price Range by Symbol (Top 10)', fontsize=14, fontweight='bold', pad=10)
    ax6.set_xlabel('Price ($)', fontsize=11)
    ax6.grid(True, alpha=0.3, linestyle='--', axis='x')
    
    # 7. Trade Value Distribution
    ax7 = fig2.add_subplot(gs2[2, 1])
    trade_values = fill_df['TradeValue']
    ax7.hist(trade_values, bins=50, color='#6A994E', edgecolor='black', alpha=0.7)
    ax7.axvline(x=trade_values.mean(), color='red', linestyle='--', linewidth=2, 
                label=f'Mean: ${trade_values.mean():,.2f}')
    ax7.axvline(x=trade_values.median(), color='blue', linestyle='--', linewidth=2,
                label=f'Median: ${trade_values.median():,.2f}')
    ax7.set_title('Trade Value Distribution', fontsize=14, fontweight='bold', pad=10)
    ax7.set_xlabel('Trade Value ($)', fontsize=11)
    ax7.set_ylabel('Frequency', fontsize=11)
    ax7.legend(loc='best', fontsize=9)
    ax7.grid(True, alpha=0.3, linestyle='--', axis='y')
    ax7.set_xscale('log')
    
    # 8. Cumulative Execution Costs
    ax8 = fig2.add_subplot(gs2[2, 2])
    fill_df_sorted = fill_df.sort_values('TradeTime')
    fill_df_sorted['CumulativeCost'] = fill_df_sorted['ExecutionCost'].cumsum()
    ax8.plot(fill_df_sorted['TradeTime'], fill_df_sorted['CumulativeCost'], 
             linewidth=2.5, color='#A23B72', label='Cumulative Costs')
    total_cost = fill_df_sorted['CumulativeCost'].iloc[-1]
    ax8.axhline(y=total_cost, color='red', linestyle='--', linewidth=1.5, 
               label=f'Total: ${total_cost:.2f}')
    ax8.set_title('Cumulative Execution Costs', fontsize=14, fontweight='bold', pad=10)
    ax8.set_xlabel('Time', fontsize=11)
    ax8.set_ylabel('Cumulative Cost ($)', fontsize=11)
    ax8.grid(True, alpha=0.3, linestyle='--')
    ax8.legend(loc='best', fontsize=9)
    ax8.tick_params(axis='x', rotation=45)
    
    plt.suptitle('Detailed Trading Analysis - OfiIndex1 Strategy', 
                fontsize=18, fontweight='bold', y=0.995)
    plt.savefig(f'{output_prefix}_detailed.png', dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Saved visualization: {output_prefix}_detailed.png")
    plt.close()
    
    # ============================================================================
    # FIGURE 3: Time Series and Heatmaps
    # ============================================================================
    fig3 = plt.figure(figsize=(20, 12))
    gs3 = fig3.add_gridspec(2, 3, hspace=0.35, wspace=0.3)
    
    # 1. PnL Change Over Time (with moving average)
    ax1 = fig3.add_subplot(gs3[0, :2])
    pnl_changes = pnl_df['PnL_Change'].copy()
    pnl_changes_ma = pnl_changes.rolling(window=20, min_periods=1).mean()
    ax1.plot(pnl_df['Time'], pnl_changes, alpha=0.4, color='gray', linewidth=1, label='PnL Change')
    ax1.plot(pnl_df['Time'], pnl_changes_ma, color='#2E86AB', linewidth=2.5, label='20-period MA')
    ax1.fill_between(pnl_df['Time'], pnl_changes, 0, where=(pnl_changes >= 0), 
                     color='green', alpha=0.3, label='Positive')
    ax1.fill_between(pnl_df['Time'], pnl_changes, 0, where=(pnl_changes < 0), 
                     color='red', alpha=0.3, label='Negative')
    ax1.axhline(y=0, color='black', linestyle='-', linewidth=1)
    ax1.set_title('PnL Change Over Time with Moving Average', fontsize=16, fontweight='bold', pad=15)
    ax1.set_xlabel('Time', fontsize=12)
    ax1.set_ylabel('PnL Change ($)', fontsize=12)
    ax1.legend(loc='best', fontsize=10)
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.tick_params(axis='x', rotation=45)
    
    # 2. Hourly Performance Heatmap
    ax2 = fig3.add_subplot(gs3[0, 2])
    pnl_df['MinuteBucket'] = (pnl_df['Minute'] // 10) * 10  # 10-minute buckets
    hourly_minute_pnl = pnl_df.groupby(['Hour', 'MinuteBucket'])['PnL_Change'].sum().unstack(fill_value=0)
    im = ax2.imshow(hourly_minute_pnl.values, cmap='RdYlGn', aspect='auto', interpolation='nearest')
    ax2.set_title('Hourly PnL Heatmap\n(10-min intervals)', fontsize=14, fontweight='bold', pad=10)
    ax2.set_xlabel('Minute of Hour', fontsize=11)
    ax2.set_ylabel('Hour of Day', fontsize=11)
    ax2.set_yticks(range(len(hourly_minute_pnl.index)))
    ax2.set_yticklabels(hourly_minute_pnl.index)
    ax2.set_xticks(range(len(hourly_minute_pnl.columns)))
    ax2.set_xticklabels(hourly_minute_pnl.columns)
    plt.colorbar(im, ax=ax2, label='PnL ($)')
    
    # 3. Trade Frequency Over Time
    ax3 = fig3.add_subplot(gs3[1, 0])
    fill_df['TimeBucket'] = pd.to_datetime(fill_df['TradeTime']).dt.floor('10min')
    trade_freq = fill_df.groupby('TimeBucket').size()
    ax3.bar(trade_freq.index, trade_freq.values, width=pd.Timedelta(minutes=9),
            color='#F18F01', alpha=0.7, edgecolor='black', linewidth=0.5)
    ax3.set_title('Trade Frequency Over Time\n(10-min buckets)', fontsize=14, fontweight='bold', pad=10)
    ax3.set_xlabel('Time', fontsize=11)
    ax3.set_ylabel('Number of Trades', fontsize=11)
    ax3.grid(True, alpha=0.3, linestyle='--', axis='y')
    ax3.tick_params(axis='x', rotation=45)
    
    # 4. Symbol Trading Activity Heatmap
    ax4 = fig3.add_subplot(gs3[1, 1])
    top_10_symbols = fill_df['Symbol'].value_counts().head(10).index
    fill_df_top = fill_df[fill_df['Symbol'].isin(top_10_symbols)]
    fill_df_top['Hour'] = pd.to_datetime(fill_df_top['TradeTime']).dt.hour
    symbol_hour_activity = fill_df_top.groupby(['Symbol', 'Hour']).size().unstack(fill_value=0)
    symbol_hour_activity = symbol_hour_activity.reindex(top_10_symbols)
    im = ax4.imshow(symbol_hour_activity.values, cmap='YlOrRd', aspect='auto', interpolation='nearest')
    ax4.set_title('Trading Activity Heatmap\n(Top 10 Symbols)', fontsize=14, fontweight='bold', pad=10)
    ax4.set_xlabel('Hour of Day', fontsize=11)
    ax4.set_ylabel('Symbol', fontsize=11)
    ax4.set_yticks(range(len(symbol_hour_activity.index)))
    ax4.set_yticklabels(symbol_hour_activity.index, fontsize=9)
    ax4.set_xticks(range(len(symbol_hour_activity.columns)))
    ax4.set_xticklabels(symbol_hour_activity.columns)
    plt.colorbar(im, ax=ax4, label='Trade Count')
    
    # 5. Execution Cost per Trade Over Time
    ax5 = fig3.add_subplot(gs3[1, 2])
    fill_df_sorted = fill_df.sort_values('TradeTime')
    fill_df_sorted['TimeBucket'] = pd.to_datetime(fill_df_sorted['TradeTime']).dt.floor('10min')
    cost_per_trade = fill_df_sorted.groupby('TimeBucket')['ExecutionCost'].mean()
    ax5.plot(cost_per_trade.index, cost_per_trade.values, 
             linewidth=2, color='#D62828', marker='o', markersize=3)
    ax5.axhline(y=cost_per_trade.mean(), color='blue', linestyle='--', linewidth=2,
               label=f'Mean: ${cost_per_trade.mean():.4f}')
    ax5.set_title('Average Execution Cost per Trade\n(10-min buckets)', fontsize=14, fontweight='bold', pad=10)
    ax5.set_xlabel('Time', fontsize=11)
    ax5.set_ylabel('Avg Cost per Trade ($)', fontsize=11)
    ax5.legend(loc='best', fontsize=9)
    ax5.grid(True, alpha=0.3, linestyle='--')
    ax5.tick_params(axis='x', rotation=45)
    
    plt.suptitle('Time Series Analysis & Heatmaps - OfiIndex1 Strategy', 
                fontsize=18, fontweight='bold', y=0.995)
    plt.savefig(f'{output_prefix}_timeseries.png', dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Saved visualization: {output_prefix}_timeseries.png")
    plt.close()
    
    # ============================================================================
    # FIGURE 4: Risk and Statistical Analysis
    # ============================================================================
    fig4 = plt.figure(figsize=(20, 12))
    gs4 = fig4.add_gridspec(2, 3, hspace=0.35, wspace=0.3)
    
    # 1. Rolling Volatility
    ax1 = fig4.add_subplot(gs4[0, 0])
    pnl_changes = pnl_df['PnL_Change'].dropna()
    rolling_vol = pnl_changes.rolling(window=50, min_periods=1).std()
    ax1.plot(pnl_df['Time'].iloc[:len(rolling_vol)], rolling_vol.values, 
             linewidth=2, color='#8B1A5A', label='Rolling Volatility (50-period)')
    ax1.axhline(y=pnl_changes.std(), color='red', linestyle='--', linewidth=2,
               label=f'Overall Std: ${pnl_changes.std():.2f}')
    ax1.set_title('Rolling Volatility', fontsize=14, fontweight='bold', pad=10)
    ax1.set_xlabel('Time', fontsize=11)
    ax1.set_ylabel('Volatility ($)', fontsize=11)
    ax1.legend(loc='best', fontsize=9)
    ax1.grid(True, alpha=0.3, linestyle='--')
    ax1.tick_params(axis='x', rotation=45)
    
    # 2. Win/Loss Analysis
    ax2 = fig4.add_subplot(gs4[0, 1])
    pnl_changes_nonzero = pnl_changes[pnl_changes != 0]
    wins = pnl_changes_nonzero[pnl_changes_nonzero > 0]
    losses = pnl_changes_nonzero[pnl_changes_nonzero < 0]
    
    win_loss_data = [
        ['Wins', len(wins), wins.mean() if len(wins) > 0 else 0, wins.sum() if len(wins) > 0 else 0],
        ['Losses', len(losses), losses.mean() if len(losses) > 0 else 0, losses.sum() if len(losses) > 0 else 0]
    ]
    
    x = np.arange(2)
    width = 0.25
    ax2.bar(x - width, [win_loss_data[0][1], win_loss_data[1][1]], width, 
            label='Count', color='#2E86AB', alpha=0.8)
    ax2.bar(x, [abs(win_loss_data[0][2]), abs(win_loss_data[1][2])], width,
            label='Avg Magnitude ($)', color='#F18F01', alpha=0.8)
    ax2.bar(x + width, [abs(win_loss_data[0][3]), abs(win_loss_data[1][3])], width,
            label='Total ($)', color='#06A77D', alpha=0.8)
    ax2.set_ylabel('Value', fontsize=11)
    ax2.set_title('Win/Loss Analysis', fontsize=14, fontweight='bold', pad=10)
    ax2.set_xticks(x)
    ax2.set_xticklabels(['Wins', 'Losses'])
    ax2.legend(loc='best', fontsize=9)
    ax2.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # 3. Cumulative PnL by Symbol
    ax3 = fig4.add_subplot(gs4[0, 2])
    # Estimate PnL contribution by symbol (simplified - using price changes)
    top_symbols = fill_df['Symbol'].value_counts().head(8).index
    symbol_pnl_contrib = []
    for symbol in top_symbols:
        symbol_fills = fill_df[fill_df['Symbol'] == symbol].sort_values('TradeTime')
        # Rough estimate: sum of (quantity * price) for buys minus sells
        symbol_pnl_contrib.append(symbol_fills['Quantity'].multiply(symbol_fills['Price']).sum())
    
    colors_bar = ['#06A77D' if x > 0 else '#D62828' for x in symbol_pnl_contrib]
    bars = ax3.barh(range(len(top_symbols)), symbol_pnl_contrib, color=colors_bar, alpha=0.8, edgecolor='black')
    ax3.set_yticks(range(len(top_symbols)))
    ax3.set_yticklabels(top_symbols, fontsize=10)
    ax3.axvline(x=0, color='black', linestyle='-', linewidth=1)
    ax3.set_title('Estimated PnL Contribution by Symbol', fontsize=14, fontweight='bold', pad=10)
    ax3.set_xlabel('Estimated PnL ($)', fontsize=11)
    ax3.grid(True, alpha=0.3, linestyle='--', axis='x')
    # Add value labels
    for i, (bar, val) in enumerate(zip(bars, symbol_pnl_contrib)):
        ax3.text(val, i, f'${val:.0f}', ha='left' if val > 0 else 'right', 
                va='center', fontsize=9, fontweight='bold')
    
    # 4. Slippage Distribution (Histogram with stats)
    ax4 = fig4.add_subplot(gs4[1, 0])
    slippage_data = order_df['Slippage'].dropna()
    ax4.hist(slippage_data, bins=60, color='#003049', edgecolor='black', alpha=0.7)
    ax4.axvline(x=0, color='red', linestyle='--', linewidth=2, label='Zero Slippage')
    ax4.axvline(x=slippage_data.mean(), color='blue', linestyle='--', linewidth=2,
               label=f'Mean: ${slippage_data.mean():.4f}')
    ax4.axvline(x=slippage_data.median(), color='green', linestyle='--', linewidth=2,
               label=f'Median: ${slippage_data.median():.4f}')
    ax4.set_title('Slippage Distribution', fontsize=14, fontweight='bold', pad=10)
    ax4.set_xlabel('Slippage ($)', fontsize=11)
    ax4.set_ylabel('Frequency', fontsize=11)
    ax4.legend(loc='best', fontsize=9)
    ax4.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # 5. Order Size Distribution
    ax5 = fig4.add_subplot(gs4[1, 1])
    order_sizes = order_df['Quantity'].abs()
    ax5.hist(order_sizes, bins=50, color='#6A994E', edgecolor='black', alpha=0.7)
    ax5.axvline(x=order_sizes.mean(), color='red', linestyle='--', linewidth=2,
               label=f'Mean: {order_sizes.mean():.2f}')
    ax5.axvline(x=order_sizes.median(), color='blue', linestyle='--', linewidth=2,
               label=f'Median: {order_sizes.median():.2f}')
    ax5.set_title('Order Size Distribution', fontsize=14, fontweight='bold', pad=10)
    ax5.set_xlabel('Order Size (shares)', fontsize=11)
    ax5.set_ylabel('Frequency', fontsize=11)
    ax5.legend(loc='best', fontsize=9)
    ax5.grid(True, alpha=0.3, linestyle='--', axis='y')
    
    # 6. Performance Metrics Summary
    ax6 = fig4.add_subplot(gs4[1, 2])
    ax6.axis('off')
    
    # Calculate key metrics
    final_pnl = pnl_df['Cumulative PnL'].iloc[-1]
    max_dd = pnl_df['Drawdown'].min()
    total_trades = len(fill_df)
    total_volume = fill_df['AbsQuantity'].sum()
    total_costs = fill_df['ExecutionCost'].sum()
    win_rate = (len(wins) / len(pnl_changes_nonzero) * 100) if len(pnl_changes_nonzero) > 0 else 0
    
    # Calculate metrics for display
    avg_win = wins.mean() if len(wins) > 0 else 0.0
    avg_loss = losses.mean() if len(losses) > 0 else 0.0
    profit_factor = abs(wins.sum()/losses.sum()) if len(losses) > 0 and losses.sum() != 0 else 0.0
    
    metrics_text = f"""
    PERFORMANCE SUMMARY
    
    Final PnL:              ${final_pnl:,.2f}
    Maximum Drawdown:       ${abs(max_dd):,.2f}
    Total Trades:           {total_trades:,}
    Total Volume:           {total_volume:,.0f} shares
    Total Costs:            ${total_costs:,.2f}
    Win Rate:               {win_rate:.2f}%
    Avg Win:                ${avg_win:.2f}
    Avg Loss:               ${avg_loss:.2f}
    Profit Factor:         {profit_factor:.2f}
    """
    
    ax6.text(0.1, 0.5, metrics_text, transform=ax6.transAxes, fontsize=12,
            verticalalignment='center', family='monospace',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8))
    ax6.set_title('Key Performance Metrics', fontsize=14, fontweight='bold', pad=10)
    
    plt.suptitle('Risk & Statistical Analysis - OfiIndex1 Strategy', 
                fontsize=18, fontweight='bold', y=0.995)
    plt.savefig(f'{output_prefix}_risk.png', dpi=300, bbox_inches='tight', facecolor='white')
    print(f"✓ Saved visualization: {output_prefix}_risk.png")
    plt.close()
    
    print("\n✓ All visualizations generated successfully!")

def generate_summary_report(pnl_df, fill_df, order_df, metrics, output_prefix="trading_analysis"):
    """Generate a comprehensive summary report"""
    print("\n" + "="*80)
    print("GENERATING SUMMARY REPORT")
    print("="*80)
    
    report = f"""
================================================================================
TRADING DATA ANALYSIS SUMMARY REPORT
================================================================================

STRATEGY: OfiIndex1
DATE: September 13, 2019
TRADING PERIOD: {pnl_df['Time'].min()} to {pnl_df['Time'].max()}

--------------------------------------------------------------------------------
PERFORMANCE SUMMARY
--------------------------------------------------------------------------------
Final Cumulative PnL:        ${pnl_df['Cumulative PnL'].iloc[-1]:,.2f}
Total Return:               ${metrics['total_return']:,.2f}
Maximum Drawdown:           ${abs(metrics['max_drawdown']):,.2f}
Volatility (Std Dev):       ${metrics['volatility']:,.2f}
Sharpe-like Ratio:          {metrics['sharpe_like']:.4f}
Win Rate:                   {metrics['win_rate']:.2f}%

--------------------------------------------------------------------------------
TRADING ACTIVITY
--------------------------------------------------------------------------------
Total Orders:               {len(order_df):,}
Filled Orders:              {len(order_df[order_df['State'] == 'FILLED']):,}
Order Fill Rate:            {(len(order_df[order_df['State'] == 'FILLED'])/len(order_df)*100):.2f}%
Total Fills:                {len(fill_df):,}
Unique Symbols Traded:      {fill_df['Symbol'].nunique()}
Total Volume:               {fill_df['Quantity'].abs().sum():,} shares
Average Trade Size:         {fill_df['Quantity'].abs().mean():.2f} shares

--------------------------------------------------------------------------------
COSTS
--------------------------------------------------------------------------------
Total Execution Costs:      ${fill_df['ExecutionCost'].sum():,.2f}
Average Cost per Fill:     ${fill_df['ExecutionCost'].mean():.4f}
Cost as % of Total Return:  {(fill_df['ExecutionCost'].sum()/abs(metrics['total_return'])*100) if metrics['total_return'] != 0 else 0:.2f}%

--------------------------------------------------------------------------------
TOP TRADED SYMBOLS
--------------------------------------------------------------------------------
"""
    
    top_symbols = fill_df.groupby('Symbol').agg({
        'Quantity': ['count', lambda x: x.abs().sum()],
        'ExecutionCost': 'sum'
    })
    top_symbols.columns = ['Fill_Count', 'Total_Volume', 'Total_Cost']
    top_symbols = top_symbols.sort_values('Fill_Count', ascending=False).head(10)
    
    for symbol, row in top_symbols.iterrows():
        report += f"{symbol:10s} - Fills: {row['Fill_Count']:5.0f}, Volume: {row['Total_Volume']:10.0f}, Cost: ${row['Total_Cost']:8.2f}\n"
    
    report += f"""
--------------------------------------------------------------------------------
TRADE TYPE BREAKDOWN
--------------------------------------------------------------------------------
"""
    fill_df['TradeType'] = fill_df['Quantity'].apply(lambda x: 'BUY' if x > 0 else 'SELL')
    trade_type_stats = fill_df.groupby('TradeType').agg({
        'Quantity': ['count', 'sum'],
        'ExecutionCost': 'sum'
    })
    trade_type_stats.columns = ['Count', 'NetQuantity', 'TotalCost']
    trade_type_stats['TotalVolume'] = fill_df.groupby('TradeType')['Quantity'].apply(lambda x: x.abs().sum())
    
    for trade_type in trade_type_stats.index:
        row = trade_type_stats.loc[trade_type]
        report += f"{trade_type:10s} - Count: {row['Count']:5.0f}, Volume: {row['TotalVolume']:10.0f}, Cost: ${row['TotalCost']:8.2f}\n"
    
    report += f"""
--------------------------------------------------------------------------------
SLIPPAGE ANALYSIS
--------------------------------------------------------------------------------
Average Slippage:           ${order_df['Slippage'].mean():.4f}
Average Slippage %:         {order_df['Slippage_Pct'].mean():.4f}%
Median Slippage:            ${order_df['Slippage'].median():.4f}
Max Positive Slippage:     ${order_df['Slippage'].max():.4f}
Max Negative Slippage:      ${order_df['Slippage'].min():.4f}

================================================================================
END OF REPORT
================================================================================
"""
    
    # Save report to file
    report_file = f'{output_prefix}_report.txt'
    with open(report_file, 'w') as f:
        f.write(report)
    
    print(report)
    print(f"✓ Saved report: {report_file}")

def analyze_single_file_set(file_set):
    """Analyze a single file set"""
    base_name = file_set['base_name']
    output_prefix = base_name.replace('BACK_', '').replace('_start_', '_').replace('_end_', '_')
    
    print("\n" + "="*80)
    print(f"ANALYZING FILE SET: {base_name}")
    print("="*80)
    
    # Load data
    pnl_df, fill_df, order_df = load_data(
        file_set['pnl_file'], 
        file_set['fill_file'], 
        file_set['order_file'],
        base_name
    )
    
    # Perform analyses
    pnl_df = analyze_pnl(pnl_df)
    fill_df = analyze_fills(fill_df)
    order_df = analyze_orders(order_df)
    
    # Calculate metrics
    metrics = calculate_performance_metrics(pnl_df, fill_df, order_df)
    
    # Create visualizations
    create_visualizations(pnl_df, fill_df, order_df, output_prefix)
    
    # Generate report
    generate_summary_report(pnl_df, fill_df, order_df, metrics, output_prefix)
    
    return {
        'base_name': base_name,
        'output_prefix': output_prefix,
        'metrics': metrics
    }

def main():
    """Main analysis function - handles multiple file sets automatically"""
    print("\n" + "="*80)
    print("TRADING DATA ANALYSIS - MULTI-FILE SET MODE")
    print("="*80)
    
    # Find all file sets
    file_sets = find_file_sets()
    
    if len(file_sets) == 0:
        print("\n❌ No file sets found!")
        print("Expected files: *_pnl.csv, *_fill.csv, *_order.csv")
        print("\nExample:")
        print("  - BACK_Strategy1_2025-01-01_pnl.csv")
        print("  - BACK_Strategy1_2025-01-01_fill.csv")
        print("  - BACK_Strategy1_2025-01-01_order.csv")
        sys.exit(1)
    
    print(f"\nFound {len(file_sets)} file set(s) to analyze:")
    for i, fs in enumerate(file_sets, 1):
        print(f"  {i}. {fs['base_name']}")
    
    # Analyze each file set
    results = []
    for file_set in file_sets:
        try:
            result = analyze_single_file_set(file_set)
            results.append(result)
        except Exception as e:
            print(f"\n❌ Error analyzing {file_set['base_name']}: {str(e)}")
            import traceback
            traceback.print_exc()
            continue
    
    # Summary
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE!")
    print("="*80)
    print(f"\nSuccessfully analyzed {len(results)} file set(s):\n")
    
    for result in results:
        print(f"  📊 {result['base_name']}")
        print(f"     Generated files:")
        print(f"       - {result['output_prefix']}_dashboard.png")
        print(f"       - {result['output_prefix']}_detailed.png")
        print(f"       - {result['output_prefix']}_timeseries.png")
        print(f"       - {result['output_prefix']}_risk.png")
        print(f"       - {result['output_prefix']}_report.txt")
        print(f"     Final PnL: ${result['metrics']['total_return']:,.2f}")
        print()

if __name__ == "__main__":
    main()

