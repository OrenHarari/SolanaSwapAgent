#!/usr/bin/env python3
"""
Improved High-Frequency Arbitrage Simulation
Fixes all profitability issues from the original simulation
"""

import pandas as pd
import numpy as np
from datetime import datetime, timezone
from decimal import Decimal, getcontext
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
import time
import random

# Set high precision for financial calculations
getcontext().prec = 28

@dataclass
class ImprovedOpportunity:
    """Represents a profitable arbitrage opportunity"""
    timestamp: datetime
    dex_buy: str
    dex_sell: str
    buy_price: float
    sell_price: float
    spread_pct: float
    expected_profit_pct: float
    volume: float
    is_profitable_after_fees: bool

@dataclass
class ImprovedExecution:
    """Represents an executed trade"""
    opportunity_id: str
    executed_at: datetime
    dex_buy: str
    dex_sell: str
    position_size: Decimal
    buy_price: float
    sell_price: float
    gross_profit: Decimal
    total_fees: Decimal
    net_profit: Decimal
    execution_time_ms: int
    success: bool

class ImprovedArbitrageSimulator:
    """Improved arbitrage simulator with proper profit calculations"""
    
    def __init__(self, symbol: str = "OPUSDT"):
        self.symbol = symbol
        self.mock_balance = Decimal("10.0")  # 10 SOL equivalent
        self.initial_balance = Decimal("10.0")
        self.trades_executed = []
        self.opportunities_found = []
        self.total_profit = Decimal("0")
        
        # Improved trading parameters - more conservative and realistic
        self.min_spread_pct = 0.15  # Minimum 0.15% spread (was 0.05% - too low!)
        self.max_position_size = Decimal("0.5")  # Max 0.5 SOL per trade (was 1.0)
        self.min_position_size = Decimal("0.01")  # Minimum trade size
        
        # Realistic fee structure
        self.dex_configs = {
            "Jupiter": {
                "trading_fee": 0.0001,  # 0.01% (Jupiter aggregator fee)
                "latency_ms": 120,
                "success_rate": 0.98,
                "slippage_factor": 0.0002  # 0.02% average slippage
            },
            "Raydium": {
                "trading_fee": 0.0025,  # 0.25% (standard AMM fee)
                "latency_ms": 180,
                "success_rate": 0.95,
                "slippage_factor": 0.0005  # 0.05% average slippage
            },
            "Phoenix": {
                "trading_fee": 0.0002,  # 0.02% (order book fee)
                "latency_ms": 80,
                "success_rate": 0.93,
                "slippage_factor": 0.0001  # 0.01% (order book has less slippage)
            },
            "Meteora": {
                "trading_fee": 0.0010,  # 0.10%
                "latency_ms": 150,
                "success_rate": 0.94,
                "slippage_factor": 0.0003  # 0.03%
            },
            "Orca": {
                "trading_fee": 0.0030,  # 0.30%
                "latency_ms": 200,
                "success_rate": 0.96,
                "slippage_factor": 0.0006  # 0.06%
            }
        }
        
        # Network costs
        self.network_fee = Decimal("0.000005")  # 5000 lamports per transaction
        self.gas_cost = Decimal("0.00001")  # Additional gas costs
    
    def load_1s_data(self, data_file: str) -> pd.DataFrame:
        """Load 1-second price data with validation"""
        try:
            print(f"📊 Loading 1-second data from: {data_file}")
            df = pd.read_csv(data_file)
            
            # Convert timestamp
            if 'open_time' in df.columns:
                df['timestamp'] = pd.to_datetime(df['open_time'])
            else:
                df['timestamp'] = pd.to_datetime(df.iloc[:, 0])
            
            # Ensure required columns
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in df.columns:
                    print(f"❌ Missing column: {col}")
                    return None
            
            print(f"✅ Loaded {len(df)} 1-second candles")
            print(f"   Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")
            return df
            
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            return None
    
    def calculate_total_fees(self, dex_buy: str, dex_sell: str, position_size: Decimal) -> Decimal:
        """Calculate total fees for a round-trip trade"""
        buy_config = self.dex_configs[dex_buy]
        sell_config = self.dex_configs[dex_sell]
        
        # Trading fees
        buy_fee = position_size * Decimal(str(buy_config["trading_fee"]))
        sell_fee = position_size * Decimal(str(sell_config["trading_fee"]))
        
        # Slippage costs
        buy_slippage = position_size * Decimal(str(buy_config["slippage_factor"]))
        sell_slippage = position_size * Decimal(str(sell_config["slippage_factor"]))
        
        # Network costs (2 transactions)
        network_costs = self.network_fee * 2 + self.gas_cost * 2
        
        total_fees = buy_fee + sell_fee + buy_slippage + sell_slippage + network_costs
        return total_fees
    
    def is_opportunity_profitable(self, buy_price: float, sell_price: float, 
                                 dex_buy: str, dex_sell: str, position_size: Decimal) -> tuple:
        """Check if opportunity is profitable after all costs"""
        
        # Calculate gross profit
        price_diff = Decimal(str(sell_price - buy_price))
        gross_profit = position_size * price_diff / Decimal(str(buy_price))
        
        # Calculate total costs
        total_fees = self.calculate_total_fees(dex_buy, dex_sell, position_size)
        
        # Net profit
        net_profit = gross_profit - total_fees
        
        # Profit percentage
        profit_pct = (net_profit / position_size) * 100
        
        return net_profit > 0, net_profit, profit_pct, total_fees
    
    def simulate_dex_prices(self, base_price: float, volume: float) -> Dict[str, float]:
        """Simulate realistic DEX prices with spreads"""
        prices = {}
        
        # Base volatility based on volume
        volatility = max(0.0001, min(0.002, 1000 / max(volume, 1000)))
        
        for dex_name in self.dex_configs.keys():
            # Each DEX has slightly different pricing
            price_variance = np.random.normal(0, volatility)
            liquidity_impact = np.random.uniform(-0.0005, 0.0005)
            
            dex_price = base_price * (1 + price_variance + liquidity_impact)
            prices[dex_name] = round(dex_price, 8)
        
        return prices
    
    def detect_opportunities(self, timestamp: datetime, base_price: float, volume: float) -> List[ImprovedOpportunity]:
        """Detect profitable arbitrage opportunities"""
        opportunities = []
        
        # Simulate DEX prices
        dex_prices = self.simulate_dex_prices(base_price, volume)
        
        # Check all DEX pairs
        dex_names = list(self.dex_configs.keys())
        
        for i, dex_buy in enumerate(dex_names):
            for j, dex_sell in enumerate(dex_names):
                if i >= j:  # Avoid duplicates
                    continue
                
                buy_price = dex_prices[dex_buy]
                sell_price = dex_prices[dex_sell]
                
                # Only consider if selling price is higher
                if sell_price <= buy_price:
                    continue
                
                # Calculate spread
                spread_pct = ((sell_price - buy_price) / buy_price) * 100
                
                # Check minimum spread
                if spread_pct < self.min_spread_pct:
                    continue
                
                # Calculate optimal position size (30% of balance max)
                position_size = min(
                    self.max_position_size,
                    self.mock_balance * Decimal("0.3")
                )
                
                if position_size < self.min_position_size:
                    continue
                
                # Check profitability
                is_profitable, net_profit, profit_pct, total_fees = self.is_opportunity_profitable(
                    buy_price, sell_price, dex_buy, dex_sell, position_size
                )
                
                if is_profitable and profit_pct > 0.05:  # Must be at least 0.05% net profit
                    opportunity = ImprovedOpportunity(
                        timestamp=timestamp,
                        dex_buy=dex_buy,
                        dex_sell=dex_sell,
                        buy_price=buy_price,
                        sell_price=sell_price,
                        spread_pct=spread_pct,
                        expected_profit_pct=float(profit_pct),
                        volume=volume,
                        is_profitable_after_fees=True
                    )
                    opportunities.append(opportunity)
        
        # Sort by expected profit percentage
        return sorted(opportunities, key=lambda x: x.expected_profit_pct, reverse=True)
    
    def execute_opportunity(self, opportunity: ImprovedOpportunity) -> Optional[ImprovedExecution]:
        """Execute an arbitrage opportunity"""
        
        # Calculate position size
        position_size = min(
            self.max_position_size,
            self.mock_balance * Decimal("0.3")
        )
        
        if position_size < self.min_position_size:
            return None
        
        # Simulate execution timing
        buy_latency = self.dex_configs[opportunity.dex_buy]["latency_ms"]
        sell_latency = self.dex_configs[opportunity.dex_sell]["latency_ms"]
        total_latency = buy_latency + sell_latency + random.randint(10, 30)
        
        # Check success rates
        buy_success_rate = self.dex_configs[opportunity.dex_buy]["success_rate"]
        sell_success_rate = self.dex_configs[opportunity.dex_sell]["success_rate"]
        combined_success_rate = buy_success_rate * sell_success_rate
        
        execution_success = random.random() < combined_success_rate
        
        if not execution_success:
            return None
        
        # Calculate actual profit/loss
        price_diff = Decimal(str(opportunity.sell_price - opportunity.buy_price))
        gross_profit = position_size * price_diff / Decimal(str(opportunity.buy_price))
        
        # Calculate fees
        total_fees = self.calculate_total_fees(
            opportunity.dex_buy, 
            opportunity.dex_sell, 
            position_size
        )
        
        net_profit = gross_profit - total_fees
        
        # Only execute if still profitable (double-check)
        if net_profit <= 0:
            return None
        
        # Update balance
        self.mock_balance += net_profit
        self.total_profit += net_profit
        
        # Create execution record
        execution = ImprovedExecution(
            opportunity_id=f"{opportunity.timestamp}_{opportunity.dex_buy}_{opportunity.dex_sell}",
            executed_at=opportunity.timestamp,
            dex_buy=opportunity.dex_buy,
            dex_sell=opportunity.dex_sell,
            position_size=position_size,
            buy_price=opportunity.buy_price,
            sell_price=opportunity.sell_price,
            gross_profit=gross_profit,
            total_fees=total_fees,
            net_profit=net_profit,
            execution_time_ms=total_latency,
            success=True
        )
        
        self.trades_executed.append(execution)
        return execution
    
    def run_simulation(self, data_file: str):
        """Run the improved arbitrage simulation"""
        print("🚀 Improved High-Frequency Arbitrage Simulation")
        print("=" * 60)
        print(f"Symbol: {self.symbol}")
        print(f"Initial Balance: {self.initial_balance} SOL")
        print(f"Minimum Spread Required: {self.min_spread_pct}%")
        print("=" * 60)
        
        # Load data
        df = self.load_1s_data(data_file)
        if df is None:
            print("❌ Failed to load data")
            return
        
        # Sample data for simulation (every 10th candle for performance)
        sample_size = min(10000, len(df))  # Max 10k candles
        df_sample = df.iloc[::max(1, len(df) // sample_size)].copy()
        
        print(f"🔍 Scanning {len(df_sample)} candles for opportunities...")
        
        opportunities_scanned = 0
        profitable_found = 0
        
        for idx, row in df_sample.iterrows():
            opportunities_scanned += 1
            
            # Get market data
            timestamp = row['timestamp']
            base_price = float(row['close'])
            volume = float(row['volume'])
            
            # Detect opportunities
            opportunities = self.detect_opportunities(timestamp, base_price, volume)
            
            if opportunities:
                profitable_found += len(opportunities)
                
                # Execute best opportunity
                best_opportunity = opportunities[0]
                execution = self.execute_opportunity(best_opportunity)
                
                if execution:
                    print(f"✅ Trade #{len(self.trades_executed)}: "
                          f"{execution.dex_buy}→{execution.dex_sell} "
                          f"Profit: +{execution.net_profit:.6f} SOL "
                          f"({(execution.net_profit/execution.position_size*100):.3f}%) "
                          f"Balance: {self.mock_balance:.6f} SOL")
                
                # Store opportunity for analysis
                self.opportunities_found.extend(opportunities)
        
        # Print results
        self.print_results(opportunities_scanned, profitable_found)
    
    def print_results(self, opportunities_scanned: int, profitable_found: int):
        """Print detailed simulation results"""
        print("\n📈 Improved Simulation Results")
        print("=" * 60)
        
        successful_trades = len(self.trades_executed)
        
        print(f"Opportunities Scanned:     {opportunities_scanned:,}")
        print(f"Profitable Opportunities:  {profitable_found:,}")
        print(f"Trades Executed:           {successful_trades:,}")
        
        if successful_trades > 0:
            avg_profit = self.total_profit / successful_trades
            roi = (self.total_profit / self.initial_balance) * 100
            
            print(f"\n💰 Financial Performance:")
            print(f"Initial Balance:            {self.initial_balance:.6f} SOL")
            print(f"Final Balance:              {self.mock_balance:.6f} SOL")
            print(f"Total Profit:              +{self.total_profit:.6f} SOL")
            print(f"ROI:                       +{roi:.2f}%")
            print(f"Average Profit per Trade:  +{avg_profit:.6f} SOL")
            print(f"Win Rate:                   100.0% (filtered for profitability)")
            
            # Calculate fee analysis
            total_fees = sum(trade.total_fees for trade in self.trades_executed)
            print(f"\n📊 Cost Analysis:")
            print(f"Total Fees Paid:           -{total_fees:.6f} SOL")
            print(f"Fee Ratio:                  {(total_fees/self.total_profit*100):.1f}% of profit")
            
            avg_execution_time = sum(trade.execution_time_ms for trade in self.trades_executed) / successful_trades
            print(f"Avg Execution Time:         {avg_execution_time:.1f}ms")
            
        else:
            print("\n❌ No profitable trades executed")
            print("This suggests market conditions were not suitable for arbitrage")
            print("or the minimum profit thresholds were too high.")

def main():
    """Run the improved simulation"""
    # Check if data file exists
    data_file = "op_1s_2024-01-15.csv"
    
    try:
        simulator = ImprovedArbitrageSimulator("OPUSDT")
        simulator.run_simulation(data_file)
        
    except FileNotFoundError:
        print(f"❌ Data file not found: {data_file}")
        print("Please run the data collection script first:")
        print("python op_1s_data.py history --date 2024-01-15 --out op_1s_2024-01-15.csv")
    except Exception as e:
        print(f"❌ Simulation error: {e}")

if __name__ == "__main__":
    main()
