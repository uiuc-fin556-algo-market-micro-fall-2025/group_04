"""
Enhanced Comprehensive High Frequency Trading Backtest Analysis
Analyzes fill.csv, order.csv, and pnl.csv files with P&L and risk metrics
Generates detailed HTML report
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import warnings
import sys
import io
from datetime import datetime
import json
warnings.filterwarnings('ignore')

# Fix Windows console encoding issues
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Set style for better visualizations
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 8)

class EnhancedHFTBacktestAnalyzer:
    def __init__(self, csv_files):
        """
        Initialize analyzer with list of CSV file paths
        
        Args:
            csv_files: List of CSV file paths to analyze
        """
        self.csv_files = csv_files
        self.fill_df = None
        self.order_df = None
        self.pnl_df = None
        self.results = {}
        self.load_data()
        
    def load_data(self):
        """Load all CSV files based on their type"""
        print("Loading CSV files...")
        
        for file_path in self.csv_files:
            filename = Path(file_path).name.lower()
            try:
                if 'fill' in filename:
                    df = pd.read_csv(file_path)
                    df['TradeTime'] = pd.to_datetime(df['TradeTime'])
                    self.fill_df = df
                    print(f"  [OK] Loaded FILL data: {filename} - {len(df)} trades")
                elif 'order' in filename:
                    df = pd.read_csv(file_path)
                    df['EntryTime'] = pd.to_datetime(df['EntryTime'])
                    df['LastModTime'] = pd.to_datetime(df['LastModTime'])
                    self.order_df = df
                    print(f"  [OK] Loaded ORDER data: {filename} - {len(df)} orders")
                elif 'pnl' in filename:
                    df = pd.read_csv(file_path)
                    # Handle mixed date formats in PNL file
                    df['Time'] = pd.to_datetime(df['Time'], format='mixed', errors='coerce')
                    df = df.dropna(subset=['Time'])  # Remove rows with invalid dates
                    self.pnl_df = df
                    print(f"  [OK] Loaded PNL data: {filename} - {len(df)} P&L records")
            except Exception as e:
                print(f"  [ERROR] Error loading {file_path}: {e}")
        
        if self.fill_df is None:
            raise ValueError("No fill data loaded successfully")
    
    def calculate_trade_pnl(self):
        """Calculate P&L from fill data by tracking positions"""
        if self.fill_df is None:
            return None
        
        df = self.fill_df.copy()
        df = df.sort_values('TradeTime')
        
        # Track positions per symbol
        positions = {}  # {symbol: quantity}
        pnl_records = []
        
        for idx, row in df.iterrows():
            symbol = row['Symbol']
            quantity = row['Quantity']
            price = row['Price']
            cost = row['ExecutionCost']
            time = row['TradeTime']
            
            # Initialize position if not exists
            if symbol not in positions:
                positions[symbol] = {'qty': 0, 'avg_price': 0, 'total_cost': 0}
            
            pos = positions[symbol]
            
            # Calculate realized P&L for sells
            if quantity < 0:  # Sell
                sell_qty = abs(quantity)
                if pos['qty'] > 0:  # We have a position to close
                    # Calculate P&L based on average buy price
                    realized_pnl = (price - pos['avg_price']) * min(sell_qty, pos['qty']) - cost
                    pnl_records.append({
                        'Time': time,
                        'Symbol': symbol,
                        'Type': 'REALIZED',
                        'PnL': realized_pnl,
                        'Quantity': -min(sell_qty, pos['qty']),
                        'Price': price
                    })
                    # Update position
                    pos['qty'] -= min(sell_qty, pos['qty'])
                    if pos['qty'] == 0:
                        pos['avg_price'] = 0
                        pos['total_cost'] = 0
                else:
                    # Short sale - track as negative position
                    pos['qty'] -= sell_qty
                    pos['avg_price'] = price
                    pos['total_cost'] += cost
            
            elif quantity > 0:  # Buy
                # Update average price
                if pos['qty'] <= 0:  # New position or covering short
                    pos['qty'] = quantity
                    pos['avg_price'] = price
                    pos['total_cost'] = cost
                else:  # Adding to position
                    total_value = pos['qty'] * pos['avg_price'] + quantity * price
                    pos['qty'] += quantity
                    pos['avg_price'] = total_value / pos['qty']
                    pos['total_cost'] += cost
        
        # Calculate unrealized P&L for remaining positions
        if self.pnl_df is not None and len(self.pnl_df) > 0:
            final_time = self.pnl_df['Time'].max()
            final_pnl = self.pnl_df['Cumulative PnL'].iloc[-1]
        else:
            final_time = df['TradeTime'].max()
            final_pnl = 0
        
        pnl_df = pd.DataFrame(pnl_records) if pnl_records else pd.DataFrame()
        return pnl_df, positions, final_pnl
    
    def calculate_risk_metrics(self):
        """Calculate risk metrics including Sharpe ratio, max drawdown, etc."""
        if self.pnl_df is None or len(self.pnl_df) == 0:
            return {}, pd.DataFrame()
        
        df = self.pnl_df.copy()
        df = df.sort_values('Time')
        
        # Calculate returns
        df['PnL_Change'] = df['Cumulative PnL'].diff()
        df['Returns'] = df['PnL_Change'] / abs(df['Cumulative PnL'].shift(1)).replace(0, np.nan)
        df['Returns'] = df['Returns'].fillna(0)
        
        # Calculate running maximum
        df['RunningMax'] = df['Cumulative PnL'].expanding().max()
        df['Drawdown'] = df['Cumulative PnL'] - df['RunningMax']
        df['DrawdownPct'] = (df['Drawdown'] / df['RunningMax'].replace(0, np.nan)) * 100
        
        # Risk metrics
        total_pnl = df['Cumulative PnL'].iloc[-1]
        final_pnl = df['Cumulative PnL'].iloc[-1]
        initial_pnl = df['Cumulative PnL'].iloc[0] if len(df) > 0 else 0
        
        # Calculate time differences for annualization
        time_diff = (df['Time'].iloc[-1] - df['Time'].iloc[0]).total_seconds() / 86400  # days
        annualization_factor = 252 / time_diff if time_diff > 0 else 1
        
        # Returns statistics
        returns = df['Returns'].dropna()
        if len(returns) > 0:
            mean_return = returns.mean()
            std_return = returns.std()
            sharpe_ratio = (mean_return / std_return * np.sqrt(252)) if std_return > 0 else 0
        else:
            mean_return = 0
            std_return = 0
            sharpe_ratio = 0
        
        # Drawdown metrics
        max_drawdown = df['Drawdown'].min()
        max_drawdown_pct = df['DrawdownPct'].min()
        avg_drawdown = df[df['Drawdown'] < 0]['Drawdown'].mean() if len(df[df['Drawdown'] < 0]) > 0 else 0
        
        # Volatility
        volatility = std_return * np.sqrt(252) if std_return > 0 else 0
        
        # Win rate (from P&L changes)
        winning_periods = len(df[df['PnL_Change'] > 0])
        losing_periods = len(df[df['PnL_Change'] < 0])
        total_periods = winning_periods + losing_periods
        win_rate = (winning_periods / total_periods * 100) if total_periods > 0 else 0
        
        # Profit factor
        total_profit = df[df['PnL_Change'] > 0]['PnL_Change'].sum()
        total_loss = abs(df[df['PnL_Change'] < 0]['PnL_Change'].sum())
        profit_factor = total_profit / total_loss if total_loss > 0 else 0
        
        metrics = {
            'Total_PnL': total_pnl,
            'Final_PnL': final_pnl,
            'Initial_PnL': initial_pnl,
            'Net_PnL': final_pnl - initial_pnl,
            'Max_Drawdown': max_drawdown,
            'Max_Drawdown_Pct': max_drawdown_pct,
            'Avg_Drawdown': avg_drawdown,
            'Sharpe_Ratio': sharpe_ratio,
            'Volatility': volatility,
            'Mean_Return': mean_return,
            'Std_Return': std_return,
            'Win_Rate': win_rate,
            'Profit_Factor': profit_factor,
            'Winning_Periods': winning_periods,
            'Losing_Periods': losing_periods,
            'Total_Periods': total_periods
        }
        
        return metrics, df
    
    def analyze_fill_data(self):
        """Analyze fill data"""
        if self.fill_df is None:
            return {}
        
        df = self.fill_df.copy()
        df['TradeValue'] = abs(df['Quantity'] * df['Price'])
        df['AbsQuantity'] = abs(df['Quantity'])
        df['Direction'] = df['Quantity'].apply(lambda x: 'BUY' if x > 0 else 'SELL')
        
        results = {
            'total_trades': len(df),
            'date_range': (df['TradeTime'].min(), df['TradeTime'].max()),
            'duration': df['TradeTime'].max() - df['TradeTime'].min(),
            'buy_orders': len(df[df['Quantity'] > 0]),
            'sell_orders': len(df[df['Quantity'] < 0]),
            'symbols': df['Symbol'].unique().tolist(),
            'symbol_counts': df['Symbol'].value_counts().to_dict(),
            'total_execution_cost': df['ExecutionCost'].sum(),
            'avg_execution_cost': df['ExecutionCost'].mean(),
            'total_trade_value': df['TradeValue'].sum(),
            'avg_trade_value': df['TradeValue'].mean(),
            'cost_by_symbol': df.groupby('Symbol')['ExecutionCost'].sum().to_dict(),
            'cost_by_direction': df.groupby('Direction')['ExecutionCost'].sum().to_dict(),
            'quantity_stats': {
                'mean': df['AbsQuantity'].mean(),
                'median': df['AbsQuantity'].median(),
                'max': df['AbsQuantity'].max(),
                'min': df['AbsQuantity'].min(),
                'std': df['AbsQuantity'].std()
            },
            'price_stats': {
                'mean': df['Price'].mean(),
                'median': df['Price'].median(),
                'max': df['Price'].max(),
                'min': df['Price'].min(),
                'std': df['Price'].std()
            }
        }
        
        return results
    
    def analyze_order_data(self):
        """Analyze order data"""
        if self.order_df is None:
            return {}
        
        df = self.order_df.copy()
        
        results = {
            'total_orders': len(df),
            'filled_orders': len(df[df['State'] == 'FILLED']),
            'order_states': df['State'].value_counts().to_dict(),
            'order_types': df['Type'].value_counts().to_dict(),
            'sides': df['Side'].value_counts().to_dict(),
            'avg_fill_price': df['AvgFillPrice'].mean(),
            'total_filled_qty': df['FilledQty'].sum(),
            'orders_by_symbol': df['Symbol'].value_counts().to_dict(),
            'execution_time_stats': {
                'mean': (df['LastModTime'] - df['EntryTime']).mean().total_seconds(),
                'median': (df['LastModTime'] - df['EntryTime']).median().total_seconds(),
                'max': (df['LastModTime'] - df['EntryTime']).max().total_seconds()
            }
        }
        
        return results
    
    def analyze_pnl_data(self):
        """Analyze P&L data"""
        if self.pnl_df is None:
            return {}
        
        df = self.pnl_df.copy()
        df = df.sort_values('Time')
        
        results = {
            'total_records': len(df),
            'initial_pnl': df['Cumulative PnL'].iloc[0],
            'final_pnl': df['Cumulative PnL'].iloc[-1],
            'net_pnl': df['Cumulative PnL'].iloc[-1] - df['Cumulative PnL'].iloc[0],
            'max_pnl': df['Cumulative PnL'].max(),
            'min_pnl': df['Cumulative PnL'].min(),
            'pnl_range': df['Cumulative PnL'].max() - df['Cumulative PnL'].min(),
            'pnl_changes': df['Cumulative PnL'].diff().dropna().tolist(),
            'date_range': (df['Time'].min(), df['Time'].max())
        }
        
        return results
    
    def create_enhanced_visualizations(self):
        """Create comprehensive visualizations"""
        print("\n[VIZ] Generating enhanced visualizations...")
        
        # Prepare fill data if available
        if self.fill_df is not None:
            fill_df_viz = self.fill_df.copy()
            if 'Direction' not in fill_df_viz.columns:
                fill_df_viz['Direction'] = fill_df_viz['Quantity'].apply(lambda x: 'BUY' if x > 0 else 'SELL')
        else:
            fill_df_viz = None
        
        fig = plt.figure(figsize=(24, 20))
        
        # 1. P&L Over Time
        if self.pnl_df is not None and len(self.pnl_df) > 0:
            ax1 = plt.subplot(4, 4, 1)
            pnl_sorted = self.pnl_df.sort_values('Time')
            ax1.plot(pnl_sorted['Time'], pnl_sorted['Cumulative PnL'], linewidth=2, color='blue')
            ax1.axhline(y=0, color='r', linestyle='--', alpha=0.5)
            ax1.set_title('Cumulative P&L Over Time', fontsize=12, fontweight='bold')
            ax1.set_xlabel('Time')
            ax1.set_ylabel('Cumulative P&L ($)')
            ax1.grid(True, alpha=0.3)
            ax1.tick_params(axis='x', rotation=45)
        
        # 2. Drawdown Chart
        if self.pnl_df is not None and len(self.pnl_df) > 0:
            ax2 = plt.subplot(4, 4, 2)
            pnl_sorted = self.pnl_df.sort_values('Time')
            running_max = pnl_sorted['Cumulative PnL'].expanding().max()
            drawdown = pnl_sorted['Cumulative PnL'] - running_max
            ax2.fill_between(pnl_sorted['Time'], drawdown, 0, color='red', alpha=0.3)
            ax2.plot(pnl_sorted['Time'], drawdown, linewidth=2, color='darkred')
            ax2.set_title('Drawdown Over Time', fontsize=12, fontweight='bold')
            ax2.set_xlabel('Time')
            ax2.set_ylabel('Drawdown ($)')
            ax2.grid(True, alpha=0.3)
            ax2.tick_params(axis='x', rotation=45)
        
        # 3. P&L Distribution
        if self.pnl_df is not None and len(self.pnl_df) > 0:
            ax3 = plt.subplot(4, 4, 3)
            pnl_changes = self.pnl_df['Cumulative PnL'].diff().dropna()
            ax3.hist(pnl_changes, bins=50, edgecolor='black', color='green', alpha=0.7)
            ax3.axvline(x=0, color='r', linestyle='--', linewidth=2)
            ax3.set_title('P&L Change Distribution', fontsize=12, fontweight='bold')
            ax3.set_xlabel('P&L Change ($)')
            ax3.set_ylabel('Frequency')
            ax3.grid(True, alpha=0.3)
        
        # 4. Trades by Symbol (Fill Data)
        if fill_df_viz is not None:
            ax4 = plt.subplot(4, 4, 4)
            symbol_counts = fill_df_viz['Symbol'].value_counts()
            symbol_counts.plot(kind='bar', ax=ax4, color='steelblue', edgecolor='black')
            ax4.set_title('Trades by Symbol', fontsize=12, fontweight='bold')
            ax4.set_xlabel('Symbol')
            ax4.set_ylabel('Number of Trades')
            ax4.tick_params(axis='x', rotation=45)
        
        # 5. Execution Cost Over Time
        if fill_df_viz is not None:
            ax5 = plt.subplot(4, 4, 5)
            fill_sorted = fill_df_viz.sort_values('TradeTime')
            fill_sorted['CumulativeCost'] = fill_sorted['ExecutionCost'].cumsum()
            ax5.plot(fill_sorted['TradeTime'], fill_sorted['CumulativeCost'], linewidth=2, color='orange')
            ax5.set_title('Cumulative Execution Cost', fontsize=12, fontweight='bold')
            ax5.set_xlabel('Time')
            ax5.set_ylabel('Cumulative Cost ($)')
            ax5.grid(True, alpha=0.3)
            ax5.tick_params(axis='x', rotation=45)
        
        # 6. Order States Distribution
        if self.order_df is not None:
            ax6 = plt.subplot(4, 4, 6)
            state_counts = self.order_df['State'].value_counts()
            state_counts.plot(kind='pie', ax=ax6, autopct='%1.1f%%', startangle=90)
            ax6.set_title('Order States Distribution', fontsize=12, fontweight='bold')
            ax6.set_ylabel('')
        
        # 7. Trading Activity by Hour
        if fill_df_viz is not None:
            ax7 = plt.subplot(4, 4, 7)
            fill_df_viz['Hour'] = fill_df_viz['TradeTime'].dt.hour
            hourly = fill_df_viz.groupby('Hour').size()
            hourly.plot(kind='bar', ax=ax7, color='purple', edgecolor='black')
            ax7.set_title('Trading Activity by Hour', fontsize=12, fontweight='bold')
            ax7.set_xlabel('Hour of Day')
            ax7.set_ylabel('Number of Trades')
            ax7.tick_params(axis='x', rotation=0)
        
        # 8. Price Distribution by Symbol
        if fill_df_viz is not None:
            ax8 = plt.subplot(4, 4, 8)
            for symbol in fill_df_viz['Symbol'].unique():
                symbol_data = fill_df_viz[fill_df_viz['Symbol'] == symbol]['Price']
                ax8.hist(symbol_data, alpha=0.6, label=symbol, bins=30)
            ax8.set_title('Price Distribution by Symbol', fontsize=12, fontweight='bold')
            ax8.set_xlabel('Price ($)')
            ax8.set_ylabel('Frequency')
            ax8.legend()
        
        # 9. Execution Cost by Symbol
        if fill_df_viz is not None:
            ax9 = plt.subplot(4, 4, 9)
            cost_by_symbol = fill_df_viz.groupby('Symbol')['ExecutionCost'].sum()
            cost_by_symbol.plot(kind='bar', ax=ax9, color='coral', edgecolor='black')
            ax9.set_title('Total Execution Cost by Symbol', fontsize=12, fontweight='bold')
            ax9.set_xlabel('Symbol')
            ax9.set_ylabel('Total Cost ($)')
            ax9.tick_params(axis='x', rotation=45)
        
        # 10. Buy vs Sell Distribution
        if fill_df_viz is not None:
            ax10 = plt.subplot(4, 4, 10)
            direction_counts = fill_df_viz['Direction'].value_counts()
            direction_counts.plot(kind='pie', ax=ax10, autopct='%1.1f%%', startangle=90)
            ax10.set_title('Buy vs Sell Distribution', fontsize=12, fontweight='bold')
            ax10.set_ylabel('')
        
        # 11. Trade Value Distribution
        if fill_df_viz is not None:
            ax11 = plt.subplot(4, 4, 11)
            trade_values = abs(fill_df_viz['Quantity'] * fill_df_viz['Price'])
            ax11.hist(trade_values, bins=50, edgecolor='black', color='lightgreen')
            ax11.set_title('Trade Value Distribution', fontsize=12, fontweight='bold')
            ax11.set_xlabel('Trade Value ($)')
            ax11.set_ylabel('Frequency')
        
        # 12. Order Execution Time Distribution
        if self.order_df is not None:
            ax12 = plt.subplot(4, 4, 12)
            exec_times = (self.order_df['LastModTime'] - self.order_df['EntryTime']).dt.total_seconds()
            ax12.hist(exec_times, bins=50, edgecolor='black', color='teal')
            ax12.set_title('Order Execution Time Distribution', fontsize=12, fontweight='bold')
            ax12.set_xlabel('Execution Time (seconds)')
            ax12.set_ylabel('Frequency')
        
        # 13. P&L Returns Distribution
        if self.pnl_df is not None and len(self.pnl_df) > 0:
            ax13 = plt.subplot(4, 4, 13)
            pnl_sorted = self.pnl_df.sort_values('Time')
            returns = pnl_sorted['Cumulative PnL'].pct_change().dropna() * 100
            ax13.hist(returns, bins=50, edgecolor='black', color='gold', alpha=0.7)
            ax13.axvline(x=0, color='r', linestyle='--', linewidth=2)
            ax13.set_title('P&L Returns Distribution', fontsize=12, fontweight='bold')
            ax13.set_xlabel('Return (%)')
            ax13.set_ylabel('Frequency')
        
        # 14. Rolling Sharpe Ratio
        if self.pnl_df is not None and len(self.pnl_df) > 0:
            ax14 = plt.subplot(4, 4, 14)
            pnl_sorted = self.pnl_df.sort_values('Time')
            returns = pnl_sorted['Cumulative PnL'].pct_change().dropna()
            window = min(20, len(returns))
            if window > 1 and len(returns) > window:
                rolling_sharpe = returns.rolling(window=window).mean() / returns.rolling(window=window).std() * np.sqrt(252)
                rolling_sharpe = rolling_sharpe.dropna()
                # Align time with rolling_sharpe (skip first window rows + 1 for pct_change)
                time_aligned = pnl_sorted['Time'].iloc[window+1:window+1+len(rolling_sharpe)]
                if len(time_aligned) == len(rolling_sharpe):
                    ax14.plot(time_aligned, rolling_sharpe, linewidth=2, color='purple')
                    ax14.axhline(y=0, color='r', linestyle='--', alpha=0.5)
                    ax14.set_title(f'Rolling Sharpe Ratio (window={window})', fontsize=12, fontweight='bold')
                    ax14.set_xlabel('Time')
                    ax14.set_ylabel('Sharpe Ratio')
                    ax14.grid(True, alpha=0.3)
                    ax14.tick_params(axis='x', rotation=45)
        
        # 15. Order Type Distribution
        if self.order_df is not None:
            ax15 = plt.subplot(4, 4, 15)
            type_counts = self.order_df['Type'].value_counts()
            type_counts.plot(kind='bar', ax=ax15, color='indigo', edgecolor='black')
            ax15.set_title('Order Type Distribution', fontsize=12, fontweight='bold')
            ax15.set_xlabel('Order Type')
            ax15.set_ylabel('Count')
            ax15.tick_params(axis='x', rotation=45)
        
        # 16. Cumulative Trades
        if fill_df_viz is not None:
            ax16 = plt.subplot(4, 4, 16)
            fill_sorted = fill_df_viz.sort_values('TradeTime')
            fill_sorted['CumulativeTrades'] = range(1, len(fill_sorted) + 1)
            ax16.plot(fill_sorted['TradeTime'], fill_sorted['CumulativeTrades'], linewidth=2, color='darkblue')
            ax16.set_title('Cumulative Trades Over Time', fontsize=12, fontweight='bold')
            ax16.set_xlabel('Time')
            ax16.set_ylabel('Cumulative Number of Trades')
            ax16.grid(True, alpha=0.3)
            ax16.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        output_path = Path(self.csv_files[0]).parent / 'hft_backtest_analysis_enhanced.png'
        plt.savefig(output_path, dpi=300, bbox_inches='tight')
        print(f"[SUCCESS] Enhanced visualizations saved to '{output_path}'")
        plt.close()
    
    def generate_html_report(self):
        """Generate a comprehensive HTML report"""
        print("\n[REPORT] Generating HTML report...")
        
        # Run all analyses
        fill_results = self.analyze_fill_data()
        order_results = self.analyze_order_data()
        pnl_results = self.analyze_pnl_data()
        risk_metrics, pnl_df_enhanced = self.calculate_risk_metrics()
        trade_pnl, positions, final_pnl = self.calculate_trade_pnl()
        
        # Handle case when risk metrics are empty
        if not risk_metrics:
            risk_metrics = {
                'Final_PnL': pnl_results.get('final_pnl', 0) if pnl_results else 0,
                'Net_PnL': pnl_results.get('net_pnl', 0) if pnl_results else 0,
                'Sharpe_Ratio': 0,
                'Max_Drawdown': 0,
                'Max_Drawdown_Pct': 0,
                'Avg_Drawdown': 0,
                'Volatility': 0,
                'Win_Rate': 0,
                'Profit_Factor': 0,
                'Winning_Periods': 0,
                'Losing_Periods': 0
            }
        
        # Create HTML content
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>HFT Backtest Analysis Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            box-shadow: 0 0 10px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            border-left: 4px solid #3498db;
            padding-left: 10px;
        }}
        h3 {{
            color: #7f8c8d;
            margin-top: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #3498db;
            color: white;
            font-weight: bold;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .metric-box {{
            display: inline-block;
            margin: 10px;
            padding: 15px;
            background-color: #ecf0f1;
            border-left: 4px solid #3498db;
            min-width: 200px;
        }}
        .metric-value {{
            font-size: 24px;
            font-weight: bold;
            color: #2c3e50;
        }}
        .metric-label {{
            font-size: 12px;
            color: #7f8c8d;
            text-transform: uppercase;
        }}
        .positive {{
            color: #27ae60;
        }}
        .negative {{
            color: #e74c3c;
        }}
        .section {{
            margin: 30px 0;
            padding: 20px;
            background-color: #fafafa;
            border-radius: 5px;
        }}
        .timestamp {{
            color: #95a5a6;
            font-size: 12px;
            text-align: right;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>High Frequency Trading Backtest Analysis Report</h1>
        <p class="timestamp">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <div class="section">
            <h2>Executive Summary</h2>
            <div class="metric-box">
                <div class="metric-label">Final P&L</div>
                <div class="metric-value {'positive' if risk_metrics.get('Final_PnL', 0) >= 0 else 'negative'}">
                    ${risk_metrics.get('Final_PnL', 0):,.2f}
                </div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Total Trades</div>
                <div class="metric-value">{fill_results.get('total_trades', 0):,}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Sharpe Ratio</div>
                <div class="metric-value">{risk_metrics.get('Sharpe_Ratio', 0):.2f}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Max Drawdown</div>
                <div class="metric-value negative">${risk_metrics.get('Max_Drawdown', 0):,.2f}</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Win Rate</div>
                <div class="metric-value">{risk_metrics.get('Win_Rate', 0):.2f}%</div>
            </div>
            <div class="metric-box">
                <div class="metric-label">Profit Factor</div>
                <div class="metric-value">{risk_metrics.get('Profit_Factor', 0):.2f}</div>
            </div>
        </div>
        
        <div class="section">
            <h2>Fill Data Analysis</h2>
            <h3>Overview</h3>
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Total Trades</td><td>{fill_results.get('total_trades', 0):,}</td></tr>
                <tr><td>Date Range</td><td>{fill_results.get('date_range', (None, None))[0]} to {fill_results.get('date_range', (None, None))[1]}</td></tr>
                <tr><td>Trading Duration</td><td>{fill_results.get('duration', pd.Timedelta(0))}</td></tr>
                <tr><td>Buy Orders</td><td>{fill_results.get('buy_orders', 0):,}</td></tr>
                <tr><td>Sell Orders</td><td>{fill_results.get('sell_orders', 0):,}</td></tr>
            </table>
            
            <h3>Symbol Breakdown</h3>
            <table>
                <tr><th>Symbol</th><th>Trade Count</th></tr>
"""
        
        for symbol, count in fill_results.get('symbol_counts', {}).items():
            html_content += f"<tr><td>{symbol}</td><td>{count:,}</td></tr>"
        
        html_content += f"""
            </table>
            
            <h3>Execution Costs</h3>
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Total Execution Cost</td><td>${fill_results.get('total_execution_cost', 0):,.4f}</td></tr>
                <tr><td>Average Cost per Trade</td><td>${fill_results.get('avg_execution_cost', 0):.6f}</td></tr>
            </table>
            
            <h3>Cost by Symbol</h3>
            <table>
                <tr><th>Symbol</th><th>Total Cost</th></tr>
"""
        
        for symbol, cost in fill_results.get('cost_by_symbol', {}).items():
            html_content += f"<tr><td>{symbol}</td><td>${cost:,.4f}</td></tr>"
        
        html_content += f"""
            </table>
        </div>
        
        <div class="section">
            <h2>Order Data Analysis</h2>
"""
        
        if order_results:
            html_content += f"""
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Total Orders</td><td>{order_results.get('total_orders', 0):,}</td></tr>
                <tr><td>Filled Orders</td><td>{order_results.get('filled_orders', 0):,}</td></tr>
                <tr><td>Average Fill Price</td><td>${order_results.get('avg_fill_price', 0):.2f}</td></tr>
                <tr><td>Total Filled Quantity</td><td>{order_results.get('total_filled_qty', 0):,}</td></tr>
            </table>
            
            <h3>Order States</h3>
            <table>
                <tr><th>State</th><th>Count</th></tr>
"""
            for state, count in order_results.get('order_states', {}).items():
                html_content += f"<tr><td>{state}</td><td>{count:,}</td></tr>"
            
            html_content += """
            </table>
            """
        else:
            html_content += "<p>No order data available.</p>"
        
        html_content += f"""
        </div>
        
        <div class="section">
            <h2>P&L Analysis</h2>
"""
        
        if pnl_results:
            html_content += f"""
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Initial P&L</td><td>${pnl_results.get('initial_pnl', 0):,.2f}</td></tr>
                <tr><td>Final P&L</td><td>${pnl_results.get('final_pnl', 0):,.2f}</td></tr>
                <tr><td>Net P&L</td><td class="{'positive' if pnl_results.get('net_pnl', 0) >= 0 else 'negative'}">${pnl_results.get('net_pnl', 0):,.2f}</td></tr>
                <tr><td>Maximum P&L</td><td>${pnl_results.get('max_pnl', 0):,.2f}</td></tr>
                <tr><td>Minimum P&L</td><td>${pnl_results.get('min_pnl', 0):,.2f}</td></tr>
                <tr><td>P&L Range</td><td>${pnl_results.get('pnl_range', 0):,.2f}</td></tr>
            </table>
            """
        else:
            html_content += "<p>No P&L data available.</p>"
        
        html_content += f"""
        </div>
        
        <div class="section">
            <h2>Risk Metrics</h2>
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Sharpe Ratio</td><td>{risk_metrics.get('Sharpe_Ratio', 0):.4f}</td></tr>
                <tr><td>Maximum Drawdown</td><td class="negative">${risk_metrics.get('Max_Drawdown', 0):,.2f}</td></tr>
                <tr><td>Maximum Drawdown %</td><td class="negative">{risk_metrics.get('Max_Drawdown_Pct', 0):.2f}%</td></tr>
                <tr><td>Average Drawdown</td><td class="negative">${risk_metrics.get('Avg_Drawdown', 0):,.2f}</td></tr>
                <tr><td>Volatility (Annualized)</td><td>{risk_metrics.get('Volatility', 0):.4f}</td></tr>
                <tr><td>Win Rate</td><td>{risk_metrics.get('Win_Rate', 0):.2f}%</td></tr>
                <tr><td>Profit Factor</td><td>{risk_metrics.get('Profit_Factor', 0):.4f}</td></tr>
                <tr><td>Winning Periods</td><td>{risk_metrics.get('Winning_Periods', 0):,}</td></tr>
                <tr><td>Losing Periods</td><td>{risk_metrics.get('Losing_Periods', 0):,}</td></tr>
            </table>
        </div>
        
        <div class="section">
            <h2>Trade Statistics</h2>
            <h3>Quantity Statistics</h3>
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Mean</td><td>{fill_results.get('quantity_stats', {}).get('mean', 0):.2f}</td></tr>
                <tr><td>Median</td><td>{fill_results.get('quantity_stats', {}).get('median', 0):.2f}</td></tr>
                <tr><td>Max</td><td>{fill_results.get('quantity_stats', {}).get('max', 0):.0f}</td></tr>
                <tr><td>Min</td><td>{fill_results.get('quantity_stats', {}).get('min', 0):.0f}</td></tr>
                <tr><td>Std Dev</td><td>{fill_results.get('quantity_stats', {}).get('std', 0):.2f}</td></tr>
            </table>
            
            <h3>Price Statistics</h3>
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Mean</td><td>${fill_results.get('price_stats', {}).get('mean', 0):.2f}</td></tr>
                <tr><td>Median</td><td>${fill_results.get('price_stats', {}).get('median', 0):.2f}</td></tr>
                <tr><td>Max</td><td>${fill_results.get('price_stats', {}).get('max', 0):.2f}</td></tr>
                <tr><td>Min</td><td>${fill_results.get('price_stats', {}).get('min', 0):.2f}</td></tr>
                <tr><td>Std Dev</td><td>${fill_results.get('price_stats', {}).get('std', 0):.2f}</td></tr>
            </table>
        </div>
        
        <div class="section">
            <h2>Visualizations</h2>
            <p>Comprehensive visualizations have been saved to: <strong>hft_backtest_analysis_enhanced.png</strong></p>
            <p>The visualization file contains 16 charts covering:</p>
            <ul>
                <li>P&L over time and drawdown analysis</li>
                <li>Trade distributions and patterns</li>
                <li>Execution costs and order analysis</li>
                <li>Risk metrics and performance indicators</li>
            </ul>
        </div>
        
    </div>
</body>
</html>
"""
        
        # Save HTML report
        output_path = Path(self.csv_files[0]).parent / 'hft_backtest_report.html'
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"[SUCCESS] HTML report saved to '{output_path}'")
        return output_path
    
    def generate_summary_report(self):
        """Generate comprehensive summary report"""
        print("\n" + "="*80)
        print("GENERATING ENHANCED SUMMARY REPORT")
        print("="*80)
        
        # Run all analyses
        fill_results = self.analyze_fill_data()
        order_results = self.analyze_order_data()
        pnl_results = self.analyze_pnl_data()
        risk_metrics, pnl_df_enhanced = self.calculate_risk_metrics()
        
        # Handle case when risk metrics are empty
        if not risk_metrics:
            risk_metrics = {
                'Final_PnL': pnl_results.get('final_pnl', 0) if pnl_results else 0,
                'Net_PnL': pnl_results.get('net_pnl', 0) if pnl_results else 0,
                'Sharpe_Ratio': 0,
                'Max_Drawdown': 0,
                'Max_Drawdown_Pct': 0,
                'Avg_Drawdown': 0,
                'Volatility': 0,
                'Win_Rate': 0,
                'Profit_Factor': 0,
                'Winning_Periods': 0,
                'Losing_Periods': 0
            }
        
        # Print summary
        print("\n" + "="*80)
        print("EXECUTIVE SUMMARY")
        print("="*80)
        print(f"\nFinal P&L: ${risk_metrics.get('Final_PnL', 0):,.2f}")
        print(f"Net P&L: ${risk_metrics.get('Net_PnL', 0):,.2f}")
        print(f"Total Trades: {fill_results.get('total_trades', 0):,}")
        print(f"Sharpe Ratio: {risk_metrics.get('Sharpe_Ratio', 0):.4f}")
        print(f"Max Drawdown: ${risk_metrics.get('Max_Drawdown', 0):,.2f} ({risk_metrics.get('Max_Drawdown_Pct', 0):.2f}%)")
        print(f"Win Rate: {risk_metrics.get('Win_Rate', 0):.2f}%")
        print(f"Profit Factor: {risk_metrics.get('Profit_Factor', 0):.4f}")
        
        # Create visualizations
        self.create_enhanced_visualizations()
        
        # Generate HTML report
        self.generate_html_report()
        
        print("\n" + "="*80)
        print("ANALYSIS COMPLETE!")
        print("="*80)
        print("\nOutput files generated:")
        print("  - hft_backtest_analysis_enhanced.png (16 comprehensive charts)")
        print("  - hft_backtest_report.html (Detailed HTML report)")


def main():
    """Main function to run the enhanced analysis"""
    import os
    import glob
    
    # Option 1: Automatically find all CSV files in the current directory
    csv_directory = r'c:\Users\ansh6'
    
    # Find all CSV files in the directory
    csv_pattern = os.path.join(csv_directory, '*.csv')
    csv_files = glob.glob(csv_pattern)
    
    # Filter to only backtest CSV files
    csv_files = [f for f in csv_files if 'BACK' in os.path.basename(f).upper()]
    
    if not csv_files:
        print("="*80)
        print("ERROR: No CSV files found!")
        print("="*80)
        print(f"Looking in: {csv_directory}")
        print("Please ensure CSV files exist in this directory.")
        return
    
    print("="*80)
    print("ENHANCED HIGH FREQUENCY TRADING BACKTEST ANALYSIS")
    print("="*80)
    print(f"\nFound {len(csv_files)} CSV file(s) to analyze:")
    for f in csv_files:
        print(f"  - {os.path.basename(f)}")
    
    try:
        analyzer = EnhancedHFTBacktestAnalyzer(csv_files)
        analyzer.generate_summary_report()
    except Exception as e:
        print(f"\n[ERROR] Error during analysis: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

