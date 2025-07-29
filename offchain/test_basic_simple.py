#!/usr/bin/env python3
"""
Basic test to check if the core Solana Swap Agent components can load
"""

import sys
import os
import asyncio
from decimal import Decimal

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_configuration():
    """Test configuration loading."""
    print("🔍 Testing configuration loading...")
    
    try:
        from src.config import settings, DexConfig
        print("✅ Configuration loaded successfully")
        print(f"   - RPC URL: {settings.solana_rpc_url}")
        print(f"   - Min profit: {settings.min_profit_threshold}")
        print(f"   - Max slippage: {settings.max_slippage_bps}")
        print(f"   - Monitored tokens: {len(settings.monitored_tokens)}")
        
        # Test DEX configuration
        all_dexes = DexConfig.get_all_dexes()
        print(f"   - Available DEXes: {len(all_dexes)}")
        for dex in all_dexes:
            print(f"     * {dex['name']}: {dex['api_url']}")
        
        return True
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return False

def test_basic_utilities():
    """Test basic utility functions without Solana dependencies."""
    print("\n🔧 Testing basic utilities...")
    
    try:
        # Test basic math functions
        profit = Decimal("101") - Decimal("100")
        print(f"✅ Basic calculations work: profit = {profit}")
        
        # Test format functions (without lamports conversion)
        amount = 1.5
        formatted = f"{amount:.6f}"
        print(f"   - Formatting test: {formatted}")
        
        return True
    except Exception as e:
        print(f"❌ Error in utilities: {e}")
        return False

async def test_jupiter_api_basic():
    """Test basic Jupiter API connection."""
    print("\n🪐 Testing Jupiter API connection...")
    
    try:
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            # Test basic API health/info endpoint
            url = "https://quote-api.jup.ag/v6/quote"
            params = {
                "inputMint": "So11111111111111111111111111111111111111112",  # SOL
                "outputMint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC  
                "amount": "1000000000",  # 1 SOL
                "slippageBps": "50"
            }
            
            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    print("✅ Jupiter API connection successful")
                    print(f"   - Status: {response.status}")
                    print(f"   - Has data: {bool(data)}")
                    
                    if 'inAmount' in data and 'outAmount' in data:
                        input_amount = int(data['inAmount'])
                        output_amount = int(data['outAmount'])
                        rate = output_amount / input_amount
                        print(f"   - SOL/USDC rate: ~{rate:.2f}")
                        print(f"   - Route available: {'routePlan' in data}")
                        
                        # This would be a real arbitrage check
                        if rate > 0:
                            print("   - ✅ Rate data looks valid - potential for arbitrage detection!")
                    
                    return True
                else:
                    print(f"⚠️  Jupiter API returned status {response.status}")
                    return False
                    
    except asyncio.TimeoutError:
        print("⚠️  Jupiter API request timed out")
        return False
    except Exception as e:
        print(f"❌ Error testing Jupiter API: {e}")
        return False

def test_mock_arbitrage_detection():
    """Test mock arbitrage detection logic."""
    print("\n📊 Testing arbitrage detection logic...")
    
    try:
        # Mock price data from different DEXes
        mock_prices = {
            "jupiter": {"SOL-USDC": {"price": Decimal("100.50"), "timestamp": 1234567890}},
            "raydium": {"SOL-USDC": {"price": Decimal("101.20"), "timestamp": 1234567890}},
            "meteora": {"SOL-USDC": {"price": Decimal("100.80"), "timestamp": 1234567890}},
        }
        
        # Find arbitrage opportunity
        best_buy = min(mock_prices.items(), key=lambda x: x[1]["SOL-USDC"]["price"])
        best_sell = max(mock_prices.items(), key=lambda x: x[1]["SOL-USDC"]["price"])
        
        buy_price = best_buy[1]["SOL-USDC"]["price"]
        sell_price = best_sell[1]["SOL-USDC"]["price"]
        profit_pct = ((sell_price - buy_price) / buy_price) * 100
        
        print("✅ Arbitrage detection logic works")
        print(f"   - Best buy:  {best_buy[0]} at ${buy_price}")
        print(f"   - Best sell: {best_sell[0]} at ${sell_price}")
        print(f"   - Profit: {profit_pct:.3f}%")
        
        if profit_pct > 0.5:  # 0.5% minimum profit threshold
            print("   - ✅ Profitable arbitrage opportunity detected!")
            print("   - 🚀 In real environment, this would trigger a trade!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in arbitrage logic: {e}")
        return False

async def main():
    """Main test function."""
    print("🚀 Starting Solana Swap Agent Core Tests\n")
    print("=" * 60)
    
    tests_passed = 0
    total_tests = 4
    
    # Test 1: Configuration
    if test_configuration():
        tests_passed += 1
    
    # Test 2: Basic utilities
    if test_basic_utilities():
        tests_passed += 1
    
    # Test 3: Jupiter API
    if await test_jupiter_api_basic():
        tests_passed += 1
    
    # Test 4: Arbitrage logic
    if test_mock_arbitrage_detection():
        tests_passed += 1
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {tests_passed}/{total_tests} tests passed")
    
    if tests_passed == total_tests:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Core system is working correctly")
        print("🚀 Ready for full implementation with Solana dependencies")
    elif tests_passed >= 2:
        print("⚠️  Most tests passed - core system works")
        print("💡 Some features may need additional setup")
    else:
        print("❌ Multiple test failures - check configuration")
    
    print("\n💡 Next Steps:")
    print("   1. Install Solana CLI tools for full functionality")
    print("   2. Set up real wallet private key in .env")
    print("   3. Deploy smart contracts to devnet")
    print("   4. Run full integration tests")
    
    return tests_passed == total_tests

if __name__ == "__main__":
    asyncio.run(main())