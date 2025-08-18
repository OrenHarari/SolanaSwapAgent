#!/usr/bin/env python3
"""
Demo Simulation - Works without requiring real SOL airdrop
Shows wallet management and trading simulation with mock balance
"""

import json
import os
import sys
import asyncio
from datetime import datetime
from decimal import Decimal
from solders.keypair import Keypair
import time

# Add source path
sys.path.append(os.path.join(os.path.dirname(__file__), 'offchain', 'src'))

class DemoSimulation:
    def __init__(self):
        self.keypair = None
        self.mock_balance = Decimal("5.0")  # Start with 5 SOL mock balance
        self.initial_balance = Decimal("5.0")
        self.trades_executed = 0
        self.total_profit = Decimal("0")
        self.trade_history = []
        
    def create_wallet(self, wallet_path=None):
        """Create or load wallet"""
        if wallet_path and os.path.exists(wallet_path):
            print(f"🔑 Loading existing wallet from: {wallet_path}")
            try:
                with open(wallet_path, 'r') as f:
                    secret = json.load(f)
                self.keypair = Keypair.from_bytes(secret)
                print(f"✅ Wallet loaded: {self.keypair.pubkey()}")
                return True
            except Exception as e:
                print(f"❌ Error loading wallet: {e}")
                # Create new wallet if loading fails
                pass
        
        print("🆕 Creating new wallet...")
        self.keypair = Keypair()
        print(f"✅ New wallet created: {self.keypair.pubkey()}")
        
        # Save wallet
        if wallet_path:
            try:
                os.makedirs(os.path.dirname(wallet_path), exist_ok=True)
                with open(wallet_path, 'w') as f:
                    json.dump(list(self.keypair.secret()), f)
                print(f"💾 Wallet saved to: {wallet_path}")
            except Exception as e:
                print(f"⚠️ Could not save wallet: {e}")
        
        return True
    
    def get_balance_sol(self):
        """Get current mock balance"""
        return float(self.mock_balance)
    
    def load_price_data(self):
        """Load historical price data"""
        tokens = ['sol', 'btc', 'eth', 'ada', 'xlm', 'xrp']
        price_data = {}
        
        print("📊 Loading historical price data...")
        for token in tokens:
            try:
                with open(f'{token}_4h.json', 'r') as f:
                    data = json.load(f)
                    price_data[token.upper()] = data
                    print(f"✅ {token.upper()}: {len(data)} price points loaded")
            except Exception as e:
                print(f"❌ Error loading {token}: {e}")
        
        return price_data
    
    def find_arbitrage_opportunities(self, price_data, min_profit_pct=1.0):
        """Find profitable arbitrage opportunities"""
        opportunities = []
        
        print(f"🔍 Analyzing {len(price_data)} tokens for arbitrage opportunities...")
        
        for token, prices in price_data.items():
            if len(prices) < 50:
                continue
            
            # Look for price differences that could represent arbitrage
            for i in range(0, len(prices) - 20, 10):  # Sample every 10 points
                current_price = Decimal(str(prices[i][1]))
                
                # Look ahead 5-15 data points (representing different exchanges)
                for j in range(5, 16):
                    if i + j >= len(prices):
                        break
                        
                    future_price = Decimal(str(prices[i + j][1]))
                    profit_pct = float((future_price - current_price) / current_price * 100)
                    
                    if abs(profit_pct) >= min_profit_pct:
                        opportunities.append({
                            'token': token,
                            'buy_price': current_price,
                            'sell_price': future_price,
                            'profit_pct': profit_pct,
                            'direction': 'LONG' if profit_pct > 0 else 'SHORT',
                            'timestamp': datetime.fromtimestamp(prices[i][0] / 1000),
                            'confidence': min(abs(profit_pct) / 5.0, 1.0)  # Confidence score
                        })
        
        # Sort by profitability
        return sorted(opportunities, key=lambda x: abs(x['profit_pct']), reverse=True)
    
    def execute_trade(self, opportunity, position_size_sol=0.2):
        """Execute a simulated trade"""
        position_value = Decimal(str(position_size_sol))
        
        # Check if we have enough balance
        if position_value > self.mock_balance:
            position_value = self.mock_balance * Decimal("0.9")  # Use 90% of available balance
        
        # Calculate profit/loss
        gross_profit = position_value * Decimal(str(opportunity['profit_pct'])) / Decimal("100")
        
        # Simulate realistic trading costs
        trading_fee = position_value * Decimal("0.003")  # 0.3% trading fee
        slippage = position_value * Decimal("0.001")     # 0.1% slippage
        network_fee = Decimal("0.000005")               # Network transaction fee
        
        total_costs = trading_fee + slippage + network_fee
        net_profit = gross_profit - total_costs
        
        # Update balance
        self.mock_balance += net_profit
        self.total_profit += net_profit
        self.trades_executed += 1
        
        # Record trade
        trade_record = {
            'id': self.trades_executed,
            'token': opportunity['token'],
            'direction': opportunity['direction'],
            'position_size': float(position_value),
            'buy_price': float(opportunity['buy_price']),
            'sell_price': float(opportunity['sell_price']),
            'gross_profit': float(gross_profit),
            'total_costs': float(total_costs),
            'net_profit': float(net_profit),
            'profit_pct': opportunity['profit_pct'],
            'timestamp': opportunity['timestamp']
        }
        
        self.trade_history.append(trade_record)
        return net_profit
    
    def print_trade_summary(self):
        """Print detailed trade summary"""
        print(f"\n📋 Trade Summary:")
        print("-" * 90)
        print(f"{'ID':<3} {'Token':<6} {'Dir':<5} {'Size':<8} {'P&L':<10} {'Profit%':<8} {'Balance':<10}")
        print("-" * 90)
        
        running_balance = float(self.initial_balance)
        for trade in self.trade_history:
            running_balance += trade['net_profit']
            print(f"{trade['id']:<3} {trade['token']:<6} {trade['direction']:<5} "
                  f"{trade['position_size']:<8.3f} {trade['net_profit']:>+9.6f} "
                  f"{trade['profit_pct']:>+7.2f}% {running_balance:<10.6f}")
    
    async def run_simulation(self, wallet_path=None, num_trades=10):
        """Run the complete trading simulation"""
        print("🚀 Starting Solana Arbitrage Trading Simulation")
        print("=" * 70)
        print("💡 This is a demo using historical data and mock SOL balance")
        print("=" * 70)
        
        # Create wallet
        if not self.create_wallet(wallet_path):
            print("❌ Failed to create wallet")
            return False
        
        # Display initial state
        print(f"\n💰 Initial Setup:")
        print(f"Wallet Address: {self.keypair.pubkey()}")
        print(f"Starting Balance: {self.get_balance_sol():.6f} SOL")
        
        # Load price data
        price_data = self.load_price_data()
        if not price_data:
            print("❌ No price data available")
            return False
        
        # Find opportunities
        print(f"\n🎯 Finding Arbitrage Opportunities...")
        opportunities = self.find_arbitrage_opportunities(price_data, min_profit_pct=0.8)
        
        if not opportunities:
            print("❌ No profitable opportunities found")
            return False
        
        print(f"Found {len(opportunities)} profitable opportunities")
        
        # Display top opportunities
        print(f"\n🔥 Top 15 Opportunities:")
        print("-" * 85)
        print(f"{'Token':<6} {'Direction':<6} {'Buy Price':<12} {'Sell Price':<12} {'Profit%':<8} {'Confidence':<10}")
        print("-" * 85)
        
        for i, opp in enumerate(opportunities[:15]):
            print(f"{opp['token']:<6} {opp['direction']:<6} "
                  f"${opp['buy_price']:<11.4f} ${opp['sell_price']:<11.4f} "
                  f"{opp['profit_pct']:>+7.2f}% {opp['confidence']:<10.1%}")
        
        # Execute trades
        print(f"\n💱 Executing Top {num_trades} Trades...")
        print("=" * 50)
        
        position_size = float(self.initial_balance) / (num_trades * 2)  # Conservative position sizing
        
        for i, opportunity in enumerate(opportunities[:num_trades]):
            if opportunity['profit_pct'] > 0.5:  # Only trade if profit > 0.5%
                net_profit = self.execute_trade(opportunity, position_size)
                
                print(f"Trade #{i+1:2d} | {opportunity['token']:<6} {opportunity['direction']:<5} | "
                      f"P&L: {net_profit:+.6f} SOL | Balance: {self.get_balance_sol():.6f} SOL")
                
                time.sleep(0.1)  # Simulate execution time
        
        # Final results
        print(f"\n📊 Final Results:")
        print("=" * 70)
        print(f"Initial Balance:       {float(self.initial_balance):10.6f} SOL")
        print(f"Final Balance:         {self.get_balance_sol():10.6f} SOL")
        print(f"Total P&L:             {float(self.total_profit):+10.6f} SOL")
        print(f"Return on Investment:  {(float(self.total_profit)/float(self.initial_balance)*100):+10.2f}%")
        print(f"Trades Executed:       {self.trades_executed:10d}")
        
        if self.trades_executed > 0:
            avg_profit = float(self.total_profit) / self.trades_executed
            print(f"Average per Trade:     {avg_profit:+10.6f} SOL")
            
            profitable_trades = len([t for t in self.trade_history if t['net_profit'] > 0])
            win_rate = profitable_trades / self.trades_executed * 100
            print(f"Win Rate:              {win_rate:10.1f}%")
        
        # Print detailed trade history
        self.print_trade_summary()
        
        print(f"\n💡 Analysis Notes:")
        print(f"• This simulation used historical price data from 6 tokens")
        print(f"• Arbitrage opportunities represent price differences over time")
        print(f"• Real trading would require actual liquidity and market access")
        print(f"• Trading fees, slippage, and network costs were simulated")
        
        return True

async def main():
    """Main function"""
    wallet_path = os.path.expanduser("~/.config/solana/demo-wallet.json")
    
    simulation = DemoSimulation()
    
    try:
        success = await simulation.run_simulation(wallet_path, num_trades=8)
        
        if success:
            print(f"\n🎉 Simulation completed successfully!")
            print(f"📁 Wallet saved to: {wallet_path}")
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

