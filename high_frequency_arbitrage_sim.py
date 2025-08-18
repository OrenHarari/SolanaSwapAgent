#!/usr/bin/env python3
"""
High-Frequency Arbitrage Simulation with 1-second Data
This simulation demonstrates arbitrage detection with realistic 1-second price data
"""

import json
import os
import sys
import asyncio
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import time

# Add source path
sys.path.append(os.path.join(os.path.dirname(__file__), 'offchain', 'src'))

@dataclass
class HighFreqOpportunity:
    """High-frequency arbitrage opportunity"""
    timestamp: datetime
    symbol: str
    dex_a: str
    dex_b: str
    price_a: Decimal
    price_b: Decimal
    spread_pct: float
    volume_available: float
    execution_window_ms: int
    confidence_score: float

@dataclass
class TradeExecution:
    """Trade execution result"""
    opportunity_id: str
    executed_at: datetime
    entry_price: Decimal
    exit_price: Decimal
    quantity: Decimal
    gross_profit: Decimal
    fees: Decimal
    net_profit: Decimal
    execution_time_ms: int
    success: bool

class HighFrequencySimulator:
    """Simulates high-frequency arbitrage with 1-second data"""
    
    def __init__(self, symbol: str = "OPUSDT"):
        self.symbol = symbol
        self.mock_balance = Decimal("10.0")  # 10 SOL equivalent
        self.initial_balance = Decimal("10.0")
        self.trades_executed = []
        self.opportunities_found = []
        self.total_profit = Decimal("0")
        
        # Trading parameters
        self.min_spread_pct = 0.05  # Minimum 0.05% spread
        self.max_position_size = Decimal("1.0")  # Max 1 SOL per trade
        self.execution_fee_pct = 0.001  # 0.1% execution fee
        self.max_execution_time_ms = 500  # 500ms max execution time
        
        # DEX simulation parameters
        self.dex_configs = {
            "Jupiter": {"base_fee": 0.0000, "latency_ms": 150, "success_rate": 0.98},
            "Raydium": {"base_fee": 0.0025, "latency_ms": 200, "success_rate": 0.95},
            "Phoenix": {"base_fee": 0.0005, "latency_ms": 100, "success_rate": 0.92},
            "Meteora": {"base_fee": 0.0010, "latency_ms": 180, "success_rate": 0.94},
            "Orca": {"base_fee": 0.0030, "latency_ms": 250, "success_rate": 0.96}
        }
    
    def load_1s_data(self, data_file: str) -> pd.DataFrame:
        """Load 1-second price data"""
        try:
            print(f"📊 Loading 1-second data from: {data_file}")
            df = pd.read_csv(data_file)
            
            # Convert timestamp column
            if 'open_time' in df.columns:
                df['timestamp'] = pd.to_datetime(df['open_time'])
            else:
                # Assume first column is timestamp
                df['timestamp'] = pd.to_datetime(df.iloc[:, 0])
            
            # Ensure required price columns
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            for col in required_cols:
                if col not in df.columns:
                    print(f"⚠️ Missing column: {col}")
                    return None
            
            df = df.sort_values('timestamp').reset_index(drop=True)
            print(f"✅ Loaded {len(df)} 1-second candles")
            print(f"   Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")
            
            return df
            
        except Exception as e:
            print(f"❌ Error loading data: {e}")
            return None
    
    def simulate_dex_prices(self, base_price: float, timestamp: datetime) -> Dict[str, float]:
        """Simulate different prices across DEXes with realistic spreads"""
        prices = {}
        
        # Base price with small random variations per DEX
        for dex_name in self.dex_configs.keys():
            # Each DEX has slight price differences due to:
            # 1. Different liquidity
            # 2. Different fee structures  
            # 3. Arbitrage not yet executed
            # 4. Different order book depths
            
            variation = np.random.normal(0, 0.001)  # 0.1% standard deviation
            
            # Add DEX-specific bias (some DEXes consistently higher/lower)
            dex_bias = {
                "Jupiter": 0.0002,   # Slight premium (aggregator)
                "Raydium": -0.0001,  # Slight discount
                "Phoenix": 0.0003,   # Higher (order book premium)
                "Meteora": -0.0002,  # Lower (competitive)
                "Orca": 0.0001       # Neutral
            }
            
            final_variation = variation + dex_bias.get(dex_name, 0)
            prices[dex_name] = base_price * (1 + final_variation)
        
        return prices
    
    def detect_arbitrage_opportunities(
        self, 
        dex_prices: Dict[str, float], 
        timestamp: datetime,
        volume: float
    ) -> List[HighFreqOpportunity]:
        """Detect arbitrage opportunities between DEX pairs"""
        opportunities = []
        
        dex_names = list(dex_prices.keys())
        
        # Check all DEX pairs
        for i in range(len(dex_names)):
            for j in range(i + 1, len(dex_names)):
                dex_a, dex_b = dex_names[i], dex_names[j]
                price_a, price_b = dex_prices[dex_a], dex_prices[dex_b]
                
                # Calculate spread
                if price_a < price_b:
                    buy_dex, sell_dex = dex_a, dex_b
                    buy_price, sell_price = price_a, price_b
                else:
                    buy_dex, sell_dex = dex_b, dex_a
                    buy_price, sell_price = price_b, price_a
                
                spread_pct = ((sell_price - buy_price) / buy_price) * 100
                
                # Check if spread meets minimum threshold
                if spread_pct >= self.min_spread_pct:
                    # Calculate execution window based on spread size
                    execution_window = max(100, min(1000, int(1000 / spread_pct)))
                    
                    # Calculate confidence score
                    confidence = min(1.0, spread_pct / 0.5)  # Full confidence at 0.5%+
                    
                    opportunity = HighFreqOpportunity(
                        timestamp=timestamp,
                        symbol=self.symbol,
                        dex_a=buy_dex,
                        dex_b=sell_dex,
                        price_a=Decimal(str(buy_price)),
                        price_b=Decimal(str(sell_price)),
                        spread_pct=spread_pct,
                        volume_available=volume,
                        execution_window_ms=execution_window,
                        confidence_score=confidence
                    )
                    
                    opportunities.append(opportunity)
        
        # Sort by spread percentage (descending)
        return sorted(opportunities, key=lambda x: x.spread_pct, reverse=True)
    
    def execute_arbitrage(self, opportunity: HighFreqOpportunity) -> Optional[TradeExecution]:
        """Simulate arbitrage execution"""
        
        # Check if we have enough balance
        position_size = min(
            self.max_position_size,
            self.mock_balance * Decimal("0.3")  # Max 30% of balance per trade
        )
        
        if position_size < Decimal("0.01"):  # Minimum trade size
            return None
        
        # Simulate execution latency
        dex_a_latency = self.dex_configs[opportunity.dex_a]["latency_ms"]
        dex_b_latency = self.dex_configs[opportunity.dex_b]["latency_ms"]
        total_latency = dex_a_latency + dex_b_latency + np.random.randint(10, 50)
        
        # Check if execution would be within window
        if total_latency > opportunity.execution_window_ms:
            return None
        
        # Simulate execution success probability
        success_rate_a = self.dex_configs[opportunity.dex_a]["success_rate"]
        success_rate_b = self.dex_configs[opportunity.dex_b]["success_rate"]
        combined_success_rate = success_rate_a * success_rate_b
        
        execution_success = np.random.random() < combined_success_rate
        
        if not execution_success:
            return None
        
        # Calculate costs
        fee_a = self.dex_configs[opportunity.dex_a]["base_fee"]
        fee_b = self.dex_configs[opportunity.dex_b]["base_fee"]
        
        # Calculate profit/loss
        gross_profit = position_size * (opportunity.price_b - opportunity.price_a) / opportunity.price_a
        
        # Calculate fees
        total_fees = position_size * Decimal(str(fee_a + fee_b + self.execution_fee_pct))
        
        net_profit = gross_profit - total_fees
        
        # Update balance
        self.mock_balance += net_profit
        self.total_profit += net_profit
        
        # Create execution record
        execution = TradeExecution(
            opportunity_id=f"{opportunity.timestamp}_{opportunity.dex_a}_{opportunity.dex_b}",
            executed_at=opportunity.timestamp,
            entry_price=opportunity.price_a,
            exit_price=opportunity.price_b,
            quantity=position_size,
            gross_profit=gross_profit,
            fees=total_fees,
            net_profit=net_profit,
            execution_time_ms=total_latency,
            success=True
        )
        
        self.trades_executed.append(execution)
        return execution
    
    async def run_simulation(self, data_file: str, max_trades: int = 50):
        """Run the high-frequency arbitrage simulation"""
        
        print("🚀 High-Frequency Arbitrage Simulation")
        print("=" * 60)
        print(f"Symbol: {self.symbol}")
        print(f"Initial Balance: {self.initial_balance} SOL")
        print(f"Min Spread: {self.min_spread_pct}%")
        print("=" * 60)
        
        # Load data
        df = self.load_1s_data(data_file)
        if df is None:
            print("❌ Failed to load data")
            return False
        
        print(f"\n🔍 Scanning {len(df)} 1-second candles for opportunities...")
        
        trades_count = 0
        opportunities_scanned = 0
        
        # Process each 1-second candle
        for idx, row in df.iterrows():
            if trades_count >= max_trades:
                break
                
            timestamp = row['timestamp']
            base_price = float(row['close'])
            volume = float(row['volume'])
            
            # Simulate DEX prices
            dex_prices = self.simulate_dex_prices(base_price, timestamp)
            
            # Find opportunities
            opportunities = self.detect_arbitrage_opportunities(
                dex_prices, timestamp, volume
            )
            
            opportunities_scanned += len(opportunities)
            
            # Execute best opportunity if available
            if opportunities:
                best_opportunity = opportunities[0]
                self.opportunities_found.append(best_opportunity)
                
                # Only execute if spread is significant enough
                if best_opportunity.spread_pct >= self.min_spread_pct * 2:  # 2x minimum
                    execution = self.execute_arbitrage(best_opportunity)
                    
                    if execution:
                        trades_count += 1
                        print(f"Trade #{trades_count:2d} | "
                              f"{timestamp.strftime('%H:%M:%S')} | "
                              f"{best_opportunity.dex_a}→{best_opportunity.dex_b} | "
                              f"Spread: {best_opportunity.spread_pct:.3f}% | "
                              f"P&L: {execution.net_profit:+.6f} SOL | "
                              f"Balance: {self.mock_balance:.6f} SOL")
            
            # Small delay to simulate real-time processing
            if idx % 100 == 0:
                await asyncio.sleep(0.01)
        
        # Print results
        self.print_results(opportunities_scanned)
        return True
    
    def print_results(self, opportunities_scanned: int):
        """Print simulation results"""
        
        print(f"\n📈 Simulation Results")
        print("=" * 60)
        print(f"Opportunities Scanned:     {opportunities_scanned:,}")
        print(f"Opportunities Found:       {len(self.opportunities_found):,}")
        print(f"Trades Executed:           {len(self.trades_executed):,}")
        print(f"Initial Balance:           {float(self.initial_balance):10.6f} SOL")
        print(f"Final Balance:             {float(self.mock_balance):10.6f} SOL")
        print(f"Total P&L:                 {float(self.total_profit):+10.6f} SOL")
        
        if self.initial_balance > 0:
            roi = (float(self.total_profit) / float(self.initial_balance)) * 100
            print(f"ROI:                       {roi:+10.2f}%")
        
        if len(self.trades_executed) > 0:
            avg_profit = float(self.total_profit) / len(self.trades_executed)
            print(f"Average Profit per Trade:  {avg_profit:+10.6f} SOL")
            
            profitable_trades = len([t for t in self.trades_executed if t.net_profit > 0])
            win_rate = (profitable_trades / len(self.trades_executed)) * 100
            print(f"Win Rate:                  {win_rate:10.1f}%")
            
            avg_execution_time = np.mean([t.execution_time_ms for t in self.trades_executed])
            print(f"Avg Execution Time:        {avg_execution_time:10.1f} ms")
        
        print(f"\n🎯 DEX Performance:")
        dex_usage = {}
        for trade in self.trades_executed:
            dex_pair = f"{trade.opportunity_id.split('_')[1]}→{trade.opportunity_id.split('_')[2]}"
            dex_usage[dex_pair] = dex_usage.get(dex_pair, 0) + 1
        
        for dex_pair, count in sorted(dex_usage.items(), key=lambda x: x[1], reverse=True):
            print(f"  {dex_pair:<20} {count:3d} trades")

async def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="High-Frequency Arbitrage Simulation")
    parser.add_argument("--data", required=True, help="Path to 1-second CSV data file")
    parser.add_argument("--symbol", default="OPUSDT", help="Trading symbol")
    parser.add_argument("--max-trades", type=int, default=50, help="Maximum trades to execute")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.data):
        print(f"❌ Data file not found: {args.data}")
        print(f"\n💡 To generate data:")
        print(f"   Historical: python op_1s_data.py history --date 2024-01-15 --out op_1s_2024-01-15.csv")
        print(f"   Live:       python op_1s_data.py live --out op_live_1s.csv")
        return
    
    simulator = HighFrequencySimulator(symbol=args.symbol)
    
    try:
        success = await simulator.run_simulation(args.data, args.max_trades)
        if success:
            print(f"\n🎉 Simulation completed successfully!")
        else:
            print(f"\n❌ Simulation failed")
    except KeyboardInterrupt:
        print(f"\n⏹️ Simulation stopped by user")
    except Exception as e:
        print(f"\n❌ Simulation error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
