#!/usr/bin/env python3
"""Simple simulation using historical price data"""

import json
import asyncio
import os
import sys
from datetime import datetime
from decimal import Decimal

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

# Set environment variables
os.environ['WALLET_PRIVATE_KEY'] = 'test_dummy_key_for_validation_purposes_only'

async def load_price_data():
    """Load price data from JSON files"""
    tokens = ['sol', 'btc', 'eth', 'ada', 'xlm', 'xrp']
    price_data = {}
    
    for token in tokens:
        try:
            with open(f'../{token}_4h.json', 'r') as f:
                data = json.load(f)
                price_data[token.upper()] = data
                print(f"✅ Loaded {len(data)} price points for {token.upper()}")
        except Exception as e:
            print(f"❌ Failed to load {token} data: {e}")
    
    return price_data

def find_arbitrage_opportunities(price_data, time_window=10):
    """Find potential arbitrage opportunities in the price data"""
    opportunities = []
    
    # Simulate comparing prices between different "exchanges" (using time offset as proxy)
    for token, prices in price_data.items():
        if len(prices) < time_window * 2:
            continue
            
        for i in range(len(prices) - time_window):
            current_price = Decimal(str(prices[i][1]))  # [timestamp, price]
            future_price = Decimal(str(prices[i + time_window][1]))
            
            price_diff_pct = float((future_price - current_price) / current_price * 100)
            
            # Look for opportunities with > 0.5% difference
            if abs(price_diff_pct) > 0.5:
                opportunities.append({
                    'token': token,
                    'timestamp': datetime.fromtimestamp(prices[i][0] / 1000),
                    'buy_price': current_price,
                    'sell_price': future_price,
                    'profit_pct': price_diff_pct,
                    'type': 'long' if price_diff_pct > 0 else 'short'
                })
    
    return sorted(opportunities, key=lambda x: abs(x['profit_pct']), reverse=True)

async def simulate_trading():
    """Simulate trading with the loaded data"""
    print("🚀 Starting Solana Swap Agent Simulation")
    print("=" * 50)
    
    # Load price data
    print("\n📊 Loading Historical Price Data...")
    price_data = await load_price_data()
    
    if not price_data:
        print("❌ No price data loaded. Cannot run simulation.")
        return
    
    # Find arbitrage opportunities
    print(f"\n🔍 Analyzing arbitrage opportunities...")
    opportunities = find_arbitrage_opportunities(price_data, time_window=5)
    
    print(f"Found {len(opportunities)} potential opportunities")
    
    # Display top 10 opportunities
    print("\n🎯 Top 10 Arbitrage Opportunities:")
    print("-" * 80)
    print(f"{'Token':<6} {'Time':<20} {'Buy Price':<12} {'Sell Price':<12} {'Profit %':<10}")
    print("-" * 80)
    
    for i, opp in enumerate(opportunities[:10]):
        print(f"{opp['token']:<6} {opp['timestamp'].strftime('%Y-%m-%d %H:%M'):<20} "
              f"${opp['buy_price']:<11.4f} ${opp['sell_price']:<11.4f} {opp['profit_pct']:>8.2f}%")
    
    # Simulate executing trades
    print("\n💱 Simulating Trade Execution...")
    total_profit = Decimal("0")
    executed_trades = 0
    
    for opp in opportunities[:5]:  # Execute top 5
        if abs(opp['profit_pct']) > 1.0:  # Only execute if > 1% profit
            position_size = Decimal("100")  # $100 position
            profit = position_size * Decimal(str(opp['profit_pct'])) / Decimal("100")
            total_profit += profit
            executed_trades += 1
            
            print(f"  ✅ {opp['token']}: ${profit:.2f} profit ({opp['profit_pct']:+.2f}%)")
    
    print("\n📈 Simulation Results:")
    print(f"  Total trades executed: {executed_trades}")
    print(f"  Total simulated profit: ${total_profit:.2f}")
    print(f"  Average profit per trade: ${total_profit/max(executed_trades,1):.2f}")
    
    # Test configuration
    print("\n⚙️ Configuration Test:")
    try:
        from config import settings
        print(f"  RPC URL: {settings.solana_rpc_url}")
        print(f"  Min profit threshold: {settings.min_profit_threshold * 100}%")
        print(f"  Max slippage: {settings.max_slippage_bps / 100}%")
    except Exception as e:
        print(f"  ❌ Configuration error: {e}")

def main():
    """Main simulation function"""
    try:
        asyncio.run(simulate_trading())
        print("\n🎉 Simulation completed successfully!")
        return 0
    except Exception as e:
        print(f"\n❌ Simulation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())