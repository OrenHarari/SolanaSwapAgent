#!/usr/bin/env python3
"""
Basic test to check if the Solana Swap Agent can load and run
"""

import sys
import os
import asyncio
from decimal import Decimal

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test if we can import our modules."""
    print("🔍 Testing imports...")
    
    try:
        from src.config import settings, DexConfig
        print("✅ Configuration loaded successfully")
        print(f"   - RPC URL: {settings.solana_rpc_url}")
        print(f"   - Min profit: {settings.min_profit_threshold}")
        print(f"   - Max slippage: {settings.max_slippage_bps}")
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return False
    
    try:
        from src.utils import calculate_profit, format_lamports
        print("✅ Utils loaded successfully")
        
        # Test utility functions
        profit = calculate_profit(Decimal("100"), Decimal("101"), Decimal("1"))
        lamports_str = format_lamports(1000000000)
        print(f"   - Test profit calculation: {profit}")
        print(f"   - Test lamports format: {lamports_str}")
    except Exception as e:
        print(f"❌ Error loading utils: {e}")
        return False
    
    return True

def test_dex_clients():
    """Test DEX client creation."""
    print("\n🌐 Testing DEX clients...")
    
    try:
        from src.dex_clients import JupiterClient, RaydiumClient, create_dex_clients
        
        # Create clients
        clients = create_dex_clients()
        print(f"✅ Created {len(clients)} DEX clients:")
        for name, client in clients.items():
            print(f"   - {name}: {client.name}")
        
    except Exception as e:
        print(f"❌ Error creating DEX clients: {e}")
        return False
    
    return True

async def test_jupiter_api():
    """Test connection to Jupiter API."""
    print("\n🪐 Testing Jupiter API connection...")
    
    try:
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
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
                    print(f"   - Input amount: {data.get('inAmount', 'N/A')}")
                    print(f"   - Output amount: {data.get('outAmount', 'N/A')}")
                    if 'routePlan' in data:
                        print(f"   - Route steps: {len(data['routePlan'])}")
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

async def main():
    """Main test function."""
    print("🚀 Starting Solana Swap Agent Basic Tests\n")
    
    # Test 1: Imports
    if not test_imports():
        print("\n❌ Import tests failed!")
        return False
    
    # Test 2: DEX Clients  
    if not test_dex_clients():
        print("\n❌ DEX client tests failed!")
        return False
    
    # Test 3: API Connection
    api_success = await test_jupiter_api()
    if not api_success:
        print("\n⚠️  API connection tests had issues (might be normal)")
    
    print("\n🎉 Basic tests completed!")
    
    if api_success:
        print("✅ All tests passed - system looks ready!")
    else:
        print("⚠️  Some API tests failed, but core system loads correctly")
    
    return True

if __name__ == "__main__":
    asyncio.run(main())